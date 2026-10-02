"""Frozen BTC trader-specific short positioning; public delayed information only."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS,SCENARIOS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('COT_SHORT','COT_NET','COT_PRICE','COT_INV');ledger.LABELS.update({x:x for x in IDS})
def sign(v):return int(v>0)-int(v<0)
def close(m,t):
 r=m.rowmaps['BS'].get(t-HOUR);return r[4] if r is not None and r[5]==t-1 else None

def features(m,rows):
 out=[]
 for i,row in enumerate(rows):
  e=dict(row,valid=False,short_signal=0,net_signal=0,price_signal=0)
  if i:
   prev=rows[i-1];a=close(m,prev['report_time']+DAY);b=close(m,row['report_time']+DAY);valid=prev['source']<=row['source'] and prev['oi']>0 and a is not None and b is not None;e.update(previous_report=prev['report_date'],previous_source=prev['source'],valid=valid)
   if valid:e.update(short_signal=sign(prev['short']-row['short']),net_signal=sign((row['long']-row['short'])-(prev['long']-prev['short'])),price_signal=sign(math.log(b/a)),short_change_scaled=(prev['short']-row['short'])/prev['oi'],net_change_scaled=((row['long']-row['short'])-(prev['long']-prev['short']))/prev['oi'],price_return=math.log(b/a))
  out.append(e)
 return out

def risk_observation(m,t,risk):
 i=m.index.get(t-DAY,-1)
 if i<20:return None
 h=m.close[i-20:i+1]
 if not np.all(np.isfinite(h)):return None
 vol=float(np.diff(np.log(h)).std(ddof=1)*math.sqrt(365));return (min(1,risk/vol) if vol>1e-12 else 0.,vol)

def schedule(m,feats,name,start,end,risk=.2):
 out=[]
 for t in range(start,end,DAY):
  obs=risk_observation(m,t,risk)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':{'risk_missing':True}});continue
  w,vol=obs;available=[e for e in feats if e['source']<=t];e=max(available,key=lambda e:e['report_time']) if available else None;valid=e is not None and e['valid'] and t<e['expiry'];s=0
  if valid:s=e[{'COT_SHORT':'short_signal','COT_NET':'net_signal','COT_PRICE':'price_signal','COT_INV':'short_signal'}[name]]*(-1 if name=='COT_INV' else 1)
  detail={'signal':s,'risk':w,'vol':vol,'report_date':e['report_date'] if e else None,'information_time':e['source'] if e else None,'age_days':(t-e['report_time'])//DAY if e else None,'expiry':e['expiry'] if e else None,'common_valid':valid}
  out.append({'source_time':t,'weights':{'BS':max(s,0)*w,'BP':min(s,0)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def run(out):
 out=Path(out);data=ROOT/'data/btc-cot-20261002';audit=read(data/'clock-audit.json');rr=read(data/'reports.json');assert sha(canonical(rr))==audit['reports_sha256'];m=Market();f=features(m,rr);write(out/'features.json',f);results={};summary={};unc={};ages={}
 for period,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan=schedule(m,f,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),cot_input_sha256=audit['reports_sha256']);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
    if name=='COT_SHORT' and scenario=='base':ages[period]={'cash_or_invalid_days':sum(not e['detail'].get('common_valid',False) for e in plan),'used_reports':len({e['detail'].get('report_date') for e in plan if e['detail'].get('common_valid')}),'age_day_counts':{str(k):sum(e['detail'].get('age_days')==k and e['detail'].get('common_valid',False) for e in plan) for k in range(21)}}
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,other in [('E_SPOT',old),('COT_PRICE',results[period,'COT_PRICE','base']),('COT_NET',results[period,'COT_NET','base'])]:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(other['daily_returns']),n) for n in (7,14,28)]
 a=results['main','COT_SHORT','base']['metrics'];b=results['recent','COT_SHORT','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','COT_SHORT','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=50,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'COT_SHORT',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={ctrl:all(results[p,'COT_SHORT','base']['metrics']['net_pnl']>results[p,ctrl,'base']['metrics']['net_pnl'] for p in PERIODS) for ctrl in ('COT_PRICE','COT_NET')};write(out/'summary.json',summary);write(out/'uncertainty.json',unc);write(out/'information-age.json',ages);write(out/'selection.json',{'primary':'COT_SHORT','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; publication assumptions not full historical PIT proof; controls not promotable'});print(json.dumps({'gates':g,'increment':extra,'information':ages}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
