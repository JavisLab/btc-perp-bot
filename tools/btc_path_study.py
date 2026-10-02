"""Preregistered BTC prior-day path-area incremental curve forecasts and preannounced trades."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_cot_study import risk_observation
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('IC_PATH','IC_PRICE','IC_MEAN','IC_INV');MODELS=IDS[:3];ledger.LABELS.update({x:x for x in IDS})
COLS={'IC_PATH':('r','rv','area'),'IC_PRICE':('r','rv'),'IC_MEAN':()}
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1}}
UPPER=np.triu_indices(24);LONG=math.log1p(.0023);SHORT=math.log1p(.0013)
def raw_curves(m,start=ms('2020-01-01'),end=ms('2026-09-01')):
 out=[]
 for d in range(start,end,DAY):
  rows=[m.rowmaps['BS'].get(d+(h-1)*HOUR) for h in range(25)];ok=all(r is not None and r[4]>0 and r[5]==r[0]+HOUR-1 for r in rows);e={'day':d,'available':d+DAY,'valid':ok}
  if ok:
   c=np.log(np.array([r[4] for r in rows[1:]])/rows[0][4]);r=float(c[-1]);e.update(curve=c.tolist(),r=r,rv=float(np.sum(np.diff(np.r_[0.,c])**2)),area=float(np.mean(c-np.arange(1,25)/24*r)))
  out.append(e)
 return out

def unpack(a):
 v=np.zeros((24,24));v[UPPER]=a;v[(UPPER[1],UPPER[0])]=a;return v

def predict(curves,start=ms('2020-01-01'),end=ms('2026-09-01')):
 table={e['day']:e for e in curves};out=[]
 for t in range(start,end,DAY):
  days=[d for d in range(t-366*DAY,t-DAY,DAY) if d in table and d-DAY in table and table[d]['valid'] and table[d-DAY]['valid']];cur=table.get(t-DAY);valid=cur is not None and cur['valid'];e={'source':t,'input_day':t-DAY,'information_time':t,'valid_input':valid,'training_days':days,'training_label_end':max(days)+DAY if days else None,'models':{}}
  Y=np.array([table[d]['curve'] for d in days])
  for name,cols in COLS.items():
   k=len(cols)+1;p={'mu':None,'covariance_upper':None,'leverage':None,'training_n':len(days)};e['models'][name]=p
   if len(days)<300 or not valid:continue
   if cols:
    X=np.array([[table[d-DAY][c] for c in cols] for d in days]);center=X.mean(axis=0);sd=X.std(axis=0);sd[sd<1e-12]=1.;Z=np.column_stack([np.ones(len(X)),(X-center)/sd]);current=np.r_[1.,(np.array([cur[c] for c in cols])-center)/sd]
   else:Z=np.ones((len(days),1));current=np.ones(1);center=sd=np.array([])
   if np.linalg.matrix_rank(Z)<k:p['reason']='rank';continue
   coef=np.linalg.lstsq(Z,Y,rcond=None)[0];res=Y-Z@coef;cov=res.T@res/(len(days)-k);h=float(current@np.linalg.solve(Z.T@Z,current));mu=current@coef
   beta=np.vstack([coef[0]-np.sum(coef[1:]*center[:,None]/sd[:,None],axis=0),coef[1:]/sd[:,None]]) if cols else coef
   p.update(mu=mu.tolist(),covariance_upper=cov[UPPER].tolist(),leverage=h,beta=beta.tolist())
  out.append(e)
 return out

def choose(p):
 if p['mu'] is None:return {'trade':False,'reason':p.get('reason','unavailable_model'),'best':None}
 mu=p['mu'];cov=unpack(p['covariance_upper']);best=None
 for i in range(1,24):
  for j in range(i+1,25):
   delta=mu[j-1]-mu[i-1];se=math.sqrt(max(0,p['leverage']*(cov[j-1,j-1]+cov[i-1,i-1]-2*cov[i-1,j-1])))
   for direction,cost in ((1,LONG),(-1,SHORT)):
    utility=direction*delta-cost-se
    if best is None or utility>best['utility']:best={'entry_hour':i,'exit_hour':j,'direction':direction,'predicted_difference':delta,'mean_se':se,'roundtrip_log_cost':cost,'utility':utility}
 return {'trade':best['utility']>0,'reason':'positive_edge' if best['utility']>0 else 'cost_and_uncertainty','best':best}

def schedule(m,feats,name,start,end,risk=.2):
 table={e['source']:e for e in feats};out=[];decisions=[]
 for t in range(start,end,DAY):
  f=table[t];p=f['models']['IC_PATH' if name=='IC_INV' else name];choice=choose(p);obs=risk_observation(m,t,risk);w,vol=obs if obs is not None else (0.,None);trade=choice['trade'] and obs is not None and w>0;detail={'decision_time':t,'input_day':f['input_day'],'training_label_end':f['training_label_end'],'choice':choice,'risk':w,'vol':vol,'trade':trade,'risk_missing':obs is None,'signal':0};weights={'BS':0.,'BP':0.}
  if trade:
   b=choice['best'];direction=b['direction']*(-1 if name=='IC_INV' else 1);detail['signal']=direction;entry=t+(b['entry_hour']-1)*HOUR;exit=t+(b['exit_hour']-1)*HOUR;weights={'BS':max(direction,0)*w,'BP':min(direction,0)*w};out.append({'source_time':entry,'decision_time':t,'weights':weights,'detail':dict(detail,action='entry')});out.append({'source_time':exit,'decision_time':t,'weights':{'BS':0.,'BP':0.},'detail':dict(detail,action='exit')})
  else:out.append({'source_time':t,'decision_time':t,'weights':weights,'detail':dict(detail,action='flat')})
  decisions.append(detail)
 assert all(a['source_time']<b['source_time'] for a,b in zip(out,out[1:]));return out,decisions

def forecast_stats(feats,curves,start,end):
 actual={e['day']:e for e in curves if e['valid']};pairs=[e for e in feats if start<=e['source']<end and e['source'] in actual and all(e['models'][n]['mu'] is not None for n in MODELS)];out={}
 for name in MODELS:
  errors=np.array([np.array(e['models'][name]['mu'])-np.array(actual[e['source']]['curve']) for e in pairs]);out[name]={'n':len(pairs),'hour_values':len(pairs)*24,'mse':float(np.mean(errors**2)) if len(pairs) else None,'paired_days':[e['source'] for e in pairs]}
 return out

def run(out):
 out=Path(out);m=Market();curves=raw_curves(m);feats=predict(curves);write(out/'curves.json.gz',curves);write(out/'features.json.gz',feats);results={};summary={};unc={};activity={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]=forecast_stats(feats,curves,start,end)
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan,decisions=schedule(m,feats,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);write(out/f'{period}-{name}-decisions-risk{risk:.2f}.json.gz',decisions);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()));write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':
     print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True);activity[period+'-'+name]={'days':len(decisions),'trade_days':sum(d['trade'] for d in decisions),'long_days':sum(d['signal']==1 for d in decisions),'short_days':sum(d['signal']==-1 for d in decisions),'cash_days':sum(not d['trade'] for d in decisions),'unavailable_model_days':sum(d['choice']['best'] is None for d in decisions),'risk_missing_days':sum(d['risk_missing'] for d in decisions),'entry_hour_counts':{str(h):sum(d['trade'] and d['choice']['best']['entry_hour']==h for d in decisions) for h in range(1,24)},'exit_hour_counts':{str(h):sum(d['trade'] and d['choice']['best']['exit_hour']==h for d in decisions) for h in range(2,25)}}
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,z in [('E_SPOT',old),('IC_PRICE',results[period,'IC_PRICE','base']),('IC_MEAN',results[period,'IC_MEAN','base'])]:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(z['daily_returns']),n) for n in (7,14,28)]
 a=results['main','IC_PATH','base']['metrics'];b=results['recent','IC_PATH','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','IC_PATH','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=50,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'IC_PATH',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={'net_beats_price_both':all(results[p,'IC_PATH','base']['metrics']['net_pnl']>results[p,'IC_PRICE','base']['metrics']['net_pnl'] for p in PERIODS),'mse_no_worse_both':all(forecast[p]['IC_PATH']['mse'] is not None and forecast[p]['IC_PATH']['mse']<=forecast[p]['IC_PRICE']['mse'] for p in PERIODS)}
 for n,v in [('summary',summary),('uncertainty',unc),('activity',activity),('forecast-summary',forecast),('selection',{'primary':'IC_PATH','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; prior-day endpoint-detrended path area beyond return/RV, 24-dimensional hourly curve; preannounced predicted not realized extrema; controls not promotable'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'forecast_mse':{p:{n:v['mse'] for n,v in z.items()} for p,z in forecast.items()}}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
