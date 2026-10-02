"""Preregistered BTC price-orthogonal order-flow experiment. No network/live API."""
import argparse,math,json
from pathlib import Path
import numpy as np
from btc_session_study import Market,simulate,write,bootstrap,PERIODS,SCENARIOS,ROOT,DAY,HOUR,STEP,sha,canonical
IDS=('OF_RES','OF_RAW','PF_REV','OF_NEG')
def features(m):
 first=min(m.hourly)//DAY*DAY;end=max(m.hourly)//DAY*DAY+DAY;days=list(range(first,end,DAY));f=[];ret=[];vol=[];bad={int(x//DAY*DAY) for x in m.conflicts if any(abs(v)>1e-3 for rec in m.resolution['unresolved'] if x==int(__import__('btc_perp_bot.research.archive',fromlist=['ms']).ms(rec['time'])) for v in rec['volume_errors'])};raw=[]
 for day in days:
  rr=[m.hourly.get(day+j*HOUR) for j in range(24)];a,b=m.close(day),m.close(day+DAY);valid=day not in bad and a is not None and b is not None and all(r is not None and r[5]>0 and r[6]==r[0]+HOUR-1 for r in rr)
  buy=math.fsum(r[10] for r in rr) if all(r is not None for r in rr) else 0.;sell=math.fsum(r[7]-r[10] for r in rr) if all(r is not None for r in rr) else 0.;valid=valid and buy>0 and sell>0
  f.append(math.log(buy/sell) if valid else float('nan'));ret.append(b/a-1 if valid else float('nan'));cl=[m.close(day+DAY-j*DAY) for j in range(20,-1,-1)];vol.append(float(np.std(np.diff(np.log(cl)),ddof=1)*math.sqrt(365)) if all(c is not None for c in cl) else float('nan'));raw.append({'day':day,'buy_quote':buy,'sell_quote':sell,'valid':valid,'conflict_day':day in bad})
 f=np.array(f);ret=np.array(ret);F=np.full(len(f),np.nan)
 for i in range(29,len(f)):
  h=f[i-29:i+1];sd=np.std(h,ddof=1)
  if np.all(np.isfinite(h)) and sd>1e-12:F[i]=f[i]/sd
 out=[]
 for i,day in enumerate(days):
  e={'source':day+DAY,'signal_day':day,'missing':True,'input':raw[i]}
  if i<365 or not np.isfinite(F[i]) or not np.isfinite(ret[i]) or not np.isfinite(vol[i]) or vol[i]<=1e-12:out.append(e);continue
  sel=np.arange(i-365,i);sel=sel[np.isfinite(F[sel])&np.isfinite(ret[sel])]
  if len(sel)<300:out.append(e);continue
  a,b=ret[sel],F[sel];am,bm=float(a.mean()),float(b.mean());den=float(np.sum((a-am)**2))
  if den<=1e-15:out.append(e);continue
  slope=float(np.sum((a-am)*(b-bm))/den);intercept=bm-slope*am;res=b-intercept-slope*a;resstd=math.sqrt(float(res@res)/(len(sel)-2));fsd=float(np.std(b,ddof=1));rsd=float(np.std(a,ddof=1))
  if min(resstd,fsd,rsd)<=1e-12:out.append(e);continue
  e.update(missing=False,r=float(ret[i]),log_flow=float(f[i]),normalized_flow=float(F[i]),training_start=days[int(sel[0])],training_end=days[int(sel[-1])]+DAY,training_count=len(sel),alpha=intercept,beta=slope,residual_std=resstd,z_res=float((F[i]-intercept-slope*ret[i])/resstd),z_raw=float((F[i]-bm)/fsd),z_price=float((ret[i]-am)/rsd),annual_vol=float(vol[i]));out.append(e)
 return out

def schedule(feats,name,start,end,risk=.2):
 out=[]
 for e in feats:
  t=e['source']
  if not start<=t<end:continue
  if e['missing']:out.append({'source':t,'weight':None,'detail':e});continue
  z=e['z_raw'] if name=='OF_RAW' else e['z_price'] if name=='PF_REV' else e['z_res'];s=(1 if z>0 else -1) if abs(z)>=1 else 0
  if name in ('PF_REV','OF_NEG'):s=-s
  out.append({'source':t,'weight':s*min(1,risk/e['annual_vol']),'detail':e|{'sign':s}})
 return out

def run(out):
 out=Path(out);m=Market();feat=features(m);write(out/'features.json.gz',feat);results={};summary={};uncertainty={}
 for p,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    risk=c.get('risk',.2);plan=schedule(feat,name,start,end,risk);write(out/f'{p}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=simulate(m,name,start,end,plan,**c);x.update(period=p,scenario=scenario,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_session_study.py').read_bytes()));write(out/f'{p}-{name}-{scenario}.json.gz',x);results[p,name,scenario]=x;summary[f'{p}-{name}-{scenario}']=x['metrics']
    if scenario=='base':print(json.dumps({'period':p,'name':name,**{k:x['metrics'][k] for k in ('return_pct','dd_pct','sharpe','fees','funding','round_trips')}}),flush=True)
  for name in IDS:
   a=np.array(results[p,name,'base']['daily_returns']);u={'mean':[bootstrap(a,n) for n in (7,14,28)]}
   for ctrl in ('OF_RAW','PF_REV'):u['vs_'+ctrl]=[bootstrap(a-np.array(results[p,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
   uncertainty[p+'-'+name]=u
 a=results['main','OF_RES','base']['metrics'];b=results['recent','OF_RES','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['dd_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['dd_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v>0 for v in a['annual'].values())>=3,'trades':a['round_trips']>=100,'margin':a['margin_breach_bars']==b['margin_breach_bars']==0}
 for c in ('base','cost_x2','delay60','delay240'):g[c]=all(results[p,'OF_RES',c]['metrics']['net']>0 for p in PERIODS)
 write(out/'summary.json',summary);write(out/'uncertainty.json',uncertainty);write(out/'selection.json',{'primary':'OF_RES','passed':all(g.values()),'checks':g,'comparisons_not_eligible':list(IDS[1:]),'scope':'development only; price orthogonal is not causal'});print(json.dumps(g),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
