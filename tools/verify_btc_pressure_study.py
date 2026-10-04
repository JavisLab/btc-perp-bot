"""Independent TP features/normal equations, pure-perp Decimal accounting, selection/CI.
Uses already-proven market/RV receipts by SHA; does not rerun unchanged 329-source audit.
No import of the new strategy or its simulator.
"""
import argparse,datetime as dt,gzip,json,math,itertools
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR,getcontext
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
from verify_btc_periodic_study import rv_source
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP');getcontext().prec=60
IDS=('TP_INFO','TP_NET','TP_VOL','TP_HAR','TP_INV','TP_TREND');COLS={'TP_INFO':list(range(6)),'TP_NET':list(range(5)),'TP_VOL':list(range(4)),'TP_HAR':list(range(3))};CONTROLS=('TP_NET','TP_VOL','TP_HAR','TP_TREND')
PRESSURE_SHA='b7bcc90d73a29cf1f2d84dcd752025a6034d356ab337d7ce48eab82f09869d5f';RV_SHA='2da197d43eb2275681050988c888093975eb8f34368f05570b146a6cc46a6c47'
PERIODS={'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def run(out):
 out=Path(out);rawmarket=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes());assert sha(rawmarket)=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4';proofp=ROOT/'runs/btc-continuity-20261003/verification.json';assert sha(proofp.read_bytes())=='38f6da0357b82a2067fed0869fd27e7a8cb1ad937044a392486fdd0d9a9e0382';market_receipt={'sha256':sha(proofp.read_bytes()),'path':str(proofp.relative_to(ROOT)),'scope':'Prior independent 329 ZIP market audit reused, not rerun; all new account events/days checked separately'};payload=json.loads(rawmarket)['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={r[0]:(D(r[2]),r[3]) for r in payload['funding']};rawprice={};rawvolume={};rawmarks={t:tuple(D(r[j]) for j in (1,2,3,4)) for t,r in marks['BP'].items()};spot={}
 for t,r in rows['BS'].items():
  rawprice['BS',t]=(D(r[1]),D(r[4]));rawvolume['BS',t]=D(1)
  if (t+HOUR)%DAY==0 and r[5]==t+HOUR-1:spot[t+HOUR]=r[4]
 pressure=read(ROOT/'data/btc-pressure-20261004/daily.json.gz');assert sha(canonical(pressure))==PRESSURE_SHA;pressure_proof=read(ROOT/'data/btc-pressure-20261004/independent-audit.json');assert pressure_proof['daily_sha256']==PRESSURE_SHA and pressure_proof['max_scaled_error']==0;flow={};raw_pressure_hours=0
 for e in pressure['rows']:
  Q=sum((D(r['quote']) for r in e['hours']),D(0));S=sum((2*D(r['buy_quote'])-D(r['quote']) for r in e['hours']),D(0));G=sum((abs(2*D(r['buy_quote'])-D(r['quote'])) for r in e['hours']),D(0));flow[e['day']]={'valid':e['valid'],'quote':Q,'net':abs(S)/Q if Q else None,'gross':G/Q if Q else None}
  for r in e['hours']:
   t=r['time'];rawprice['BP',t]=(D(r['ohlc'][0]),D(r['ohlc'][3]));rawvolume['BP',t]=D(r['base']);raw_pressure_hours+=1
   assert t in rows['BP'] and (D(rows['BP'][t][1]),D(rows['BP'][t][4]))==rawprice['BP',t] and rows['BP'][t][5]==r['end']
 days=list(range(ms('2020-02-02'),max(spot)+1,DAY));daily=np.array([spot.get(t,np.nan) for t in days]);dayidx={t:i for i,t in enumerate(days)};em={}
 for span in (8,16,32,64,128):
  acc=None;a=2/(span+1);track=[]
  for c in daily:
   if not math.isfinite(c):acc=None;track.append(float('nan'));continue
   acc=c if acc is None else a*c+(1-a)*acc;track.append(acc)
  em[span]=track
 source,source_counts=rv_source();feature_checks=regressions=forecast_checks=0;fit_worst=0.;ff={};pp={};saved_predictions={}
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
 def restore(logv):
  if not math.isfinite(logv):return None,False,None
  try:raw=math.exp(logv)
  except OverflowError:return None,False,None
  if not math.isfinite(raw):return None,False,None
  return max(1e-8,raw),raw<1e-8,raw
 for lag in (0,7):
  ff[lag]={};pp[lag]={};saved_predictions[lag]={};observed=read(out/f'features-lag{lag}.json.gz');assert [e['source'] for e in observed]==[t+DAY for t in source]
  for e in observed:
   t=e['source'];rdays=list(range(t-22*DAY,t,DAY));d=t-(lag+1)*DAY;fdays=list(range(d-28*DAY,d+DAY,DAY));r=[source.get(u) for u in rdays];f=[flow.get(u) for u in fdays];good=all(x is not None and x['valid'] for x in r) and all(x is not None and x['valid'] and x['quote']>0 and 0<=x['net']<=x['gross']<=1 for x in f);x=[math.log(float(r[-1]['rv'])),math.log(float(sum(z['rv'] for z in r[-5:])/5)),math.log(float(sum(z['rv'] for z in r)/22)),math.log(float(f[-1]['quote']/(sum(z['quote'] for z in f[:-1])/28))),float(f[-1]['net']),float(f[-1]['gross'])] if good else [None]*6;y=source.get(t);truth=float(y['rv']) if y is not None and y['valid'] else None;end=t+DAY if y is not None else None
   assert e['flow_lag']==lag and e['flow_day']==d and e['rv_days']==rdays and e['flow_days']==fdays and e['valid']==good and e['truth_end']==end
   if good:near(e['features'],x,1e-13)
   else:assert e['features']==x
   if truth is None:assert e['truth'] is None
   else:near(e['truth'],truth,1e-14)
   ff[lag][t]={'valid':good,'features':x,'truth':truth,'truth_end':end};feature_checks+=1
  saved=read(out/f'predictions-lag{lag}.json.gz');assert [p['source'] for p in saved]==list(ff[lag])
  for actual in saved:
   t=actual['source'];f=ff[lag];train=[u for u in range(t-365*DAY,t,DAY) if u in f and f[u]['valid'] and f[u]['truth'] is not None and f[u]['truth_end']<=t];last=max((f[u]['truth_end'] for u in train),default=None);assert actual['flow_lag']==lag and actual['training_days']==train and actual['training_n']==len(train) and actual['training_label_end']==last;models={};valid=f[t]['valid'] and len(train)>=300
   for name,cols in COLS.items():
    p=actual['models'][name]
    if not valid:assert p['prediction'] is None;models[name]={'prediction':None,'floor':False};continue
    X=np.array([[1.]+[f[u]['features'][c] for c in cols] for u in train]);y=np.log([f[u]['truth'] for u in train]);cur=np.array([1.]+[f[t]['features'][c] for c in cols]);rank=np.linalg.matrix_rank(X)
    if rank<X.shape[1]:assert p['prediction'] is None;models[name]={'prediction':None,'floor':False};continue
    beta=np.linalg.solve(X.T@X,X.T@y);res=y-X@beta;logsmear=math.log(math.fsum(math.exp(float(r)) for r in res)/len(res));mu=float(cur@beta);prediction,floor,raw=restore(mu+logsmear);assert p['n']==len(train) and p['rank']==rank and p['floor']==floor;near(p['beta'],beta);near(p['residuals'],res);near(p['residual_ss'],res@res);near(p['log_smearing'],logsmear);near(p['smearing'],math.exp(logsmear));near(p['log_point'],mu);near(p['feature_mean'],X[:,1:].mean(axis=0),1e-13);scale=X[:,1:].std(axis=0);scale[scale<1e-12]=1;near(p['feature_scale'],scale,1e-13)
    if prediction is None:assert p['prediction'] is None
    else:near(p['prediction'],prediction,1e-12);near(p['unclipped'],raw,1e-12);near(p['log_variance'],mu+logsmear)
    models[name]={'prediction':prediction,'floor':floor,'beta':beta.tolist()};regressions+=1
   a,b=models['TP_INFO']['prediction'],models['TP_NET']['prediction'];inv,floor,raw=restore(2*math.log(b)-math.log(a)) if a is not None and b is not None else (None,False,None);models['TP_INV']={'prediction':inv,'floor':floor};assert actual['models']['TP_INV']['floor']==floor
   if inv is None:assert actual['models']['TP_INV']['prediction'] is None
   else:near(actual['models']['TP_INV']['prediction'],inv,1e-12)
   obs=observation(t);trend=obs[2]**2/365 if obs else None;models['TP_TREND']={'prediction':trend,'floor':False}
   if trend is None:assert actual['models']['TP_TREND']['prediction'] is None
   else:near(actual['models']['TP_TREND']['prediction'],trend,1e-13)
   pp[lag][t]=models;saved_predictions[lag][t]=actual;forecast_checks+=1
 print(json.dumps({'stage':'independent_pressure_risk_fits','features':feature_checks,'fits':regressions,'max_error':fit_worst}),flush=True)
 bootstrap_checks=0
 def verify_bootstrap(series,records):
  nonlocal bootstrap_checks
  n=len(series);prefix=np.r_[0.,np.cumsum(np.r_[series,series])]
  for block,actual in zip((7,14,28),records):
   count=math.ceil(n/block);rng=np.random.default_rng(1490+block);starts=rng.integers(n,size=(2000,count));lengths=np.full(count,block);lengths[-1]=n-(count-1)*block;sums=(prefix[starts+lengths]-prefix[starts]).sum(axis=1)/n*100
   assert actual['block_days']==block and actual['replicates']==2000;near(actual['mean_daily_pct'],math.fsum(series)/n*100,1e-13);near(actual['ci95'],np.quantile(sums,[.025,.975]),1e-13);bootstrap_checks+=1
 forecast_results=read(out/'forecast-summary.json')
 for period,(start,end) in PERIODS.items():
  paired=[t for t,v in pp[0].items() if start<=t<end and ff[0][t]['truth'] is not None and ff[0][t]['truth_end']<=end and all(z['prediction'] is not None and math.isfinite(z['prediction']) and z['prediction']>0 for z in v.values())];fc=forecast_results[period];assert fc['common_days']==paired and fc['n']==len(paired) and fc['calendar_days']==(end-start)//DAY;near(fc['coverage'],len(paired)/((end-start)//DAY),1e-14);losses={};y=np.array([ff[0][t]['truth'] for t in paired])
  for name in IDS:
   v=np.array([pp[0][t][name]['prediction'] for t in paired]);mse=(y-v)**2;q=y/v-np.log(y/v)-1;losses[name]=(mse,q);scheduled=[v[name] for t,v in pp[0].items() if start<=t<end and v[name]['prediction'] is not None];floor=sum(z['floor'] for z in scheduled);r=fc['models'][name];assert r['n']==len(paired) and r['scheduled_predictions']==len(scheduled) and r['floor_count']==floor;near(r['mse'],np.mean(mse),1e-14);near(r['qlike'],np.mean(q),1e-10);near(r['floor_fraction'],floor/len(scheduled),1e-14)
  for ctrl in ('TP_NET','TP_HAR'):
   for j,k in enumerate(('mse_improvement','qlike_improvement')):verify_bootstrap(losses[ctrl][j]-losses['TP_INFO'][j],fc['loss_differences']['INFO_vs_'+ctrl][k])
  betas=[v['TP_INFO']['beta'][-1] for t,v in pp[0].items() if start<=t<end and 'beta' in v['TP_INFO']];b=fc['gross_coefficient'];assert b['n']==len(betas) and b['positive']==sum(z>0 for z in betas) and b['zero_or_negative']==sum(z<=0 for z in betas);near(b['median'],np.median(betas))
 plans_checked=0;raw_signals={}
 for p in sorted(out.glob('*-plan-*.json.gz')):
  plan=read(p);period,name=p.name.split('-')[:2];risk=float(p.name.split('-risk')[1].split('-')[0]);lag=int(p.name.split('-lag')[1].split('.')[0]);start,end=PERIODS[period];assert [e['source_time'] for e in plan]==list(range(start,end,DAY))
  for e in plan:
   t=e['source_time'];detail=e['detail'];model=pp[lag][t][name];v=model['prediction'];obs=observation(t,risk);raw=saved_predictions[lag][t];assert detail['flow_lag']==lag and detail['flow_day']==t-(lag+1)*DAY and detail['training_n']==raw['training_n'] and detail['training_label_end']==raw['training_label_end'] and detail['input_valid']==ff[lag][t]['valid'] and detail['floor']==model['floor']
   if v is None:assert detail['forecast'] is None
   else:near(detail['forecast'],v,1e-12)
   if obs is None or v is None:assert e['weights'] is None and detail['missing'];continue
   score,w,oldvol=obs;vol=oldvol if name=='TP_TREND' else math.sqrt(365*v);riskweight=w if name=='TP_TREND' else min(1,risk/vol);assert not detail['missing'] and detail['score']==score and detail['signal']==score;near(detail['old_vol'],oldvol,1e-10);near(detail['vol'],vol,1e-10);near(detail['risk'],riskweight,1e-10);near(e['weights']['BP'],score*riskweight,1e-10);assert e['weights']['BS']==0 and -1<=e['weights']['BP']<=1;raw_signals[name,risk,lag,t]=e;plans_checked+=1
 print(json.dumps({'stage':'independent_plans','decisions':plans_checked}),flush=True)
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','predictions','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/x['schedule_file']);planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_pressure_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
  assert x['rv_input_sha256']==RV_SHA and x['pressure_input_sha256']==PRESSURE_SHA and x['flow_lag']==(7 if x['scenario']=='data_delay7' else 0)
  multiplier=2 if x['scenario']=='cost_x2' else 1;assert model['fee_bps']=={'BS':10*multiplier,'BP':5*multiplier} and model['impact_bps']==1.5*multiplier and model['extra_delay_hours']=={'delay1':1,'delay24':24}.get(x['scenario'],0) and x['risk_target']==(.1 if x['scenario']=='risk10' else .2)
  margin_min=None;breaches=0;exposure_sum=D(0);max_exposure=D(0);episodes=0;directions={k:{a:D(0) for a in ('gross','fees','impact','funding')} for k in ('long','short')}
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
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['risk_target'],x['flow_lag'],e['source_time']) in raw_signals
    step=D('.00001' if k=='BS' else '.001');equal(D(e['position'])/step,round(float(D(e['position'])/step)));reducing=q[k]*dq<0 and abs(D(e['position']))<abs(q[k]);assert abs(dq)*px>=D(5 if k=='BS' else 50)-D('1e-7') or(k=='BP' and reducing)
   if q[k] and (abs(q[k]+dq)<D('1e-12') or q[k]*(q[k]+dq)<0):episodes+=1
   parts=[(-q[k],'long' if q[k]>0 else 'short'),(q[k]+dq,'long' if q[k]+dq>0 else 'short')] if q[k] and q[k]*(q[k]+dq)<=0 else [(dq,'long' if (q[k]+dq or q[k])>0 else 'short')]
   for delta,direction in parts:
    directions[direction]['gross']-=delta*ref;directions[direction]['fees']+=abs(delta)*px*D(model['fee_bps'][k])/10000;directions[direction]['impact']+=abs(delta)*ref*slip
   q[k]+=dq;cash-=dq*px+charge;fee_sum+=charge;impact_sum+=loss;sides[k]['gross']-=dq*ref;sides[k]['fees']+=charge;sides[k]['impact']+=loss;equal(q[k],e['position'])
   if abs(q[k])<D('1e-12'):q[k]=D(0)
   assert q['BS']==0 and k=='BP'
  for t in range(start,end,HOUR):
   op={};cl={}
   for k in KEYS:
    r=rawprice.get((k,t)) if k=='BS' else(rawmarks[t][0],rawmarks[t][3])
    if r is None:op[k]=cl[k]=latest[k]
    else:op[k],cl[k]=r;latest[k]=r[1]
   events=bytime.get(t,[]);fe=[e for e in events if e['kind']=='funding'];assert len(fe)==int(bool(q['BP']) and t in funds)
   for e in fe:
    rate,raw=funds[t];flow=-q['BP']*op['BP']*rate;equal(flow,e['cashflow']);equal(q['BP'],e['position']);equal(op['BP'],e['reference']);assert rate==D(e['rate']) and raw==e['observed_time'];cash+=flow;fund_sum+=flow;sides['BP']['funding']+=flow;directions['long' if q['BP']>0 else 'short']['funding']+=flow;raw_funding_events+=1
   observe(op);pe=planned.get(t);fills=[e for e in events if e['kind']=='fill'];expected=dict(q)
   if pe is not None and pe['weights'] is not None:
    w={k:D(pe['weights'][k]) for k in KEYS};E=value(op);relevant=[k for k in KEYS if q[k] or w[k]];needed=any((q[k]==0 and w[k]!=0) or q[k]*w[k]<0 or(q[k]!=0 and w[k]==0) or abs(w[k]-q[k]*op[k]/E)>=D('.05') for k in KEYS)
    if needed and all((k,t) in rawprice and rawvolume[(k,t)]>0 for k in relevant):
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
    adverse=rawmarks[t][2] if q['BP']>0 else rawmarks[t][1];ratio=(cash+q['BP']*adverse)/(abs(q['BP'])*adverse);margin_min=ratio if margin_min is None else min(margin_min,ratio);breaches+=int(ratio<D('.05'))
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
  equal(cash,x['metrics']['equity']);equal(dd,x['metrics']['max_drawdown_pct']);side={k:{**{a:float(v) for a,v in z.items()},'net':float(z['gross']-z['fees']-z['impact']+z['funding'])} for k,z in sides.items()};equal(sum(z['net'] for z in side.values()),x['metrics']['net_pnl']);directional={k:{**{a:float(v) for a,v in z.items()},'net':float(z['gross']-z['fees']-z['impact']+z['funding'])} for k,z in directions.items()};equal(sum(z['net'] for z in directional.values()),x['metrics']['net_pnl']);diag[p.name]={'sides':side,'long_short':directional,'skips':x['skips']};reports.append({'file':p.name,'events':len(x['events']),'daily':len(x['daily'])})
  if len(reports)%10==0:print(json.dumps({'stage':'independent_accounts','accounts':len(reports),'max_error':worst}),flush=True)
 assert len(reports)==72
 summary=read(out/'summary.json');selection=read(out/'selection.json');a=summary['main-TP_INFO-base']['metrics'];b=summary['recent-TP_INFO-base']['metrics'];checks={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-TP_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):checks[c]=all(summary[p+'-TP_INFO-'+c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in CONTROLS:extra['net_beats_'+name+'_both']=all(summary[p+'-TP_INFO-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_NET_both']=all(summary[p+'-TP_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-TP_NET-base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for period,fc in forecast_results.items():
  aa,bb,cc=[fc['models'][n] for n in ('TP_INFO','TP_NET','TP_HAR')];extra[period+'_coverage']=fc['coverage']>=.90;extra[period+'_floor']=aa['floor_fraction'] is not None and aa['floor_fraction']<=.01;extra[period+'_prediction']=all(x['qlike'] is not None for x in (aa,bb,cc)) and aa['qlike']<bb['qlike'] and aa['qlike']<cc['qlike'] and aa['mse']<=bb['mse'];extra[period+'_positive_gross_coefficient']=fc['gross_coefficient']['median'] is not None and fc['gross_coefficient']['median']>0
 assert selection['checks']==checks and selection['information_increment']==extra and selection['passed']==(all(checks.values()) and all(extra.values()))
 assert set(summary)=={r['file'].removesuffix('.json.gz') for r in reports}
 for key,row in summary.items():
  account=read(out/(key+'.json.gz'));assert row=={'metrics':account['metrics'],'annual':account['periods']['yearly']}
 uncertainty=read(out/'uncertainty.json')
 for period in PERIODS:
  ret={n:np.array(read(out/f'{period}-{n}-base.json.gz')['daily_returns']) for n in IDS}
  for name,r in ret.items():
   for category,series in [('mean',r)]+[('vs_'+n,r-ret[n]) for n in CONTROLS]:verify_bootstrap(series,uncertainty[period+'-'+name][category])
 activity=read(out/'activity.json')
 for period in PERIODS:
  for name in IDS:
   for scenario in ('base','cost_x2','delay1','delay24','risk10','data_delay7'):
    risk=.1 if scenario=='risk10' else .2;lag=7 if scenario=='data_delay7' else 0;plan=read(out/f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz');expected={'missing_days':sum(e['weights'] is None for e in plan),'floor_days':sum(e['detail']['floor'] for e in plan),'long_target_days':sum(e['weights'] is not None and e['weights']['BP']>0 for e in plan),'short_target_days':sum(e['weights'] is not None and e['weights']['BP']<0 for e in plan)};assert activity[period][name+'-'+scenario]==expected
 proof={'accounts':len(reports),'new_pressure_raw_hours':raw_pressure_hours,'pressure_prior_raw_receipt':pressure_proof,'rv_source_receipt_reuse':source_counts,'market_source_receipt_reuse':market_receipt,'raw_feature_days':feature_checks,'raw_forecast_days':forecast_checks,'independent_model_fits':regressions,'max_fit_numeric_error':fit_worst,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'selection_independently_checked':True,'return_and_loss_block_bootstrap_checks':bootstrap_checks,'scope':'Separate Decimal pressure reconstruction on stored raw hourly fields already audited to 80 ZIPs; market329 and RV80 raw receipts reused by SHA, not fully reaudited. Independent risk features/365 common training/unscaled normal equations/smearing/inverse risk/QLIKE/MSE/beta; original signed direction on pure BTC perpetual only. Closed-form postcost quantities, no-trades, Decimal cash/funding/hourly margin long low/short high, annual metrics/selection/CI. Current vintage repeated development data, not OOS or trading authorization.'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
