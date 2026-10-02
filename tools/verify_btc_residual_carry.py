"""Independent BTC mining-source, EMA/momentum, and account verification and analytic/Decimal target-account replay."""
import argparse,hashlib,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def run(out):
 out=Path(out);payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={};rawvolume={};rawmarks={};archive_count=0
 for name,key in [('spot','BS'),('perp','BP'),('funding','funding'),('mark','mark')]:
  paths=sorted((ROOT/f'data/archive-1448/{name}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{name}').glob('????-??.zip'))
  if name=='mark':paths+=sorted((ROOT/f'data/archive-1448/{name}').glob('????-??-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{name}').glob('????-??-??.zip'))
  for p in paths:
   assert sha(p.read_bytes())==p.with_suffix('.CHECKSUM').read_text().split()[0];archive_count+=1
   with zipfile.ZipFile(p) as z:
    for rr in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
     if not rr[0].isdigit():continue
     t=int(rr[0]);t=t//1000 if t>10**14 else t
     if key=='funding':funds[t//HOUR*HOUR]=(D(rr[2]),t)
     elif key=='mark':rawmarks[t]=tuple(D(rr[j]) for j in (1,2,3,4))
     else:
      rawprice[(key,t)]=(D(rr[1]),D(rr[4]));rawvolume[(key,t)]=D(rr[5])
      if key=='BS' and t%DAY==23*HOUR and t>=ms('2020-02-01'):spot[t+HOUR]=float(rr[4])
 assert all(rawvolume[('BS',t-HOUR)]>0 for t in spot)
 for t,r in marks['BP'].items():assert tuple(D(r[j]) for j in (1,2,3,4))==rawmarks[t]
 for t,r in marks['BS'].items():assert (D(r[1]),D(r[4]))==rawprice[('BS',t)]
 days=list(range(ms('2020-02-02'),max(spot)+1,DAY));daily=np.array([spot.get(t,np.nan) for t in days]);dayidx={t:i for i,t in enumerate(days)}
 em={}
 for span in (8,16,32,64,128):
  acc=None;a=2/(span+1);track=[]
  for c in daily:
   if not math.isfinite(c):acc=None;track.append(float('nan'));continue
   acc=c if acc is None else a*c+(1-a)*acc;track.append(acc)
  em[span]=track
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk=float(p.name.split('-risk')[1].removesuffix('.json.gz'))
  for e in plan:
   t=e['source_time'];i=dayidx[t];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   ret=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(ret)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in ret)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6;core=max(0,score)*w if name!='RC_CARRY' else 0.;allocation=.8 if name!='RC_TREND' else 0.
   assert abs(e['core_weight']-core)<1e-9 and e['carry_allocation']==allocation and e['detail']['score']==score and abs(e['detail']['vol']-vol)<1e-9
   raw_signals[name,risk,t]=e;plans_checked+=1
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0;budget_checks=0;matched_targets=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith('features'):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  core_episodes=0;margin_min=None;breaches=0;gross_exposure_sum=D(0);core_exposure_sum=D(0);max_exposure=D(0);max_core=D(0)
  for e in x['events']:bytime[e['time']].append(e)
  def equal(a,b):
   nonlocal worst
   delta=float(abs(D(a)-D(b)));worst=max(worst,delta);assert delta<1e-7,(p.name,a,b)
  def value(prices):return cash+sum(q[k]*D(prices[k]) for k in KEYS)
  def observe(prices):
   nonlocal peak,dd,max_exposure
   eq=value(prices);peak=max(peak,eq);dd=max(dd,(1-eq/peak)*100);max_exposure=max(max_exposure,sum(abs(q[k])*D(prices[k]) for k in KEYS)/eq);return eq
  def fill(e):
   nonlocal cash,fee_sum,impact_sum
   k=e['instrument'];t=e['time'];dq=D(e['delta']);ref=rawprice[(k,end-HOUR)][1] if t==end else rawprice[(k,t)][0];slip=D(model['impact_bps'])/10000;px=ref*(1+(slip if dq>0 else -slip));charge=abs(dq)*px*D(model['fee_bps'][k])/10000;loss=abs(dq)*ref*slip
   equal(ref,e['reference']);equal(px,e['price']);equal(charge,e['fee']);equal(loss,e['impact']);assert rawvolume[(k,end-HOUR if t==end else t)]>0
   if t<end:
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['risk_target'],e['source_time']) in raw_signals
    step=D('.00001' if k=='BS' else '.001');equal(D(e['position'])/step,round(float(D(e['position'])/step)));reducing=q[k]*dq<0 and abs(D(e['position']))<abs(q[k]);assert abs(dq)*px>=D(5 if k=='BS' else 50)-D('1e-7') or(k=='BP' and reducing)
   q[k]+=dq;cash-=dq*px+charge;fee_sum+=charge;impact_sum+=loss;sides[k]['gross']-=dq*ref;sides[k]['fees']+=charge;sides[k]['impact']+=loss;equal(q[k],e['position'])
   if abs(q[k])<D('1e-12'):q[k]=D(0)
   assert q['BS']>=0 and q['BP']<=0
  for t in range(start,end,HOUR):
   op={};cl={}
   for k in KEYS:
    r=rawprice.get((k,t)) if k=='BS' else(rawmarks[t][0],rawmarks[t][3])
    if r is None:op[k]=cl[k]=latest[k]
    else:op[k],cl[k]=r;latest[k]=r[1]
   events=bytime.get(t,[]);fe=[e for e in events if e['kind']=='funding'];assert len(fe)==int(bool(q['BP']) and t in funds)
   for e in fe:
    rate,raw=funds[t];unadjusted=-q['BP']*op['BP']*rate;credit=D(model['funding_credit_factor']) if unadjusted>0 else D(1);flow=unadjusted*credit;equal(unadjusted,e['unadjusted_cashflow']);equal(credit,e['credit_factor']);equal(flow,e['cashflow']);equal(q['BP'],e['position']);equal(op['BP'],e['reference']);assert rate==D(e['rate']) and raw==e['observed_time'];cash+=flow;fund_sum+=flow;sides['BP']['funding']+=flow;raw_funding_events+=1
   observe(op);before_core=q['BS']+q['BP'];pe=planned.get(t);fills=[e for e in events if e['kind']=='fill'];expected=dict(q)
   if pe is not None and pe['weights'] is not None:
    core=D(pe['core_weight']);allocation=D(pe['carry_allocation']);h=allocation*(1-core)*op['BS']/(op['BS']+op['BP']);w={'BS':core+h,'BP':-h*op['BP']/op['BS']};assert abs(sum(abs(v) for v in w.values())-(core+allocation*(1-core)))<D('1e-20') and sum(abs(v) for v in w.values())<=1+D('1e-20');budget_checks+=1;E=value(op);relevant=[k for k in KEYS if q[k] or w[k]];needed=any((q[k]==0 and w[k]!=0) or q[k]*w[k]<0 or(q[k]!=0 and w[k]==0) or abs(w[k]-q[k]*op[k]/E)>=D('.05') for k in KEYS)
    if needed and all((k,t) in rawprice for k in relevant):
     solutions=[];slip=D(model['impact_bps'])/10000
     for signs in itertools.product((-1,1),repeat=len(relevant)):
      coeff={k:w[k]/op[k] for k in relevant};A={k:op[k]-rawprice[(k,t)][0]*(1+D(s)*slip)*(1+D(s)*D(model['fee_bps'][k])/10000) for k,s in zip(relevant,signs)};post=(E-sum(A[k]*q[k] for k in relevant))/(1-sum(A[k]*coeff[k] for k in relevant));desired={k:coeff[k]*post for k in relevant}
      if all(D(s)*(desired[k]-q[k])>=D('-1e-20') for k,s in zip(relevant,signs)):solutions.append((desired,post))
     assert solutions,(p.name,t,'no analytic target');desired,post=solutions[0]
     coreq=((core*post/op['BS']+D('1e-12'))/D('.00001')).to_integral_value(rounding=ROUND_FLOOR)*D('.00001');hedgeq=((h*post/op['BS']+D('1e-12'))/D('.001')).to_integral_value(rounding=ROUND_FLOOR)*D('.001');new={'BS':coreq+hedgeq,'BP':-hedgeq};assert new['BS']+new['BP']==coreq;matched_targets+=1
     invalid=[]
     for k in relevant:
      dq=new[k]-q[k];step=D('.00001' if k=='BS' else '.001')
      if abs(dq)<step/10:continue
      px=rawprice[(k,t)][0]*(1+(slip if dq>0 else -slip));reducing=q[k]*dq<0 and abs(new[k])<abs(q[k])
      if abs(dq)*px<D(5 if k=='BS' else 50) and(k=='BS' or not reducing):invalid.append(k)
     if not invalid:expected=new
    changes=[k for k in KEYS if abs(expected[k]-q[k])>=D('.000001' if k=='BS' else '.0001')];assert len(fills)==len(changes),(p.name,t,'fill count',changes,len(fills))
    for k in changes:
     found=[e for e in fills if e['instrument']==k];assert len(found)==1;equal(expected[k],found[0]['position']);quantities+=1
    if not changes:no_trade+=1
   else:assert not fills
   for e in fills:fill(e)
   after_core=q['BS']+q['BP'];assert after_core>=D('-1e-10')
   if before_core>D('1e-10') and after_core<=D('1e-10'):core_episodes+=1
   observe(op);eq=observe(cl);gross_exposure_sum+=sum(abs(q[k])*cl[k] for k in KEYS)/eq;core_exp=max(D(0),after_core)*cl['BS']/eq;core_exposure_sum+=core_exp;max_core=max(max_core,core_exp)
   if q['BP']:
    high=rawmarks[t][1];ratio=(cash+q['BP']*high)/(-q['BP']*high);margin_min=ratio if margin_min is None else min(margin_min,ratio);breaches+=int(ratio<D('.05'))
   if not q['BP']:assert cash>=D('-1e-7')
   if t+HOUR in daily_map:
    d=daily_map[t+HOUR]
    if t+HOUR==end:
     if q['BS']+q['BP']>D('1e-10'):core_episodes+=1
     for e in bytime[end]:fill(e)
     eq=observe({k:rawprice[(k,end-HOUR)][1] for k in KEYS})
    equal(eq,d['equity']);equal(cash,d['cash']);equal(fee_sum,d['fees']);equal(impact_sum,d['impact']);equal(fund_sum,d['funding']);equal((1-eq/peak)*100,d['drawdown_pct'])
    for k in KEYS:equal(q[k],d['positions'][k])
  assert core_episodes==x['metrics']['core_round_trips'] and breaches==x['metrics']['margin_buffer_breach_hours'];equal(gross_exposure_sum/D((end-start)//HOUR),x['metrics']['mean_exposure']);equal(core_exposure_sum/D((end-start)//HOUR),x['metrics']['mean_core_exposure']);equal(max_exposure,x['metrics']['max_exposure']);equal(max_core,x['metrics']['max_core_exposure'])
  if margin_min is not None:equal(margin_min,x['metrics']['min_adverse_margin_ratio'])
  else:assert x['metrics']['min_adverse_margin_ratio'] is None
  equal(cash,x['metrics']['equity']);equal(dd,x['metrics']['max_drawdown_pct']);side={k:{**{a:float(v) for a,v in z.items()},'net':float(z['gross']-z['fees']-z['impact']+z['funding'])} for k,z in sides.items()};equal(sum(z['net'] for z in side.values()),x['metrics']['net_pnl']);diag[p.name]={'sides':side,'skips':x['skips']};reports.append({'file':p.name,'events':len(x['events']),'daily':len(x['daily'])})
 proof={'accounts':len(reports),'raw_archives':archive_count,'raw_daily_decisions':plans_checked,'capital_budget_checks':budget_checks,'matched_core_hedge_targets':matched_targets,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'independent raw BTC daily EMA/momentum/volatility; exact capital fractions, closed-form post-cost capital, separately rounded core and matched hedge BTC; minimum/band no-trades; Decimal cash/actual funding with positive-credit haircut; separated margin at raw adverse mark high; core-only episodes and gross/net exposure; complete hourly drawdown'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
