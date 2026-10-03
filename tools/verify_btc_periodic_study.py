"""Independent BTC weekday-risk normal equations, losses, raw-price and Decimal accounts."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
IDS=('PS_CAL','PS_HAR','PS_DAY','PS_MEAN','PS_INV','PS_TREND')
COLS={'PS_CAL':list(range(9)),'PS_HAR':[0,1,2],'PS_DAY':list(range(3,9)),'PS_MEAN':[]}
RV_SHA='2da197d43eb2275681050988c888093975eb8f34368f05570b146a6cc46a6c47'
PERIODS={'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def rv_source():
 p=ROOT/'data/btc-rv-20261002';hashes={'daily-rv.json.gz':'61b3b68aa4ac96116f30986e76303a8cb394837edff6a22242dbb226f20ef1ee','audit.json':'0e9531e91d532305902625df2e9d8a49414c954ece2e6a693c80c2150d1dc725','verification.json':'f70aceabfe3016dc26a15404478e4b8bd314e1b974885226aaae3b9ed4bd640e'}
 for k,h in hashes.items():assert sha((p/k).read_bytes())==h
 a=read(p/'daily-rv.json.gz');assert sha(canonical(a))==RV_SHA and [r['day'] for r in a]==list(range(ms('2020-01-01'),ms('2026-09-01'),DAY));receipt=read(p/'verification.json');assert receipt['max_rv_error']<1e-12
 source={}
 for r in a:
  assert r['end']==r['day']+DAY;v=D(r['rv']) if r['rv'] is not None else None;good=r['valid'] and v is not None and v.is_finite() and v>0;source[r['day']]={'rv':v,'valid':good,'end':r['end']}
 return source,{'canonical_sha256':RV_SHA,'files':hashes,'prior_raw_receipt':receipt,'scope':'Frozen 80-month raw-RV verification receipt reused by SHA, not a fresh reconstruction of all 701280 five-minute bars'}
def run(out):
 out=Path(out);payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={};rawvolume={};rawmarks={};rawclock={};archive_count=0
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
      rawprice[(key,t)]=(D(rr[1]),D(rr[4]));rawvolume[(key,t)]=D(rr[5]);ct=int(rr[6]);rawclock[(key,t)]=ct//1000 if ct>10**14 else ct
      if key=='BS' and t%DAY==23*HOUR and t>=ms('2020-01-01'):spot[t+HOUR]=float(rr[4])
 assert all(rawvolume[('BS',t-HOUR)]>0 for t in spot), 'nonpositive raw daily-boundary spot volume'
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
 source,source_counts=rv_source();feature_checks=regressions=forecast_checks=0;fit_worst=feature_worst=0.;ff={};pp={}
 assert sha(gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes()))=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4'
 for key in KEYS:
  for t,r in rows[key].items():assert (D(r[1]),D(r[4]))==rawprice[(key,t)] and r[5]==rawclock[(key,t)]
 def near(a,b,tolerance=2e-9):
  nonlocal fit_worst
  aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float);assert aa.shape==bb.shape;error=float(np.max(np.abs(aa-bb))) if aa.size else 0.;fit_worst=max(fit_worst,error);assert np.allclose(aa,bb,rtol=2e-8,atol=tolerance),(aa,bb,error)
 def observation(t,risk=.2):
  i=dayidx.get(t,-1)
  if i<128:return None
  hist=daily[i-20:i+1]
  if not np.all(np.isfinite(hist)):return None
  rr=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(rr)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in rr)/19*365);weight=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda x:int(x>0)-int(x<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6
  return (score,weight,vol) if math.isfinite(score) else None
 def day(t):return dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).weekday()
 def cal(t):
  d=day(t);return [-1]*6 if d==6 else [1 if k==d else 0 for k in range(6)]
 observed=read(out/'features.json.gz');assert [r['source'] for r in observed]==[u+DAY for u in source]
 for e in observed:
  t=e['source'];wanted=[t-i*DAY for i in range(22,0,-1)];parts=[source.get(u) for u in wanted];good=all(r is not None and r['valid'] for r in parts);values=[r['rv'] for r in parts] if good else None
  z=[math.log(float(values[-1])),math.log(float(sum(values[-5:])/5)),math.log(float(sum(values)/22))] if good else [None]*3;y=source.get(t);truth=float(y['rv']) if y is not None and y['valid'] else None
  assert e['observed_day']==t-DAY and e['input_days']==wanted and e['valid']==good and e['weekday']==day(t) and e['calendar']==cal(t) and e['truth_end']==(t+DAY if y is not None else None)
  if good:near(e['input_rv'],[float(v) for v in values],1e-14);near(e['log_rv_features'],z,1e-13);near(e['features'],z+cal(t),1e-13)
  else:assert e['input_rv'] is None and e['log_rv_features']==[None]*3 and e['features']==z+cal(t)
  if truth is None:assert e['truth'] is None
  else:near(e['truth'],truth,1e-14)
  ff[t]={'valid':good,'features':z+cal(t),'truth':truth,'truth_end':t+DAY if y is not None else None};feature_checks+=1
 def restore(logv):
  if not math.isfinite(logv):return None,False,None
  try:raw=math.exp(logv)
  except OverflowError:return None,False,None
  if not math.isfinite(raw):return None,False,None
  return max(1e-8,raw),raw<1e-8,raw
 saved=read(out/'predictions.json.gz');assert [p['source'] for p in saved]==list(ff);saved_predictions={p['source']:p for p in saved}
 for actual in saved:
  t=actual['source'];train=[u for u in range(t-365*DAY,t,DAY) if u in ff and ff[u]['valid'] and ff[u]['truth'] is not None and ff[u]['truth_end']<=t];counts=[sum(day(u)==k for u in train) for k in range(7)];last=max((ff[u]['truth_end'] for u in train),default=None)
  assert actual['training_days']==train and actual['training_n']==len(train) and actual['training_weekday_counts']==counts and actual['training_label_end']==last;valid=ff[t]['valid'] and len(train)>=300 and min(counts)>=40;models={}
  for name,cols in COLS.items():
   p=actual['models'][name]
   if not valid:assert p['prediction'] is None;models[name]={'prediction':None,'floor':False};continue
   X=np.array([[1.]+[ff[u]['features'][k] for k in cols] for u in train]);y=np.log([ff[u]['truth'] for u in train]);cur=np.array([1.]+[ff[t]['features'][k] for k in cols]);rank=np.linalg.matrix_rank(X)
   if rank<X.shape[1]:assert p['prediction'] is None;models[name]={'prediction':None,'floor':False};continue
   beta=np.linalg.solve(X.T@X,X.T@y);res=y-X@beta;logsmear=math.log(math.fsum(math.exp(float(r)) for r in res)/len(res));mu=float(cur@beta);prediction,floor,raw=restore(mu+logsmear)
   assert p['n']==len(train) and p['rank']==rank and p['floor']==floor;near(p['beta'],beta);near(p['residuals'],res);near(p['residual_ss'],res@res);near(p['log_smearing'],logsmear);near(p['smearing'],math.exp(logsmear));near(p['log_point'],mu);near(p['feature_mean'],X[:,1:].mean(axis=0),1e-13);scale=X[:,1:].std(axis=0);scale[scale<1e-12]=1;near(p['feature_scale'],scale,1e-13)
   if prediction is None:assert p['prediction'] is None
   else:near(p['prediction'],prediction,1e-12);near(p['unclipped'],raw,1e-12);near(p['log_variance'],mu+logsmear)
   if name=='PS_MEAN':near(prediction,math.fsum(ff[u]['truth'] for u in train)/len(train),1e-13)
   models[name]={'prediction':prediction,'floor':floor};regressions+=1
  a,b=models['PS_CAL']['prediction'],models['PS_HAR']['prediction'];inv,floor,raw=restore(2*math.log(b)-math.log(a)) if a is not None and b is not None else (None,False,None);models['PS_INV']={'prediction':inv,'floor':floor};assert actual['models']['PS_INV']['floor']==floor
  if inv is None:assert actual['models']['PS_INV']['prediction'] is None
  else:near(actual['models']['PS_INV']['prediction'],inv,1e-12)
  obs=observation(t);trend=obs[2]**2/365 if obs is not None else None;models['PS_TREND']={'prediction':trend,'floor':False}
  if trend is None:assert actual['models']['PS_TREND']['prediction'] is None
  else:near(actual['models']['PS_TREND']['prediction'],trend,1e-13)
  pp[t]=models;forecast_checks+=1
 print(json.dumps({'stage':'independent_daily_features_and_fits','fits':regressions,'features':feature_checks,'max_fit_error':fit_worst}),flush=True)
 bootstrap_checks=0
 def verify_bootstrap(series,records):
  nonlocal bootstrap_checks
  n=len(series);prefix=np.r_[0.,np.cumsum(np.r_[series,series])]
  for block,actual in zip((7,14,28),records):
   count=math.ceil(n/block);rng=np.random.default_rng(1490+block);starts=rng.integers(n,size=(2000,count));lengths=np.full(count,block);lengths[-1]=n-(count-1)*block;sums=(prefix[starts+lengths]-prefix[starts]).sum(axis=1)/n*100
   assert actual['block_days']==block and actual['replicates']==2000;near(actual['mean_daily_pct'],math.fsum(series)/n*100,1e-13);near(actual['ci95'],np.quantile(sums,[.025,.975]),1e-13);bootstrap_checks+=1
 forecast_results=read(out/'forecast-summary.json')
 for period,(start,end) in PERIODS.items():
  paired=[t for t,v in pp.items() if start<=t<end and ff[t]['truth'] is not None and ff[t]['truth_end']<=end and all(z['prediction'] is not None and math.isfinite(z['prediction']) and z['prediction']>0 for z in v.values())];fc=forecast_results[period];assert fc['common_days']==paired and fc['n']==len(paired) and fc['calendar_days']==(end-start)//DAY;near(fc['coverage'],len(paired)/((end-start)//DAY),1e-14);losses={};y=np.array([ff[t]['truth'] for t in paired])
  for name in IDS:
   v=np.array([pp[t][name]['prediction'] for t in paired]);mse=(y-v)**2;q=y/v-np.log(y/v)-1;losses[name]=(mse,q);scheduled=[v[name] for t,v in pp.items() if start<=t<end and v[name]['prediction'] is not None];floor=sum(z['floor'] for z in scheduled);r=fc['models'][name];assert r['n']==len(paired) and r['scheduled_predictions']==len(scheduled) and r['floor_count']==floor;near(r['mse'],np.mean(mse),1e-14);near(r['qlike'],np.mean(q),1e-10);near(r['floor_fraction'],floor/len(scheduled),1e-14)
  for ctrl in ('PS_HAR','PS_MEAN'):
   for j,k in enumerate(('mse_improvement','qlike_improvement')):verify_bootstrap(losses[ctrl][j]-losses['PS_CAL'][j],fc['loss_differences']['CAL_vs_'+ctrl][k])
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);period,name=p.name.split('-')[:2];risk=float(p.name.split('-risk')[1].removesuffix('.json.gz'));start,end=PERIODS[period];assert [e['source_time'] for e in plan]==list(range(start,end,DAY))
  for e in plan:
   t=e['source_time'];detail=e['detail'];model=pp[t][name];v=model['prediction'];obs=observation(t,risk);raw=saved_predictions[t];assert detail['weekday']==day(t) and detail['training_n']==raw['training_n'] and detail['training_label_end']==raw['training_label_end'] and detail['input_valid']==ff[t]['valid'] and detail['floor']==model['floor']
   if v is None:assert detail['forecast'] is None
   else:near(detail['forecast'],v,1e-12)
   if obs is None or v is None:assert e['weights'] is None and detail['missing'];continue
   score,w,oldvol=obs;vol=oldvol if name=='PS_TREND' else math.sqrt(365*v);riskweight=w if name=='PS_TREND' else min(1,risk/vol);signal=max(0,score);assert not detail['missing'] and detail['score']==score and detail['signal']==signal;near(detail['old_vol'],oldvol,1e-10);near(detail['vol'],vol,1e-10);near(detail['risk'],riskweight,1e-10);near(e['weights']['BS'],signal*riskweight,1e-10);assert e['weights']['BP']==0 and 0<=e['weights']['BS']<=1;raw_signals[name,risk,t]=e;plans_checked+=1
 print(json.dumps({'stage':'independent_plans','daily_decisions':plans_checked}),flush=True)
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','predictions','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_periodic_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
  assert x['rv_input_sha256']==RV_SHA
  multiplier=2 if x['scenario']=='cost_x2' else 1;assert model['fee_bps']=={'BS':10*multiplier,'BP':5*multiplier} and model['impact_bps']==1.5*multiplier and model['extra_delay_hours']=={'delay1':1,'delay24':24}.get(x['scenario'],0) and x['risk_target']==(.1 if x['scenario']=='risk10' else .2)
  margin_min=None;breaches=0;exposure_sum=D(0);max_exposure=D(0);episodes=0
  for e in x['events']:bytime[e['time']].append(e)
  def equal(a,b):
   nonlocal worst
   delta=float(abs(D(a)-D(b)));worst=max(worst,delta);assert delta<1e-7,(p.name,a,b)
  def value(prices):return cash+sum(q[k]*D(prices[k]) for k in KEYS)
  def observe(prices):
   nonlocal peak,dd,max_exposure
   eq=value(prices);peak=max(peak,eq);dd=max(dd,(1-eq/peak)*100);max_exposure=max(max_exposure,sum(abs(q[k])*D(prices[k]) for k in KEYS)/eq);return eq
  def fill(e):
   nonlocal cash,fee_sum,impact_sum,episodes
   k=e['instrument'];t=e['time'];dq=D(e['delta']);ref=rawprice[(k,end-HOUR)][1] if t==end else rawprice[(k,t)][0];slip=D(model['impact_bps'])/10000;px=ref*(1+(slip if dq>0 else -slip));charge=abs(dq)*px*D(model['fee_bps'][k])/10000;loss=abs(dq)*ref*slip
   equal(ref,e['reference']);equal(px,e['price']);equal(charge,e['fee']);equal(loss,e['impact']);assert rawvolume[(k,end-HOUR if t==end else t)]>0
   if t<end:
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['risk_target'],e['source_time']) in raw_signals
    step=D('.00001' if k=='BS' else '.001');equal(D(e['position'])/step,round(float(D(e['position'])/step)));reducing=q[k]*dq<0 and abs(D(e['position']))<abs(q[k]);assert abs(dq)*px>=D(5 if k=='BS' else 50)-D('1e-7') or(k=='BP' and reducing)
   if q[k] and (abs(q[k]+dq)<D('1e-12') or q[k]*(q[k]+dq)<0):episodes+=1
   q[k]+=dq;cash-=dq*px+charge;fee_sum+=charge;impact_sum+=loss;sides[k]['gross']-=dq*ref;sides[k]['fees']+=charge;sides[k]['impact']+=loss;equal(q[k],e['position'])
   if abs(q[k])<D('1e-12'):q[k]=D(0)
   assert q['BS']>=0 and q['BP']==0 and not(q['BS'] and q['BP'])
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
   observe(op);eq=observe(cl);exposure_sum+=sum(abs(q[k])*cl[k] for k in KEYS)/eq
   if q['BP']:
    high=rawmarks[t][1];ratio=(cash+q['BP']*high)/(-q['BP']*high);margin_min=ratio if margin_min is None else min(margin_min,ratio);breaches+=int(ratio<D('.05'))
   if not q['BP']:assert cash>=D('-1e-7')
   if t+HOUR in daily_map:
    d=daily_map[t+HOUR]
    if t+HOUR==end:
     for e in bytime[end]:fill(e)
     eq=observe({k:rawprice[(k,end-HOUR)][1] for k in KEYS})
    equal(eq,d['equity']);equal(cash,d['cash']);equal(fee_sum,d['fees']);equal(impact_sum,d['impact']);equal(fund_sum,d['funding']);equal((1-eq/peak)*100,d['drawdown_pct'])
    for k in KEYS:equal(q[k],d['positions'][k])
  assert episodes==x['metrics']['round_trips'] and breaches==x['metrics']['margin_buffer_breach_hours'];equal(exposure_sum/D((end-start)//HOUR),x['metrics']['mean_exposure']);equal(max_exposure,x['metrics']['max_exposure'])
  if margin_min is None:assert x['metrics']['min_adverse_margin_ratio'] is None
  else:equal(margin_min,x['metrics']['min_adverse_margin_ratio'])
  previous=1000.;rr=[];years={}
  for day in x['daily']:
   eqday=day['equity'];rr.append(eqday/previous-1);year=utc(day['time']-1)[:4];part=years.setdefault(year,{'start_equity':previous,'end_equity':previous});part['end_equity']=eqday;previous=eqday
  assert len(rr)==len(x['daily_returns'])
  for a,b in zip(rr,x['daily_returns']):equal(a,b)
  mean=float(np.mean(rr));std=float(np.std(rr,ddof=1));equal(std*math.sqrt(365)*100,x['metrics']['realized_vol_pct']);equal(mean/std*math.sqrt(365),x['metrics']['sharpe']);equal(mean*100,x['metrics']['daily_mean_pct']);equal((float(cash)/1000-1)*100,x['metrics']['return_pct'])
  for year,y in years.items():
   expected=x['periods']['yearly'][year];equal(y['start_equity'],expected['start_equity']);equal(y['end_equity'],expected['end_equity']);equal(100*(y['end_equity']/y['start_equity']-1),expected['return_pct']);equal(y['end_equity']-y['start_equity'],expected['pnl'])
  equal(cash,x['metrics']['equity']);equal(dd,x['metrics']['max_drawdown_pct']);side={k:{**{a:float(v) for a,v in z.items()},'net':float(z['gross']-z['fees']-z['impact']+z['funding'])} for k,z in sides.items()};equal(sum(z['net'] for z in side.values()),x['metrics']['net_pnl']);diag[p.name]={'sides':side,'skips':x['skips']};reports.append({'file':p.name,'events':len(x['events']),'daily':len(x['daily'])})
  if len(reports)%10==0:print(json.dumps({'stage':'independent_accounts','accounts':len(reports),'max_error':worst}),flush=True)
 assert len(reports)==60
 summary=read(out/'summary.json');selection=read(out/'selection.json');a=summary['main-PS_CAL-base']['metrics'];b=summary['recent-PS_CAL-base']['metrics'];checks={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-PS_CAL-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):checks[c]=all(summary[p+'-PS_CAL-'+c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in ('PS_HAR','PS_DAY','PS_MEAN','PS_TREND'):extra['net_beats_'+name+'_both']=all(summary[p+'-PS_CAL-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_HAR_both']=all(summary[p+'-PS_CAL-base']['metrics']['max_drawdown_pct']<=summary[p+'-PS_HAR-base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for period,fc in forecast_results.items():
  aa,bb,cc=[fc['models'][n] for n in ('PS_CAL','PS_HAR','PS_MEAN')];extra[period+'_coverage']=fc['coverage']>=.90;extra[period+'_floor']=aa['floor_fraction'] is not None and aa['floor_fraction']<=.01;extra[period+'_prediction']=aa['qlike'] is not None and bb['qlike'] is not None and cc['qlike'] is not None and aa['qlike']<bb['qlike'] and aa['qlike']<cc['qlike'] and aa['mse']<=bb['mse']
 assert selection['checks']==checks and selection['information_increment']==extra and selection['passed']==(all(checks.values()) and all(extra.values()))
 assert set(summary)=={r['file'].removesuffix('.json.gz') for r in reports}
 for key,row in summary.items():
  account=read(out/(key+'.json.gz'));assert row=={'metrics':account['metrics'],'annual':account['periods']['yearly']}
 identity=read(out/'control-identity.json');uncertainty=read(out/'uncertainty.json')
 for period in PERIODS:
  actual=read(out/f'{period}-PS_TREND-base.json.gz');saved=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');near(actual['daily_returns'],saved['daily_returns']);near(identity[period]['daily_return_max_error'],max(abs(a-b) for a,b in zip(actual['daily_returns'],saved['daily_returns'])))
  for metric in ('return_pct','max_drawdown_pct','fees','impact','funding'):near(actual['metrics'][metric],saved['metrics'][metric]);near(identity[period]['metric_errors'][metric],abs(actual['metrics'][metric]-saved['metrics'][metric]))
  ret={n:np.array(read(out/f'{period}-{n}-base.json.gz')['daily_returns']) for n in IDS}
  for name,r in ret.items():
   for category,series in [('mean',r)]+[('vs_'+n,r-ret[n]) for n in ('PS_HAR','PS_DAY','PS_MEAN','PS_TREND')]:verify_bootstrap(series,uncertainty[period+'-'+name][category])
 activity=read(out/'activity.json')
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);period,name=p.name.split('-')[:2];risk=float(p.name.split('-risk')[1].removesuffix('.json.gz'));key=name+('-risk10' if risk==.1 else '-base');expected={'missing_days':sum(e['weights'] is None for e in plan),'floor_days':sum(e['detail']['floor'] for e in plan),'positive_direction_days':sum(e['detail'].get('signal',0)>0 for e in plan),'long_target_days':sum(e['weights'] is not None and e['weights']['BS']>0 for e in plan)};assert activity[period][key]==expected
  if risk==.2:
   for scenario in ('cost_x2','delay1','delay24'):assert activity[period][name+'-'+scenario]==expected
 assert raw_funding_events==0
 proof={'accounts':len(reports),'raw_archives':archive_count,'rv_source_receipt_reuse':source_counts,'raw_feature_days':feature_checks,'raw_forecast_days':forecast_checks,'independent_model_fits':regressions,'max_fit_numeric_error':fit_worst,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'selection_independently_checked':True,'return_and_loss_block_bootstrap_checks':bootstrap_checks,'scope':'Frozen daily BTC RV and raw reconstruction receipts reused by SHA; fresh 329 BTC price/funding/volume ZIP checks. Independent Decimal RV aggregation/log features, weekday contrasts/365-calendar/common samples, unscaled normal-equation fits/residual smearing, mean identity/inverse risk factor, common MSE/QLIKE, daily risk with original long-only direction; closed-form postcost quantities and no-trades, Decimal events/hourly DD/exposure/annual/vol/margin/funding zero, summary/selection/E_SPOT identity and circular-block uncertainty. Not a fresh reconstruction of all five-minute bars, original EGARCH replication, unused OOS, or guaranteed executable spot risk from perp RV.'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
