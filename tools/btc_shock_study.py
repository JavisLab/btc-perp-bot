"""Fixed three-sigma two-hour BTC shock reversal, not a timing/threshold search."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_session_study import Market,simulate,write,read,bootstrap,PERIODS,SCENARIOS,ROOT,DAY,HOUR,sha,canonical
IDS=('SH_REV','SH_MOM','SH_ALL','SH_SMALL');BLOCK=2*HOUR

def event_signal(r,sigma,name):
 s=int(r>0)-int(r<0);J=abs(r)>=3*sigma
 return -s*J if name=='SH_REV' else s*J if name=='SH_MOM' else -s if name=='SH_ALL' else -s*(not J)

def features(m):
 first=min(m.hourly)//BLOCK*BLOCK+BLOCK;end=(max(m.hourly)//BLOCK+1)*BLOCK;rows=[];volumes={}
 for t in range(first,end+1,BLOCK):
  a,b=m.close(t-BLOCK),m.close(t);hours=[m.hourly.get(t-j*HOUR) for j in (2,1)];valid=a is not None and b is not None and all(r is not None and r[5]>0 and r[6]==r[0]+HOUR-1 for r in hours);day=t//DAY*DAY
  if day not in volumes:
   cl=[m.close(day-j*DAY) for j in range(20,-1,-1)];volumes[day]=float(np.std(np.diff(np.log(cl)),ddof=1)*math.sqrt(365)) if all(v is not None for v in cl) else None
  rows.append({'source':t,'r':math.log(b/a) if valid else None,'price_valid':valid,'sigma':None,'risk_end':day,'annual_vol':volumes[day],'current_start':t-BLOCK,'training_last':t-BLOCK,'training_first':t-360*BLOCK,'signal_conflicts':[x for x in (t-3*HOUR,t-2*HOUR,t-HOUR) if x in m.conflicts]})
 for i,e in enumerate(rows):
  h=rows[max(0,i-360):i]
  if len(h)==360 and all(r['price_valid'] for r in h):e['sigma']=float(np.std([r['r'] for r in h],ddof=1))
 return rows

def schedule(feats,name,start,end,risk=.2):
 out=[]
 for e in feats:
  if not start<=e['source']<end:continue
  vol=e['annual_vol'];valid=e['r'] is not None and e['sigma'] is not None and e['sigma']>1e-12 and vol is not None and vol>1e-12;s=event_signal(e['r'],e['sigma'],name) if valid else 0;w=s*min(1,risk/vol) if valid else 0.;out.append({'source':e['source'],'weight':w,'detail':dict(e,common_valid=valid,sign=int(s),shock=bool(abs(e['r'])>=3*e['sigma']) if valid else None)})
 return out

def run(out):
 out=Path(out);m=Market();f=features(m);write(out/'features.json.gz',f);results={};summary={};unc={};incidence={}
 for p,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    risk=c.get('risk',.2);plan=schedule(f,name,start,end,risk);write(out/f'{p}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=simulate(m,name,start,end,plan,**c);x.update(period=p,scenario=scenario,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_session_study.py').read_bytes()));write(out/f'{p}-{name}-{scenario}.json.gz',x);results[p,name,scenario]=x;summary[f'{p}-{name}-{scenario}']=x['metrics']
    if scenario=='base':print(json.dumps({'period':p,'name':name,**{k:x['metrics'][k] for k in ('return_pct','dd_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
    if name=='SH_REV' and scenario=='base':incidence[p]={'decisions':len(plan),'invalid_cash':sum(not e['detail']['common_valid'] for e in plan),'positive_shocks':sum(e['detail']['shock'] and e['detail']['r']>0 for e in plan if e['detail']['shock'] is not None),'negative_shocks':sum(e['detail']['shock'] and e['detail']['r']<0 for e in plan if e['detail']['shock'] is not None),'conflict_sources':sum(bool(e['detail']['signal_conflicts']) for e in plan)}
  old=read(ROOT/f'runs/search-1458/{p}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[p,name,'base']['daily_returns']);unc[p+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,other in [('E_SPOT',old),('SH_MOM',results[p,'SH_MOM','base']),('SH_SMALL',results[p,'SH_SMALL','base'])]:unc[p+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(other['daily_returns']),n) for n in (7,14,28)]
 a=results['main','SH_REV','base']['metrics'];b=results['recent','SH_REV','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['dd_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['dd_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v>0 for v in a['annual'].values())>=3,'trades':a['round_trips']>=100,'margin':a['margin_breach_bars']==b['margin_breach_bars']==0}
 for c in ('base','cost_x2','delay60','delay240'):g[c]=all(results[p,'SH_REV',c]['metrics']['net']>0 for p in PERIODS)
 for n,v in [('summary',summary),('uncertainty',unc),('shock-incidence',incidence),('selection',{'primary':'SH_REV','passed':all(g.values()),'checks':g,'comparisons_not_eligible':list(IDS[1:]),'scope':'development only; price shocks not observed liquidations; author horizon selection disclosed; missing features cash, no hindsight timing/peak exits'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'incidence':incidence}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
