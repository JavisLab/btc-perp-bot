"""Preregistered BTC same-session rules; offline only, no exchange/client imports."""
import argparse,gzip,json,math
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,sha,utc
ROOT=Path(__file__).resolve().parents[1];STEP=300000
IDS=('SR00','SM00','SL00','SR08')
PERIODS={'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}
SCENARIOS={'base':{},'cost_x2':{'cost':2.},'delay60':{'delay':HOUR},'delay240':{'delay':4*HOUR},'risk10':{'risk':.1}}
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);b=canonical(x)
 if p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 if p.exists() and p.read_bytes()!=b:raise ValueError('Refusing to replace prior result '+str(p))
 p.write_bytes(b)
class Market:
 def __init__(self):
  self.resolution=read(ROOT/'data/structure-1471/resolution.json');self.rows=read(ROOT/'data/structure-1471/bars-repaired.json.gz')['rows'];assert sha(canonical(self.rows))==self.resolution['repaired_rows_sha256']
  h=read(ROOT/'runs/price-volume-1462/ohlcv.json.gz')['rows'];assert sha(canonical(h))=='1724851f889b7602fa4736dc71a9e6c76db1547be6a3d7be64092f55c27ba551';self.hourly={r[0]:r for r in h}
  b=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes());assert sha(b)=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4';d=json.loads(b)['series']['BTCUSDT'];marks={r[0]:r[1] for r in d['mark']};self.funds={r[0]:(r[2],marks[r[0]],r[3]) for r in d['funding']}
  self.first=self.rows[0][0];self.conflicts={ms(r['time']) for r in self.resolution['unresolved']}
  assert all(r[0]==self.first+i*STEP and r[6]==r[0]+STEP-1 for i,r in enumerate(self.rows))
 def close(self,t):
  r=self.hourly.get(t-HOUR)
  return r[4] if r is not None and r[6]==t-1 and r[5]>0 else None
 def plan(self,name,start,end,risk=.2):
  cutoff=8 if name=='SR08' else 0;out=[]
  for t in range(start+cutoff*HOUR,end,12*HOUR):
   a,b=self.close(t-DAY),self.close(t-12*HOUR);day=t//DAY*DAY;cl=[self.close(day-j*DAY) for j in range(20,-1,-1)];detail={'signal_start':t-DAY,'signal_end':t-12*HOUR,'risk_end':day}
   if a is None or b is None or any(c is None for c in cl):out.append({'source':t,'weight':None,'detail':detail|{'missing':True}});continue
   r=b/a-1.;vol=float(np.std(np.diff(np.log(cl)),ddof=1)*math.sqrt(365));s=1 if name=='SL00' else (1 if r>0 else -1 if r<0 else 0)*(1 if name=='SM00' else -1)
   w=s*min(1.,risk/vol) if vol>1e-12 else None
   detail.update(lagged_return=r,sign=s,annual_vol=vol,signal_conflict=[x for x in (t-DAY-HOUR,t-12*HOUR-HOUR) if x in self.conflicts],risk_conflict=[day-j*DAY-HOUR for j in range(21) if day-j*DAY-HOUR in self.conflicts])
   out.append({'source':t,'weight':w,'detail':detail})
  return out

