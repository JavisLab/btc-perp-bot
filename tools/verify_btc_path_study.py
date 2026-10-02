"""Independent raw curve/path area, multivariate normal equations, information/release clocks and account ledger."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())


COLS={'IC_PATH':('r','rv','area'),'IC_PRICE':('r','rv'),'IC_MEAN':()}
def independent_curve(rawprice,rawclock,d):
 times=[d+(i-1)*HOUR for i in range(25)];rows=[rawprice.get(('BS',t)) for t in times];valid=all(r is not None and r[1]>0 and rawclock[('BS',t)]==t+HOUR-1 for t,r in zip(times,rows));e={'day':d,'available':d+DAY,'valid':valid}
 if valid:
  c=[math.log(float(r[1])/float(rows[0][1])) for r in rows[1:]];delta=[b-a for a,b in zip([0.]+c,c)];e.update(curve=c,r=c[-1],rv=math.fsum(r*r for r in delta),area=math.fsum(x-(i+1)*c[-1]/24 for i,x in enumerate(c))/24)
 return e

def independent_model(curves,t):
 days=[d for d in range(t-366*DAY,t-DAY,DAY) if d in curves and d-DAY in curves and curves[d]['valid'] and curves[d-DAY]['valid']];current=curves.get(t-DAY);valid=current is not None and current['valid'];e={'source':t,'input_day':t-DAY,'information_time':t,'valid_input':valid,'training_days':days,'training_label_end':max(days)+DAY if days else None,'models':{}}
 for name,cols in COLS.items():
  n=len(days);k=len(cols)+1;p={'mu':None,'covariance_upper':None,'leverage':None,'training_n':n};e['models'][name]=p
  if n<300 or not valid:continue
  X=np.array([[1.]+[curves[d-DAY][c] for c in cols] for d in days]);Y=np.array([curves[d]['curve'] for d in days]);scale=np.sqrt(np.mean(X*X,axis=0));scale[scale<1e-12]=1.;Z=X/scale
  if np.linalg.matrix_rank(Z)<k:p['reason']='rank';continue
  G=Z.T@Z;coef=np.linalg.solve(G,Z.T@Y);x=np.array([1.]+[current[c] for c in cols])/scale;mu=x@coef;res=Y-Z@coef;cov=res.T@res/(n-k);h=float(x@np.linalg.solve(G,x));p.update(mu=mu.tolist(),covariance_upper=[float(cov[i,j]) for i in range(24) for j in range(i,24)],leverage=h,beta=(coef/scale[:,None]).tolist())
 return e

def independent_choice(p):
 if p['mu'] is None:return {'trade':False,'reason':p.get('reason','unavailable_model'),'best':None}
 covariance={};cursor=0
 for i in range(24):
  for j in range(i,24):covariance[i,j]=covariance[j,i]=p['covariance_upper'][cursor];cursor+=1
 candidates=[]
 for i in range(1,24):
  for j in range(i+1,25):
   delta=p['mu'][j-1]-p['mu'][i-1];se=math.sqrt(max(0,p['leverage']*(covariance[j-1,j-1]+covariance[i-1,i-1]-2*covariance[i-1,j-1])))
   for d,c in [(1,math.log1p(.0023)),(-1,math.log1p(.0013))]:candidates.append({'entry_hour':i,'exit_hour':j,'direction':d,'predicted_difference':delta,'mean_se':se,'roundtrip_log_cost':c,'utility':d*delta-c-se})
 best=sorted(candidates,key=lambda e:(-e['utility'],e['entry_hour'],e['exit_hour'],-e['direction']))[0];return {'trade':best['utility']>0,'reason':'positive_edge' if best['utility']>0 else 'cost_and_uncertainty','best':best}

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


 recorded_curves=read(out/'curves.json.gz');curves={};curve_checks=0
 assert [e['day'] for e in recorded_curves]==list(range(ms('2020-01-01'),ms('2026-09-01'),DAY))
 for e in recorded_curves:
  t=e['day'];z=independent_curve(rawprice,rawclock,t);curves[t]=z
  for k in ('day','available','valid'):assert e[k]==z[k]
  if z['valid']:
   for k in ('r','rv','area','curve'):assert np.max(np.abs(np.array(e[k])-np.array(z[k])))<1e-12,(t,k)
   curve_checks+=1
 predicted={};predictions_checked=0;prediction_error=0.;recorded=read(out/'features.json.gz');assert len(recorded)==2435
 for e in recorded:
  t=e['source'];z=independent_model(curves,t);predicted[t]=z
  for k in ('input_day','information_time','valid_input','training_days','training_label_end'):assert e[k]==z[k],(t,k)
  if z['training_label_end'] is not None:assert z['training_label_end']<=t-DAY
  for name,p in z['models'].items():
   a=e['models'][name];assert a['training_n']==p['training_n']
   if p['mu'] is None:assert a['mu'] is None;continue
   for k in ('mu','covariance_upper','leverage'):
    err=float(np.max(np.abs(np.array(a[k])-np.array(p[k]))));prediction_error=max(prediction_error,err);assert err<1e-9,(t,name,k,err)
   assert np.allclose(a['beta'],p['beta'],atol=1e-7,rtol=1e-8),(t,name,'beta');predictions_checked+=1
 decisions_checked=0;plans_checked=0;raw_signals={};choices_checked=0
 for file in out.glob('*-decisions-risk*.json.gz'):
  dec=read(file);name=file.name.split('-')[1];risk=float(file.name.split('-risk')[1].removesuffix('.json.gz'));plan=read(file.with_name(file.name.replace('-decisions-','-plan-')));cursor=0
  for record in dec:
   t=record['decision_time'];z=predicted[t];choice=independent_choice(z['models']['IC_PATH' if name=='IC_INV' else name]);assert choice['trade']==record['choice']['trade'] and choice['reason']==record['choice']['reason']
   if choice['best'] is not None:
    for k in ('entry_hour','exit_hour','direction'):assert choice['best'][k]==record['choice']['best'][k],(file.name,t,k)
    for k in ('utility','mean_se','predicted_difference','roundtrip_log_cost'):assert abs(choice['best'][k]-record['choice']['best'][k])<1e-9
    choices_checked+=1
   else:assert record['choice']['best'] is None
   i=dayidx[t];hist=daily[i-20:i+1];missing=i<20 or not np.all(np.isfinite(hist));vol=None;w=0.
   if not missing:
    rr=[math.log(b/a) for a,b in zip(hist,hist[1:])];avg=math.fsum(rr)/20;vol=math.sqrt(math.fsum((r-avg)**2 for r in rr)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0
   trade=choice['trade'] and not missing and w>0;direction=choice['best']['direction']*(-1 if name=='IC_INV' else 1) if trade else 0;assert record['trade']==trade and record['signal']==direction and record['risk_missing']==missing and record['input_day']==t-DAY and record['training_label_end']==z['training_label_end'];assert abs(record['risk']-w)<1e-9
   if vol is None:assert record['vol'] is None
   else:assert abs(record['vol']-vol)<1e-9
   if trade:
    b=choice['best'];actions=[(t+(b['entry_hour']-1)*HOUR,'entry',{'BS':max(direction,0)*w,'BP':min(direction,0)*w}),(t+(b['exit_hour']-1)*HOUR,'exit',{'BS':0.,'BP':0.})]
   else:actions=[(t,'flat',{'BS':0.,'BP':0.})]
   for release,action,weights in actions:
    e=plan[cursor];cursor+=1;assert e['source_time']==release and e['decision_time']==t and t<=release<t+DAY and release+HOUR>=t+HOUR and e['detail']['action']==action
    assert {k:v for k,v in e['detail'].items() if k!='action'}==record
    for k in KEYS:assert abs(e['weights'][k]-weights[k])<1e-9
    assert sum(abs(v) for v in e['weights'].values())<=1+1e-12;raw_signals[name,risk,release]=e;plans_checked+=1
   decisions_checked+=1
  assert cursor==len(plan) and all(a['source_time']<b['source_time'] for a,b in zip(plan,plan[1:]))
 forecasts=read(out/'forecast-summary.json')
 for period,(begin,finish) in {'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}.items():
  common=[t for t,e in predicted.items() if begin<=t<finish and curves[t]['valid'] and all(e['models'][n]['mu'] is not None for n in COLS)]
  for name in COLS:
   a=forecasts[period][name];assert a['paired_days']==common and a['hour_values']==len(common)*24 and a['n']==len(common)
   mse=math.fsum((float(p)-float(y))**2 for t in common for p,y in zip(predicted[t]['models'][name]['mu'],curves[t]['curve']))/(len(common)*24) if common else None
   if mse is None:assert a['mse'] is None
   else:assert abs(a['mse']-mse)<1e-12
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or '-decisions-' in p.name or p.name.startswith(('features','curves')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
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
  equal(cash,x['metrics']['equity']);equal(dd,x['metrics']['max_drawdown_pct']);side={k:{**{a:float(v) for a,v in z.items()},'net':float(z['gross']-z['fees']-z['impact']+z['funding'])} for k,z in sides.items()};equal(sum(z['net'] for z in side.values()),x['metrics']['net_pnl']);diag[p.name]={'sides':side,'skips':x['skips']};reports.append({'file':p.name,'events':len(x['events']),'daily':len(x['daily'])})
 proof={'accounts':len(reports),'raw_archives':archive_count,'raw_complete_daily_curves':curve_checks,'multivariate_normal_equation_fits':predictions_checked,'forecast_hour_values':predictions_checked*24,'max_prediction_error':prediction_error,'independent_day_decisions':decisions_checked,'independent_interval_selections':choices_checked,'raw_release_targets':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'raw BTC 25 complete boundaries/day, endpoint-detrended area/RV and exact previous-day pairs; extra-day purge and 365 calendar window; independent uncentered 24-response normal equations, joint covariance/meanSE and all276 clock pairs both sides; decision versus future release/actual fills; independent raw risk, analytical postcost target/no-trades, Decimal cash/actual funding/continuous hourlyDD, exposure, margin, episodes; selected forecast extrema not actual hindsight extrema'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
