"""Independent FINRA raw/API, uncentered constrained normal equations, calendar-grid HAC and Decimal BTC accounts."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())

def source_check():
 data=ROOT/'data/btc-etfshort-20261002';frozen=read(data/'btc-etfshort.json');assert sha((data/'btc-etfshort.json').read_bytes())=='759c0daec5f061c2a5dfa9c29982faadad3fde971c0c70813fe71c02b1221a23';source={};indexed=set()
 for p in (data/'indices').glob('*.html'):
  indexed.update(re.findall(r'CNMSshvol(\d{8})\.txt',p.read_text()))
 indexed={d for d in indexed if '20240111'<=d<='20260831'}
 for p in sorted((data/'raw').glob('CNMSshvol*.txt')):
  date=p.stem[-8:];meta=read(Path(str(p)+'.meta.json'));assert sha(p.read_bytes())==meta['subset_sha256'];values={}
  for r in csv.DictReader(p.read_text().splitlines(),delimiter='|'):
   assert r['Date']==date and r['Symbol'] in ('IBIT','FBTC','GBTC') and r['Symbol'] not in values
   short,exempt,total=(D(r[k]) for k in ('ShortVolume','ShortExemptVolume','TotalVolume'));assert 0<=exempt<=short<=total and total>0;values[r['Symbol']]={'short':r['ShortVolume'],'exempt':r['ShortExemptVolume'],'total':r['TotalVolume'],'markets':r['Market']}
  assert len(values)==3 and meta['retained_rows']==3 and meta['source_trailer_records']>=3 and re.fullmatch('[0-9a-f]{64}',meta['full_response_sha256']);source[date]=values
 assert len(source)==661 and set(source)==indexed and frozen['rows']==[{'date':d,'values':v} for d,v in sorted(source.items())]
 api_matches=0;log=read(data/'api-fetch-log.json')
 for symbol in ('IBIT','FBTC','GBTC'):
  p=data/(symbol+'-api-raw.json');entries=json.loads(p.read_text(),parse_float=Decimal);receipt=next(r for r in log if r['symbol']==symbol);assert sha(p.read_bytes())==receipt['response_sha256'] and len(entries)==receipt['records']==int(receipt['response_headers']['record-total']);group=defaultdict(list)
  for e in entries:assert e['securitiesInformationProcessorSymbolIdentifier']==symbol;group[e['tradeReportDate'].replace('-','')].append(e)
  for date,rows in group.items():
   v=source[date][symbol];assert len({r['marketCode'] for r in rows})==len(rows) and {r['marketCode'] for r in rows}==set(v['markets'].split(','))
   for field,col in [('short','shortParQuantity'),('exempt','shortExemptParQuantity'),('total','totalParQuantity')]:assert sum(D(r[col]) for r in rows)==D(v[field])
   api_matches+=1
 assert api_matches==687;return source,api_matches

def independent_fit(X,y,dates,current,constrain):
 n,k=X.shape;rank=np.linalg.matrix_rank(X)
 if rank<k:return None
 coef=np.linalg.solve(X.T@X,X.T@y);unrestricted=coef.copy();active=bool(constrain and coef[-1]>0);free=list(range(k-int(active)));F=X[:,free];bread=np.linalg.inv(F.T@F);b=np.linalg.solve(F.T@F,F.T@y);residual=y-F@b;lo=min(dates);grid=np.zeros((int((max(dates)-lo)//DAY)+1,len(free)))
 for date,row,res in zip(dates,F,residual):grid[int((date-lo)//DAY)]=row*res
 meat=grid.T@grid
 for lag in range(1,8):
  cross=grid[lag:].T@grid[:-lag];meat+=(8-lag)/8*(cross+cross.T)
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
 source,api_matches=source_check();source_dates=sorted(source);from zoneinfo import ZoneInfo
 ny=ZoneInfo('America/New_York');feature_checks=0;regressions=0;forecast_checks=0;fit_worst=0.;raw_features={};raw_predictions={};saved_predictions={};target={}
 def raw_close(t):
  r=rawprice.get(('BS',t-HOUR))
  return float(r[1]) if r is not None and rawclock[('BS',t-HOUR)]==t-1 and r[1]>0 else None
 def logreturn(a,b):
  x,y=raw_close(a),raw_close(b);return math.log(y/x) if x is not None and y is not None else None
 def near(a,b,tolerance=2e-9):
  nonlocal fit_worst
  aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float);assert aa.shape==bb.shape;error=float(np.max(np.abs(aa-bb))) if aa.size else 0.;fit_worst=max(fit_worst,error);assert np.allclose(aa,bb,rtol=2e-8,atol=tolerance),(aa,bb,error)
 for t in range(ms('2020-01-01'),ms('2026-09-01'),DAY):target[t]={'end':t+7*DAY,'value':logreturn(t,t+7*DAY)}
 observed_targets=read(out/'labels.json.gz');assert set(observed_targets)=={str(t) for t in target}
 for t,v in target.items():
  actual=observed_targets[str(t)];assert actual['end']==v['end']
  if v['value'] is None:assert actual['value'] is None
  else:near(actual['value'],v['value'],1e-14)
 for lag in (0,7):
  rr=[]
  for i,date in enumerate(source_dates):
   d=dt.datetime.strptime(date,'%Y%m%d').date();release=dt.datetime.combine(d,dt.time(18),tzinfo=ny).astimezone(dt.timezone.utc)+dt.timedelta(hours=24+24*lag);pt=int(dt.datetime.combine(d,dt.time(16),tzinfo=ny).timestamp()*1000);prior=source_dates[max(0,i-20):i];xx=activity=None
   if i>=20:
    pressures=[];activities=[]
    for symbol in ('IBIT','FBTC','GBTC'):
     now=source[date][symbol];v=D(now['total']);mean_q=sum(D(source[u][symbol]['short'])/D(source[u][symbol]['total']) for u in prior)/20;mean_v=sum(D(source[u][symbol]['total']) for u in prior)/20;pressures.append(D(now['short'])/v-mean_q);activities.append(math.log(float(v/mean_v)))
    xx=float(sum(pressures)/3);activity=sum(activities)/3
   rr.append({'date':date,'available':int(release.timestamp()*1000),'price_time':pt,'previous20':prior,'x':xx,'a':activity,'r_report':logreturn(pt-DAY,pt)})
  published=read(out/f'reports-lag{lag}.json.gz');assert len(published)==661
  for actual,expected in zip(published,rr):
   for k,v in expected.items():
    if v is None or isinstance(v,(str,int,list)):assert actual[k]==v,(k,actual[k],v)
    else:near(actual[k],v,1e-14)
  observed_features=read(out/f'features-lag{lag}.json.gz');ff={}
  assert [e['source'] for e in observed_features]==list(target)
  for actual in observed_features:
   t=actual['source'];eligible=[r for r in rr if r['available']<=t];r=eligible[-1] if eligible else None;e={'source':t,'availability_delay_days':lag,'report':r['date'] if r else None,'available':r['available'] if r else None,'age_hours':(t-r['available'])/HOUR if r else None,'report_price_time':r['price_time'] if r else None,'previous20':r['previous20'] if r else [],'r_now':logreturn(t-DAY,t),'r_report':r['r_report'] if r else None,'x':r['x'] if r else None,'a':r['a'] if r else None}
   e['valid']=r is not None and t-r['available']<=7*DAY and all(e[k] is not None for k in ('r_now','r_report','a','x'));ff[t]=e
   for k,v in e.items():
    if v is None or isinstance(v,(str,int,list,bool)):assert actual[k]==v,(lag,t,k,actual[k],v)
    else:near(actual[k],v,1e-14)
   feature_checks+=1
  pp={};observed_forecasts=read(out/f'forecasts-lag{lag}.json.gz');assert [p['source'] for p in observed_forecasts]==list(target)
  for actual in observed_forecasts:
   t=actual['source'];days_train=[u for u in range(t-372*DAY,t-7*DAY,DAY) if u in ff and ff[u]['valid'] and target[u]['value'] is not None and target[u]['end']<=t-DAY];assert actual['training_days']==days_train and actual['training_n']==len(days_train) and actual['training_label_end']==max((target[u]['end'] for u in days_train),default=None);preds={}
   for name,cols in [('EF_INFO',('r_now','r_report','a','x')),('EF_PRICE',('r_now','r_report','a')),('EF_RAW',('x',))]:
    p=actual['models'][name];assert p['training_n']==len(days_train)
    if not ff[t]['valid'] or len(days_train)<126:assert p['mu'] is None and p['se'] is None;preds[name]=None;continue
    X=np.array([[1]+[ff[u][c] for c in cols] for u in days_train]);y=np.array([target[u]['value'] for u in days_train]);current=np.array([1]+[ff[t][c] for c in cols]);fit=independent_fit(X,y,days_train,current,name!='EF_PRICE')
    if fit is None:assert p['mu'] is None;preds[name]=None;continue
    for k in ('constraint_active','unrestricted_rank','rank','free_columns'):assert p[k]==fit[k],(lag,t,name,k)
    for k in ('mu','se','beta','covariance','unrestricted_beta','residual_ss'):near(p[k],fit[k])
    near(p['feature_mean'],X[:,1:].mean(axis=0),1e-13);preds[name]=fit;regressions+=1
   pp[t]=preds;forecast_checks+=1
  raw_features[lag]=ff;raw_predictions[lag]=pp;saved_predictions[lag]={v['source']:v for v in observed_forecasts}
 forecast_results=read(out/'forecast-summary.json')
 for period,(start,end) in {'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}.items():
  for lag in (0,7):
   paired=[t for t,models in raw_predictions[lag].items() if start<=t<end and target[t]['end']<=end and target[t]['value'] is not None and all(p is not None for p in models.values())]
   for name in ('EF_INFO','EF_PRICE','EF_RAW'):
    actual=forecast_results[period][str(lag)][name];assert actual['n']==len(paired) and actual['paired_source_times']==paired
    if paired:
     predictions=[raw_predictions[lag][t][name] for t in paired];near(actual['mse'],sum((p['mu']-target[t]['value'])**2 for p,t in zip(predictions,paired))/len(paired));near(actual['sign_accuracy'],sum(np.sign(p['mu'])==np.sign(target[t]['value']) for p,t in zip(predictions,paired))/len(paired));assert actual['constraint_days']==sum(p['constraint_active'] for p in predictions)
    else:assert actual['mse'] is None
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk=float(p.name.split('-risk')[1].split('-lag')[0]);lag=int(p.name.split('-lag')[1].split('.')[0])
  for e in plan:
   t=e['source_time'];detail=e['detail'];f=raw_features[lag][t];models=raw_predictions[lag][t]
   for k in ('report','available','age_hours'):assert detail[k]==f[k]
   assert detail['common_valid']==f['valid'] and detail['models']==saved_predictions[lag][t]['models'] and detail['training_n']==saved_predictions[lag][t]['training_n'] and detail['training_label_end']==saved_predictions[lag][t]['training_label_end'];i=dayidx[t];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6
   info,price,raw=(models[n] for n in ('EF_INFO','EF_PRICE','EF_RAW'))
   def eligible(p):
    if p is None:return 0
    hurdle=math.log1p(.0023 if p['mu']>0 else .0013)
    return sign(p['mu']) if abs(p['mu'])>hurdle+p['se'] else 0
   delta=None;info_side=0
   if info is not None and price is not None:
    delta=0. if info['constraint_active'] else info['mu']-price['mu']
    if abs(delta)>1e-12 and delta*info['mu']>0:info_side=eligible(info)
   over=info_side if name=='EF_INFO' else -info_side if name=='EF_INV' else eligible(price) if name=='EF_PRICE' else eligible(raw) if name=='EF_RAW' else 0;direction=over if over else max(0,score)
   assert detail['override']==bool(over) and detail['core_fallback']==(not over)
   if delta is None:assert detail['increment'] is None
   else:near(detail['increment'],delta)
   assert detail['score']==score and detail['signal']==direction and abs(detail['vol']-vol)<1e-9 and abs(detail['risk']-w)<1e-9
   for k,v in [('BS',max(direction,0)*w),('BP',min(direction,0)*w)]:assert abs(e['weights'][k]-v)<1e-9
   assert sum(abs(v) for v in e['weights'].values())<=1+1e-12;raw_signals[name,risk,lag,t]=e;plans_checked+=1
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}-lag{x['availability_delay_days']}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_etfshort_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
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
 proof={'accounts':len(reports),'raw_archives':archive_count,'finra_raw_days':len(source),'api_cdn_exact_symbol_days':api_matches,'raw_feature_days':feature_checks,'raw_forecast_days':forecast_checks,'independent_model_fits':regressions,'max_fit_numeric_error':fit_worst,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'independent exact FINRA BTC rows and API Decimal facility sums; UTC/NY release and completed BTC raw ZIP prices; all features, 7-day labels with purge; uncentered normal equations constrained refit, calendar-grid HAC, all predictions, MSE and directions; closed-form postcost qty/no-trade; Decimal cash, actual mark/funding, hourlyDD, exposure, episodes, annual returns, volatility, Sharpe and adverse margin; current archive vintage remains unproven'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
