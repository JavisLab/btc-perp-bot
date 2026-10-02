"""Independent BTC disjoint two-hour shock and prior-window volatility reconstruction and Decimal/vector cash replay.
Does not import the strategy implementation or its simulator.
"""
import argparse,csv,gzip,io,json,math,zipfile
from pathlib import Path
from decimal import Decimal,ROUND_FLOOR
from collections import defaultdict
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,sha
ROOT=Path(__file__).resolve().parents[1];STEP=300000;D=lambda x:Decimal(str(x))
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def records(p):
 with zipfile.ZipFile(p) as z:
  for row in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
   if row[0].isdigit():yield row

def run(out):
 out=Path(out);resolution=read(ROOT/'data/structure-1471/resolution.json');fine={};hourly={};funds={};marks={}
 # Reconstruct raw execution quotes; only documented 2023 daily repairs take precedence.
 for rec in resolution['files']:
  p=ROOT/'data/structure-1471/raw'/(rec['month']+'.zip');assert sha(p.read_bytes())==rec['sha256']
  for r in records(p):fine[int(r[0])]=[int(r[0]),*map(float,r[1:6]),int(r[6])]
 for rec in resolution['repairs']:
  t=ms(rec['hour'])
  for r in records(ROOT/rec['source']):
   if t<=int(r[0])<t+HOUR:fine[int(r[0])]=[int(r[0]),*map(float,r[1:6]),int(r[6])]
 for kind in ('perp','funding','mark'):
  paths=sorted((ROOT/f'data/archive-1448/{kind}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{kind}').glob('????-??.zip'))
  if kind=='mark':paths+=sorted((ROOT/'data/archive-1448/mark').glob('????-??-??.zip'))+sorted((ROOT/'data/archive-1458/BTCUSDT/mark').glob('????-??-??.zip'))
  for p in paths:
   assert sha(p.read_bytes())==p.with_suffix('.CHECKSUM').read_text().split()[0]
   for r in records(p):
    t=int(r[0])
    if kind=='perp':hourly[t]=(D(r[4]),int(r[6]),D(r[5]))
    elif kind=='funding':funds[t//HOUR*HOUR]=(D(r[2]),t)
    else:marks[t]=D(r[1])
 # Existing audited mark repairs are not re-fetched; every used proxy must tie raw monthly or repaired archive.
 market=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];normalized_marks={r[0]:D(r[1]) for r in market['mark']}
 def close(t):
  r=hourly.get(t-HOUR)
  return float(r[0]) if r and r[1]==t-1 and r[2]>0 else None
 decisions=0;plans={}
 BLOCK=2*HOUR;first=min(hourly)//BLOCK*BLOCK+BLOCK;end=(max(hourly)//BLOCK+1)*BLOCK;times=list(range(first,end+1,BLOCK));ret=[];vols={};good=[]
 for t in times:
  a,b=close(t-BLOCK),close(t);ok=a is not None and b is not None and all((t-j*HOUR) in hourly and hourly[t-j*HOUR][1]==t-j*HOUR+HOUR-1 and hourly[t-j*HOUR][2]>0 for j in (2,1));good.append(ok);ret.append(math.log(b/a) if ok else np.nan);day=t//DAY*DAY
  if day not in vols:
   cl=[close(day-j*DAY) for j in range(20,-1,-1)]
   if any(c is None for c in cl):vols[day]=None
   else:
    r=[math.log(b/a) for a,b in zip(cl,cl[1:])];mu=math.fsum(r)/20;vols[day]=math.sqrt(math.fsum((v-mu)**2 for v in r)/19*365)
 values=np.nan_to_num(ret);sums=np.r_[0.,np.cumsum(values)];squares=np.r_[0.,np.cumsum(values*values)];counts=np.r_[0,np.cumsum(good)];derived={};feature_count=0
 saved=read(out/'features.json.gz');assert len(saved)==len(times)
 for i,(t,e) in enumerate(zip(times,saved)):
  assert e['source']==t and e['price_valid']==good[i];sigma=None
  if i>=360 and counts[i]-counts[i-360]==360:
   total=sums[i]-sums[i-360];ss=squares[i]-squares[i-360];sigma=math.sqrt(max(0,(ss-total*total/360)/359))
  if sigma is None:assert e['sigma'] is None
  else:assert abs(e['sigma']-sigma)<1e-10
  if good[i]:assert abs(e['r']-ret[i])<1e-13
  else:assert e['r'] is None
  day=t//DAY*DAY;vol=vols[day]
  if vol is None:assert e['annual_vol'] is None
  else:assert abs(e['annual_vol']-vol)<1e-10
  assert e['current_start']==t-BLOCK and e['risk_end']==day and e['training_first']==t-360*BLOCK and e['training_last']==t-BLOCK;derived[t]=(ret[i],sigma,vol);feature_count+=1
 for p in sorted(out.glob('*-plan-risk*.json.gz')):
  period,name,_,riskstr=p.name.split('-',3);risk=float(riskstr.removeprefix('risk').removesuffix('.json.gz'));plan=read(p);plans[(period,name,risk)]=plan
  for e in plan:
   r,sigma,vol=derived[e['source']];valid=np.isfinite(r) and sigma is not None and sigma>1e-12 and vol is not None and vol>1e-12;s=0
   if valid:
    J=abs(r)>=3*sigma;sgn=int(r>0)-int(r<0);s={'SH_REV':-sgn*J,'SH_MOM':sgn*J,'SH_ALL':-sgn,'SH_SMALL':-sgn*(1-J)}[name]
   expected=s*min(1,risk/vol) if valid else 0.;assert abs(expected-e['weight'])<1e-10 and s==e['detail']['sign'] and bool(valid)==e['detail']['common_valid'];decisions+=1
 worst=0.;reports=[];maxerr=0.;events_count=daily_count=bars_count=0;target_quantities=no_trade_decisions=0;rawmark_fallback=set()
 def equal(a,b,tol=1e-7):
  nonlocal worst
  delta=float(abs(D(a)-D(b)));worst=max(worst,delta);assert delta<tol,(a,b,delta)
 for path in sorted(out.glob('*.json.gz')):
  if '-plan-' in path.name or path.name=='features.json.gz':continue
  x=read(path);start,end=x['start'],x['end'];conf=x['config'];arr=np.array([fine[t] for t in range(start,end,STEP)]);n=len(arr);bytime=defaultdict(list)
  for e in x['events']:bytime[e['time']].append(e)
  plan=plans[(x['period'],x['strategy'],conf['risk'])];due={};expected_zero=[]
  for j,p in enumerate(plan):
   a=p['source']+STEP+conf['delay'];b=plan[j+1]['source']+STEP+conf['delay'] if j+1<len(plan) else end
   if p['weight'] is None:continue
   for t in range(a,min(b,end),STEP):
    if fine[t][5]>0:due[t]=p;break
    expected_zero.append((t,p['source']))
  assert [(e['time'],e['source']) for e in x['skips'] if e['reason']=='zero_volume_retry']==expected_zero
  last=max(t for t in range(start,end,STEP) if fine[t][5]>0);finaltime=last+STEP
  q=D(0);cash=D(1000);fee_sum=impact_sum=funding_sum=D(0);cash_fund=np.zeros(n);cash_fill=np.zeros(n);dq_fill=np.zeros(n);cash_end=np.zeros(n);dq_end=np.zeros(n);expected_events=[]
  def dofill(new,ref,t,source,reason):
   nonlocal cash,q,fee_sum,impact_sum,target_quantities
   delta=new-q
   if abs(delta)<D('.0001'):return
   impact=D(conf['impact']);fee=D(conf['fee']);px=ref*(1+(impact if delta>0 else -impact));charge=abs(delta)*px*fee;slip=abs(delta)*ref*impact;reducing=q*delta<0 and abs(new)<abs(q) and q*new>=0
   if reason!='period_end' and abs(delta)*px<50 and not reducing:return
   es=[e for e in bytime[t] if e['kind']=='fill' and e['reason']==reason];assert len(es)==1,(path.name,t,reason,len(es));e=es[0];target_quantities+=int(reason=='target');equal(new,e['position']);equal(delta,e['delta']);equal(ref,e['reference']);equal(px,e['price']);equal(charge,e['fee']);equal(slip,e['impact']);assert e['source']==source
   flow=-delta*px-charge;cash+=flow;fee_sum+=charge;impact_sum+=slip;q=new;idx=(t-start)//STEP
   if reason=='period_end':idx-=1;cash_end[idx]+=float(flow);dq_end[idx]+=float(delta)
   else:cash_fill[idx]+=float(flow);dq_fill[idx]+=float(delta)
   expected_events.append(('fill',t,reason))
  times=sorted(set(due)|{t for t in funds if start<=t<end}|{finaltime})
  for t in times:
   if t in funds and t<end and q:
    rate,raw=funds[t];mark=marks.get(t)
    if mark is None:mark=normalized_marks[t];rawmark_fallback.add(t)
    else:assert mark==normalized_marks[t]
    flow=-q*rate*mark;es=[e for e in bytime[t] if e['kind']=='funding'];assert len(es)==1;e=es[0];assert e['raw_time']==raw;equal(q,e['position']);equal(mark,e['reference']);equal(rate,e['rate']);equal(flow,e['cashflow']);cash+=flow;funding_sum+=flow;cash_fund[(t-start)//STEP]+=float(flow);expected_events.append(('funding',t,None))
   if t in due:
    before_fills=len(expected_events);p=due[t];ref=D(fine[t][1]);w=D(p['weight']);eq=cash+q*ref;needs=(q==0 and w!=0) or q*w<0 or(q!=0 and w==0) or abs(w-q*ref/eq)>=D('.05')
    if needs:
     # Independent analytic solution, not the strategy's 12-iteration routine.
     ds=D(1) if w*eq/ref-q>=0 else D(-1);loss_per_unit=ref*(D(conf['impact'])+D(conf['fee'])*(1+ds*D(conf['impact'])));post=(eq+ds*q*loss_per_unit)/(1+ds*w*loss_per_unit/ref);target=w*post/ref;new=((abs(target)+D('1e-12'))/D('.001')).to_integral_value(rounding=ROUND_FLOOR)*D('.001')*(1 if target>=0 else -1);dofill(new,ref,t,p['source'],'target')
    if len(expected_events)==before_fills:no_trade_decisions+=1
   if t==finaltime:dofill(D(0),D(fine[last][4]),t,None,'period_end')
  assert sorted(expected_events)==sorted((e['kind'],e['time'],e.get('reason')) for e in x['events']),(path.name,'unexpected or missing event')
  equal(cash,x['metrics']['equity']);equal(fee_sum,x['metrics']['fees']);equal(impact_sum,x['metrics']['impact']);equal(funding_sum,x['metrics']['funding']);assert q==0
  qpre=np.cumsum(dq_fill+dq_end)-dq_fill-dq_end;cpre=1000+np.cumsum(cash_fund+cash_fill+cash_end)-cash_fill-cash_end;qpost=qpre+dq_fill;cpost=cpre+cash_fill;eqpre=cpre+qpre*arr[:,1];eqpost=cpost+qpost*arr[:,1];eqclose=cpost+qpost*arr[:,4];eqfinal=eqclose+cash_end+dq_end*arr[:,4]
  timeline=np.column_stack((eqpre,eqpost,eqclose,eqfinal)).reshape(-1);peaks=np.maximum.accumulate(np.r_[1000,timeline])[1:];dd=100*np.max(1-timeline/peaks);equal(dd,x['metrics']['dd_pct'],1e-6)
  for d in x['daily']:
   idx=(d['time']-start)//STEP-1;equal(eqfinal[idx],d['equity']);equal(cpost[idx]+cash_end[idx],d['cash']);equal(qpost[idx]+dq_end[idx],d['position']);equal(100*(1-eqfinal[idx]/peaks[4*idx+3]),d['drawdown_pct'],1e-6)
  daily_eq=np.array([d['equity'] for d in x['daily']]);dr=daily_eq/np.r_[1000,daily_eq[:-1]]-1
  assert np.max(np.abs(dr-np.array(x['daily_returns'])))<1e-12
  equal((float(cash)/1000-1)*100,x['metrics']['return_pct']);equal(float(np.std(dr,ddof=1)*math.sqrt(365)*100),x['metrics']['realized_vol_pct'])
  equal(float(np.mean(dr)/np.std(dr,ddof=1)*math.sqrt(365)) if np.std(dr,ddof=1)>0 else 0.,x['metrics']['sharpe'])
  events_count+=len(x['events']);daily_count+=len(x['daily']);bars_count+=n;reports.append({'file':path.name,'events':len(x['events']),'bars':n})
 assert not rawmark_fallback,('Used normalized mark without raw match',sorted(rawmark_fallback))
 result={'accounts':len(reports),'independent_target_quantities':target_quantities,'no_trade_decisions':no_trade_decisions,'independent_shock_features':feature_count,'raw_signal_decisions':decisions,'raw_feature_rows':len(derived),'events':events_count,'daily_equities':daily_count,'five_minute_account_bars':bars_count,'maximum_numeric_error':worst,'raw_mark_fallback':sorted(rawmark_fallback),'scope':'raw BTC 1h/5m/funding/mark; independent analytic sizing and Decimal cash replay; vector 5m/DD/day-end; not execution acceptance'}
 (out/'verification.json').write_bytes(canonical(result));print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
