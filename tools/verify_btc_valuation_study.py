"""Independent raw BTC incremental-option normal equations/clocks/signals and analytic/Decimal target-account replay."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def audit_valuation():
 from decimal import localcontext
 p=ROOT/'data/btc-valuation-20261002';raw=(p/'coinmetrics.json').read_bytes();assert sha(raw)=='db696818880b69e8320e192c60eb5429a40db0ecf5845ece194a01b0524d4a61';js=json.loads(raw);assert not js.get('next_page_url');data={};cross=0
 csvfile=ROOT/'data/btc-mining-20261002/btc-community.csv';assert sha(csvfile.read_bytes())=='06495ff8e643432e6948b7b4686ce44fc106217287dabdc1b38351d9ddec46c3';prior={e['time']:e for e in csv.DictReader(csvfile.open())}
 for e in js['data']:
  day=e['time'][:10];t=ms(day);assert e['asset']=='btc' and t not in data
  values=[D(e[k]) for k in ('PriceUSD','SplyCur','CapMrktCurUSD','CapMVRVCur')];assert all(v.is_finite() and v>0 for v in values)
  with localcontext() as c:c.prec=60;assert values[0]*values[1]==values[2];realized=values[2]/values[3];assert realized>0
  if day in prior and prior[day]['CapMVRVCur']:assert D(prior[day]['CapMVRVCur'])==values[3];cross+=1
  data[t]=float(values[3])
 assert len(data)==2435 and sorted(data)==list(range(ms('2020-01-01'),ms('2026-09-01'),DAY)) and cross==2335
 return data,{'days':len(data),'raw_sha256':sha(raw),'decimal_market_cap_identity':'exact','cross_snapshot_mvrv_exact':cross,'full_utxo_realized_cap_reconstruction':False,'first_release_vintages_proven':False}

def independent_predictions(data,spot,lag):
 rows=[]
 for t in range(ms('2020-01-06'),ms('2026-09-01'),7*DAY):
  d=t-lag*DAY;b=d+DAY;values=[spot.get(b-j*DAY) for j in range(200)];v=data.get(d);valid=v is not None and v>0 and all(z is not None and z>0 and math.isfinite(z) for z in values)
  e={'source':t,'observation':d,'price_end':b,'expiry':t+7*DAY,'truth_end':t+7*DAY,'truth':None,'valid':valid,'models':{}};a,z=spot.get(t),spot.get(t+7*DAY)
  if a is not None and z is not None:e['truth']=math.log(z/a)
  if valid:e['x']=[math.log(values[0]/values[7]),math.log(values[0]*200/math.fsum(values)),math.log(v)]
  rows.append(e)
 for i,e in enumerate(rows):
  keep=[j for j in range(max(0,i-104),i) if rows[j]['valid'] and rows[j]['truth'] is not None and rows[j]['truth_end']<=e['source']-7*DAY]
  for name,cols in [('VA_INC',(0,1,2)),('VA_PRICE',(0,1)),('VA_VALUE',(2,))]:
   k=len(cols)+1;p={'mu':None,'se':None,'training_n':len(keep)};e['models'][name]=p
   if not e['valid'] or len(keep)<78:continue
   X=np.array([[1.]+[rows[j]['x'][c] for c in cols] for j in keep]);y=np.array([rows[j]['truth'] for j in keep]);scale=np.sqrt(np.mean(X*X,axis=0));scale[scale<1e-12]=1.;Z=X/scale
   if np.linalg.matrix_rank(Z)<k:continue
   gram=Z.T@Z;coef=np.linalg.solve(gram,Z.T@y);cur=np.array([1.]+[e['x'][c] for c in cols])/scale;mu=float(cur@coef);res=y-Z@coef;s2=math.fsum(v*v for v in res)/(len(y)-k);se=math.sqrt(max(0.,s2*float(cur@np.linalg.solve(gram,cur))))
   p.update(mu=mu,se=se,beta=(coef/scale).tolist(),training_indices=keep,training_label_end=max(rows[j]['truth_end'] for j in keep))
 return rows

def run(out):
 out=Path(out);data,data_proof=audit_valuation();payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={};rawvolume={};rawmarks={};archive_count=0
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
      if key=='BS' and t%DAY==23*HOUR and t>=ms('2020-01-01'):spot[t+HOUR]=float(rr[4])
 assert all(rawvolume[('BS',t-HOUR)]>0 for t in spot), 'nonpositive raw daily-boundary spot volume'
 for t,r in marks['BP'].items():assert tuple(D(r[j]) for j in (1,2,3,4))==rawmarks[t]
 for t,r in marks['BS'].items():assert (D(r[1]),D(r[4]))==rawprice[('BS',t)]
 days=list(range(ms('2020-02-02'),max(spot)+1,DAY));daily=np.array([spot.get(t,np.nan) for t in days]);dayidx={t:i for i,t in enumerate(days)}
 predictions={};predictions_checked=0;prediction_error=0.;feature_checks=0
 for variant,lag in [('base',2),('source_delay7',9)]:
  rr=independent_predictions(data,spot,lag);predictions[variant]=rr;recorded=read(out/f'features-{variant}.json.gz');assert len(recorded)==len(rr)
  for e,z in zip(recorded,rr):
   for k in ('source','observation','price_end','expiry','valid','truth_end','truth'):assert e[k]==z[k],(variant,k,e['source'])
   assert e['observation']+lag*DAY==e['source'] and e['price_end']<=e['source']-DAY
   if z['valid']:
    for k,v in zip(('r7','p200','v'),z['x']):assert abs(e[k]-v)<1e-12
    feature_checks+=1
   for name,p in z['models'].items():
    a=e['models'][name];assert a['training_n']==p['training_n']
    if p['mu'] is None:assert a['mu'] is None;continue
    assert a['training_indices']==p['training_indices'] and a['training_label_end']==p['training_label_end']<=e['source']-7*DAY
    for k in ('mu','se'):
     error=abs(a[k]-p[k]);prediction_error=max(prediction_error,error);assert error<1e-9,(variant,name,k,e['source'],error)
    assert np.allclose(a['beta'],p['beta'],atol=1e-8,rtol=1e-8);predictions_checked+=1
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];variant=p.name.split('-plan-')[1].split('-risk')[0];risk=float(p.name.split('-risk')[1].removesuffix('.json.gz'))
  for e in plan:
   t=e['source_time'];i=dayidx[t];hist=daily[i-20:i+1]
   if not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;known=[r for r in predictions[variant] if r['source']<=t];last=max(known,key=lambda r:r['source']) if known else None;valid=last is not None and last['valid'] and t<last['expiry'];s=0
   if valid:
    pred=last['models']['VA_INC' if name=='VA_INV' else name]
    if pred['mu'] is not None:s=(1 if pred['mu']>math.log1p(.0023)+pred['se'] else -1 if pred['mu']<-math.log1p(.0013)-pred['se'] else 0)*(-1 if name=='VA_INV' else 1)
   assert e['detail']['signal']==s and e['detail']['common_valid']==valid
   if last:assert e['detail']['observed_day']==last['observation'] and e['detail']['information_time']==last['source'] and e['detail']['age_days']==(t-last['observation'])//DAY
   else:assert e['detail']['observed_day'] is None
   for k,v in [('BS',max(s,0)*w),('BP',min(s,0)*w)]:assert abs(e['weights'][k]-v)<1e-9
   raw_signals[(name,variant,risk,t)]=e;plans_checked+=1
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith('features-'):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-{x['input_variant']}-risk{x['risk_target']:.2f}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
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
   k=e['instrument'];t=e['time'];dq=D(e['delta']);ref=rawprice[(k,end-HOUR)][1] if t==end else rawprice[(k,t)][0];slip=D(model['impact_bps'])/10000;px=ref*(1+(slip if dq>0 else -slip));charge=abs(dq)*px*D(model['fee_bps'][k])/10000;loss=abs(dq)*ref*slip
   equal(ref,e['reference']);equal(px,e['price']);equal(charge,e['fee']);equal(loss,e['impact']);assert rawvolume[(k,end-HOUR if t==end else t)]>0
   if t<end:
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['input_variant'],x['risk_target'],e['source_time']) in raw_signals
    step=D('.00001' if k=='BS' else '.001');equal(D(e['position'])/step,round(float(D(e['position'])/step)));reducing=q[k]*dq<0 and abs(D(e['position']))<abs(q[k]);assert abs(dq)*px>=D(5 if k=='BS' else 50)-D('1e-7') or(k=='BP' and reducing)
   q[k]+=dq;cash-=dq*px+charge;fee_sum+=charge;impact_sum+=loss;sides[k]['gross']-=dq*ref;sides[k]['fees']+=charge;sides[k]['impact']+=loss;equal(q[k],e['position'])
   if abs(q[k])<D('1e-12'):q[k]=D(0)
   assert q['BS']>=0 and q['BP']<=0 and not(q['BS'] and q['BP'])
  for t in range(start,end,HOUR):
   op={};cl={}
   for k in KEYS:
    r=rawprice.get((k,t)) if k=='BS' else(rawmarks[t][0],rawmarks[t][3])
    if r is None:op[k]=cl[k]=latest[k]
    else:op[k],cl[k]=r;latest[k]=r[1]
   events=bytime.get(t,[]);fe=[e for e in events if e['kind']=='funding'];assert len(fe)==int(bool(q['BP']) and t in funds)
   for e in fe:
    rate,raw=funds[t];flow=-q['BP']*op['BP']*rate;equal(flow,e['cashflow']);equal(q['BP'],e['position']);equal(op['BP'],e['reference']);assert rate==D(e['rate']) and raw==e['observed_time'];cash+=flow;fund_sum+=flow;sides['BP']['funding']+=flow;raw_funding_events+=1
   observe(op);pe=planned.get(t);fills=[e for e in events if e['kind']=='fill'];expected=dict(q)
   if pe is not None and pe['weights'] is not None:
    w={k:D(pe['weights'][k]) for k in KEYS};E=value(op);relevant=[k for k in KEYS if q[k] or w[k]];needed=any((q[k]==0 and w[k]!=0) or q[k]*w[k]<0 or(q[k]!=0 and w[k]==0) or abs(w[k]-q[k]*op[k]/E)>=D('.05') for k in KEYS)
    if needed and all((k,t) in rawprice for k in relevant):
     solutions=[];slip=D(model['impact_bps'])/10000
     for signs in itertools.product((-1,1),repeat=len(relevant)):
      coeff={k:w[k]/op[k] for k in relevant};A={k:op[k]-rawprice[(k,t)][0]*(1+D(s)*slip)*(1+D(s)*D(model['fee_bps'][k])/10000) for k,s in zip(relevant,signs)};post=(E-sum(A[k]*q[k] for k in relevant))/(1-sum(A[k]*coeff[k] for k in relevant));desired={k:coeff[k]*post for k in relevant}
      if all(D(s)*(desired[k]-q[k])>=D('-1e-20') for k,s in zip(relevant,signs)):solutions.append(desired)
     assert solutions,(p.name,t,'no analytic target');desired=solutions[0];new={k:D(0) for k in KEYS}
     for k,v in desired.items():
      step=D('.00001' if k=='BS' else '.001');new[k]=((abs(v)+D('1e-12'))/step).to_integral_value(rounding=ROUND_FLOOR)*step*(1 if v>=0 else -1)
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
   observe(op);eq=observe(cl)
   if not q['BP']:assert cash>=D('-1e-7')
   if t+HOUR in daily_map:
    d=daily_map[t+HOUR]
    if t+HOUR==end:
     for e in bytime[end]:fill(e)
     eq=observe({k:rawprice[(k,end-HOUR)][1] for k in KEYS})
    equal(eq,d['equity']);equal(cash,d['cash']);equal(fee_sum,d['fees']);equal(impact_sum,d['impact']);equal(fund_sum,d['funding']);equal((1-eq/peak)*100,d['drawdown_pct'])
    for k in KEYS:equal(q[k],d['positions'][k])
  equal(cash,x['metrics']['equity']);equal(dd,x['metrics']['max_drawdown_pct']);side={k:{**{a:float(v) for a,v in z.items()},'net':float(z['gross']-z['fees']-z['impact']+z['funding'])} for k,z in sides.items()};equal(sum(z['net'] for z in side.values()),x['metrics']['net_pnl']);diag[p.name]={'sides':side,'skips':x['skips']};reports.append({'file':p.name,'events':len(x['events']),'daily':len(x['daily'])})
 proof={'accounts':len(reports),'independent_predictions':predictions_checked,'max_prediction_error':prediction_error,'raw_feature_windows':feature_checks,'data':data_proof,'raw_archives':archive_count,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'independent CM raw MVRV/Decimal capitalization and prior-snapshot ratios; separate raw BTC daily close, 200d mean, weekly returns, 2/9d clocks and extra-week label purge; uncentered normal-equation mean/SE versus centered SVD; raw daily risk; piecewise closed-form post-cost targets/no-trade; raw positive-volume fills, mark and actual funding; Decimal cash/hourlyDD; full UTXO chain/vendor first vintages NOT reconstructed'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path);p.add_argument('--data-only',action='store_true');a=p.parse_args()
 if a.data_only:
  _,proof=audit_valuation();print(json.dumps(proof))
 else:run(a.out)
