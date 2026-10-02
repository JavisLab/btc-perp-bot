"""Attribute EXISTING BTC-only ledgers; does not calculate a new strategy."""
import gzip,json,math
from collections import Counter
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,utc
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if str(p).endswith('.gz') else json.loads(p.read_text())
def run(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);allresults={}
 for period in ('main','recent'):
  for name in ('E_SPOT','E_PERP','E_LS'):
   x=read(ROOT/f'runs/search-1458/{period}-{name}.json.gz');m=x['metrics'];q=0.;cashflow={1:0.,-1:0.};fees={1:0.,-1:0.};imp={1:0.,-1:0.};fund={1:0.,-1:0.};entry=None;holds=[];components=[]
   for e in x['events']:
    if e['kind']=='funding':fund[1 if e['position']>0 else -1]+=e['cashflow'];continue
    if e['kind']!='fill':continue
    dq=e['delta'];nq=q+dq
    parts=[]
    if q*dq<0:
     closed=min(abs(q),abs(dq));parts.append((1 if q>0 else -1,-math.copysign(closed,q)))
     if abs(dq)>closed+1e-12:parts.append((1 if dq>0 else -1,math.copysign(abs(dq)-closed,dq)))
    else:parts.append((1 if dq>0 else -1,dq))
    for s,d in parts:
     share=abs(d/dq);cashflow[s]-=d*e['reference'];fees[s]+=share*e['fee'];imp[s]+=share*e['impact']
    if abs(q)<1e-10 and abs(nq)>1e-10:entry=e['time']
    if abs(q)>1e-10 and (abs(nq)<1e-10 or q*nq<0):
     holds.append((e['time']-entry)/HOUR);entry=e['time'] if abs(nq)>1e-10 else None
    q=nq
   sides={str(s):{'price_gross':cashflow[s],'fees':fees[s],'impact':imp[s],'funding':fund[s],'net':cashflow[s]-fees[s]-imp[s]+fund[s]} for s in (1,-1)}
   assert abs(sum(v['net'] for v in sides.values())-m['net_pnl'])<1e-7
   a={'metrics':m,'annual':x['periods']['yearly'],'sides':sides,'holding_hours':{'mean':float(np.mean(holds)),'median':float(np.median(holds)),'max':max(holds),'episodes':len(holds)},'minimum_skips':dict(Counter(e['reason'] for e in x['skips'])),
    'time_in_position_pct':sum(holds)*HOUR/(ms(x['end'])-ms(x['start']))*100,'delay_stress':{}}
   for scenario in ('cost_x2','delay1','delay24','risk10','risk30'):
    y=read(ROOT/f'runs/search-1458/{period}-{name}-{scenario}.json.gz')['metrics'];a['delay_stress'][scenario]={k:y[k] for k in ('return_pct','max_drawdown_pct','realized_vol_pct','mean_exposure')}
   allresults[period+'-'+name]=a
  signals=read(ROOT/'runs/structure-1471/signals.json.gz')['signals'];diagnostics=read(ROOT/'runs/structure-1471/diagnostics.json')
  for name in ('A_ACCEPT','R_RETEST','F_REJECT','P_RESUME','C_CHANNEL'):
   x=read(ROOT/f'runs/structure-1471/{period}-{name}-base.json.gz');tr=x['trades'];util=[]
   for t in tr:
    loss=t['side']*(t['fill']-t['initial_stop']*(1-t['side']*.00015))+ .0005*(t['fill']+t['initial_stop']*(1-t['side']*.00015))
    util.append(t['qty']*loss/t['risk_budget'])
   a={'metrics':x['summary'],'exposure':diagnostics[f'{period}-{name}-base'],'declared_signals':sum(x['start']<=e['source']<x['end'] for e in signals[name]),'mean_initial_stop_risk_budget_utilization_pct':float(np.mean(util)*100) if util else 0,'annual':x['summary']['annual'],'delay_stress':{}}
   for scenario in ('cost_x2','delay60','risk_half','risk_double','stop_5bp'):
    y=read(ROOT/f'runs/structure-1471/{period}-{name}-{scenario}.json.gz')['summary'];a['delay_stress'][scenario]={k:y[k] for k in ('return_pct','dd_pct','trades')}
   allresults[period+'-'+name]=a
 (out/'constraints.json').write_bytes(canonical(allresults))
 for k,v in allresults.items():
  m=v['metrics'];print(k, json.dumps({'return':m['return_pct'],'sides':v.get('sides',m.get('sides')),'exposure':m.get('mean_exposure',v.get('exposure')),'signals':v.get('declared_signals'),'risk_util':v.get('mean_initial_stop_risk_budget_utilization_pct'),'holds':v.get('holding_hours')}))
if __name__=='__main__':run(ROOT/'runs/btc-continuation-20261002')
