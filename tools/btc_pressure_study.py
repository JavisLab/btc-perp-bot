"""Preregistered causal clock-time BTC pressure risk; every account is perp-only."""
import argparse,math
from pathlib import Path
import numpy as np
from btc_session_study import ROOT,DAY,HOUR,ms,sha,canonical,read,write,bootstrap
from btc_persistence_study import Market,PERIODS,SCENARIOS as COMMON_SCENARIOS
from btc_periodic_study import inputs as rv_inputs,fit,restore,RV_SHA
import btc_target_ledger as ledger
IDS=('TP_INFO','TP_NET','TP_VOL','TP_HAR','TP_INV','TP_TREND');COLS={'TP_INFO':(0,1,2,3,4,5),'TP_NET':(0,1,2,3,4),'TP_VOL':(0,1,2,3),'TP_HAR':(0,1,2)};CONTROLS=('TP_NET','TP_VOL','TP_HAR','TP_TREND');SCENARIOS={**COMMON_SCENARIOS,'data_delay7':{'flow_lag':7}};ledger.LABELS.update({n:n for n in IDS})
PRESSURE_SHA='b7bcc90d73a29cf1f2d84dcd752025a6034d356ab337d7ce48eab82f09869d5f'
PRESSURE_GZIP='9529f16033f2229e9ebaff6333e9bb0a4d8becab180eb737a8a834b9b065add7'
def inputs():
 p=ROOT/'data/btc-pressure-20261004';assert sha((p/'daily.json.gz').read_bytes())==PRESSURE_GZIP;d=read(p/'daily.json.gz');assert sha(canonical(d))==PRESSURE_SHA;a=read(p/'independent-audit.json');assert a['daily_sha256']==PRESSURE_SHA and a['max_scaled_error']==0 and a['raw_hours']==58440;return d,rv_inputs()
def features(flow,rv,lag=0):
 fm={r['day']:r for r in flow};vm={r['day']:r for r in rv};out=[]
 def good_rv(x):return x is not None and x['end']==x['day']+DAY and x['valid'] and x['rv'] is not None and math.isfinite(x['rv']) and x['rv']>0
 def good_flow(x):return x is not None and x['end']==x['day']+DAY and x['valid'] and all(x[k] is not None and math.isfinite(x[k]) for k in ('quote','net','gross')) and x['quote']>0 and 0<=x['net']<=x['gross']<=1
 for r in rv:
  t=r['end'];d=t-(lag+1)*DAY;rdays=list(range(t-22*DAY,t,DAY));fdays=list(range(d-28*DAY,d+DAY,DAY));rr=[vm.get(u) for u in rdays];ss=[fm.get(u) for u in fdays];ok=all(good_rv(v) for v in rr) and all(good_flow(v) for v in ss);v=[e['rv'] for e in rr] if ok else None
  x=[math.log(v[-1]),math.log(math.fsum(v[-5:])/5),math.log(math.fsum(v)/22),math.log(ss[-1]['quote']/(math.fsum(a['quote'] for a in ss[:-1])/28)),ss[-1]['net'],ss[-1]['gross']] if ok else [None]*6;y=vm.get(t)
  out.append({'source':t,'flow_lag':lag,'flow_day':d,'rv_days':rdays,'flow_days':fdays,'valid':ok,'features':x,'truth':y['rv'] if good_rv(y) else None,'truth_end':t+DAY if y is not None else None})
 return out

