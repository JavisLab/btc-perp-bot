"""Independent raw-price normal-equation grid, causal state and analytic/Decimal account verification."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())

N=672
GRID=list(itertools.product((.05,.1,.2,1/3),(.1,.3,.5,.7,.9),(4,8,12,16,20,24)))
def independently_fit(rawprice,rawclock,t):
 times=[t-j*HOUR for j in range(N,0,-1)];rows=[rawprice.get(('BS',h)) for h in times];ok=all(r is not None and r[1]>0 and rawclock[('BS',h)]==h+HOUR-1 for h,r in zip(times,rows))
 if not ok:return {'valid':False,'bubble':0,'quadratic':0}
 y=np.array([math.log(float(r[1])/float(rows[0][1])) for r in rows]);coef=INVPROJ@y;res=np.matmul(MATRICES,coef[:,:,None])[:,:,0]-y;sse=np.sum(res*res,axis=1);j=int(np.argmin(sse));b=coef[j];d,m,w=GRID[j];linear=np.linalg.solve(LINE.T@LINE,LINE.T@y);quad=np.linalg.solve(QUAD.T@QUAD,QUAD.T@y);ls=float(np.sum((LINE@linear-y)**2));qs=float(np.sum((QUAD@quad-y)**2));bic=lambda v,k,g=1:N*math.log(max(v/N,1e-24))+k*math.log(N)+2*math.log(g);score=bic(float(sse[j]),7,120);cycles=w*math.log((1+d)/d)/(2*math.pi);amp=math.sqrt(b[2]**2+b[3]**2);damping=m*abs(float(b[1]))/(w*amp) if amp else None;maxerr=max(abs(math.expm1(r)) for r in res[j]);direction=1 if b[1]<0 and y[-1]>0 else -1 if b[1]>0 and y[-1]<0 else 0
 checks={'linear_bic':bic(ls,2)-score>=10,'quadratic_bic':bic(qs,3)-score>=10,'horizon':d<=.2,'full_cycles':cycles>=2.5,'damping':damping is None or damping>=1,'relative_error':maxerr<=.15,'direction':direction!=0};qdir=int(quad[2]>0)-int(quad[2]<0);qflag=qdir if qdir and qdir*y[-1]>0 and qdir*(quad[1]+2*quad[2])>0 and bic(ls,2)-bic(qs,3)>=10 else 0
 return {'valid':True,'best_index':j,'parameters':list(GRID[j]),'beta':b.tolist(),'sse_all':sse.tolist(),'linear_beta':linear.tolist(),'quadratic_beta':quad.tolist(),'linear_sse':ls,'quadratic_sse':qs,'bic':score,'linear_bic':bic(ls,2),'quadratic_bic':bic(qs,3),'full_cycles':cycles,'damping':damping,'max_relative_error':maxerr,'checks':checks,'bubble':direction if all(checks.values()) else 0,'quadratic':qflag,'window_log_return':float(y[-1])}
MATRICES=[]
for d,m,w in GRID:
 matrix=[]
 for i in range(N):
  z=1+d-i/(N-1);f=math.pow(z,m);l=math.log(z);matrix.append([1.,f,f*math.cos(w*l),f*math.sin(w*l)])
 MATRICES.append(matrix)
MATRICES=np.array(MATRICES);INVPROJ=np.array([np.linalg.solve(x.T@x,x.T) for x in MATRICES]);QUAD=np.array([[1.,i/(N-1),(i/(N-1))**2] for i in range(N)]);LINE=QUAD[:,:2]
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
 rec=read(out/'features.json.gz');assert len(rec)==2435;feature_checks=0;normal_fits=0;feature_error=0.;flags={}
 for a in rec:
  t=a['source'];assert a['first_open']==t-N*HOUR and a['last_close']==t-1;b=independently_fit(rawprice,rawclock,t);flags[t]=b
  for k in ('valid','bubble','quadratic'):assert a[k]==b[k],(t,k,a[k],b[k])
  if not b['valid']:continue
  for k in ('best_index','parameters','checks'):assert a[k]==b[k],(t,k)
  for k in ('beta','sse_all','linear_beta','quadratic_beta','linear_sse','quadratic_sse','bic','linear_bic','quadratic_bic','full_cycles','max_relative_error','window_log_return'):
   error=float(np.max(np.abs(np.array(a[k])-np.array(b[k]))));feature_error=max(feature_error,error);assert error<1e-7,(t,k,error)
  if b['damping'] is None:assert a['damping'] is None
  else:assert abs(a['damping']-b['damping'])<1e-7
  feature_checks+=1;normal_fits+=120
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];risk=float(p.name.split('-risk')[1].removesuffix('.json.gz'));active=0;expiry=plan[0]['source_time'];cause=None;field='quadratic' if name=='BB_QUAD' else 'bubble'
  for e in plan:
   t=e['source_time'];trigger=False
   if t>=expiry:active=0;cause=None
   rv=math.log(spot[t]/spot[t-DAY]) if t in spot and t-DAY in spot else None
   if name!='BB_TREND' and not active:
    report=None
    for u in range(t-DAY,t-8*DAY,-DAY):
     if u in flags and flags[u]['valid'] and flags[u][field]:report=u;break
    if report is not None and rv is not None and rv*flags[report][field]<0:active=-flags[report][field];expiry=t+7*DAY;cause=report;trigger=True
   detail=e['detail'];assert detail['direction']==active and detail['cause']==cause and detail['expiry']==(expiry if active else None) and detail['triggered']==trigger;assert detail['last_day_return']==rv
   if cause is not None:assert t>=cause+DAY
   i=dayidx[t];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6;direction=(0 if name=='BB_CASH' else active) if active else max(0,score)
   assert detail['score']==score and detail['signal']==direction and abs(detail['vol']-vol)<1e-9
   for k,v in [('BS',max(direction,0)*w),('BP',min(direction,0)*w)]:assert abs(e['weights'][k]-v)<1e-9
   assert sum(abs(v) for v in e['weights'].values())<=1+1e-12
   raw_signals[name,risk,t]=e;plans_checked+=1
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith('features'):continue
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
 proof={'accounts':len(reports),'raw_archives':archive_count,'raw_hourly_curve_windows':feature_checks,'normal_equation_grid_fits':normal_fits,'max_curve_error':feature_error,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'raw BTC complete hourly log-price curves; all120 independent normal-equation fits versus SVD projections, polynomial and filter calculations; prior-day-only last7d source, fixed7d expiry/no overwrite; raw EMA/vol and targets; closed-form postcost qty and no-trade; raw positive-volume fills, mark and funding; Decimal cash/continuous hourlyDD, exposure, episodes and adverse margin; discrete approximation not calibrated crash probability'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
