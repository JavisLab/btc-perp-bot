"""Frozen BTC-only ETF reported-short information overlay; no ETF trading or live services."""
import argparse,bisect,datetime as dt,json,math
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('EF_INFO','EF_PRICE','EF_RAW','EF_INV','EF_TREND');MODELS=IDS[:3]
ledger.LABELS.update({x:x for x in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'data_delay7':{'availability_delay_days':7}}
COLS={'EF_INFO':(0,1,2,3),'EF_PRICE':(0,1,2),'EF_RAW':(3,)}
SYMS=('IBIT','FBTC','GBTC');NY=ZoneInfo('America/New_York')
INPUT_SHA='759c0daec5f061c2a5dfa9c29982faadad3fde971c0c70813fe71c02b1221a23'
LONG_GATE=math.log1p(.0023);SHORT_GATE=math.log1p(.0013)

def inputs():
 p=ROOT/'data/btc-etfshort-20261002/btc-etfshort.json';assert sha(p.read_bytes())==INPUT_SHA
 data=read(p);assert set(data['symbols'])==set(SYMS);rows=data['rows'];assert len(rows)==661 and [x['date'] for x in rows]==sorted(set(x['date'] for x in rows))
 for row in rows:
  assert set(row['values'])==set(SYMS)
  for v in row['values'].values():assert 0<=float(v['exempt'])<=float(v['short'])<=float(v['total']) and float(v['total'])>0
 return rows

def ny_time(date,hour):
 return int(dt.datetime.strptime(date,'%Y%m%d').replace(hour=hour,tzinfo=NY).timestamp()*1000)

def close(m,t):
 row=m.rowmaps['BS'].get(t-HOUR)
 return row[4] if row is not None and row[5]==t-1 and math.isfinite(row[4]) and row[4]>0 else None

def reports(m,raw,lag=0):
 out=[]
 for i,e in enumerate(raw):
  date=e['date'];a=ny_time(date,18)+(1+lag)*DAY;pt=ny_time(date,16);c0,c1=close(m,pt-DAY),close(m,pt)
  r={'date':date,'available':a,'price_time':pt,'previous20':[z['date'] for z in raw[max(0,i-20):i]],'x':None,'a':None,'r_report':math.log(c1/c0) if c0 is not None and c1 is not None else None}
  if i>=20:
   pressure=[];activity=[]
   for symbol in SYMS:
    past=[z['values'][symbol] for z in raw[i-20:i]];now=e['values'][symbol];q=float(now['short'])/float(now['total']);pressure.append(q-math.fsum(float(z['short'])/float(z['total']) for z in past)/20);activity.append(math.log(float(now['total'])/(math.fsum(float(z['total']) for z in past)/20)))
   r.update(x=math.fsum(pressure)/3,a=math.fsum(activity)/3)
  out.append(r)
 return out

def features(m,rr,lag=0,start=ms('2020-01-01'),end=ms('2026-09-01')):
 avail=[r['available'] for r in rr];out=[]
 for t in range(start,end,DAY):
  k=bisect.bisect_right(avail,t)-1;r=rr[k] if k>=0 else None;c0,c1=close(m,t-DAY),close(m,t)
  e={'source':t,'availability_delay_days':lag,'report':r['date'] if r else None,'available':r['available'] if r else None,'age_hours':(t-r['available'])/HOUR if r else None,'report_price_time':r['price_time'] if r else None,'previous20':r['previous20'] if r else [],'valid':False,'r_now':math.log(c1/c0) if c0 is not None and c1 is not None else None,'r_report':r['r_report'] if r else None,'a':r['a'] if r else None,'x':r['x'] if r else None}
  e['valid']=r is not None and t-r['available']<=7*DAY and all(e[k] is not None and math.isfinite(e[k]) for k in ('r_now','r_report','a','x'))
  out.append(e)
 return out

def labels(m,start=ms('2020-01-01'),end=ms('2026-09-01')):
 out={}
 for t in range(start,end,DAY):
  a,b=close(m,t),close(m,t+7*DAY);out[t]={'end':t+7*DAY,'value':math.log(b/a) if a is not None and b is not None else None}
 return out

def hac(Z,res,days):
 """Exact calendar-lag score products; centered-design sandwich."""
 n,k=Z.shape;scores=Z*res[:,None];meat=scores.T@scores;idx={int(t):i for i,t in enumerate(days)}
 for lag in range(1,8):
  pairs=[(i,idx[int(t)-lag*DAY]) for i,t in enumerate(days) if int(t)-lag*DAY in idx]
  if pairs:
   a,b=map(np.array,zip(*pairs));v=scores[a].T@scores[b];meat+=(1-lag/8)*(v+v.T)
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
 row=rows[i];t=row['source'];keep=[j for j in range(max(0,i-372),i) if t-372*DAY<=rows[j]['source']<=t-8*DAY and rows[j]['valid'] and yy[rows[j]['source']]['value'] is not None and yy[rows[j]['source']]['end']<=t-DAY];days=[rows[j]['source'] for j in keep]
 e={'source':t,'training_days':days,'training_n':len(keep),'training_label_end':max((yy[u]['end'] for u in days),default=None),'models':{}}
 for name,cols in COLS.items():
  if not row['valid'] or len(keep)<126:e['models'][name]={'mu':None,'se':None,'training_n':len(keep),'reason':'feature_or_warmup'};continue
  keys=('r_now','r_report','a','x');a=np.array([[rows[j][keys[c]] for c in cols] for j in keep]);y=np.array([yy[u]['value'] for u in days]);cur=np.array([row[keys[c]] for c in cols]);e['models'][name]=fit(a,y,days,cur,constrain=name!='EF_PRICE')
 return e

def predict(rows,yy):return [forecast_one(rows,yy,i) for i in range(len(rows))]

def threshold(mu,se):return (1 if mu>0 else -1) if abs(mu)>(LONG_GATE if mu>0 else SHORT_GATE)+se else 0

def decision(name,models,score):
 core=max(0,score);info,price,raw=(models[k] for k in MODELS);s=0;delta=None
 if info['mu'] is not None and price['mu'] is not None:
  delta=0. if info.get('constraint_active') else info['mu']-price['mu'];gate=threshold(info['mu'],info['se'])
  if gate and abs(delta)>1e-12 and delta*info['mu']>0:s=gate
 if name in ('EF_INFO','EF_INV'):override=s*(-1 if name=='EF_INV' else 1)
 elif name=='EF_TREND':override=0
 else:
  pred=price if name=='EF_PRICE' else raw;override=threshold(pred['mu'],pred['se']) if pred['mu'] is not None else 0
 return (float(override) if override else core),bool(override),delta

def schedule(m,ff,pp,name,start,end,risk=.2):
 ft={e['source']:e for e in ff};pt={e['source']:e for e in pp};out=[]
 for t in range(start,end,DAY):
  f=ft[t];p=pt[t];obs=m.observation(t,risk);detail={'report':f['report'],'available':f['available'],'age_hours':f['age_hours'],'common_valid':f['valid'],'models':p['models'],'training_n':p['training_n'],'training_label_end':p['training_label_end']}
  if obs is None:out.append({'source_time':t,'weights':None,'detail':dict(detail,risk_missing=True)});continue
  score,w,vol=obs;s,override,delta=decision(name,p['models'],score);detail.update(score=score,risk=w,vol=vol,signal=s,override=override,core_fallback=not override,increment=delta)
  out.append({'source_time':t,'weights':{'BS':max(0,s)*w,'BP':min(0,s)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def forecast_summary(pp,yy,start,end):
 paired=[p for p in pp if start<=p['source']<end and yy[p['source']]['end']<=end and yy[p['source']]['value'] is not None and all(p['models'][k]['mu'] is not None for k in MODELS)];out={}
 for name in MODELS:
  mu=np.array([p['models'][name]['mu'] for p in paired]);y=np.array([yy[p['source']]['value'] for p in paired]);out[name]={'n':len(y),'mse':float(np.mean((mu-y)**2)) if len(y) else None,'sign_accuracy':float(np.mean(np.sign(mu)==np.sign(y))) if len(y) else None,'constraint_days':sum(p['models'][name].get('constraint_active',False) for p in paired),'paired_source_times':[p['source'] for p in paired]}
 return out

def run(out):
 out=Path(out);m=Market();raw=inputs();yy=labels(m);write(out/'labels.json.gz',{str(k):v for k,v in yy.items()});feats={};forecasts={}
 for lag in (0,7):
  rr=reports(m,raw,lag);ff=features(m,rr,lag);pp=predict(ff,yy);feats[lag]=ff;forecasts[lag]=pp
  for kind,data in [('reports',rr),('features',ff),('forecasts',pp)]:write(out/f'{kind}-lag{lag}.json.gz',data)
 results={};summary={};unc={};identity={};activity={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={str(lag):forecast_summary(pp,yy,start,end) for lag,pp in forecasts.items()};activity[period]={}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);lag=cfg.pop('availability_delay_days',0);plan=schedule(m,feats[lag],forecasts[lag],name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,availability_delay_days=lag,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),etf_input_sha256=INPUT_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    activity[period][name+'-'+scenario]={'override_days':sum(e['detail'].get('override',False) for e in plan),'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_feature_days':sum(not e['detail']['common_valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['EF_INFO']['mu'] is None for e in plan),'unique_available_reports':len({e['detail']['report'] for e in plan if e['detail']['common_valid']}),'source_age_hours':{str(h):sum(e['detail']['age_hours']==h for e in plan) for h in sorted({e['detail']['age_hours'] for e in plan if e['detail']['age_hours'] is not None})}}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'EF_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':f'runs/search-1458/{period}-E_SPOT.json.gz'}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('EF_PRICE','EF_TREND'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','EF_INFO','base']['metrics'];b=results['recent','EF_INFO','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','EF_INFO','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):g[c]=all(results[p,'EF_INFO',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in ('EF_PRICE','EF_TREND'):extra['net_beats_'+name+'_both']=all(results[p,'EF_INFO','base']['metrics']['net_pnl']>results[p,name,'base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_price_both']=all(results[p,'EF_INFO','base']['metrics']['max_drawdown_pct']<=results[p,'EF_PRICE','base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 extra['mse_strictly_better_both']=all(forecast[p]['0']['EF_INFO']['mse'] is not None and forecast[p]['0']['EF_PRICE']['mse'] is not None and forecast[p]['0']['EF_INFO']['mse']<forecast[p]['0']['EF_PRICE']['mse'] for p in PERIODS)
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('forecast-summary',forecast),('selection',{'primary':'EF_INFO','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; reported marked-short volume is not net positions, selected three ETFs, current archives not original publication vintage, 7-day overlapping targets and core fallback before ETF data; controls not promotable'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'forecast':{p:{n:{k:v for k,v in d.items() if k!='paired_source_times'} for n,d in forecast[p]['0'].items()} for p in PERIODS}}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
