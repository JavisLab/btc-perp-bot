"""Preregistered ordinary last-Friday demand window; no claim of an exact actual CME expiry history."""
import argparse,math,json
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import ROOT,DAY,HOUR,ms,read,write,sha,canonical,bootstrap
import btc_target_ledger as ledger
IDS=('EX_LONG','EX_ONLY','EX_INV','EX_PLACEBO','EX_WEEKLY','EX_CLOCK','EX_TREND');ledger.LABELS.update({n:n for n in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1}}
CAL_SHA='6aa1f877a7ee6d0a8e59f3e0eed4f251dcfb85231427a7836f3f35498261b8b9'
def inputs():
 p=ROOT/'data/btc-expiry-20261003/calendar.json';assert sha(p.read_bytes())==CAL_SHA;return read(p)
def events(cal,name):
 if name=='EX_TREND':return []
 if name=='EX_WEEKLY':return cal['weekly_controls']
 if name=='EX_PLACEBO':return [e['placebo'] for e in cal['events']]
 return cal['events']
def schedule(m,cal,name,start,end,risk=.2):
 points={t:{'role':'daily','event':None} for t in range(start,end,DAY)}
 for e in events(cal,name):
  for role,t in [('enter',e['signal_start']),('exit',e['signal_end'])]:
   if start<=t<end:assert t not in points;points[t]={'role':role,'event':e}
 plan=[]
 for t,point in sorted(points.items()):
  risk_day=t//DAY*DAY;obs=m.observation(risk_day,risk);role=point['role'];cash=name=='EX_ONLY' and role!='enter';detail={'role':role,'event':point['event'],'risk_day':risk_day,'risk_latest_close':risk_day,'override':role=='enter' and name!='EX_CLOCK'}
  if obs is None:
   plan.append({'source_time':t,'weights':{'BS':0.,'BP':0.} if cash else None,'rebalance':True,'hedge':False,'detail':dict(detail,risk_missing=True,known_cash=cash)});continue
  score,w,vol=obs;signal=0. if cash else max(0,score)
  if detail['override']:signal=-1. if name=='EX_INV' else 1.
  detail.update(score=score,risk=w,vol=vol,signal=signal,core_fallback=not detail['override'] and name!='EX_ONLY');plan.append({'source_time':t,'weights':{'BS':max(0,signal)*w,'BP':min(0,signal)*w},'rebalance':True,'hedge':False,'detail':detail})
 return plan

def event_diagnostics(m,cal):
 rows=[];mask=set(read(ROOT/'data/btc-venue-20261003/masks.json')['binance_spot_no_trade'])
 def outcome(e):
  a,b=e['base_entry'],e['base_exit'];p,q=m.rowmaps['BS'].get(a),m.rowmaps['BS'].get(b)
  if p is None or q is None or a in mask or b in mask:return None
  return math.log(q[1]/p[1])
 for e in cal['events']:
  a,b=outcome(e),outcome(e['placebo']);rows.append({'date':e['date'],'period':'main' if e['date']<'2026-01-01' else 'recent','entry':e['base_entry'],'exit':e['base_exit'],'placebo_entry':e['placebo']['base_entry'],'placebo_exit':e['placebo']['base_exit'],'spot_open_log_return':a,'prior_week_spot_open_log_return':b,'paired_log_return_difference':a-b if a is not None and b is not None else None})
 ci={}
 for period in PERIODS:
  a=np.array([e['paired_log_return_difference'] for e in rows if e['period']==period and e['paired_log_return_difference'] is not None]);interval=[]
  for block in (1,3,6):
   rng=np.random.default_rng(1499+block);idx=(rng.integers(0,len(a),(2000,math.ceil(len(a)/block),1))+np.arange(block))%len(a);sample=a[idx.reshape(2000,-1)[:,:len(a)]].mean(axis=1)*100;interval.append({'block_months':block,'draws':2000,'mean_log_difference_pct':float(a.mean()*100),'ci95':np.quantile(sample,[.025,.975]).tolist()})
  ci[period]={'paired_months':len(a),'bootstrap':interval}
 return {'scope':'post-event gross six-hour spot open log returns, no fees/quantity/funding; not account profit and never used in signals','events':rows,'paired_uncertainty':ci}

def run(out):
 out=Path(out);m=Market();cal=inputs();write(out/'calendar.json',cal);write(out/'event-outcomes.json',event_diagnostics(m,cal));results={};summary={};unc={};identity={};activity={}
 for period,(start,end) in PERIODS.items():
  activity[period]={}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan=schedule(m,cal,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),calendar_sha256=CAL_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']};activity[period][name+'-'+scenario]={'daily_plans':sum(e['detail']['role']=='daily' for e in plan),'event_start_plans':sum(e['detail']['role']=='enter' for e in plan),'event_exit_plans':sum(e['detail']['role']=='exit' for e in plan),'override_plans':sum(e['detail']['override'] for e in plan),'missing_risk_plans':sum(e['detail'].get('risk_missing',False) for e in plan)}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'EX_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':f'runs/search-1458/{period}-E_SPOT.json.gz'}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('EX_CLOCK','EX_PLACEBO','EX_TREND'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','EX_LONG','base']['metrics'];b=results['recent','EX_LONG','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','EX_LONG','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'EX_LONG',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in ('EX_CLOCK','EX_PLACEBO','EX_WEEKLY','EX_TREND'):extra['net_beats_'+name+'_both']=all(results[p,'EX_LONG','base']['metrics']['net_pnl']>results[p,name,'base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_clock_both']=all(results[p,'EX_LONG','base']['metrics']['max_drawdown_pct']<=results[p,'EX_CLOCK','base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for c in ('base','cost_x2'):extra['event_only_'+c+'_positive_both']=all(results[p,'EX_ONLY',c]['metrics']['net_pnl']>0 for p in PERIODS)
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('selection',{'primary':'EX_LONG','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; ordinary non-holiday last-Friday clock, not recovered actual CME expiry; fixed literature-inspired window after published cumulative multiwindow discovery; no accepted control promotion'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
