"""Preregistered BTC settlement premium defensive information; USD forecast, USDT BTC ledger."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('PG_INFO','PG_PRICE','PG_SHORT','PG_INV','PG_TREND');MODELS=IDS[:2]
ledger.LABELS.update({n:n for n in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'data_delay24':{'availability_delay_hours':24}}
COLS={'PG_INFO':('r1','r7','fx','premium'),'PG_PRICE':('r1','r7','fx')}
FIRST=ms('2021-05-01');END=ms('2026-09-01')
INPUT_SHA='8dd4eb828dccde133cb3317bc98af56f086ad7500358149197a3ebf904d1bb31';MASK_SHA='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd'
LONG_GATE=math.log1p(.0023);SHORT_GATE=math.log1p(.0013)

def inputs():
 data=ROOT/'data/btc-venue-20261003';p=data/'candles.json';q=data/'masks.json';assert sha(p.read_bytes())==INPUT_SHA and sha(q.read_bytes())==MASK_SHA
 a=read(p);mask=read(q);series={n:{int(r[0]):r for r in rows} for n,rows in a['series'].items()}
 return series,{n:set(v) for n,v in mask['external'].items()},set(mask['binance_spot_no_trade'])

def external_close(series,masks,n,q):
 r=series[n].get(q-HOUR)
 if r is None or q-HOUR in masks[n]:return None
 o,h,l,c,v=map(float,r[1:]);return c if all(math.isfinite(x) for x in (o,h,l,c,v)) and 0<l<=min(o,c)<=max(o,c)<=h and v>0 else None

def ext_return(series,masks,n,a,b):
 x,y=external_close(series,masks,n,a),external_close(series,masks,n,b)
 return math.log(y/x) if x is not None and y is not None else None

def features(m,series,masks,excluded,lag=0,start=FIRST,end=END):
 out=[]
 for t in range(start,end,DAY):
  q=t-(1+lag)*HOUR;qs=list(range(q-23*HOUR,q+HOUR,HOUR));fx_values=[external_close(series,masks,'coinbase-usdtusd',u) for u in qs];missing=[u for u,v in zip(qs,fx_values) if v is None];complete=not missing
  e={'source':t,'availability_delay_hours':lag,'window_first_close':qs[0],'window_last_close':q,'last_available':q+(1+lag)*HOUR,'missing_window_ends':missing,'r1':ext_return(series,masks,'coinbase-btcusd',q-DAY,q),'r7':ext_return(series,masks,'coinbase-btcusd',q-7*DAY,q),'fx':ext_return(series,masks,'coinbase-usdtusd',q-DAY,q),'premium':math.fsum(math.log(v) for v in fx_values)/24 if complete else None,'fx_window_closes':fx_values}
  e['valid']=complete and all(e[k] is not None and math.isfinite(e[k]) for k in ('r1','r7','fx','premium'));out.append(e)
 return out

def labels(series,masks,start=FIRST,end=END):
 return {t:{'end':t+DAY,'base_available':t+DAY+HOUR,'value':ext_return(series,masks,'coinbase-btcusd',t,t+DAY),'currency':'USD'} for t in range(start,end,DAY)}

def hac(Z,res,days):
 """Exact calendar-lag score products; centered-design sandwich."""
 n,k=Z.shape;scores=Z*res[:,None];meat=scores.T@scores;idx={int(t):i for i,t in enumerate(days)}
 for lag in range(1,2):
  pairs=[(i,idx[int(t)-lag*DAY]) for i,t in enumerate(days) if int(t)-lag*DAY in idx]
  if pairs:
   a,b=map(np.array,zip(*pairs));v=scores[a].T@scores[b];meat+=(1-lag/2)*(v+v.T)
 _,ss,vh=np.linalg.svd(Z,full_matrices=False);bread=(vh.T/(ss*ss))@vh
 return (n/(n-k))*(bread@meat@bread)

def fit(a,y,days,current,constrain=False):
 """Centered SVD, then an exact nonpositive last-slope active-set refit."""
 n,p=a.shape;means=a.mean(axis=0);Z=np.column_stack([np.ones(n),a-means]);k=p+1;rank=int(np.linalg.matrix_rank(Z)) if np.all(np.isfinite(Z)) else 0;out={'mu':None,'se':None,'training_n':n,'unrestricted_rank':rank,'constraint_active':False,'feature_mean':means.tolist()}
 if n<=k or rank!=k or not(np.all(np.isfinite(Z)) and np.all(np.isfinite(y))):out['reason']='rank_or_nonfinite';return out
 coef=np.linalg.lstsq(Z,y,rcond=None)[0];unrestricted=np.r_[coef[0]-coef[1:]@means,coef[1:]];out['unrestricted_beta']=unrestricted.tolist();active=bool(constrain and coef[-1]>0);free=list(range(p-1 if active else p));af=a[:,free];mean=af.mean(axis=0);Z=np.column_stack([np.ones(n),af-mean]);k=Z.shape[1]
 coef=np.linalg.lstsq(Z,y,rcond=None)[0];res=y-Z@coef;cov=hac(Z,res,days);J=np.eye(k);J[0,1:]=-mean;beta_free=J@coef;cov_free=J@cov@J.T;beta=np.zeros(p+1);cov_raw=np.zeros((p+1,p+1));where=[0]+[i+1 for i in free];beta[where]=beta_free;cov_raw[np.ix_(where,where)]=cov_free;cur=np.r_[1.,current];mu=float(cur@beta);se=math.sqrt(max(0.,float(cur@cov_raw@cur)))
 if not(math.isfinite(mu) and math.isfinite(se) and np.all(np.isfinite(cov_raw))):out['reason']='nonfinite_prediction';return out
 out.update(mu=mu,se=se,beta=beta.tolist(),covariance=cov_raw.tolist(),rank=k,free_columns=where,constraint_active=active,residual_ss=float(res@res),fit_mean=mean.tolist())
 return out

def forecast_one(rows,yy,i):
 row=rows[i];t=row['source'];keep=[j for j in range(max(0,i-366),i) if t-366*DAY<=rows[j]['source']<=t-2*DAY and rows[j]['valid'] and yy[rows[j]['source']]['value'] is not None and yy[rows[j]['source']]['end']<=t-DAY and yy[rows[j]['source']]['base_available']+row['availability_delay_hours']*HOUR<=t];days=[rows[j]['source'] for j in keep]
 e={'source':t,'training_days':days,'training_n':len(keep),'training_label_end':max((yy[u]['end'] for u in days),default=None),'training_label_available':max((yy[u]['base_available']+row['availability_delay_hours']*HOUR for u in days),default=None),'models':{}}
 for name,cols in COLS.items():
  if not row['valid'] or len(keep)<126:e['models'][name]={'mu':None,'se':None,'training_n':len(keep),'reason':'feature_or_warmup'};continue
  a=np.array([[rows[j][c] for c in cols] for j in keep]);y=np.array([yy[u]['value'] for u in days]);cur=np.array([row[c] for c in cols]);e['models'][name]=fit(a,y,days,cur,constrain=name=='PG_INFO')
 return e

def predict(rows,yy):return [forecast_one(rows,yy,i) for i in range(len(rows))]
def defensive_event(models,f):
 info,price=(models[n] for n in MODELS)
 if info['mu'] is None or price['mu'] is None:return False,None
 delta=0. if info.get('constraint_active') else info['mu']-price['mu']
 event=bool(not info.get('constraint_active') and f['premium'] is not None and f['premium']>0 and info['mu']<-(info['se']+LONG_GATE) and delta < -1e-12)
 return event,delta

def decision(name,models,f,score):
 event,delta=defensive_event(models,f);price=models['PG_PRICE'];over=event if name in ('PG_INFO','PG_SHORT','PG_INV') else bool(price['mu'] is not None and price['mu']<-(price['se']+LONG_GATE)) if name=='PG_PRICE' else False
 signal=(0. if name in ('PG_INFO','PG_PRICE') else -1. if name=='PG_SHORT' else 1.) if over else max(0,score)
 return signal,over,delta

def schedule(m,ff,pp,name,start,end,risk=.2):
 ft={e['source']:e for e in ff};pt={e['source']:e for e in pp};out=[]
 for t in range(start,end,DAY):
  f=ft[t];p=pt[t];obs=m.observation(t,risk);detail={'feature':f,'models':p['models'],'training_n':p['training_n'],'training_label_end':p['training_label_end'],'training_label_available':p['training_label_available']}
  if obs is None:out.append({'source_time':t,'weights':None,'detail':dict(detail,risk_missing=True)});continue
  score,w,vol=obs;s,override,delta=decision(name,p['models'],f,score);detail.update(score=score,risk=w,vol=vol,signal=s,override=override,core_fallback=not override,increment=delta)
  out.append({'source_time':t,'weights':{'BS':max(0,s)*w,'BP':min(0,s)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def forecast_summary(pp,yy,start,end):
 paired=[p for p in pp if start<=p['source']<end and yy[p['source']]['end']<=end and yy[p['source']]['value'] is not None and all(p['models'][k]['mu'] is not None for k in MODELS)];out={}
 for name in MODELS:
  mu=np.array([p['models'][name]['mu'] for p in paired]);y=np.array([yy[p['source']]['value'] for p in paired]);out[name]={'n':len(y),'mse':float(np.mean((mu-y)**2)) if len(y) else None,'sign_accuracy':float(np.mean(np.sign(mu)==np.sign(y))) if len(y) else None,'constraint_days':sum(p['models'][name].get('constraint_active',False) for p in paired),'paired_source_times':[p['source'] for p in paired]}
 return out

def run(out):
 out=Path(out);m=Market();series,masks,excluded=inputs();yy=labels(series,masks);write(out/'labels.json.gz',{str(k):v for k,v in yy.items()});feats={};forecasts={}
 for lag in (0,24):
  ff=features(m,series,masks,excluded,lag);pp=predict(ff,yy);feats[lag]=ff;forecasts[lag]=pp
  for kind,data in [('features',ff),('forecasts',pp)]:write(out/f'{kind}-lag{lag}.json.gz',data)
 results={};summary={};unc={};identity={};activity={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={str(lag):forecast_summary(pp,yy,start,end) for lag,pp in forecasts.items()};activity[period]={};fstart=external_close(series,masks,'coinbase-usdtusd',start);fend=external_close(series,masks,'coinbase-usdtusd',end);assert fstart is not None and fend is not None
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);lag=cfg.pop('availability_delay_hours',0);plan=schedule(m,feats[lag],forecasts[lag],name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,availability_delay_hours=lag,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),settlement_input_sha256=INPUT_SHA,settlement_mask_sha256=MASK_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly'],'usd_translation':{'start_usd_per_usdt':fstart,'end_usd_per_usdt':fend,'return_pct':((1+x['metrics']['return_pct']/100)*fend/fstart-1)*100,'not_conversion_execution':True}}
    activity[period][name+'-'+scenario]={'override_days':sum(e['detail'].get('override',False) for e in plan),'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_feature_days':sum(not e['detail']['feature']['valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['PG_INFO']['mu'] is None for e in plan)}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'PG_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':f'runs/search-1458/{period}-E_SPOT.json.gz'}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('PG_PRICE','PG_TREND'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','PG_INFO','base']['metrics'];b=results['recent','PG_INFO','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','PG_INFO','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay24'):g[c]=all(results[p,'PG_INFO',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in ('PG_PRICE','PG_TREND'):extra['net_beats_'+name+'_both']=all(results[p,'PG_INFO','base']['metrics']['net_pnl']>results[p,name,'base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_price_both']=all(results[p,'PG_INFO','base']['metrics']['max_drawdown_pct']<=results[p,'PG_PRICE','base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 extra['mse_strictly_better_both']=all(forecast[p]['0']['PG_INFO']['mse'] is not None and forecast[p]['0']['PG_PRICE']['mse'] is not None and forecast[p]['0']['PG_INFO']['mse']<forecast[p]['0']['PG_PRICE']['mse'] for p in PERIODS)
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('forecast-summary',forecast),('selection',{'primary':'PG_INFO','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; current API vintage not original availability; single surviving venue; continuous quote premium not BNS jumps; BTC/USD forecast and native USDT BTC account differ; cash defense not USDT trade; no control promotion'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'forecast':{p:{n:{k:v for k,v in d.items() if k!='paired_source_times'} for n,d in forecast[p]['0'].items()} for p in PERIODS}}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
