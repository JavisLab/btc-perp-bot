"""Independent TS raw Decimal features, normal equations/calendar HAC and perp accounting.
New strategy/simulator are not imported. Frozen prior raw-market receipts are reused.
"""
import argparse,datetime as dt,gzip,json,math,itertools
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR,getcontext
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP');getcontext().prec=60;WEEK=7*DAY
IDS=('TS_INFO','TS_FUND','TS_TERM','TS_PRICE','TS_INV','TS_TREND');CONTROLS=('TS_FUND','TS_TERM','TS_PRICE','TS_TREND');COLS={'TS_INFO':('r7','r28','tau','funding','carry'),'TS_FUND':('r7','r28','tau','funding'),'TS_TERM':('r7','r28','tau','carry'),'TS_PRICE':('r7','r28','tau')}
DATA_SHA='5a398450cb7522e2ae8d6ead313ccfb6195f152f8e732eef08d6f61999da30c1';PRESSURE_SHA='b7bcc90d73a29cf1f2d84dcd752025a6034d356ab337d7ce48eab82f09869d5f';PERIODS={'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())

def independent_fit(X,y,dates,current,constrain):
 n,k=X.shape;rank=np.linalg.matrix_rank(X)
 if rank<k:return None
 coef=np.linalg.solve(X.T@X,X.T@y);unrestricted=coef.copy();active=bool(constrain and coef[-1]<0);free=list(range(k-int(active)));F=X[:,free];bread=np.linalg.inv(F.T@F);b=np.linalg.solve(F.T@F,F.T@y);residual=y-F@b;lo=min(dates);grid=np.zeros((int((max(dates)-lo)//WEEK)+1,len(free)))
 for date,row,res in zip(dates,F,residual):grid[int((date-lo)//WEEK)]=row*res
 meat=grid.T@grid
 for lag in range(1,2):
  cross=grid[lag:].T@grid[:-lag];meat+=(2-lag)/2*(cross+cross.T)
 cov_small=n/(n-len(free))*bread@meat@bread;beta=np.zeros(k);cov=np.zeros((k,k));beta[free]=b;cov[np.ix_(free,free)]=cov_small
 return {'mu':float(current@beta),'se':math.sqrt(max(0,float(current@cov@current))),'beta':beta,'covariance':cov,'constraint_active':active,'unrestricted_beta':unrestricted,'unrestricted_rank':int(rank),'rank':len(free),'free_columns':free,'residual_ss':float(residual@residual)}

def run(out):
 out=Path(out);rawmarket=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes());assert sha(rawmarket)=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4';proofp=ROOT/'runs/btc-continuity-20261003/verification.json';assert sha(proofp.read_bytes())=='38f6da0357b82a2067fed0869fd27e7a8cb1ad937044a392486fdd0d9a9e0382';market_receipt={'sha256':sha(proofp.read_bytes()),'path':str(proofp.relative_to(ROOT)),'scope':'Prior independent 329 ZIP market audit reused, not rerun; all new account events/days checked separately'};payload=json.loads(rawmarket)['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={r[0]:(D(r[2]),r[3]) for r in payload['funding']};rawprice={};rawvolume={};rawmarks={t:tuple(D(r[j]) for j in (1,2,3,4)) for t,r in marks['BP'].items()};spot={}
 for t,r in rows['BS'].items():
  rawprice['BS',t]=(D(r[1]),D(r[4]));rawvolume['BS',t]=D(1)
  if (t+HOUR)%DAY==0 and r[5]==t+HOUR-1:spot[t+HOUR]=r[4]
 pressure=read(ROOT/'data/btc-pressure-20261004/daily.json.gz');assert sha(canonical(pressure))==PRESSURE_SHA;pressure_proof=read(ROOT/'data/btc-pressure-20261004/independent-audit.json');assert pressure_proof['daily_sha256']==PRESSURE_SHA and pressure_proof['max_scaled_error']==0;raw_pressure_hours=0
 for e in pressure['rows']:
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
 feature_checks=regressions=forecast_checks=0;fit_worst=feature_worst=0.;ff={};pp={};saved_predictions={}
 term=read(ROOT/'data/btc-term-20261004/contracts.json.gz');assert sha(canonical(term))==DATA_SHA;term_receipt=read(ROOT/'data/btc-term-20261004/independent-audit.json');assert term_receipt['canonical_sha256']==DATA_SHA and term_receipt['raw_rows_exact'] and term_receipt['archives']==173
 contracts={c['symbol']:c for c in term['contracts']};quotes={sym:{int(e['raw'][0]):e for e in c['rows']} for sym,c in contracts.items()}
 def near(a,b,tolerance=2e-9):
  nonlocal fit_worst
  aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float);assert aa.shape==bb.shape;error=float(np.max(np.abs(aa-bb))) if aa.size else 0.;fit_worst=max(fit_worst,error);assert np.allclose(aa,bb,rtol=2e-8,atol=tolerance),(aa,bb,error)
 def feature_equal(a,b,path=''):
  nonlocal feature_worst
  if isinstance(b,dict):
   assert set(a)==set(b),(path,set(a)^set(b))
   for k,v in b.items():feature_equal(a[k],v,path+'.'+k)
  elif isinstance(b,list):
   assert len(a)==len(b),(path,len(a),len(b))
   for x,y in zip(a,b):feature_equal(x,y,path+'[]')
  elif b is None or isinstance(b,(str,int,bool)):assert a==b,(path,a,b)
  else:
   error=abs(a-b)/max(1,abs(b));feature_worst=max(feature_worst,error);assert math.isclose(a,b,rel_tol=3e-10,abs_tol=2e-12),(path,a,b)
 def observation(t,risk=.2):
  i=dayidx.get(t,-1)
  if i<128:return None
  hist=daily[i-20:i+1]
  if not np.all(np.isfinite(hist)):return None
  rr=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(rr)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in rr)/19*365);weight=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda x:int(x>0)-int(x<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6
  return (score,weight,vol) if math.isfinite(score) else None
 def price(t):
  p=rawprice.get(('BP',t-HOUR));r=rows['BP'].get(t-HOUR)
  return p[1] if p is not None and rawvolume['BP',t-HOUR]>0 and r[5]==t-1 and p[1].is_finite() and p[1]>0 else None
 target={}
 for t in range(ms('2020-01-06'),ms('2026-09-01'),WEEK):
  a,b=price(t),price(t+WEEK);target[t]={'end':t+WEEK,'value':float(b.ln()-a.ln()) if a is not None and b is not None else None}
 for k,v in read(out/'labels.json.gz').items():feature_equal(v,target[int(k)])
 for lag in (0,7):
  ff[lag]={};pp[lag]={};saved_predictions[lag]={};observed=read(out/f'features-lag{lag}.json.gz');assert [e['source'] for e in observed]==list(target)
  for actual in observed:
   t=actual['source'];C=t-lag*DAY;symbols=[]
   for sym,c in contracts.items():
    observed_past=[u for u,v in quotes[sym].items() if u+HOUR<=C and v['valid']]
    if observed_past and c['expiry_date_proxy']>C:symbols.append(sym)
   symbols.sort(key=lambda sym:contracts[sym]['expiry_date_proxy']);pair=symbols[:2];rr=[quotes[sym].get(C-HOUR) for sym in pair];goodcurve=len(pair)==2 and all(r is not None and r['valid'] and int(r['raw'][6])==C-1 for r in rr);times=[t-(28-i)*DAY for i in range(29)];closes=[price(u) for u in times];goodprice=all(p is not None for p in closes);buckets=[C-WEEK+i*8*HOUR for i in range(21)];settled=[r for r in payload['funding'] if C-WEEK<=r[3]<C];settled.sort(key=lambda r:(r[3]//(8*HOUR),r[0]));counts={u:sum(r[3]//(8*HOUR)*(8*HOUR)==u for r in settled) for u in buckets};goodfund=all(n==1 for n in counts.values()) and all(D(r[2]).is_finite() for r in settled)
   e={'source':t,'derivative_lag':lag,'derivative_cutoff':C,'eligible_symbols':symbols,'selected_symbols':pair,'selected_expiry_dates':[contracts[s]['expiry_date_proxy'] for s in pair],'selected_closes':[float(r['raw'][4]) if r is not None else None for r in rr],'selected_valid':[r is not None and r['valid'] for r in rr],'curve_valid':goodcurve,'price_times':times,'price_closes':[float(p) if p is not None else None for p in closes],'price_valid':goodprice,'funding_buckets':buckets,'funding_rows':settled,'funding_valid':goodfund,'valid':goodcurve and goodprice and goodfund,'r7':None,'r28':None,'tau':None,'funding':None,'carry':None}
   if goodcurve:
    a,b=[contracts[s]['expiry_date_proxy'] for s in pair];e['tau']=float(D(a-C)/D(365*DAY));e['carry']=float(D(365*DAY)/D(b-a)*(D(rr[1]['raw'][4]).ln()-D(rr[0]['raw'][4]).ln()))
   if goodprice:e['r7']=float(closes[-1].ln()-closes[-8].ln());e['r28']=float(closes[-1].ln()-closes[0].ln())
   if goodfund:e['funding']=float(D(365)/D(7)*sum((D(r[2]) for r in settled),D(0)))
   feature_equal(actual,e);ff[lag][t]=e;feature_checks+=1
  observed=read(out/f'forecasts-lag{lag}.json.gz');assert [p['source'] for p in observed]==list(target)
  for actual in observed:
   t=actual['source'];f=ff[lag];train=[u for u in range(t-105*WEEK,t-WEEK,WEEK) if u in f and f[u]['valid'] and target[u]['value'] is not None and target[u]['end']<=t-DAY];assert actual['training_weeks']==train and actual['training_n']==len(train) and actual['training_label_end']==max((target[u]['end'] for u in train),default=None);models={}
   for name,cols in COLS.items():
    p=actual['models'][name];assert p['training_n']==len(train)
    if not f[t]['valid'] or len(train)<52:assert p['mu'] is None and p['se'] is None;models[name]=None;continue
    X=np.array([[1.]+[f[u][c] for c in cols] for u in train]);y=np.array([target[u]['value'] for u in train]);current=np.array([1.]+[f[t][c] for c in cols]);fit=independent_fit(X,y,train,current,False)
    if fit is None:assert p['mu'] is None;models[name]=None;continue
    for k,v in fit.items():
     if isinstance(v,(bool,int,list)):assert p[k]==v
     else:near(p[k],v)
    near(p['feature_mean'],X[:,1:].mean(axis=0));models[name]=fit;regressions+=1
   pp[lag][t]=models;saved_predictions[lag][t]=actual;forecast_checks+=1
 print(json.dumps({'stage':'independent_term_features_hac','features':feature_checks,'fits':regressions,'max_feature_error':feature_worst,'max_fit_error':fit_worst}),flush=True)
 bootstrap_checks=0
 def verify_bootstrap(series,records):
  nonlocal bootstrap_checks
  n=len(series);prefix=np.r_[0.,np.cumsum(np.r_[series,series])]
  for block,actual in zip((7,14,28),records):
   count=math.ceil(n/block);rng=np.random.default_rng(1490+block);starts=rng.integers(n,size=(2000,count));lengths=np.full(count,block);lengths[-1]=n-(count-1)*block;sums=(prefix[starts+lengths]-prefix[starts]).sum(axis=1)/n*100
   assert actual['block_days']==block and actual['replicates']==2000;near(actual['mean_daily_pct'],math.fsum(series)/n*100,1e-13);near(actual['ci95'],np.quantile(sums,[.025,.975]),1e-13);bootstrap_checks+=1
 forecast_results=read(out/'forecast-summary.json')
 for period,(start,end) in PERIODS.items():
  for lag in (0,7):
   valid=[t for t in target if start<=t<end and target[t]['end']<=end and target[t]['value'] is not None];pair=[t for t in valid if all(p is not None for p in pp[lag][t].values())];fc=forecast_results[period][str(lag)];assert fc['common_weeks']==pair and fc['n']==len(pair) and fc['eligible_label_weeks']==len(valid);near(fc['coverage'],len(pair)/len(valid));y=np.array([target[t]['value'] for t in pair])
   for name in COLS:
    r=fc['models'][name];mu=np.array([pp[lag][t][name]['mu'] for t in pair]);bb=[pp[lag][t][name]['beta'][-1] for t in pair];assert r['n']==len(pair) and r['negative_last_beta_weeks']==sum(b<0 for b in bb)
    if pair:near(r['mse'],np.mean((mu-y)**2),1e-12);near(r['sign_accuracy'],np.mean(np.sign(mu)==np.sign(y)));near(r['median_last_beta'],np.median(bb))
    else:assert r['mse'] is None and r['sign_accuracy'] is None and r['median_last_beta'] is None
 def direction(name,p,score):
  def gate(q):return (1 if q['mu']>0 else -1) if abs(q['mu'])>q['se']+math.log1p(.0013) else 0
  info,base=p['TS_INFO'],p['TS_FUND'];delta=None;override=0
  if info is not None and base is not None:
   delta=info['mu']-base['mu']
   if info['beta'][-1]<0 and abs(delta)>1e-12 and delta*info['mu']>0:override=gate(info)
  if name=='TS_INV':override=-override
  elif name=='TS_TREND':override=0
  elif name not in ('TS_INFO','TS_INV'):
   model=p[name];override=gate(model) if model is not None and (name=='TS_PRICE' or model['beta'][-1]<0) else 0
  return float(override) if override else score,bool(override),delta
 plans_checked=0;raw_signals={}
 for path in sorted(out.glob('*-plan-*.json.gz')):
  plan=read(path);period,name=path.name.split('-')[:2];risk=float(path.name.split('-risk')[1].split('-')[0]);lag=int(path.name.split('-lag')[1].split('.')[0]);start,end=PERIODS[period];assert [e['source_time'] for e in plan]==list(range(start,end,DAY))
  for e in plan:
   t=e['source_time'];week=t-dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).weekday()*DAY;d=e['detail'];p=pp[lag][week];saved=saved_predictions[lag][week];assert d['week_source']==week and d['training_n']==saved['training_n'] and d['training_label_end']==saved['training_label_end'] and d['models']==saved['models'];feature_equal(d['feature'],ff[lag][week]);obs=observation(t,risk)
   if obs is None:assert e['weights'] is None and d['risk_missing'];continue
   score,w,vol=obs;signal,over,delta=direction(name,p,score);assert d['score']==score and d['signal']==signal and d['override']==over and d['core_fallback']==(not over);near(d['risk'],w,1e-10);near(d['vol'],vol,1e-10);assert e['weights']['BS']==0.;near(e['weights']['BP'],signal*w,1e-10)
   if delta is None:assert d['increment'] is None
   else:near(d['increment'],delta,1e-10)
   raw_signals[name,risk,lag,t]=e;plans_checked+=1
 print(json.dumps({'stage':'independent_daily_plans','decisions':plans_checked}),flush=True)
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','predictions','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/x['schedule_file']);planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_term_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
  assert x['term_input_sha256']==DATA_SHA and x['derivative_lag']==(7 if x['scenario']=='data_delay7' else 0)
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
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['risk_target'],x['derivative_lag'],e['source_time']) in raw_signals
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
 summary=read(out/'summary.json');selection=read(out/'selection.json');activity=read(out/'activity.json')
 for period in PERIODS:
  for name in IDS:
   for scenario in ('base','cost_x2','delay1','delay24','risk10','data_delay7'):
    risk=.1 if scenario=='risk10' else .2;lag=7 if scenario=='data_delay7' else 0;plan=read(out/f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz');expected={'override_days':sum(e['detail'].get('override',False) for e in plan),'override_weeks':len({e['detail']['week_source'] for e in plan if e['detail'].get('override')}),'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_feature_days':sum(not e['detail']['feature']['valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['TS_INFO']['mu'] is None for e in plan),'nonnegative_carry_beta_days':sum(e['detail']['models']['TS_INFO']['mu'] is not None and e['detail']['models']['TS_INFO']['beta'][-1]>=0 for e in plan)};assert activity[period][name+'-'+scenario]==expected
 a=summary['main-TS_INFO-base']['metrics'];b=summary['recent-TS_INFO-base']['metrics'];checks={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-TS_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):checks[c]=all(summary[p+'-TS_INFO-'+c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in CONTROLS:extra['net_beats_'+name+'_both']=all(summary[p+'-TS_INFO-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_FUND_both']=all(summary[p+'-TS_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-TS_FUND-base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for ctrl in ('TS_FUND','TS_PRICE'):extra['mse_strictly_better_'+ctrl+'_both']=all(forecast_results[p]['0']['models']['TS_INFO']['mse'] is not None and forecast_results[p]['0']['models'][ctrl]['mse'] is not None and forecast_results[p]['0']['models']['TS_INFO']['mse']<forecast_results[p]['0']['models'][ctrl]['mse'] for p in PERIODS)
 for p in PERIODS:
  f=forecast_results[p]['0'];beta=f['models']['TS_INFO']['median_last_beta'];extra[p+'_enough_forecasts']=f['n']>=(52 if p=='main' else 20);extra[p+'_coverage']=f['coverage']>=.8;extra[p+'_negative_carry_beta']=beta is not None and beta<0;extra[p+'_new_information_active']=activity[p]['TS_INFO-base']['override_weeks']>=(20 if p=='main' else 5)
 assert selection['checks']==checks and selection['information_increment']==extra and selection['passed']==(all(checks.values()) and all(extra.values()))
 assert set(summary)=={r['file'].removesuffix('.json.gz') for r in reports}
 for key,row in summary.items():
  account=read(out/(key+'.json.gz'));assert row=={'metrics':account['metrics'],'annual':account['periods']['yearly']}
 uncertainty=read(out/'uncertainty.json')
 for period in PERIODS:
  ret={n:np.array(read(out/f'{period}-{n}-base.json.gz')['daily_returns']) for n in IDS}
  for name,r in ret.items():
   for category,series in [('mean',r)]+[('vs_'+n,r-ret[n]) for n in CONTROLS]:verify_bootstrap(series,uncertainty[period+'-'+name][category])
 identity=read(out/'control-identity.json')
 for period in PERIODS:
  old=read(ROOT/f'runs/btc-pressure-20261004/{period}-TP_TREND-base.json.gz');new=read(out/f'{period}-TS_TREND-base.json.gz');errors={k:abs(old['metrics'][k]-new['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(old['daily_returns'],new['daily_returns']));assert identity[period]['metric_errors']==errors and identity[period]['daily_return_max_error']==daily and max(errors.values())<1e-7 and daily<1e-9
 proof={'accounts':len(reports),'new_term_source_receipt':term_receipt,'perp_raw_hour_tuple_receipt_reuse':pressure_proof,'market_source_receipt_reuse':market_receipt,'raw_feature_weeks':feature_checks,'raw_forecast_weeks':forecast_checks,'independent_model_fits':regressions,'max_feature_scaled_error':feature_worst,'max_fit_numeric_error':fit_worst,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'selection_independently_checked':True,'return_block_bootstrap_checks':bootstrap_checks,'scope':'New 26 BTC dated contracts/173ZIP raw-input receipt; Decimal log ratio, all past-listed contract selection with no replacement on missing quote, nominal date maturity proxy, actual-ms settled 21-funding, current BP price controls/label, common weekly purge and normal-equation calendar-HAC. Old 329 market/80 perp raw receipts reused, not rerun. Independent pure-perp long/short target quantities/cash/funding/margin/annual/selection/CI; no prior-vintage archive/OOS or live trading evidence.'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