def simulate(m,name,start,end,plan,cost=1.,delay=0,risk=.2):
 rows=m.rows[(start-m.first)//STEP:(end-m.first)//STEP];n=len(rows);final_i=max(i for i,r in enumerate(rows) if r[5]>0)
 fee=.0005*cost;impact=.00015*cost;cash=1000.;q=0.;events=[];daily=[];skips=[];peak=1000.;dd=adverse_dd=0.;fees=impacts=funding=turnover=0.;maxexpo=exposum=0.;breaches=held=0;min_margin=None;episodes=0;halted=False;cursor=0;pending=None;conflict_held=set();conflict_fills=set();sides={s:dict(gross=0.,fees=0.,impact=0.,funding=0.) for s in ('long','short')}
 def observe(ref):
  nonlocal peak,dd,maxexpo
  eq=cash+q*ref;peak=max(peak,eq);dd=max(dd,100*(1-eq/peak));maxexpo=max(maxexpo,abs(q)*ref/eq if eq>0 else 0.);return eq
 def fill(new,ref,t,source,reason,force=False):
  nonlocal cash,q,fees,impacts,turnover,episodes
  dq=new-q
  if abs(dq)<.0001:return False
  px=ref*(1+math.copysign(impact,dq));reducing=q*dq<0 and abs(new)<abs(q) and q*new>=0
  if not force and abs(dq)*px<50 and not reducing:skips.append({'time':t,'source':source,'reason':'minimum','notional':abs(dq)*px});return False
  charge=abs(dq)*px*fee;slip=abs(dq)*ref*impact;old=q
  components=[(-old,'long' if old>0 else 'short'),(new,'long' if new>0 else 'short')] if old and old*new<=0 else [(dq,'long' if (new or old)>0 else 'short')]
  for delta,side in components:
   if not delta:continue
   sides[side]['gross']-=delta*ref;sides[side]['fees']+=abs(delta)*px*fee;sides[side]['impact']+=abs(delta)*ref*impact
  if old and old*new<=0:episodes+=1
  cash-=dq*px+charge;q=new;fees+=charge;impacts+=slip;turnover+=abs(dq)*px
  events.append({'kind':'fill','time':int(t),'source':source,'reason':reason,'delta':dq,'before':old,'position':new,'reference':ref,'price':px,'fee':charge,'impact':slip})
  hour=(t if reason!='period_end' else t-STEP)//HOUR*HOUR
  if hour in m.conflicts:conflict_fills.add(hour)
  return True
 for i,row in enumerate(rows):
  t,o,h,l,c,v=row[:6]
  if t in m.funds and q:
   rate,mark,raw=m.funds[t];flow=-q*mark*rate;cash+=flow;funding+=flow;sides['long' if q>0 else 'short']['funding']+=flow;events.append({'kind':'funding','time':t,'raw_time':raw,'rate':rate,'reference':mark,'position':q,'cashflow':flow})
  eq=observe(o)
  if eq<=0:halted=True
  if halted and q and v>0:fill(0.,o,t,None,'nonpositive',True)
  while cursor<len(plan) and plan[cursor]['source']+STEP+delay<=t:
   pending=plan[cursor];cursor+=1
  if pending is not None and not halted and i<=final_i:
   if pending['weight'] is None:skips.append({'time':t,'source':pending['source'],'reason':'missing_observation'});pending=None
   elif v<=0:skips.append({'time':t,'source':pending['source'],'reason':'zero_volume_retry'})
   else:
    w=pending['weight'];eq=cash+q*o;needs=(q==0 and w!=0) or q*w<0 or(q!=0 and w==0) or abs(w-q*o/eq)>=.05
    if needs:
     post=eq
     for _ in range(12):
      target=w*post/o;dq=target-q;px=o*(1+math.copysign(impact,dq)) if dq else o;post=eq+dq*(o-px)-abs(dq)*px*fee
     target=w*post/o;new=math.copysign(math.floor((abs(target)+1e-12)/.001)*.001,target)
     fill(new,o,t,pending['source'],'target')
    pending=None
  observe(o)
  if q:
   held+=1;adverse=l if q>0 else h;aeq=cash+q*adverse;ratio=aeq/(abs(q)*adverse);min_margin=ratio if min_margin is None else min(min_margin,ratio);breaches+=int(ratio<.05);adverse_dd=max(adverse_dd,100*(1-aeq/peak));hour=t//HOUR*HOUR
   if hour in m.conflicts:conflict_held.add(hour)
  eq=observe(c);exposum+=abs(q)*c/eq if eq>0 else 0.
  if i==final_i:fill(0.,c,t+STEP,None,'period_end',True);eq=observe(c)
  if (t+STEP)%DAY==0:daily.append({'time':t+STEP,'equity':eq,'cash':cash,'position':q,'reference':c,'fees':fees,'impact':impacts,'funding':funding,'drawdown_pct':100*(1-eq/peak)})
 initial=1000.;eq=cash;ret=np.diff(np.r_[initial,[d['equity'] for d in daily]])/np.r_[initial,[d['equity'] for d in daily]][:-1];annual={};quarter={}
 for d,r in zip(daily,ret):
  date=utc(d['time']-1);year=date[:4];qua=year+'Q'+str((int(date[5:7])-1)//3+1);annual[year]=annual.get(year,1.)*(1+r);quarter[qua]=quarter.get(qua,1.)*(1+r)
 gross=math.fsum(-e['delta']*e['reference'] for e in events if e['kind']=='fill');assert abs(initial+gross+funding-fees-impacts-eq)<1e-7
 for x in sides.values():x['net']=x['gross']-x['fees']-x['impact']+x['funding']
 met={'equity':eq,'return_pct':(eq/initial-1)*100,'cagr_pct':((eq/initial)**(365.25*DAY/(end-start))-1)*100 if eq>0 else -100.,'dd_pct':dd,'adverse_bar_dd_pct':adverse_dd,'sharpe':float(ret.mean()/ret.std(ddof=1)*math.sqrt(365)) if ret.std(ddof=1)>0 else 0.,'realized_vol_pct':float(ret.std(ddof=1)*math.sqrt(365)*100),'annual':{k:float((v-1)*100) for k,v in annual.items()},'quarterly':{k:float((v-1)*100) for k,v in quarter.items()},'fees':fees,'impact':impacts,'funding':funding,'gross':gross,'net':eq-initial,'turnover':turnover,'round_trips':episodes,'fills':sum(e['kind']=='fill' for e in events),'mean_exposure':exposum/n,'max_exposure':maxexpo,'held_bars':held,'margin_breach_bars':breaches,'min_adverse_margin_ratio':min_margin,'sides':sides,'halted':halted,'accounting_residual':initial+gross+funding-fees-impacts-eq}
 return {'strategy':name,'start':start,'end':end,'config':{'cost':cost,'delay':delay,'risk':risk,'base_delay':STEP,'band':.05,'fee':fee,'impact':impact,'step':.001,'minimum':50,'funding_reference':'hourly mark open proxy; raw timestamp retained'},'metrics':met,'daily':daily,'daily_returns':ret.tolist(),'events':events,'skips':skips,'conflict_held_hours':sorted(conflict_held),'conflict_fill_hours':sorted(conflict_fills)}
def bootstrap(a,length):
 a=np.array(a);rng=np.random.default_rng(1490+length);ix=(rng.integers(0,len(a),(2000,math.ceil(len(a)/length),1))+np.arange(length))%len(a);v=a[ix.reshape(2000,-1)[:,:len(a)]].mean(axis=1)*100
 return {'block_days':length,'mean_daily_pct':float(a.mean()*100),'ci95':np.quantile(v,[.025,.975]).tolist(),'replicates':2000}
def run(out):
 out=Path(out);m=Market();summary={};results={};uncertainty={}
 for p,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,conf in SCENARIOS.items():
    risk=conf.get('risk',.2);plan=m.plan(name,start,end,risk);write(out/f'{p}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=simulate(m,name,start,end,plan,**conf);x.update(period=p,scenario=scenario,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()));write(out/f'{p}-{name}-{scenario}.json.gz',x);summary[f'{p}-{name}-{scenario}']=x['metrics'];results[(p,name,scenario)]=x
    if scenario=='base':print(json.dumps({'period':p,'name':name,**{k:x['metrics'][k] for k in ('return_pct','dd_pct','sharpe','fees','funding','round_trips')}}),flush=True)
  for name in IDS:
   a=np.array(results[(p,name,'base')]['daily_returns']);b=np.array(results[(p,'SL00','base')]['daily_returns']);uncertainty[p+'-'+name]={'mean':[bootstrap(a,n) for n in (7,14,28)],'vs_SL00':[bootstrap(a-b,n) for n in (7,14,28)]}
 a=results[('main','SR00','base')]['metrics'];b=results[('recent','SR00','base')]['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['dd_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['dd_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v>0 for v in a['annual'].values())>=3,'trades':a['round_trips']>=100,'margin':a['margin_breach_bars']==b['margin_breach_bars']==0}
 for c in ('base','cost_x2','delay60','delay240'):g[c]=all(results[(p,'SR00',c)]['metrics']['net']>0 for p in PERIODS)
 write(out/'summary.json',summary);write(out/'uncertainty.json',uncertainty);write(out/'selection.json',{'primary':'SR00','passed':all(g.values()),'checks':g,'comparisons_not_eligible':list(IDS[1:]),'scope':'development only; not new OOS'});print(json.dumps(g),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
