"""Preregistered BTC-only option-implied variance for spot risk sizing; never live trading."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
FIRST=ms('2021-04-03');END=ms('2026-09-01');IDS=('VI_INFO','VI_PRICE','VI_RAW','VI_INV','VI_TREND');MODELS=IDS[:2];ledger.LABELS.update({n:n for n in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'data_delay7':{'availability_delay_days':7}}
INPUT_SHA='200f61fa5869ee8351956a960f1265da6c559d25356e5fe2783ba399e84330ea';MASK_SHA='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd'
def inputs():
 p=ROOT/'data/btc-dvol-20261003/dvol-daily.json';assert sha(p.read_bytes())==INPUT_SHA;d=read(p);p=ROOT/'data/btc-venue-20261003/masks.json';assert sha(p.read_bytes())==MASK_SHA
 return {r[0]:float(r[4]) for r in d['rows']},set(read(p)['binance_spot_no_trade'])
def close(m,t,excluded=frozenset()):
 r=m.rowmaps['BS'].get(t-HOUR);return r[4] if r is not None and t-HOUR not in excluded and r[5]==t-1 and math.isfinite(r[4]) and r[4]>0 else None
def variance(m,start,excluded=frozenset()):
 values=[close(m,t,excluded) for t in range(start,start+31*DAY,DAY)]
 if any(v is None for v in values):return None
 v=365/30*math.fsum(math.log(b/a)**2 for a,b in zip(values,values[1:]));return v if v>0 and math.isfinite(v) else None
def features(m,dvol,excluded,lag=0,start=FIRST,end=END):
 out=[]
 for t in range(start,end,DAY):
  bar=t-(2+lag)*DAY;value=dvol.get(bar) if bar>=ms('2021-04-01') else None;q=(value/100)**2 if value is not None and value>0 and math.isfinite(value) else None;rv=variance(m,t-30*DAY,excluded);e={'source':t,'dvol_bar':bar,'dvol_end':bar+DAY,'assumed_available':bar+(2+lag)*DAY,'availability_delay_days':lag,'dvol_percent':value,'q':q,'past_variance':rv,'log_r':math.log(rv) if rv is not None else None,'log_q':math.log(q) if q is not None else None};e['valid']=rv is not None and q is not None;out.append(e)
 return out
def labels(m,excluded=frozenset(),start=FIRST,end=END):return {t:{'end':t+30*DAY,'value':variance(m,t,excluded)} for t in range(start,end,DAY)}
def fit(a,y,current,constrain=False):
 n,p=a.shape;mean=a.mean(axis=0);Z=np.column_stack([np.ones(n),a-mean]);rank=int(np.linalg.matrix_rank(Z)) if np.all(np.isfinite(Z)) else 0;out={'variance':None,'training_n':n,'unrestricted_rank':rank,'constraint_active':False,'feature_mean':mean.tolist()}
 if n<=p+1 or rank!=p+1 or not np.all(np.isfinite(y)):out['reason']='rank_or_nonfinite';return out
 b=np.linalg.lstsq(Z,y,rcond=None)[0];out['unrestricted_beta']=np.r_[b[0]-b[1:]@mean,b[1:]].tolist();active=bool(constrain and b[-1]<0);free=list(range(p-int(active)));a=a[:,free];mean=a.mean(axis=0);Z=np.column_stack([np.ones(n),a-mean]);coef=np.linalg.lstsq(Z,y,rcond=None)[0];beta=np.zeros(p+1);beta[0]=coef[0]-coef[1:]@mean;beta[[i+1 for i in free]]=coef[1:];res=y-Z@coef;mu=float(np.r_[1.,current]@beta)
 try:smear=float(np.mean(np.exp(res)));prediction=math.exp(mu)*smear
 except (OverflowError,FloatingPointError):out['reason']='overflow';return out
 if not math.isfinite(prediction) or prediction<=0:out['reason']='nonfinite_prediction';return out
 out.update(variance=prediction,log_mean=mu,smearing=smear,beta=beta.tolist(),constraint_active=active,rank=Z.shape[1],free_columns=[0]+[i+1 for i in free],residual_ss=float(res@res));return out
def forecast_one(rows,yy,i):
 r=rows[i];t=r['source'];keep=[j for j in range(max(0,i-760),max(0,i-30)) if t-760*DAY<=rows[j]['source']<=t-31*DAY and rows[j]['valid'] and yy[rows[j]['source']]['value'] is not None and yy[rows[j]['source']]['end']<=t-DAY];days=[rows[j]['source'] for j in keep];out={'source':t,'training_days':days,'training_n':len(days),'training_label_end':max((yy[u]['end'] for u in days),default=None),'models':{}}
 for name,cols in [('VI_INFO',('log_r','log_q')),('VI_PRICE',('log_r',))]:
  if not r['valid'] or len(keep)<365:out['models'][name]={'variance':None,'training_n':len(keep),'reason':'feature_or_warmup'};continue
  a=np.array([[rows[j][c] for c in cols] for j in keep]);y=np.log([yy[u]['value'] for u in days]);out['models'][name]=fit(a,y,np.array([r[c] for c in cols]),name=='VI_INFO')
 return out
def predict(rows,yy):return [forecast_one(rows,yy,i) for i in range(len(rows))]
def weight(name,f,models,risk,core):
 iv,pv=(models[n]['variance'] for n in MODELS);v=None
 if name=='VI_INFO' and iv is not None:v=risk/math.sqrt(iv)
 elif name=='VI_PRICE' and pv is not None:v=risk/math.sqrt(pv)
 elif name=='VI_RAW' and f['q'] is not None:v=risk/math.sqrt(f['q'])
 elif name=='VI_INV' and iv is not None and pv is not None:v=risk*math.sqrt(iv)/pv
 return (min(1.,v),False) if v is not None else (core,True)
def schedule(m,ff,pp,name,start,end,risk=.2):
 ft={f['source']:f for f in ff};pt={p['source']:p for p in pp};out=[]
 for t in range(start,end,DAY):
  f,p=ft[t],pt[t];obs=m.observation(t,risk);detail={'feature':f,'models':p['models'],'training_n':p['training_n'],'training_label_end':p['training_label_end']}
  if obs is None:out.append({'source_time':t,'weights':None,'detail':dict(detail,risk_missing=True)});continue
  score,core,vol=obs;w,fallback=weight(name,f,p['models'],risk,core);detail.update(score=score,core_risk=core,vol=vol,risk=w,core_fallback=fallback,signal=max(0,score));out.append({'source_time':t,'weights':{'BS':max(0,score)*w,'BP':0.},'rebalance':True,'hedge':False,'detail':detail})
 return out
def calendar_bootstrap(values,block):
 x=np.array(values,dtype=float);good=np.isfinite(x);out={'block_days':block,'calendar_days':len(x),'valid_days':int(good.sum()),'mean':float(np.nanmean(x)) if np.any(good) else None,'ci95':None,'replicates':2000}
 if not np.any(good):return out
 rng=np.random.default_rng(8300+block);starts=rng.integers(0,len(x),size=(2000,math.ceil(len(x)/block)));idx=(starts[:,:,None]+np.arange(block))%len(x);samples=x[idx.reshape(2000,-1)[:,:len(x)]];stat=np.nanmean(samples,axis=1);finite=stat[np.isfinite(stat)];out['ci95']=np.quantile(finite,[.025,.975]).tolist() if len(finite) else None;out['finite_replicates']=len(finite);return out

def forecast_summary(pp,ff,yy,start,end):
 paired=[p for p in pp if start<=p['source']<end and yy[p['source']]['end']<=end and yy[p['source']]['value'] is not None and all(p['models'][k]['variance'] is not None for k in MODELS)];ft={f['source']:f for f in ff};out={};loss={}
 for name in ('VI_INFO','VI_PRICE','VI_RAW'):
  pred=np.array([p['models'][name]['variance'] if name!='VI_RAW' else ft[p['source']]['q'] for p in paired]);y=np.array([yy[p['source']]['value'] for p in paired]);mse=(pred-y)**2;ql=np.log(pred)+y/pred;out[name]={'n':len(y),'mse':float(np.mean(mse)) if len(y) else None,'qlike':float(np.mean(ql)) if len(y) else None,'constraint_days':sum(p['models'][name].get('constraint_active',False) for p in paired) if name in MODELS else 0,'paired_source_times':[p['source'] for p in paired]};loss[name]={'mse':mse,'qlike':ql}
 for metric in ('mse','qlike'):
  diff={p['source']:float(v) for p,v in zip(paired,loss['VI_INFO'][metric]-loss['VI_PRICE'][metric])};grid=[diff.get(t,np.nan) for t in range(start,end,DAY)];out[metric+'_difference']=[calendar_bootstrap(grid,n) for n in (30,60,90)]
 return out

def run(out):
 out=Path(out);m=Market();dvol,excluded=inputs();yy=labels(m,excluded);write(out/'labels.json.gz',{str(k):v for k,v in yy.items()});feats={};forecasts={}
 for lag in (0,7):
  ff=features(m,dvol,excluded,lag);pp=predict(ff,yy);feats[lag]=ff;forecasts[lag]=pp
  for kind,data in [('features',ff),('forecasts',pp)]:write(out/f'{kind}-lag{lag}.json.gz',data)
  print(json.dumps({'stage':'risk_forecasts','lag':lag,'days':len(ff),'fitted':sum(p['models']['VI_INFO']['variance'] is not None for p in pp)}),flush=True)
 results={};summary={};unc={};identity={};activity={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={str(lag):forecast_summary(pp,feats[lag],yy,start,end) for lag,pp in forecasts.items()};activity[period]={}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);lag=cfg.pop('availability_delay_days',0);plan=schedule(m,feats[lag],forecasts[lag],name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,availability_delay_days=lag,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),dvol_input_sha256=INPUT_SHA,btc_no_trade_mask_sha256=MASK_SHA);assert x['metrics']['funding']==0;write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    activity[period][name+'-'+scenario]={'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'invalid_feature_days':sum(not e['detail']['feature']['valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['VI_INFO']['variance'] is None for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'risk_cap_days':sum(e['detail'].get('risk',0)==1 for e in plan)}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'VI_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':f'runs/search-1458/{period}-E_SPOT.json.gz'}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('VI_PRICE','VI_TREND'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','VI_INFO','base']['metrics'];b=results['recent','VI_INFO','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','VI_INFO','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):g[c]=all(results[p,'VI_INFO',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in ('VI_PRICE','VI_TREND'):extra['net_beats_'+name+'_both']=all(results[p,'VI_INFO','base']['metrics']['net_pnl']>results[p,name,'base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_price_both']=all(results[p,'VI_INFO','base']['metrics']['max_drawdown_pct']<=results[p,'VI_PRICE','base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for metric in ('mse','qlike'):extra[metric+'_strictly_better_both']=all(forecast[p]['0']['VI_INFO'][metric] is not None and forecast[p]['0']['VI_PRICE'][metric] is not None and forecast[p]['0']['VI_INFO'][metric]<forecast[p]['0']['VI_PRICE'][metric] for p in PERIODS)
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('forecast-summary',forecast),('selection',{'primary':'VI_INFO','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'BTC-only development, current historical DVOL with one-day plus optional seven-day availability buffer, not first-release vintages; daily-overlapping 30-day variance labels are not independent; spot/cash risk sizing, not option return or direction prediction'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