def forecast_one(ff,i):
 e=ff[i];t=e['source'];keep=[j for j in range(max(0,i-365),i) if t-365*DAY<=ff[j]['source']<t and ff[j]['valid'] and ff[j]['truth'] is not None and ff[j]['truth_end']<=t];out={'source':t,'flow_lag':e['flow_lag'],'training_days':[ff[j]['source'] for j in keep],'training_n':len(keep),'training_label_end':max((ff[j]['truth_end'] for j in keep),default=None),'models':{}};ok=e['valid'] and len(keep)>=300
 for name,cols in COLS.items():
  if not ok:out['models'][name]={'prediction':None,'floor':False,'reason':'feature_or_common_warmup'};continue
  x=np.array([[ff[j]['features'][c] for c in cols] for j in keep]);y=np.log([ff[j]['truth'] for j in keep]);cur=np.array([e['features'][c] for c in cols]);out['models'][name]=fit(x,y,cur)
 a,b=out['models']['TP_INFO']['prediction'],out['models']['TP_NET']['prediction'];out['models']['TP_INV']=restore(2*math.log(b)-math.log(a),0.) if a is not None and b is not None else {'prediction':None,'floor':False,'reason':'base_model_missing'};return out

def predict(ff,m):
 out=[]
 for i,e in enumerate(ff):
  p=forecast_one(ff,i);obs=m.observation(e['source']);p['models']['TP_TREND']={'prediction':obs[2]**2/365 if obs else None,'floor':False};out.append(p)
 return out

def schedule(m,ff,pp,name,start,end,risk=.2):
 out=[];fm={e['source']:e for e in ff}
 for p in pp:
  t=p['source']
  if not start<=t<end:continue
  model=p['models'][name];v=model['prediction'];obs=m.observation(t,risk);detail={'forecast':v,'floor':model['floor'],'flow_lag':p['flow_lag'],'flow_day':fm[t]['flow_day'],'input_valid':fm[t]['valid'],'training_n':p['training_n'],'training_label_end':p['training_label_end']}
  if v is None or obs is None:out.append({'source_time':t,'weights':None,'detail':dict(detail,missing=True)});continue
  score,oldrisk,oldvol=obs;vol=oldvol if name=='TP_TREND' else math.sqrt(365*v);riskweight=oldrisk if name=='TP_TREND' else min(1,risk/vol);detail.update(missing=False,score=score,signal=score,risk=riskweight,vol=vol,old_vol=oldvol)
  out.append({'source_time':t,'weights':{'BS':0.,'BP':score*riskweight},'hedge':False,'rebalance':True,'detail':detail})
 return out

