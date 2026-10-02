"""BTC raw regime/daily-signal verification and independent Decimal event/account replay."""
import argparse,csv,gzip,io,json,math,zipfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def run(out):
 out=Path(out);payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={}
 for name,key in [('spot','BS'),('perp','BP'),('funding','funding')]:
  for p in sorted((ROOT/f'data/archive-1448/{name}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{name}').glob('????-??.zip')):
   with zipfile.ZipFile(p) as z:
    for rr in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
     if not rr[0].isdigit():continue
     t=int(rr[0]);t=t//1000 if t>10**14 else t
     if key=='funding':funds[t//HOUR*HOUR]=(D(rr[2]),t)
     else:
      rawprice[(key,t)]=(D(rr[1]),D(rr[4]))
      if key=='BS' and t%DAY==23*HOUR and t>=ms('2020-02-01'):spot[t+HOUR]=float(rr[4])
 days=list(range(ms('2020-02-02'),max(spot)+1,DAY));daily=np.array([spot.get(t,np.nan) for t in days]);dayidx={t:i for i,t in enumerate(days)}
 em={};
 for n in (8,16,32,64,128):
  a=[];prev=float('nan')
  for v in daily:
   if not math.isfinite(v):prev=float('nan')
   elif math.isnan(prev):prev=v
   else:prev=(v*2+prev*(n-1))/(n+1)
   a.append(prev)
  em[n]=a
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk_target=float(p.name.split('-risk')[1].removesuffix('.json.gz'));state=0
  for e in plan:
   t=e['source_time'];i=dayidx[t];history=daily[i-20:i+1]
   score=(sum(np.sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(np.sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6
   if not math.isfinite(score) or not np.all(np.isfinite(history)):assert e['weights'] is None;continue
   vol=float(np.diff(np.log(history)).std(ddof=1)*math.sqrt(365));weight=min(1.,risk_target/vol) if vol>1e-12 else 0.
   if name=='E_MIX':signal=score
   elif name=='B_MIX':signal=float(np.sign(score))
   elif name=='E_STRICT':signal=score if score>0 or score==-1 else 0.
   elif name.startswith('RG_'):
    h=daily[i-19:i+1];delta=h[-1]-h[0];length=math.fsum(abs(b-a) for a,b in zip(h,h[1:]));er=abs(delta)/length if length else 0.;down=er>=.3 and delta<0
    if score>=0:state=0
    elif down:state=1
    signal=score if score>0 or(score<0 and (down if name=='RG_FLAT' else bool(state))) else 0.
    assert abs(e['detail']['er']-er)<1e-10 and e['detail']['efficient_down']==down
   else:
    if (state>0 and score<=0) or(state<0 and score>=0):state=0
    if state==0:
     if score>=2/3:state=1
     elif score<=(-1 if name=='H_STRICT' else -2/3):state=-1
    signal=state
   assert abs(e['detail']['score']-score)<1e-12 and e['detail']['signal']==signal
   for k,v in [('BS',max(signal,0)*weight),('BP',min(signal,0)*weight)]:assert abs(e['weights'][k]-v)<1e-10,(p.name,t,k)
   raw_signals[(name,risk_target,t)]=e;plans_checked+=1
 reports=[];worst=0.;diag={}
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name:continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS}
  for e in x['events']:bytime[e['time']].append(e)
  def equal(a,b):
   nonlocal worst
   delta=float(abs(D(a)-D(b)));worst=max(worst,delta);assert delta<1e-7,(p.name,a,b)
  def value(prices):return cash+sum(q[k]*D(prices[k]) for k in KEYS)
  def observe(prices):
   nonlocal peak,dd
   eq=value(prices);peak=max(peak,eq);dd=max(dd,(1-eq/peak)*100);return eq
  def fill(e):
   nonlocal cash,fee_sum,impact_sum
   k=e['instrument'];t=e['time'];dq=D(e['delta']);ref=rawprice[(k,end-HOUR)][1] if t==end else rawprice[(k,t)][0];impact=D(model['impact_bps'])/10000
   price=ref*(1+(impact if dq>0 else -impact));charge=abs(dq)*price*D(model['fee_bps'][k])/10000;slip=abs(dq)*ref*impact
   equal(ref,e['reference']);equal(price,e['price']);equal(charge,e['fee']);equal(slip,e['impact'])
   if t<end:
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours'])
    assert (x['strategy'],x['risk_target'],e['source_time']) in raw_signals
    step=D('.00001' if k=='BS' else '.001');equal(D(e['position'])/step,round(float(D(e['position'])/step)))
    reducing=q[k]*dq<0 and abs(D(e['position']))<abs(q[k]);assert abs(dq)*price>=D(5 if k=='BS' else 50)-D('1e-7') or(k=='BP' and reducing)
   q[k]+=dq;cash-=dq*price+charge;fee_sum+=charge;impact_sum+=slip;sides[k]['gross']-=dq*ref;sides[k]['fees']+=charge;sides[k]['impact']+=slip;equal(q[k],e['position'])
   if abs(q[k])<D('1e-12'):q[k]=D(0)
   assert q['BS']>=0 and q['BP']<=0 and not(q['BS'] and q['BP'])
  for t in range(start,end,HOUR):
   op={};cl={}
   for k in KEYS:
    r=marks[k].get(t)
    if r is None:assert k=='BS';op[k]=cl[k]=latest[k]
    else:op[k]=r[1];cl[k]=r[4];latest[k]=r[4]
   events=bytime.get(t,[]);fe=[e for e in events if e['kind']=='funding'];assert len(fe)==int(bool(q['BP']) and t in funds)
   for e in fe:
    rate,raw=funds[t];flow=-q['BP']*D(op['BP'])*rate;equal(flow,e['cashflow']);equal(q['BP'],e['position']);assert rate==D(e['rate']) and raw==e['observed_time'];cash+=flow;fund_sum+=flow;sides['BP']['funding']+=flow
   observe(op)
   for e in events:
    if e['kind']=='fill':fill(e)
   observe(op);eq=observe(cl)
   if not q['BP']:assert cash>=D('-1e-7')
   if t+HOUR in daily_map:
    d=daily_map[t+HOUR]
    if t+HOUR==end:
     for e in bytime[end]:fill(e)
     eq=observe({k:rawprice[(k,end-HOUR)][1] for k in KEYS})
    equal(eq,d['equity']);equal(cash,d['cash']);equal(fee_sum,d['fees']);equal(impact_sum,d['impact']);equal(fund_sum,d['funding']);equal((1-eq/peak)*100,d['drawdown_pct'])
    for k in KEYS:equal(q[k],d['positions'][k])
  equal(cash,x['metrics']['equity']);equal(dd,x['metrics']['max_drawdown_pct'])
  byside={k:{**{a:float(v) for a,v in val.items()},'net':float(val['gross']-val['fees']-val['impact']+val['funding'])} for k,val in sides.items()};equal(sum(v['net'] for v in byside.values()),x['metrics']['net_pnl'])
  diag[p.name]={'sides':byside,'skips':x['skips']};reports.append({'file':p.name,'events':len(x['events']),'daily':len(x['daily'])})
 result={'accounts':len(reports),'raw_daily_decisions':plans_checked,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'raw BTC spot EMA/signals, raw BTC spot/perp fills and funding, independent Decimal cash inventory; hourly/daily equity/DD; no actual execution proof'}
 (out/'verification.json').write_bytes(canonical(result));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
