"""BTC independent HAR/SRV forecasts and raw trend-signal verification and independent Decimal event/account replay."""
import argparse,csv,gzip,io,json,math,zipfile
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def run(out):
 out=Path(out);payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={};rawvolume={}
 for name,key in [('spot','BS'),('perp','BP'),('funding','funding')]:
  for p in sorted((ROOT/f'data/archive-1448/{name}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{name}').glob('????-??.zip')):
   with zipfile.ZipFile(p) as z:
    for rr in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
     if not rr[0].isdigit():continue
     t=int(rr[0]);t=t//1000 if t>10**14 else t
     if key=='funding':funds[t//HOUR*HOUR]=(D(rr[2]),t)
     else:
      rawprice[(key,t)]=(D(rr[1]),D(rr[4]));rawvolume[(key,t)]=D(rr[5])
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
 # The RV source was separately reconstructed from all original BTC ZIP closes.
 rvrows=read(ROOT/'data/btc-rv-20261002/daily-rv.json.gz');audit=read(ROOT/'data/btc-rv-20261002/audit.json');from btc_perp_bot.research.archive import sha
 assert sha(canonical(rvrows))==audit['daily_sha256'];assert read(ROOT/'data/btc-rv-20261002/verification.json')['max_rv_error']<1e-12
 rv=np.array([r['rv'] if r['rv'] is not None else np.nan for r in rvrows]);up=np.array([r['up'] if r['up'] is not None else np.nan for r in rvrows]);dn=np.array([r['down'] if r['down'] is not None else np.nan for r in rvrows]);inputs={k:np.full((len(rvrows),4 if k=='V_HAR' else 5),np.nan) for k in ('V_HAR','V_SRV')}
 for i in range(21,len(rvrows)):
  if not np.all(np.isfinite(rv[i-21:i+1])):continue
  w=math.fsum(rv[i-4:i+1])/5;mth=math.fsum(rv[i-21:i+1])/22;inputs['V_HAR'][i]=[1,rv[i],w,mth];inputs['V_SRV'][i]=[1,up[i],dn[i],w,mth]
 predictions={};forecast_models=0;preds=read(out/'predictions.json.gz')
 for i,e in enumerate(preds):
  t=e['source'];predictions[t]={}
  for name in ('V_HAR','V_SRV','V_RV20'):
   got=e['models'][name]
   if name=='V_RV20':pred=math.fsum(rv[i-19:i+1])/20 if i>=19 and np.all(np.isfinite(rv[i-19:i+1])) else None
   else:
    ix=[j for j in range(max(0,i-365),i) if np.isfinite(rv[j+1]) and np.all(np.isfinite(inputs[name][j]))]
    if len(ix)<300 or not np.all(np.isfinite(inputs[name][i])):assert got['prediction'] is None;predictions[t][name]=None;continue
    x=inputs[name][ix,1:];y=rv[np.array(ix)+1];xm=x.mean(axis=0);ym=y.mean();sd=x.std(axis=0);sd[sd<1e-12]=1.;xx=(x-xm)/sd;coef=np.linalg.solve(xx.T@xx,xx.T@(y-ym))/sd;intercept=ym-xm@coef;raw=float(intercept+inputs[name][i,1:]@coef);pred=max(raw,1e-8);assert abs(raw-got['unclipped'])<1e-10;assert got['training_label_end']<=t;assert len(ix)==got['training_n'];forecast_models+=1
   if pred is None:assert got['prediction'] is None
   else:assert abs(pred-got['prediction'])<1e-10
   predictions[t][name]=pred
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk_target=float(p.name.split('-risk')[1].removesuffix('.json.gz'));state=0
  for e in plan:
   t=e['source_time'];i=dayidx[t];history=daily[i-20:i+1]
   score=(sum(np.sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(np.sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6
   if not math.isfinite(score) or not np.all(np.isfinite(history)):assert e['weights'] is None;continue
   vol=float(np.diff(np.log(history)).std(ddof=1)*math.sqrt(365));weight=min(1.,risk_target/vol) if vol>1e-12 else 0.
   pred=predictions[t][name]
   if pred is None:assert e['weights'] is None;continue
   vol=math.sqrt(365*pred);weight=min(1,risk_target/vol);signal=max(score,0)
   assert abs(e['detail']['score']-score)<1e-12 and e['detail']['signal']==signal
   assert abs(e['detail']['forecast']-pred)<1e-10
   for k,v in [('BS',signal*weight),('BP',0.)]:assert abs(e['weights'][k]-v)<1e-8,(p.name,t,k)
   raw_signals[(name,risk_target,t)]=e;plans_checked+=1
 reports=[];worst=0.;diag={};quantities_checked=0;no_trade_decisions=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name=='predictions.json.gz':continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS}
  for e in x['events']:bytime[e['time']].append(e)
  planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}.json.gz")}
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
    assert rawvolume[(k,t)]>0
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
   pe=planned.get(t)
   if pe is not None and pe['weights'] is not None:
    w=D(pe['weights']['BS']);oldq=q['BS'];E=value(op);P=D(op['BS']);fills=[e for e in events if e['kind']=='fill'];target=oldq
    needed=(oldq==0 and w!=0) or(oldq!=0 and w==0) or abs(w-oldq*P/E)>=D('.05')
    if needed and ('BS',t) in rawprice:
     sign=D(1) if w*E/P>=oldq else D(-1);slip=D(model['impact_bps'])/10000;fee=D(model['fee_bps']['BS'])/10000;k=P*(slip+(1+sign*slip)*fee)
     # Closed-form single-spot post-cost target, independent of the engine's 12 iterations.
     desired=w*(E+sign*k*oldq)/(P+w*sign*k);step=D('.00001');rounded=((desired+D('1e-12'))//step)*step;delta=rounded-oldq
     if abs(delta)>=step/10 and abs(delta)*P*(1+(slip if delta>0 else -slip))>=5:target=rounded
    if target==oldq:assert not fills,(p.name,t,'unexpected fill');no_trade_decisions+=1
    else:assert len(fills)==1 and fills[0]['instrument']=='BS';equal(target,fills[0]['position']);quantities_checked+=1
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
 result={'accounts':len(reports),'independent_forecast_models':forecast_models,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities_checked,'no_trade_decisions':no_trade_decisions,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'raw BTC spot EMA/signals, raw BTC spot fills and positive trade volume, closed-form post-cost quantities/no-trade rules, independent Decimal cash inventory; hourly/daily equity/DD; no actual execution proof'}
 (out/'verification.json').write_bytes(canonical(result));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