def forecast_summary(ff,pp,start,end):
 fm={e['source']:e for e in ff};pair=[p for p in pp if start<=p['source']<end and fm[p['source']]['truth'] is not None and fm[p['source']]['truth_end']<=end and all(p['models'][n]['prediction'] is not None and math.isfinite(p['models'][n]['prediction']) and p['models'][n]['prediction']>0 for n in IDS)];y=np.array([fm[p['source']]['truth'] for p in pair]);out={'n':len(pair),'common_days':[p['source'] for p in pair],'coverage':len(pair)/((end-start)//DAY),'calendar_days':(end-start)//DAY,'models':{},'loss_differences':{},'ci_units':'generic bootstrap output /100 gives raw MSE or QLIKE difference; development observations, no independent OOS'};loss={}
 for name in IDS:
  pred=np.array([p['models'][name]['prediction'] for p in pair]);mse=(y-pred)**2;ratio=y/pred;ql=ratio-np.log(ratio)-1;scheduled=[p['models'][name] for p in pp if start<=p['source']<end and p['models'][name]['prediction'] is not None];floors=sum(p['floor'] for p in scheduled);out['models'][name]={'n':len(pair),'mse':float(mse.mean()) if len(pair) else None,'qlike':float(ql.mean()) if len(pair) else None,'floor_count':floors,'scheduled_predictions':len(scheduled),'floor_fraction':floors/len(scheduled) if scheduled else None};loss[name]=(mse,ql)
 for ctrl in ('TP_NET','TP_HAR'):out['loss_differences']['INFO_vs_'+ctrl]={label:[bootstrap(loss[ctrl][i]-loss['TP_INFO'][i],b) for b in (7,14,28)] if len(pair) else [] for i,label in enumerate(('mse_improvement','qlike_improvement'))}
 beta=[p['models']['TP_INFO']['beta'][-1] for p in pp if start<=p['source']<end and 'beta' in p['models']['TP_INFO']];out['gross_coefficient']={'n':len(beta),'median':float(np.median(beta)) if beta else None,'positive':sum(b>0 for b in beta),'zero_or_negative':sum(b<=0 for b in beta)};return out

def selection(summary,forecast):
 a=summary['main-TP_INFO-base']['metrics'];b=summary['recent-TP_INFO-base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-TP_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):g[c]=all(summary[p+'-TP_INFO-'+c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for ctrl in CONTROLS:extra['net_beats_'+ctrl+'_both']=all(summary[p+'-TP_INFO-base']['metrics']['net_pnl']>summary[p+'-'+ctrl+'-base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_NET_both']=all(summary[p+'-TP_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-TP_NET-base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for p,f in forecast.items():
  x,y,z=[f['models'][n] for n in ('TP_INFO','TP_NET','TP_HAR')];extra[p+'_coverage']=f['coverage']>=.9;extra[p+'_floor']=x['floor_fraction'] is not None and x['floor_fraction']<=.01;extra[p+'_prediction']=all(v['qlike'] is not None for v in (x,y,z)) and x['qlike']<y['qlike'] and x['qlike']<z['qlike'] and x['mse']<=y['mse'];extra[p+'_positive_gross_coefficient']=f['gross_coefficient']['median'] is not None and f['gross_coefficient']['median']>0
 return {'primary':'TP_INFO','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'Only BTC perpetual accounts; gross hourly pressure incremental risk, not VPIN or informed-trader identity; repeatedly inspected development paths; no comparison promotion, OOS, live execution or operating service'}

def run(out):
 out=Path(out);flow,rv=inputs();m=Market()
 for t in flow['zero_execution_hours']:m.rowmaps['BP'].pop(t,None)
 ff={lag:features(flow['rows'],rv,lag) for lag in (0,7)};pp={lag:predict(ff[lag],m) for lag in (0,7)}
 for lag in (0,7):write(out/f'features-lag{lag}.json.gz',ff[lag]);write(out/f'predictions-lag{lag}.json.gz',pp[lag])
 summary={};forecast={};unc={};activity={};results={}
 for period,(start,end) in PERIODS.items():
  forecast[period]=forecast_summary(ff[0],pp[0],start,end);activity[period]={}
  for name in IDS:
   for scenario,cfg in SCENARIOS.items():
    c=dict(cfg);risk=c.pop('risk_target',.2);lag=c.pop('flow_lag',0);plan=schedule(m,ff[lag],pp[lag],name,start,end,risk);planfile=f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz';write(out/planfile,plan);x=ledger.simulate(m,name,start,end,plan,**c);assert all(e.get('instrument')=='BP' for e in x['events']) and all(d['positions']['BS']==0 for d in x['daily']);x.update(period=period,scenario=scenario,risk_target=risk,flow_lag=lag,schedule_file=planfile,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),fit_helper_sha256=sha((ROOT/'tools/btc_periodic_study.py').read_bytes()),pressure_input_sha256=PRESSURE_SHA,rv_input_sha256=RV_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']};activity[period][name+'-'+scenario]={'missing_days':sum(e['weights'] is None for e in plan),'floor_days':sum(e['detail']['floor'] for e in plan),'long_target_days':sum(e['weights'] is not None and e['weights']['BP']>0 for e in plan),'short_target_days':sum(e['weights'] is not None and e['weights']['BP']<0 for e in plan)}
    if scenario=='base':print({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','fees','funding','round_trips')}},flush=True)
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);u={'mean':[bootstrap(r,b) for b in (7,14,28)]}
   for ctrl in CONTROLS:u['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),b) for b in (7,14,28)]
   unc[period+'-'+name]=u
 sel=selection(summary,forecast)
 for key,v in [('summary',summary),('forecast-summary',forecast),('uncertainty',unc),('activity',activity),('selection',sel)]:write(out/(key+'.json'),v)
 print({'selection':sel,'forecasts':{p:{'n':f['n'],'models':f['models'],'gross_coefficient':f['gross_coefficient']} for p,f in forecast.items()}},flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
