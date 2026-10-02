"""Preregistered BTC FOMC rate repricing overlay; offline only."""
import argparse,math,json
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS,SCENARIOS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('MB_RATE','MB_INV','MB_PRICE','MB_CASH');ledger.LABELS.update({k:k for k in IDS})
def sign(x):return (x>0)-(x<0)
def completed_close(m,t):
 r=m.rowmaps['BS'].get(t-HOUR)
 return r[4] if r is not None and r[5]==t-1 else None

def event_features(m,events):
 out=[]
 for e in events:
  t=e['source_time'];a=completed_close(m,ms(e['event'])+DAY);b=completed_close(m,t);valid=e['valid'] and a is not None and b is not None
  out.append(dict(e,end_time=t+5*DAY,price_start=ms(e['event'])+DAY,price_end=t,price_return=math.log(b/a) if valid else None,usable=valid))
 return out

def schedule(m,events,name,start,end,risk=.2):
 out=[]
 for t in range(start,end,DAY):
  obs=m.observation(t,risk);active=[e for e in events if e['source_time']<=t<e['end_time']];assert len(active)<=1
  if obs is None:out.append({'source_time':t,'weights':None,'detail':{'missing':True}});continue
  score,w,vol=obs;s=max(score,0);detail={'score':score,'risk':w,'vol':vol,'event':None}
  if active:
   e=active[0];detail.update(event=e['event'],vintage_date=e['vintage_date'],event_source=e['source_time'],event_end=e['end_time'],delta=e.get('delta_percentage_points'),price_return=e['price_return'],usable=e['usable'])
   if not e['usable'] or name=='MB_CASH':s=0
   elif name=='MB_PRICE':s=sign(e['price_return'])
   else:s=sign(e['delta_percentage_points'])*(-1 if name=='MB_RATE' else 1)
  detail['signal']=s;out.append({'source_time':t,'weights':{'BS':max(s,0)*w,'BP':min(s,0)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def run(out):
 out=Path(out);data=ROOT/'data/btc-macro-vintage-20261002';audit=read(data/'audit.json');events=read(data/'events.json');assert sha((data/'events.json').read_bytes())==audit['events_sha256'];m=Market();feats=event_features(m,events);write(out/'event-features.json',feats);results={};summary={};unc={}
 for period,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan=schedule(m,feats,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),macro_input_sha256=audit['events_sha256']);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,other in [('E_SPOT',old),('MB_PRICE',results[period,'MB_PRICE','base']),('MB_CASH',results[period,'MB_CASH','base'])]:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(other['daily_returns']),n) for n in (7,14,28)]
 a=results['main','MB_RATE','base']['metrics'];b=results['recent','MB_RATE','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','MB_RATE','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0,'all_37_events':len(feats)==37 and all(e['usable'] for e in feats)}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'MB_RATE',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={ctrl:all(results[p,'MB_RATE','base']['metrics']['net_pnl']>results[p,ctrl,'base']['metrics']['net_pnl'] for p in PERIODS) for ctrl in ('MB_PRICE','MB_CASH')}
 counts={str(y):{'n':sum(e['event'].startswith(str(y)) for e in feats),'rate_positive':sum(e['event'].startswith(str(y)) and e.get('delta_percentage_points',0)>0 for e in feats),'rate_negative':sum(e['event'].startswith(str(y)) and e.get('delta_percentage_points',0)<0 for e in feats)} for y in range(2022,2027)}
 write(out/'summary.json',summary);write(out/'uncertainty.json',unc);write(out/'selection.json',{'primary':'MB_RATE','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'counts':counts,'scope':'development; daily rate change is not identified unexpected monetary shock; sparse events; controls not promotable'});print(json.dumps({'gates':g,'increment':extra,'events':counts}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
