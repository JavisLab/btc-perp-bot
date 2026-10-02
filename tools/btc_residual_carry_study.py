"""Preregistered residual-cash BTC carry allocation, not price-alpha research."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT
import btc_residual_ledger as ledger
IDS=('RC_BLEND','RC_TREND','RC_CARRY')
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'funding_haircut50':{'funding_credit_factor':.5}}
def schedule(m,name,start,end,risk=.2):
 out=[]
 for t in range(start,end,DAY):
  obs=m.observation(t,risk)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':{'missing_warmup':True}});continue
  score,w,vol=obs;core=max(0,score)*w if name!='RC_CARRY' else 0.;allocation=.8 if name!='RC_TREND' else 0.
  out.append({'source_time':t,'weights':{'BS':core,'BP':0},'core_weight':core,'carry_allocation':allocation,'rebalance':True,'hedge':False,'detail':{'score':score,'risk':w,'vol':vol}})
 return out

def run(out):
 out=Path(out);m=Market();results={};summary={};unc={};identity={}
 for period,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan=schedule(m,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_residual_ledger.py').read_bytes()));write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','core_round_trips','fees','funding','margin_buffer_breach_hours')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'RC_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7,(period,errors,daily);identity[period]={'metric_errors':errors,'daily_return_max_error':daily}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('RC_TREND','RC_CARRY'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','RC_BLEND','base']['metrics'];b=results['recent','RC_BLEND','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(e['return_pct']>0 for e in results['main','RC_BLEND','base']['periods']['yearly'].values())>=3,'core_episodes':a['core_round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','funding_haircut50'):g[c]=all(results[p,'RC_BLEND',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={'net_beats_trend_both':all(results[p,'RC_BLEND','base']['metrics']['net_pnl']>results[p,'RC_TREND','base']['metrics']['net_pnl'] for p in PERIODS),'dd_no_worse_both':all(results[p,'RC_BLEND','base']['metrics']['max_drawdown_pct']<=results[p,'RC_TREND','base']['metrics']['max_drawdown_pct'] for p in PERIODS)}
 for n,v in [('summary',summary),('uncertainty',unc),('trend-identity',identity),('selection',{'primary':'RC_BLEND','passed':all(g.values()) and all(extra.values()),'checks':g,'capital_allocation_increment':extra,'scope':'development only; idle cash deployed into funding/basis/operational risk, NOT new price-prediction alpha; controls not promotable'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'trend_identity':identity}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
