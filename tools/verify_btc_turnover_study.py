"""Independent BTC estimated transfer-share incremental information and all raw accounts verification."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile,urllib.parse
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
WEEK=7*DAY
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())

def source_check():
 from audit_btc_turnover_data import audit
 raw,report=audit(save=False);assert report['normalized_sha256']=='dd175183838fb123c6bed86adca795e20d28ecaacdc9797b15e3c18b04003040';return raw,report

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
 out=Path(out);payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={};rawvolume={};rawquote={};rawmarks={};rawclock={};raw_ohlc={};archive_count=0
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
      raw_ohlc[(key,t)]=tuple(D(rr[j]) for j in (1,2,3,4));rawprice[(key,t)]=(D(rr[1]),D(rr[4]));rawvolume[(key,t)]=D(rr[5]);rawquote[(key,t)]=D(rr[7]);ct=int(rr[6]);rawclock[(key,t)]=ct//1000 if ct>10**14 else ct
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
 source,source_counts=source_check();mask=ROOT/'data/btc-venue-20261003/masks.json';assert sha(mask.read_bytes())=='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd';excluded=set(read(mask)['binance_spot_no_trade']);assert excluded=={t for (k,t),v in rawvolume.items() if k=='BS' and v<=0}
 feature_checks=regressions=forecast_checks=0;fit_worst=feature_worst=0.;raw_features={};raw_predictions={};saved_predictions={};target={}
 assert sha(gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes()))=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4'
 for key in KEYS:
  for t,r in rows[key].items():assert (D(r[1]),D(r[4]))==rawprice[(key,t)] and r[5]==rawclock[(key,t)]
 raw_close_checks={}
 def raw_close(t):
  r=rawprice.get(('BS',t-HOUR));v=float(r[1]) if r is not None and t-HOUR not in excluded and rawclock[('BS',t-HOUR)]==t-1 and r[1].is_finite() and r[1]>0 else None;raw_close_checks[t]=v is not None;return v
 def logreturn(a,b):
  x,y=raw_close(a),raw_close(b);return math.log(y/x) if x is not None and y is not None else None
 def near(a,b,tolerance=2e-9):
  nonlocal fit_worst
  aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float);assert aa.shape==bb.shape;error=float(np.max(np.abs(aa-bb))) if aa.size else 0.;fit_worst=max(fit_worst,error);assert np.allclose(aa,bb,rtol=2e-8,atol=tolerance),(aa,bb,error)
 def feature_equal(actual,expected,path=''):
  nonlocal feature_worst
  if isinstance(expected,dict):
   for k,v in expected.items():feature_equal(actual[k],v,path+'.'+k)
  elif isinstance(expected,list):
   assert len(actual)==len(expected),(path,len(actual),len(expected))
   for a,b in zip(actual,expected):feature_equal(a,b,path+'[]')
  elif expected is None or isinstance(expected,(str,int,bool)):assert actual==expected,(path,actual,expected)
  else:
   error=abs(actual-expected);feature_worst=max(feature_worst,error/max(1.,abs(expected)))
   assert math.isclose(actual,expected,rel_tol=3e-10,abs_tol=2e-12),(path,actual,expected,error)
 for t in range(ms('2020-01-06'),ms('2026-09-01'),WEEK):target[t]={'end':t+WEEK,'value':logreturn(t,t+WEEK)}
 observed_targets=read(out/'labels.json.gz');assert set(observed_targets)=={str(t) for t in target}
 for t,v in target.items():
  actual=observed_targets[str(t)];assert actual['end']==v['end']
  if v['value'] is None:assert actual['value'] is None
  else:near(actual['value'],v['value'],1e-14)
 columns={'NV_INFO':('r7','r28','raw','share'),'NV_RAW':('r7','r28','raw'),'NV_ADJ':('r7','r28','adjusted'),'NV_PRICE':('r7','r28')};feature_cols=('r7','r28','raw','share','adjusted')
 for lag in (0,7):
  ff={};observed=read(out/f'features-lag{lag}.json.gz');assert [r['source'] for r in observed]==list(target)
  for actual in observed:
   t=actual['source'];effective=t-lag*DAY;last=effective-2*DAY;wanted=[last-(27-i)*DAY for i in range(28)];observations=[source.get(u) for u in wanted]
   good=[]
   for u,r in zip(wanted,observations):
    valid=r is not None and r['valid'] and r['day']==u and r['end']==u+DAY and r['base_assumed_available']==u+2*DAY and r['base_assumed_available']<=effective
    if valid:valid=all(r[k] is not None and math.isfinite(r[k]) and r[k]>0 for k in ('adjusted','raw','supply')) and r['adjusted']<=r['raw']
    good.append(bool(valid))
   values={k:[r[k] if r is not None else None for r in observations] for k in ('adjusted','raw','supply')};price_times=[last+DAY-n*DAY for n in (0,7,28)];prices=[raw_close(u) for u in price_times]
   e={'source':t,'availability_delay_days':lag,'effective_time':effective,'last_observation_day':last,'last_assumed_available':last+(2+lag)*DAY,'last_market_close':last+DAY,'input_days':wanted,'daily_inputs':values,'bad_days':[u for u,v in zip(wanted,good) if not v],'price_times':price_times,'price_closes':prices,'bad_price_times':[u for u,v in zip(price_times,prices) if v is None],'adjusted_sum28':None,'raw_sum28':None,'latest_supply':None};e.update({k:None for k in feature_cols})
   if all(good):
    A=sum(D(v) for v in values['adjusted']);O=sum(D(v) for v in values['raw']);S=D(values['supply'][-1]);e.update(adjusted_sum28=float(A),raw_sum28=float(O),latest_supply=float(S),raw=float(O.ln()-S.ln()),share=float(A.ln()-O.ln()),adjusted=float(A.ln()-S.ln()));assert e['share']<=0 and abs(e['adjusted']-e['raw']-e['share'])<1e-12
   if all(v is not None for v in prices):e.update(r7=float(D(prices[0]).ln()-D(prices[1]).ln()),r28=float(D(prices[0]).ln()-D(prices[2]).ln()))
   e['valid']=all(good) and all(e[k] is not None and math.isfinite(e[k]) for k in feature_cols);ff[t]=e;feature_equal(actual,e);feature_checks+=1
  pp={};observed=read(out/f'forecasts-lag{lag}.json.gz');assert [p['source'] for p in observed]==list(target)
  for actual in observed:
   t=actual['source'];train=[u for u in range(t-105*WEEK,t-WEEK,WEEK) if u in ff and ff[u]['valid'] and target[u]['value'] is not None and target[u]['end']<=t-DAY];assert actual['training_weeks']==train and actual['training_n']==len(train) and actual['training_label_end']==max((target[u]['end'] for u in train),default=None);models={}
   for name,cols in columns.items():
    p=actual['models'][name];assert p['training_n']==len(train)
    if not ff[t]['valid'] or len(train)<52:assert p['mu'] is None and p['se'] is None;models[name]=None;continue
    X=np.array([[1]+[ff[u][c] for c in cols] for u in train]);y=np.array([target[u]['value'] for u in train]);current=np.array([1]+[ff[t][c] for c in cols]);fit=independent_fit(X,y,train,current,False)
    if fit is None:assert p['mu'] is None;models[name]=None;continue
    for k in ('constraint_active','unrestricted_rank','rank','free_columns'):assert p[k]==fit[k],(lag,t,name,k)
    for k in ('mu','se','beta','covariance','unrestricted_beta','residual_ss'):near(p[k],fit[k])
    near(p['feature_mean'],X[:,1:].mean(axis=0),1e-13);models[name]=fit;regressions+=1
   pp[t]=models;forecast_checks+=1
  raw_features[lag]=ff;raw_predictions[lag]=pp;saved_predictions[lag]={v['source']:v for v in observed};print(json.dumps({'stage':'independent_turnover_features_and_fits','lag':lag,'fits':regressions,'features':feature_checks,'max_fit_error':fit_worst}),flush=True)
 forecast_results=read(out/'forecast-summary.json')
 for period,(start,end) in {'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}.items():
  for lag in (0,7):
   paired=[t for t,models in raw_predictions[lag].items() if start<=t<end and target[t]['end']<=end and target[t]['value'] is not None and all(p is not None for p in models.values())]
   for name in ('NV_INFO','NV_RAW','NV_ADJ','NV_PRICE'):
    actual=forecast_results[period][str(lag)][name];assert actual['n']==len(paired) and actual['paired_source_times']==paired
    if paired:
     predictions=[raw_predictions[lag][t][name] for t in paired];near(actual['mse'],sum((p['mu']-target[t]['value'])**2 for p,t in zip(predictions,paired))/len(paired));near(actual['sign_accuracy'],sum(np.sign(p['mu'])==np.sign(target[t]['value']) for p,t in zip(predictions,paired))/len(paired));assert actual['constraint_weeks']==sum(p['constraint_active'] for p in predictions)
    else:assert actual['mse'] is None
    beta_count=sum(raw_predictions[lag][t][name]['beta'][-1]<=0 for t in paired) if name in ('NV_INFO','NV_RAW','NV_ADJ') else None;assert actual['nonpositive_turnover_beta_weeks']==beta_count
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk=float(p.name.split('-risk')[1].split('-lag')[0]);lag=int(p.name.split('-lag')[1].split('.')[0])
  for e in plan:
   t=e['source_time'];week=t-dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).weekday()*DAY;detail=e['detail'];f=raw_features[lag][week];models=raw_predictions[lag][week];assert detail['week_source']==week;feature_equal(detail['feature'],f)
   assert detail['models']==saved_predictions[lag][week]['models'] and detail['training_n']==saved_predictions[lag][week]['training_n'] and detail['training_label_end']==saved_predictions[lag][week]['training_label_end'];i=dayidx[t];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6
   info,add=models['NV_INFO'],models['NV_RAW']
   def eligible(pred):
    if pred is None:return 0
    hurdle=math.log1p(.0023 if pred['mu']>0 else .0013);return sign(pred['mu']) if abs(pred['mu'])>hurdle+pred['se'] else 0
   side=0;delta=None
   if info is not None and add is not None:
    delta=info['mu']-add['mu'];gate=eligible(info)
    if gate and info['beta'][-1]>0 and abs(delta)>1e-12 and delta*info['mu']>0:side=gate
   if name in ('NV_RAW','NV_ADJ'):over=eligible(models[name]) if models[name] is not None and models[name]['beta'][-1]>0 else 0
   else:over=side if name=='NV_INFO' else -side if name=='NV_INV' else 0 if name=='NV_TREND' else eligible(models[name])
   direction=over if over else max(0,score)
   assert detail['override']==bool(over) and detail['core_fallback']==(not over)
   if delta is None:assert detail['increment'] is None
   else:near(detail['increment'],delta)
   assert detail['score']==score and detail['signal']==direction and abs(detail['vol']-vol)<1e-9 and abs(detail['risk']-w)<1e-9
   for k,v in [('BS',max(direction,0)*w),('BP',min(direction,0)*w)]:assert abs(e['weights'][k]-v)<1e-9
   assert sum(abs(v) for v in e['weights'].values())<=1+1e-12;raw_signals[name,risk,lag,t]=e;plans_checked+=1
 print(json.dumps({'stage':'independent_plans','daily_decisions':plans_checked}),flush=True)
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}-lag{x['availability_delay_days']}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_turnover_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
  assert x['turnover_input_sha256']=='dd175183838fb123c6bed86adca795e20d28ecaacdc9797b15e3c18b04003040' and x['btc_no_trade_mask_sha256']=='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd'
  multiplier=2 if x['scenario']=='cost_x2' else 1;assert model['fee_bps']=={'BS':10*multiplier,'BP':5*multiplier} and model['impact_bps']==1.5*multiplier and model['extra_delay_hours']=={'delay1':1,'delay24':24}.get(x['scenario'],0) and x['availability_delay_days']==(7 if x['scenario']=='data_delay7' else 0) and x['risk_target']==(.1 if x['scenario']=='risk10' else .2)
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
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['risk_target'],x['availability_delay_days'],e['source_time']) in raw_signals
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
 assert len(reports)==72
 summary=read(out/'summary.json');selection=read(out/'selection.json');a=summary['main-NV_INFO-base']['metrics'];b=summary['recent-NV_INFO-base']['metrics'];checks={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-NV_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):checks[c]=all(summary[p+'-NV_INFO-'+c]['metrics']['net_pnl']>0 for p in ('main','recent'))
 extra={}
 for name in ('NV_RAW','NV_ADJ','NV_PRICE','NV_TREND'):extra['net_beats_'+name+'_both']=all(summary[p+'-NV_INFO-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in ('main','recent'))
 extra['dd_no_worse_raw_both']=all(summary[p+'-NV_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-NV_RAW-base']['metrics']['max_drawdown_pct'] for p in ('main','recent'))
 for ctrl in ('NV_RAW','NV_PRICE'):extra['mse_strictly_better_'+ctrl+'_both']=all(forecast_results[p]['0']['NV_INFO']['mse'] is not None and forecast_results[p]['0'][ctrl]['mse'] is not None and forecast_results[p]['0']['NV_INFO']['mse']<forecast_results[p]['0'][ctrl]['mse'] for p in ('main','recent'))
 for period in ('main','recent'):extra[period+'_enough_forecasts']=forecast_results[period]['0']['NV_INFO']['n']>=(52 if period=='main' else 20)
 assert selection['checks']==checks and selection['information_increment']==extra and selection['passed']==(all(checks.values()) and all(extra.values()))
 assert set(summary)=={r['file'].removesuffix('.json.gz') for r in reports}
 for key,row in summary.items():
  account=read(out/(key+'.json.gz'));assert row=={'metrics':account['metrics'],'annual':account['periods']['yearly']}
 identity=read(out/'control-identity.json');uncertainty=read(out/'uncertainty.json');bootstrap_checks=0
 for period in ('main','recent'):
  actual=read(out/f'{period}-NV_TREND-base.json.gz');saved=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');near(actual['daily_returns'],saved['daily_returns']);near(identity[period]['daily_return_max_error'],max(abs(a-b) for a,b in zip(actual['daily_returns'],saved['daily_returns'])))
  for metric in ('return_pct','max_drawdown_pct','fees','impact','funding'):near(actual['metrics'][metric],saved['metrics'][metric]);near(identity[period]['metric_errors'][metric],abs(actual['metrics'][metric]-saved['metrics'][metric]))
  ret={n:np.array(read(out/f'{period}-{n}-base.json.gz')['daily_returns']) for n in ('NV_INFO','NV_RAW','NV_ADJ','NV_PRICE','NV_INV','NV_TREND')}
  for name,r in ret.items():
   for category,series in [('mean',r)]+[('vs_'+n,r-ret[n]) for n in ('NV_RAW','NV_ADJ','NV_PRICE','NV_TREND')]:
    # Independent circular block sums using prefix differences, not original element-index matrix.
    n=len(series);prefix=np.r_[0.,np.cumsum(np.r_[series,series])]
    for block,actual in zip((7,14,28),uncertainty[period+'-'+name][category]):
     count=math.ceil(n/block);rng=np.random.default_rng(1490+block);starts=rng.integers(n,size=(2000,count));lengths=np.full(count,block);lengths[-1]=n-(count-1)*block;sums=(prefix[starts+lengths]-prefix[starts]).sum(axis=1)/n*100
     assert actual['block_days']==block and actual['replicates']==2000;near(actual['mean_daily_pct'],math.fsum(series)/n*100,1e-13);near(actual['ci95'],np.quantile(sums,[.025,.975]),1e-13);bootstrap_checks+=1
 activity=read(out/'activity.json')
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);period,name=p.name.split('-')[:2];risk=float(p.name.split('-risk')[1].split('-lag')[0]);lag=int(p.name.split('-lag')[1].split('.')[0]);key=name+('-risk10' if risk==.1 else '-data_delay7' if lag==7 else '-base')
  expected={'override_days':sum(e['detail'].get('override',False) for e in plan),'override_weeks':len({e['detail']['week_source'] for e in plan if e['detail'].get('override',False)}),'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_feature_days':sum(not e['detail']['feature']['valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['NV_INFO']['mu'] is None for e in plan),'nonpositive_share_beta_days':sum(e['detail']['models']['NV_INFO']['mu'] is not None and e['detail']['models']['NV_INFO']['beta'][-1]<=0 for e in plan)}
  assert activity[period][key]==expected
  if risk==.2 and lag==0:
   for scenario in ('cost_x2','delay1','delay24'):assert activity[period][name+'-'+scenario]==expected
 proof={'accounts':len(reports),'raw_archives':archive_count,'transfer_source_audit':source_counts,'raw_spot_boundary_queries':len(raw_close_checks),'raw_valid_spot_boundary_closes':sum(raw_close_checks.values()),'raw_feature_weeks':feature_checks,'raw_forecast_weeks':forecast_checks,'independent_model_fits':regressions,'max_fit_numeric_error':fit_worst,'max_feature_relative_error':feature_worst,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'selection_independently_checked':True,'daily_return_block_bootstrap_checks':bootstrap_checks,'scope':'Independent raw BTC ZIP OHLC/volume/funding and separate Decimal public transfer parsing, same-provider supply cap identity and 100 BTC snapshot discrepancy preservation. Not independent change-heuristic or chain-supply reconstruction. Separate 28 consecutive daily inputs/latest stock/3 exact BTC price boundaries/D+2(+7), 4 unconstrained normal equations/calendar HAC, positive share slope and INFO-RAW incremental gate; RAW/ADJ own positive slope/cost-SE only. Common MSE/weeks, weekly direction/daily risk, analytic postcost quantities/no-trades and Decimal account/hourly DD/exposure/annual/vol/margin; gates, E_SPOT identity and block uncertainty. Current vintages not first releases or unused OOS; no other-asset trading or control promotion.'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps({k:v for k,v in proof.items() if k!='transfer_source_audit'}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
