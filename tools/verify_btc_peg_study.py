"""Independent BTC settlement-premium/USD forecast, cash events and Decimal account verification."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())

def source_check():
 folder=ROOT/'data/btc-venue-20261003';frozen=read(folder/'candles.json');saved_mask=read(folder/'masks.json');prior=read(folder/'independent-audit.json');assert sha((folder/'candles.json').read_bytes())==prior['candles_sha256']=='8dd4eb828dccde133cb3317bc98af56f086ad7500358149197a3ebf904d1bb31';assert sha((folder/'masks.json').read_bytes())==prior['mask_sha256']=='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd';raw={n:{} for n in ('coinbase-btcusd','coinbase-usdtusd')};count=0
 for e in read(folder/'archive-manifest.json'):
  n=e['series']
  if n not in raw:continue
  blob=(folder/e['file']).read_bytes();assert sha(blob)==e['sha256'];data=json.loads(blob,parse_float=Decimal);assert len(data)==e['rows'];count+=1
  for r in data:
   t=int(r[0])*1000;v=[D(r[j]) for j in (3,2,1,4,5)]
   if not frozen['start']<=t<frozen['end']:continue
   assert t%HOUR==0 and all(x.is_finite() for x in v);o,h,l,c,vol=v;assert 0<l<=o<=h and l<=c<=h and vol>0
   if t in raw[n]:assert raw[n][t]==v
   raw[n][t]=v
 for n,rr in raw.items():assert rr=={r[0]:[D(v) for v in r[1:]] for r in frozen['series'][n]}
 # Reuse prior native-daily audit, not refetch/replay unchanged daily probes or Bitstamp.
 clocks=[x for x in prior['daily_clock_checks'] if x['series'] in raw];assert len(clocks)==12
 return raw,{n:set(saved_mask['external'][n]) for n in raw},set(saved_mask['binance_spot_no_trade']),count,{'native_daily_checks_reused':len(clocks),'audit_sha256':sha((folder/'independent-audit.json').read_bytes()),'new_daily_probe_queries':0}

def independent_fit(X,y,dates,current,constrain):
 n,k=X.shape;rank=np.linalg.matrix_rank(X)
 if rank<k:return None
 coef=np.linalg.solve(X.T@X,X.T@y);unrestricted=coef.copy();active=bool(constrain and coef[-1]>0);free=list(range(k-int(active)));F=X[:,free];bread=np.linalg.inv(F.T@F);b=np.linalg.solve(F.T@F,F.T@y);residual=y-F@b;lo=min(dates);grid=np.zeros((int((max(dates)-lo)//DAY)+1,len(free)))
 for date,row,res in zip(dates,F,residual):grid[int((date-lo)//DAY)]=row*res
 meat=grid.T@grid
 for lag in range(1,2):
  cross=grid[lag:].T@grid[:-lag];meat+=(2-lag)/2*(cross+cross.T)
 cov_small=n/(n-len(free))*bread@meat@bread;beta=np.zeros(k);cov=np.zeros((k,k));beta[free]=b;cov[np.ix_(free,free)]=cov_small
 return {'mu':float(current@beta),'se':math.sqrt(max(0,float(current@cov@current))),'beta':beta,'covariance':cov,'constraint_active':active,'unrestricted_beta':unrestricted,'unrestricted_rank':int(rank),'rank':len(free),'free_columns':free,'residual_ss':float(residual@residual)}

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
 source,masks,excluded,api_count,clock_checks=source_check();assert excluded=={t for (k,t),v in rawvolume.items() if k=='BS' and v<=0};feature_checks=0;regressions=0;forecast_checks=0;fit_worst=0.;raw_features={};raw_predictions={};saved_predictions={};target={}
 def raw_close(t):
  r=rawprice.get(('BS',t-HOUR));return float(r[1]) if r is not None and t-HOUR not in excluded and rawclock[('BS',t-HOUR)]==t-1 and r[1]>0 else None
 def logreturn(a,b):
  x,y=raw_close(a),raw_close(b);return math.log(y/x) if x is not None and y is not None else None
 def ext(n,end):
  t=end-HOUR;v=source[n].get(t)
  return v[3] if v is not None and t not in masks[n] and v[4]>0 else None
 def near(a,b,tolerance=2e-9):
  nonlocal fit_worst
  aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float);assert aa.shape==bb.shape;error=float(np.max(np.abs(aa-bb))) if aa.size else 0.;fit_worst=max(fit_worst,error);assert np.allclose(aa,bb,rtol=2e-8,atol=tolerance),(aa,bb,error)
 def usd_return(a,b):
  x,y=ext('coinbase-btcusd',a),ext('coinbase-btcusd',b);return math.log(float(y/x)) if x is not None and y is not None else None
 for t in range(ms('2021-05-01'),ms('2026-09-01'),DAY):target[t]={'end':t+DAY,'base_available':t+DAY+HOUR,'value':usd_return(t,t+DAY),'currency':'USD'}
 observed_targets=read(out/'labels.json.gz');assert set(observed_targets)=={str(t) for t in target}
 for t,v in target.items():
  actual=observed_targets[str(t)];assert actual['end']==v['end'] and actual['base_available']==v['base_available'] and actual['currency']=='USD'
  if v['value'] is None:assert actual['value'] is None
  else:near(actual['value'],v['value'],1e-14)
 for lag in (0,24):
  ff={};observed=read(out/f'features-lag{lag}.json.gz');assert [r['source'] for r in observed]==list(target)
  for actual in observed:
   t=actual['source'];last=t-HOUR*(1+lag);ends=list(range(last-23*HOUR,last+HOUR,HOUR));values=[ext('coinbase-usdtusd',q) for q in ends];missing=[q for q,v in zip(ends,values) if v is None];a,b=ext('coinbase-usdtusd',last-DAY),ext('coinbase-usdtusd',last)
   e={'source':t,'availability_delay_hours':lag,'window_first_close':ends[0],'window_last_close':last,'last_available':t,'missing_window_ends':missing,'r1':usd_return(last-DAY,last),'r7':usd_return(last-7*DAY,last),'fx':math.log(float(b/a)) if a is not None and b is not None else None,'premium':sum(math.log(float(v)) for v in values)/24 if not missing else None,'fx_window_closes':[float(v) if v is not None else None for v in values]};e['valid']=not missing and all(e[k] is not None for k in ('r1','r7','fx','premium'));ff[t]=e
   for k,v in e.items():
    if v is None or isinstance(v,(int,list,bool)):assert actual[k]==v,(lag,t,k,actual[k],v)
    else:near(actual[k],v,1e-14)
   feature_checks+=1
  pp={};observed=read(out/f'forecasts-lag{lag}.json.gz');assert [p['source'] for p in observed]==list(target)
  for actual in observed:
   t=actual['source'];train=[u for u in range(t-366*DAY,t-DAY,DAY) if u in ff and ff[u]['valid'] and target[u]['value'] is not None and target[u]['end']<=t-DAY and target[u]['base_available']+lag*HOUR<=t];assert actual['training_days']==train and actual['training_n']==len(train) and actual['training_label_end']==max((target[u]['end'] for u in train),default=None) and actual['training_label_available']==max((target[u]['base_available']+lag*HOUR for u in train),default=None);models={}
   for name,cols in [('PG_INFO',('r1','r7','fx','premium')),('PG_PRICE',('r1','r7','fx'))]:
    p=actual['models'][name];assert p['training_n']==len(train)
    if not ff[t]['valid'] or len(train)<126:assert p['mu'] is None and p['se'] is None;models[name]=None;continue
    X=np.array([[1]+[ff[u][c] for c in cols] for u in train]);y=np.array([target[u]['value'] for u in train]);current=np.array([1]+[ff[t][c] for c in cols]);fit=independent_fit(X,y,train,current,name=='PG_INFO')
    if fit is None:assert p['mu'] is None;models[name]=None;continue
    for k in ('constraint_active','unrestricted_rank','rank','free_columns'):assert p[k]==fit[k],(lag,t,name,k)
    for k in ('mu','se','beta','covariance','unrestricted_beta','residual_ss'):near(p[k],fit[k])
    near(p['feature_mean'],X[:,1:].mean(axis=0),1e-13);models[name]=fit;regressions+=1
   pp[t]=models;forecast_checks+=1
  raw_features[lag]=ff;raw_predictions[lag]=pp;saved_predictions[lag]={v['source']:v for v in observed}
  print(json.dumps({'stage':'independent_features_and_fits','lag':lag,'fits':regressions,'features':feature_checks,'max_fit_error':fit_worst}),flush=True)
 forecast_results=read(out/'forecast-summary.json')
 for period,(start,end) in {'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}.items():
  for lag in (0,24):
   paired=[t for t,models in raw_predictions[lag].items() if start<=t<end and target[t]['end']<=end and target[t]['value'] is not None and all(p is not None for p in models.values())]
   for name in ('PG_INFO','PG_PRICE'):
    actual=forecast_results[period][str(lag)][name];assert actual['n']==len(paired) and actual['paired_source_times']==paired
    if paired:
     predictions=[raw_predictions[lag][t][name] for t in paired];near(actual['mse'],sum((p['mu']-target[t]['value'])**2 for p,t in zip(predictions,paired))/len(paired));near(actual['sign_accuracy'],sum(np.sign(p['mu'])==np.sign(target[t]['value']) for p,t in zip(predictions,paired))/len(paired));assert actual['constraint_days']==sum(p['constraint_active'] for p in predictions)
    else:assert actual['mse'] is None
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk=float(p.name.split('-risk')[1].split('-lag')[0]);lag=int(p.name.split('-lag')[1].split('.')[0])
  for e in plan:
   t=e['source_time'];detail=e['detail'];f=raw_features[lag][t];models=raw_predictions[lag][t];savedf=detail['feature']
   for k,v in f.items():
    if v is None or isinstance(v,(int,list,bool)):assert savedf[k]==v
    else:near(savedf[k],v,1e-14)
   assert detail['models']==saved_predictions[lag][t]['models'] and detail['training_n']==saved_predictions[lag][t]['training_n'] and detail['training_label_end']==saved_predictions[lag][t]['training_label_end'] and detail['training_label_available']==saved_predictions[lag][t]['training_label_available'];i=dayidx[t];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6
   info,price=(models[n] for n in ('PG_INFO','PG_PRICE'));delta=None if info is None or price is None else 0. if info['constraint_active'] else info['mu']-price['mu'];event=bool(delta is not None and not info['constraint_active'] and f['premium'] is not None and f['premium']>0 and info['mu']+info['se']+math.log1p(.0023)<0 and delta < -1e-12)
   over=event if name in ('PG_INFO','PG_SHORT','PG_INV') else bool(price is not None and price['mu']+price['se']+math.log1p(.0023)<0) if name=='PG_PRICE' else False
   direction=(0. if name in ('PG_INFO','PG_PRICE') else -1. if name=='PG_SHORT' else 1.) if over else max(0,score)
   assert detail['override']==over and detail['core_fallback']==(not over)
   if delta is None:assert detail['increment'] is None
   else:near(detail['increment'],delta)
   assert detail['score']==score and detail['signal']==direction and abs(detail['vol']-vol)<1e-9 and abs(detail['risk']-w)<1e-9
   for k,v in [('BS',max(direction,0)*w),('BP',min(direction,0)*w)]:assert abs(e['weights'][k]-v)<1e-9
   assert sum(abs(v) for v in e['weights'].values())<=1+1e-12;raw_signals[name,risk,lag,t]=e;plans_checked+=1
 print(json.dumps({'stage':'independent_plans','daily_decisions':plans_checked}),flush=True)
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}-lag{x['availability_delay_hours']}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_peg_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
  multiplier=2 if x['scenario']=='cost_x2' else 1;assert model['fee_bps']=={'BS':10*multiplier,'BP':5*multiplier} and model['impact_bps']==1.5*multiplier and model['extra_delay_hours']=={'delay1':1,'delay24':24}.get(x['scenario'],0) and x['availability_delay_hours']==(24 if x['scenario']=='data_delay24' else 0) and x['risk_target']==(.1 if x['scenario']=='risk10' else .2)
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
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['risk_target'],x['availability_delay_hours'],e['source_time']) in raw_signals
    step=D('.00001' if k=='BS' else '.001');equal(D(e['position'])/step,round(float(D(e['position'])/step)));reducing=q[k]*dq<0 and abs(D(e['position']))<abs(q[k]);assert abs(dq)*px>=D(5 if k=='BS' else 50)-D('1e-7') or(k=='BP' and reducing)
   if q[k] and (abs(q[k]+dq)<D('1e-12') or q[k]*(q[k]+dq)<0):episodes+=1
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
 summary=read(out/'summary.json');selection=read(out/'selection.json');a=summary['main-PG_INFO-base']['metrics'];b=summary['recent-PG_INFO-base']['metrics'];checks={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-PG_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay24'):checks[c]=all(summary[p+'-PG_INFO-'+c]['metrics']['net_pnl']>0 for p in ('main','recent'))
 extra={}
 for name in ('PG_PRICE','PG_TREND'):extra['net_beats_'+name+'_both']=all(summary[p+'-PG_INFO-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in ('main','recent'))
 extra['dd_no_worse_price_both']=all(summary[p+'-PG_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-PG_PRICE-base']['metrics']['max_drawdown_pct'] for p in ('main','recent'));extra['mse_strictly_better_both']=all(forecast_results[p]['0']['PG_INFO']['mse'] is not None and forecast_results[p]['0']['PG_PRICE']['mse'] is not None and forecast_results[p]['0']['PG_INFO']['mse']<forecast_results[p]['0']['PG_PRICE']['mse'] for p in ('main','recent'));assert selection['checks']==checks and selection['information_increment']==extra and selection['passed']==(all(checks.values()) and all(extra.values()))
 assert set(summary)=={r['file'].removesuffix('.json.gz') for r in reports}
 for key,row in summary.items():
  account=read(out/(key+'.json.gz'));assert row['metrics']==account['metrics'] and row['annual']==account['periods']['yearly'];start,end=ms(account['start']),ms(account['end']);fx0,fx1=ext('coinbase-usdtusd',start),ext('coinbase-usdtusd',end);usd=row['usd_translation'];near(usd['start_usd_per_usdt'],float(fx0));near(usd['end_usd_per_usdt'],float(fx1));near(usd['return_pct'],float((D(account['metrics']['equity'])/1000*fx1/fx0-1)*100));assert usd['not_conversion_execution']
 identity=read(out/'control-identity.json');uncertainty=read(out/'uncertainty.json');bootstrap_checks=0
 for period in ('main','recent'):
  actual=read(out/f'{period}-PG_TREND-base.json.gz');saved=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');near(actual['daily_returns'],saved['daily_returns']);near(identity[period]['daily_return_max_error'],max(abs(a-b) for a,b in zip(actual['daily_returns'],saved['daily_returns'])))
  for metric in ('return_pct','max_drawdown_pct','fees','impact','funding'):near(actual['metrics'][metric],saved['metrics'][metric]);near(identity[period]['metric_errors'][metric],abs(actual['metrics'][metric]-saved['metrics'][metric]))
  ret={n:np.array(read(out/f'{period}-{n}-base.json.gz')['daily_returns']) for n in ('PG_INFO','PG_PRICE','PG_SHORT','PG_INV','PG_TREND')}
  for name,r in ret.items():
   for category,series in [('mean',r)]+[('vs_'+n,r-ret[n]) for n in ('PG_PRICE','PG_TREND')]:
    # Independent circular block sums using prefix differences, not original element-index matrix.
    n=len(series);prefix=np.r_[0.,np.cumsum(np.r_[series,series])]
    for block,actual in zip((7,14,28),uncertainty[period+'-'+name][category]):
     count=math.ceil(n/block);rng=np.random.default_rng(1490+block);starts=rng.integers(n,size=(2000,count));lengths=np.full(count,block);lengths[-1]=n-(count-1)*block;sums=(prefix[starts+lengths]-prefix[starts]).sum(axis=1)/n*100
     assert actual['block_days']==block and actual['replicates']==2000;near(actual['mean_daily_pct'],math.fsum(series)/n*100,1e-13);near(actual['ci95'],np.quantile(sums,[.025,.975]),1e-13);bootstrap_checks+=1
 proof={'accounts':len(reports),'raw_archives':archive_count,'official_api_responses':api_count,'external_hourly_rows':sum(len(v) for v in source.values()),'prior_native_daily_audit_reused':clock_checks,'raw_feature_days':feature_checks,'raw_forecast_days':forecast_checks,'independent_model_fits':regressions,'max_fit_numeric_error':fit_worst,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'selection_independently_checked':True,'usd_translation_accounts':len(summary),'daily_return_block_bootstrap_checks':bootstrap_checks,'scope':'Independent Decimal two Coinbase input series and frozen prior masks/daily-audit receipt; raw BTC ZIP/funding; USD targets and 24h log peg level, negative-slope normal-equation refit/calendar HAC; past-label availability including extra delay; all MSE/signals/cash-zero events; closed-form postcost quantities/no-trade and Decimal hourly-DD/annual/margin accounts; USD translations, summary, identity and block bootstrap. Current API vintage and USD/native USDT basis remain limitations.'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
