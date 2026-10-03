"""Preregistered BTC positive liquidity-compensation information beyond price and realized risk."""
import argparse,datetime as dt,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
WEEK=7*DAY;FIRST=ms('2020-01-06');END=ms('2026-09-01')
IDS=('LQ_INFO','LQ_RISK','LQ_ALT','LQ_PRICE','LQ_INV','LQ_TREND');MODELS=IDS[:4];ledger.LABELS.update({n:n for n in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'data_delay7':{'availability_delay_days':7}}
MARKET_COLS=('r7','r28','v1','v7','v28');COLS={'LQ_INFO':MARKET_COLS+('cs',),'LQ_RISK':MARKET_COLS,'LQ_ALT':MARKET_COLS+('ar',),'LQ_PRICE':('r7','r28')}
INPUT_SHA='2b7c5a957845d2df07c1d71f7cefb0da2c536cdeec598478e34a3340f5703c3b';GZIP_SHA='52fcd1b1b9bbb03a372951f1c72af419ceaf081d87fb84bcc65480bacbea1970';MASK_SHA='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd';LONG_GATE=math.log1p(.0023);SHORT_GATE=math.log1p(.0013)
def inputs():
 p=ROOT/'data/btc-liquidity-20261003/daily.json.gz';assert sha(p.read_bytes())==GZIP_SHA;data=read(p);assert sha(canonical(data))==INPUT_SHA
 assert sha((p.parent/'independent-audit.json').read_bytes())=='9ef9e7e9d4d3d0d670be8d27fee9f61a11476cb96804264ebe0c4728a1307a40'
 proof=read(p.parent/'independent-audit.json');assert proof['canonical_sha256']==INPUT_SHA and proof['gzip_sha256']==GZIP_SHA
 p=ROOT/'data/btc-venue-20261003/masks.json';assert sha(p.read_bytes())==MASK_SHA
 return {r['day']:r for r in data['days']},set(read(p)['binance_spot_no_trade'])
def date(t):return dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat()
def close(m,t,excluded=frozenset()):
 r=m.rowmaps['BS'].get(t-HOUR);return r[4] if r is not None and t-HOUR not in excluded and r[5]==t-1 and math.isfinite(r[4]) and r[4]>0 else None
def logreturn(m,a,b,excluded=frozenset()):
 x,y=close(m,a,excluded),close(m,b,excluded);return math.log(y/x) if x is not None and y is not None else None
def features(m,daily,excluded,lag=0,start=FIRST,end=END):
 out=[]
 for t in range(start,end,WEEK):
  d=t-(1+lag)*DAY;wanted=list(range(d-34*DAY,d+DAY,DAY));rr=[daily.get(u) for u in wanted]
  valid=[r is not None and r['valid'] and r['day']==u and r['end']==u+DAY and r['end']+lag*DAY<=t and all(r[k] is not None and math.isfinite(r[k]) and r[k]>=0 for k in ('cs','ar','rv')) and r['close'] is not None and math.isfinite(r['close']) and r['close']>0 for u,r in zip(wanted,rr)]
  values={k:[r[k] if r is not None else None for r in rr] for k in ('cs','ar','rv','close')}
  e={'source':t,'availability_delay_days':lag,'last_observation_day':d,'last_market_close':d+DAY,'last_assumed_available':d+(1+lag)*DAY,'input_days':wanted,'daily_inputs':values,'bad_days':[u for u,v in zip(wanted,valid) if not v]};e.update({k:None for k in MARKET_COLS+('cs','ar')})
  if all(valid):
   prices=values['close'];rv=values['rv'];risk=[rv[-1],math.fsum(rv[-7:])/7,math.fsum(rv[-28:])/28]
   e.update(r7=math.log(prices[-1]/prices[-8]),r28=math.log(prices[-1]/prices[-29]))
   for name,v in zip(('v1','v7','v28'),risk):e[name]=math.log(v) if v>0 and math.isfinite(v) else None
   for name in ('cs','ar'):
    v=values[name];e[name]=math.log1p(10000*math.fsum(v[-7:])/7)-math.log1p(10000*math.fsum(v[:28])/28)
  e['valid']=all(valid) and all(e[k] is not None and math.isfinite(e[k]) for k in MARKET_COLS+('cs','ar'));out.append(e)
 return out
def labels(m,excluded=frozenset(),start=FIRST,end=END):return {t:{'end':t+WEEK,'value':logreturn(m,t,t+WEEK,excluded)} for t in range(start,end,WEEK)}

def hac(Z,res,days):
 """Exact calendar-lag score products; centered-design sandwich."""
 n,k=Z.shape;scores=Z*res[:,None];meat=scores.T@scores;idx={int(t):i for i,t in enumerate(days)}
 for lag in range(1,2):
  pairs=[(i,idx[int(t)-lag*WEEK]) for i,t in enumerate(days) if int(t)-lag*WEEK in idx]
  if pairs:
   a,b=map(np.array,zip(*pairs));v=scores[a].T@scores[b];meat+=(1-lag/2)*(v+v.T)
 _,ss,vh=np.linalg.svd(Z,full_matrices=False);bread=(vh.T/(ss*ss))@vh
 return (n/(n-k))*(bread@meat@bread)

def fit(a,y,days,current,constrain=False):
 """Shared centered SVD/HAC solver; this study always uses unconstrained coefficients."""
 n,p=a.shape;means=a.mean(axis=0);Z=np.column_stack([np.ones(n),a-means]);k=p+1;rank=int(np.linalg.matrix_rank(Z)) if np.all(np.isfinite(Z)) else 0;out={'mu':None,'se':None,'training_n':n,'unrestricted_rank':rank,'constraint_active':False,'feature_mean':means.tolist()}
 if n<=k or rank!=k or not(np.all(np.isfinite(Z)) and np.all(np.isfinite(y))):out['reason']='rank_or_nonfinite';return out
 coef=np.linalg.lstsq(Z,y,rcond=None)[0];unrestricted=np.r_[coef[0]-coef[1:]@means,coef[1:]];out['unrestricted_beta']=unrestricted.tolist();active=bool(constrain and coef[-1]<0);free=list(range(p-1 if active else p));af=a[:,free];mean=af.mean(axis=0);Z=np.column_stack([np.ones(n),af-mean]);k=Z.shape[1]
 coef=np.linalg.lstsq(Z,y,rcond=None)[0];res=y-Z@coef;cov=hac(Z,res,days);J=np.eye(k);J[0,1:]=-mean;beta_free=J@coef;cov_free=J@cov@J.T;beta=np.zeros(p+1);cov_raw=np.zeros((p+1,p+1));where=[0]+[i+1 for i in free];beta[where]=beta_free;cov_raw[np.ix_(where,where)]=cov_free;cur=np.r_[1.,current];mu=float(cur@beta);se=math.sqrt(max(0.,float(cur@cov_raw@cur)))
 if not(math.isfinite(mu) and math.isfinite(se) and np.all(np.isfinite(cov_raw))):out['reason']='nonfinite_prediction';return out
 out.update(mu=mu,se=se,beta=beta.tolist(),covariance=cov_raw.tolist(),rank=k,free_columns=where,constraint_active=active,residual_ss=float(res@res),fit_mean=mean.tolist())
 return out

def forecast_one(rows,yy,i):
 row=rows[i];t=row['source'];keep=[j for j in range(max(0,i-105),i) if t-105*WEEK<=rows[j]['source']<=t-2*WEEK and rows[j]['valid'] and yy[rows[j]['source']]['value'] is not None and yy[rows[j]['source']]['end']<=t-DAY];weeks=[rows[j]['source'] for j in keep];e={'source':t,'training_weeks':weeks,'training_n':len(weeks),'training_label_end':max((yy[u]['end'] for u in weeks),default=None),'models':{}}
 for name,cols in COLS.items():
  if not row['valid'] or len(keep)<52:e['models'][name]={'mu':None,'se':None,'training_n':len(weeks),'reason':'feature_or_warmup'};continue
  a=np.array([[rows[j][c] for c in cols] for j in keep]);y=np.array([yy[u]['value'] for u in weeks]);cur=np.array([row[c] for c in cols]);e['models'][name]=fit(a,y,weeks,cur,constrain=False)
 return e
def predict(rows,yy):return [forecast_one(rows,yy,i) for i in range(len(rows))]
def threshold(mu,se):return (1 if mu>0 else -1) if abs(mu)>(LONG_GATE if mu>0 else SHORT_GATE)+se else 0
def decision(name,models,score):
 info,base=models['LQ_INFO'],models['LQ_RISK'];side=0;delta=None
 def compensated(pred):
  if pred['mu'] is None or base['mu'] is None or pred['beta'][-1]<=0:return 0
  increment=pred['mu']-base['mu'];gate=threshold(pred['mu'],pred['se']);return gate if gate and abs(increment)>1e-12 and increment*pred['mu']>0 else 0
 if info['mu'] is not None and base['mu'] is not None:delta=info['mu']-base['mu'];side=compensated(info)
 if name in ('LQ_INFO','LQ_INV'):over=side*(-1 if name=='LQ_INV' else 1)
 elif name=='LQ_TREND':over=0
 elif name=='LQ_ALT':over=compensated(models[name])
 else:
  pred=models[name];over=threshold(pred['mu'],pred['se']) if pred['mu'] is not None else 0
 return float(over) if over else max(0,score),bool(over),delta

def schedule(m,ff,pp,name,start,end,risk=.2):
 ft={f['source']:f for f in ff};pt={p['source']:p for p in pp};out=[]
 for t in range(start,end,DAY):
  week=t-dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).weekday()*DAY;f=ft[week];p=pt[week];obs=m.observation(t,risk);detail={'week_source':week,'feature':f,'models':p['models'],'training_n':p['training_n'],'training_label_end':p['training_label_end']}
  if obs is None:out.append({'source_time':t,'weights':None,'detail':dict(detail,risk_missing=True)});continue
  score,w,vol=obs;signal,over,delta=decision(name,p['models'],score);detail.update(score=score,risk=w,vol=vol,signal=signal,override=over,core_fallback=not over,increment=delta)
  out.append({'source_time':t,'weights':{'BS':max(0,signal)*w,'BP':min(0,signal)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def forecast_summary(pp,yy,start,end):
 paired=[p for p in pp if start<=p['source']<end and yy[p['source']]['end']<=end and yy[p['source']]['value'] is not None and all(p['models'][k]['mu'] is not None for k in MODELS)];out={}
 for name in MODELS:
  mu=np.array([p['models'][name]['mu'] for p in paired]);y=np.array([yy[p['source']]['value'] for p in paired]);out[name]={'n':len(y),'mse':float(np.mean((mu-y)**2)) if len(y) else None,'sign_accuracy':float(np.mean(np.sign(mu)==np.sign(y))) if len(y) else None,'constraint_weeks':sum(p['models'][name].get('constraint_active',False) for p in paired),'paired_source_times':[p['source'] for p in paired],'nonpositive_liquidity_beta_weeks':sum(p['models'][name]['beta'][-1]<=0 for p in paired) if name in ('LQ_INFO','LQ_ALT') else None}
 return out

def run(out):
 out=Path(out);m=Market();daily,excluded=inputs();yy=labels(m,excluded);write(out/'labels.json.gz',{str(k):v for k,v in yy.items()});feats={};forecasts={}
 for lag in (0,7):
  ff=features(m,daily,excluded,lag);pp=predict(ff,yy);feats[lag]=ff;forecasts[lag]=pp
  for kind,data in [('features',ff),('forecasts',pp)]:write(out/f'{kind}-lag{lag}.json.gz',data)
 results={};summary={};unc={};identity={};activity={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={str(lag):forecast_summary(pp,yy,start,end) for lag,pp in forecasts.items()};activity[period]={}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);lag=cfg.pop('availability_delay_days',0);plan=schedule(m,feats[lag],forecasts[lag],name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,availability_delay_days=lag,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),liquidity_input_sha256=INPUT_SHA,btc_no_trade_mask_sha256=MASK_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    activity[period][name+'-'+scenario]={'override_days':sum(e['detail'].get('override',False) for e in plan),'override_weeks':len({e['detail']['week_source'] for e in plan if e['detail'].get('override',False)}),'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_feature_days':sum(not e['detail']['feature']['valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['LQ_INFO']['mu'] is None for e in plan),'nonpositive_liquidity_beta_days':sum(e['detail']['models']['LQ_INFO']['mu'] is not None and e['detail']['models']['LQ_INFO']['beta'][-1]<=0 for e in plan)}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'LQ_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':f'runs/search-1458/{period}-E_SPOT.json.gz'}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('LQ_RISK','LQ_ALT','LQ_PRICE','LQ_TREND'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','LQ_INFO','base']['metrics'];b=results['recent','LQ_INFO','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','LQ_INFO','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):g[c]=all(results[p,'LQ_INFO',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in ('LQ_RISK','LQ_ALT','LQ_PRICE','LQ_TREND'):extra['net_beats_'+name+'_both']=all(results[p,'LQ_INFO','base']['metrics']['net_pnl']>results[p,name,'base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_market_both']=all(results[p,'LQ_INFO','base']['metrics']['max_drawdown_pct']<=results[p,'LQ_RISK','base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for ctrl in ('LQ_RISK','LQ_PRICE'):extra['mse_strictly_better_'+ctrl+'_both']=all(forecast[p]['0']['LQ_INFO']['mse'] is not None and forecast[p]['0'][ctrl]['mse'] is not None and forecast[p]['0']['LQ_INFO']['mse']<forecast[p]['0'][ctrl]['mse'] for p in PERIODS)
 for period in PERIODS:extra[period+'_enough_forecasts']=forecast[period]['0']['LQ_INFO']['n']>=(52 if period=='main' else 20)
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('forecast-summary',forecast),('selection',{'primary':'LQ_INFO','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'BTC-only development; completed hourly range liquidity proxies beyond price and realized variance, positive compensation coefficient required for INFO/ALT trades; not actual spreads or causal identification; current archives, not first releases or unused OOS; no cost reduction or control promotion'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'forecast':{p:{n:{k:v for k,v in d.items() if k!='paired_source_times'} for n,d in forecast[p]['0'].items()} for p in PERIODS}}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
