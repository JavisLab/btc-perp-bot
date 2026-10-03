"""Independent raw DVOL/BTC variance features, normal equations and Decimal BTC accounts."""
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
 from audit_btc_dvol_data import run as independent_source_audit
 raw,counts=independent_source_audit(write=False);assert counts['input_sha256']=='200f61fa5869ee8351956a960f1265da6c559d25356e5fe2783ba399e84330ea'
 mask=ROOT/'data/btc-venue-20261003/masks.json';assert sha(mask.read_bytes())=='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd'
 return raw,set(read(mask)['binance_spot_no_trade']),counts

def independent_fit(X,y,current,constrain):
 n,k=X.shape;rank=int(np.linalg.matrix_rank(X))
 if rank<k:return None
 unres=np.linalg.solve(X.T@X,X.T@y);active=bool(constrain and unres[-1]<0);free=list(range(k-int(active)));F=X[:,free];b=np.linalg.solve(F.T@F,F.T@y);res=y-F@b;beta=np.zeros(k);beta[free]=b;mu=float(current@beta);smear=math.fsum(math.exp(v) for v in res)/n;prediction=math.exp(mu)*smear
 return {'variance':prediction,'log_mean':mu,'smearing':smear,'beta':beta,'constraint_active':active,'unrestricted_beta':unres,'unrestricted_rank':rank,'rank':len(free),'free_columns':free,'residual_ss':float(res@res)}

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
 source,excluded,source_counts=source_check();assert excluded=={t for (k,t),v in rawvolume.items() if k=='BS' and v<=0};feature_checks=0;regressions=0;forecast_checks=0;fit_worst=0.;raw_features={};raw_predictions={};saved_predictions={};target={};bootstrap_checks=0
 assert sha(gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes()))=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4'
 for key in KEYS:
  for t,r in rows[key].items():assert (D(r[1]),D(r[4]))==rawprice[(key,t)] and r[5]==rawclock[(key,t)]
 def raw_variance(start):
  closes=[]
  for j in range(31):
   t=start+j*DAY-HOUR;r=rawprice.get(('BS',t))
   if r is None or t in excluded or rawclock[('BS',t)]!=t+HOUR-1 or r[1]<=0:return None
   closes.append(float(r[1]))
  v=math.fsum(math.log(b/a)**2 for a,b in zip(closes,closes[1:]))*365/30
  return v if v>0 and math.isfinite(v) else None
 def near(a,b,tolerance=2e-9):
  nonlocal fit_worst
  aa,bb=np.asarray(a,dtype=float),np.asarray(b,dtype=float);assert aa.shape==bb.shape;error=float(np.max(np.abs(aa-bb))) if aa.size else 0.;fit_worst=max(fit_worst,error);assert np.allclose(aa,bb,rtol=2e-8,atol=tolerance),(aa,bb,error)
 def feature_equal(actual,expected):
  for k,v in expected.items():
   if v is None or isinstance(v,(str,int,list,bool)):assert actual[k]==v,(k,actual[k],v)
   else:near(actual[k],v,1e-14)
 for t in range(ms('2021-04-03'),ms('2026-09-01'),DAY):target[t]={'end':t+30*DAY,'value':raw_variance(t)}
 observed_targets=read(out/'labels.json.gz');assert set(observed_targets)=={str(t) for t in target}
 for t,v in target.items():
  actual=observed_targets[str(t)];assert actual['end']==v['end']
  if v['value'] is None:assert actual['value'] is None
  else:near(actual['value'],v['value'],1e-14)
 for lag in (0,7):
  ff={};observed=read(out/f'features-lag{lag}.json.gz');assert [r['source'] for r in observed]==list(target)
  for actual in observed:
   t=actual['source'];bar=t-(2+lag)*DAY;value=source.get(bar,[None]*4)[3] if bar>=ms('2021-04-01') else None;q=float((value/100)**2) if value is not None and value>0 else None;rv=raw_variance(t-30*DAY);e={'source':t,'dvol_bar':bar,'dvol_end':bar+DAY,'assumed_available':bar+(2+lag)*DAY,'availability_delay_days':lag,'dvol_percent':float(value) if value is not None else None,'q':q,'past_variance':rv,'log_r':math.log(rv) if rv is not None else None,'log_q':math.log(q) if q is not None else None};e['valid']=rv is not None and q is not None;ff[t]=e;feature_equal(actual,e);feature_checks+=1
  pp={};observed=read(out/f'forecasts-lag{lag}.json.gz');assert [p['source'] for p in observed]==list(target)
  for actual in observed:
   t=actual['source'];train=[u for u in range(t-760*DAY,t-30*DAY,DAY) if u in ff and ff[u]['valid'] and target[u]['value'] is not None and target[u]['end']<=t-DAY];assert actual['training_days']==train and actual['training_n']==len(train) and actual['training_label_end']==max((target[u]['end'] for u in train),default=None);models={}
   for name,cols in [('VI_INFO',('log_r','log_q')),('VI_PRICE',('log_r',))]:
    p=actual['models'][name];assert p['training_n']==len(train)
    if not ff[t]['valid'] or len(train)<365:assert p['variance'] is None;models[name]=None;continue
    X=np.array([[1]+[ff[u][c] for c in cols] for u in train]);y=np.array([math.log(target[u]['value']) for u in train]);current=np.array([1]+[ff[t][c] for c in cols]);fit=independent_fit(X,y,current,name=='VI_INFO')
    if fit is None:assert p['variance'] is None;models[name]=None;continue
    for k in ('constraint_active','unrestricted_rank','rank','free_columns'):assert p[k]==fit[k],(lag,t,name,k)
    for k in ('variance','log_mean','smearing','beta','unrestricted_beta','residual_ss'):near(p[k],fit[k])
    near(p['feature_mean'],X[:,1:].mean(axis=0),1e-13);models[name]=fit;regressions+=1
   pp[t]=models;forecast_checks+=1
  raw_features[lag]=ff;raw_predictions[lag]=pp;saved_predictions[lag]={v['source']:v for v in observed};print(json.dumps({'stage':'independent_variance_fits','lag':lag,'fits':regressions,'max_fit_error':fit_worst}),flush=True)
 forecast_results=read(out/'forecast-summary.json')
 for period,(start,end) in {'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}.items():
  for lag in (0,7):
   paired=[t for t,models in raw_predictions[lag].items() if start<=t<end and target[t]['end']<=end and target[t]['value'] is not None and all(p is not None for p in models.values())];loss={}
   for name in ('VI_INFO','VI_PRICE','VI_RAW'):
    actual=forecast_results[period][str(lag)][name];assert actual['n']==len(paired) and actual['paired_source_times']==paired;pred=[raw_predictions[lag][t][name]['variance'] if name!='VI_RAW' else raw_features[lag][t]['q'] for t in paired];mse=[(v-target[t]['value'])**2 for t,v in zip(paired,pred)];ql=[math.log(v)+target[t]['value']/v for t,v in zip(paired,pred)];loss[name]={'mse':mse,'qlike':ql}
    for metric,values in [('mse',mse),('qlike',ql)]:near(actual[metric],math.fsum(values)/len(values))
    assert actual['constraint_days']==(sum(raw_predictions[lag][t][name]['constraint_active'] for t in paired) if name!='VI_RAW' else 0)
   for metric in ('mse','qlike'):
    diffs={t:a-b for t,a,b in zip(paired,loss['VI_INFO'][metric],loss['VI_PRICE'][metric])};grid=np.array([diffs.get(t,np.nan) for t in range(start,end,DAY)])
    for actual in forecast_results[period][str(lag)][metric+'_difference']:
     block=actual['block_days'];assert block in (30,60,90) and actual['calendar_days']==len(grid) and actual['valid_days']==len(paired);near(actual['mean'],np.nanmean(grid));rng=np.random.default_rng(8300+block);starts=rng.integers(0,len(grid),size=(2000,math.ceil(len(grid)/block)));stats=[]
     for ss in starts:
      sample=np.concatenate([grid[(np.arange(block)+j)%len(grid)] for j in ss])[:len(grid)];stats.append(np.nanmean(sample))
     finite=[v for v in stats if math.isfinite(v)];near(actual['ci95'],np.quantile(finite,[.025,.975]));assert actual['finite_replicates']==len(finite) and actual['replicates']==2000;bootstrap_checks+=1
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk=float(p.name.split('-risk')[1].split('-lag')[0]);lag=int(p.name.split('-lag')[1].split('.')[0])
  for e in plan:
   t=e['source_time'];detail=e['detail'];f=raw_features[lag][t];models=raw_predictions[lag][t];feature_equal(detail['feature'],f);assert detail['models']==saved_predictions[lag][t]['models'] and detail['training_n']==saved_predictions[lag][t]['training_n'] and detail['training_label_end']==saved_predictions[lag][t]['training_label_end'];i=dayidx[t];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);core=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6;info,price=models['VI_INFO'],models['VI_PRICE'];candidate=None
   if name=='VI_INFO' and info is not None:candidate=risk/math.sqrt(info['variance'])
   elif name=='VI_PRICE' and price is not None:candidate=risk/math.sqrt(price['variance'])
   elif name=='VI_RAW' and f['q'] is not None:candidate=risk/math.sqrt(f['q'])
   elif name=='VI_INV' and info is not None and price is not None:candidate=risk*math.sqrt(info['variance'])/price['variance']
   w=core if candidate is None else min(1,candidate);assert detail['core_fallback']==(candidate is None);assert detail['score']==score and detail['signal']==max(0,score);near(detail['vol'],vol,1e-12);near(detail['core_risk'],core,1e-12);near(detail['risk'],w,1e-10);near(e['weights']['BS'],max(0,score)*w,1e-10);assert e['weights']['BP']==0 and 0<=e['weights']['BS']<=1;raw_signals[name,risk,lag,t]=e;plans_checked+=1
 print(json.dumps({'stage':'independent_plans','daily_decisions':plans_checked}),flush=True)
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}-lag{x['availability_delay_days']}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_dvol_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
  assert x['dvol_input_sha256']=='200f61fa5869ee8351956a960f1265da6c559d25356e5fe2783ba399e84330ea' and x['btc_no_trade_mask_sha256']=='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd'
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
 assert len(reports)==60
 summary=read(out/'summary.json');selection=read(out/'selection.json');a=summary['main-VI_INFO-base']['metrics'];b=summary['recent-VI_INFO-base']['metrics'];checks={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-VI_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):checks[c]=all(summary[p+'-VI_INFO-'+c]['metrics']['net_pnl']>0 for p in ('main','recent'))
 extra={}
 for name in ('VI_PRICE','VI_TREND'):extra['net_beats_'+name+'_both']=all(summary[p+'-VI_INFO-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in ('main','recent'))
 extra['dd_no_worse_price_both']=all(summary[p+'-VI_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-VI_PRICE-base']['metrics']['max_drawdown_pct'] for p in ('main','recent'))
 for metric in ('mse','qlike'):extra[metric+'_strictly_better_both']=all(forecast_results[p]['0']['VI_INFO'][metric] is not None and forecast_results[p]['0']['VI_PRICE'][metric] is not None and forecast_results[p]['0']['VI_INFO'][metric]<forecast_results[p]['0']['VI_PRICE'][metric] for p in ('main','recent'))
 assert selection['checks']==checks and selection['information_increment']==extra and selection['passed']==(all(checks.values()) and all(extra.values())) and selection['primary']=='VI_INFO'
 assert raw_funding_events==0
 for key,row in summary.items():
  account=read(out/(key+'.json.gz'));assert row['metrics']==account['metrics'] and row['annual']==account['periods']['yearly'] and account['metrics']['funding']==0
 identity=read(out/'control-identity.json')
 for period in ('main','recent'):
  actual=read(out/(period+'-VI_TREND-base.json.gz'));saved=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');near(actual['daily_returns'],saved['daily_returns'],1e-12)
  for metric in ('return_pct','max_drawdown_pct','fees','impact','funding'):near(actual['metrics'][metric],saved['metrics'][metric]);near(identity[period]['metric_errors'][metric],abs(actual['metrics'][metric]-saved['metrics'][metric]))
 proof={'accounts':len(reports),'raw_archives':archive_count,'official_dvol_responses':source_counts['daily_responses'],'dvol_daily_observations':source_counts['daily_observations'],'clock_probes':len(source_counts['clock_probes']),'raw_feature_days':feature_checks,'raw_forecast_days':forecast_checks,'independent_model_fits':regressions,'max_fit_numeric_error':fit_worst,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'selection_independently_checked':True,'forecast_loss_bootstrap_checks':bootstrap_checks,'scope':'Independent Decimal public DVOL/UTC/native24h clocks, raw BTC ZIP prices/volumes; past and future variance windows/purged training; uncentered normal equations and constrained refit plus training-only smearing; paired variance MSE/QLIKE/calendar-block loss uncertainty; spot-only targets and funding0; closed-form postcost quantities/no-trade; Decimal ledger/hourly DD/margin/exposure/annual and E_SPOT identity; current historical DVOL is not first-release vintage'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
