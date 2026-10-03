"""Independent ordinary-Friday/manual-DST, raw completed daily-risk and Decimal BTC account verification."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile,urllib.parse
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
import audit_btc_expiry_calendar as calendar_audit
WEEK=7*DAY
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())

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
 cal,calendar_proof=calendar_audit.run();excluded={t for (k,t),v in rawvolume.items() if k=='BS' and v<=0};assert excluded==set(read(ROOT/'data/btc-venue-20261003/masks.json')['binance_spot_no_trade']);assert read(out/'calendar.json')==cal
 assert sha(gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes()))=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4'
 for key in KEYS:
  for t,r in rows[key].items():assert (D(r[1]),D(r[4]))==rawprice[(key,t)] and r[5]==rawclock[(key,t)]
 def eqnum(a,b):assert abs(float(a)-float(b))<1e-9,(a,b)
 diagnostics=read(out/'event-outcomes.json');assert len(diagnostics['events'])==54;event_returns={p:[] for p in ('main','recent')}
 for actual,e in zip(diagnostics['events'],cal['events']):
  pe=e['placebo'];period='main' if e['date']<'2026-01-01' else 'recent';assert actual['date']==e['date'] and actual['period']==period and actual['entry']==e['base_entry'] and actual['exit']==e['base_exit'] and actual['placebo_entry']==pe['base_entry'] and actual['placebo_exit']==pe['base_exit']
  def outcome(event):
   a,b=event['base_entry'],event['base_exit']
   if ('BS',a) not in rawprice or ('BS',b) not in rawprice or rawvolume[('BS',a)]<=0 or rawvolume[('BS',b)]<=0:return None
   return math.log(float(rawprice[('BS',b)][0]/rawprice[('BS',a)][0]))
  x,y=outcome(e),outcome(pe)
  for k,v in [('spot_open_log_return',x),('prior_week_spot_open_log_return',y),('paired_log_return_difference',x-y if x is not None and y is not None else None)]:
   if v is None:assert actual[k] is None
   else:eqnum(actual[k],v)
  if x is not None and y is not None:event_returns[period].append(x-y)
 for period,values in event_returns.items():
  actual=diagnostics['paired_uncertainty'][period];assert actual['paired_months']==len(values)
  for got,block in zip(actual['bootstrap'],(1,3,6)):
   assert got['block_months']==block and got['draws']==2000;rng=np.random.default_rng(1499+block);samples=[]
   for _ in range(2000):
    starts=rng.integers(0,len(values),math.ceil(len(values)/block));v=[values[(int(start)+j)%len(values)] for start in starts for j in range(block)][:len(values)];samples.append(math.fsum(v)/len(v)*100)
   eqnum(got['mean_log_difference_pct'],math.fsum(values)/len(values)*100)
   for a,b in zip(got['ci95'],np.quantile(samples,[.025,.975])):eqnum(a,b)
 plans_checked=0;raw_signals={};event_plans=0
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);period,name=p.name.split('-')[:2];risk=float(p.name.split('-risk')[1].removesuffix('.json.gz'));start,end=(ms('2022-01-01'),ms('2026-01-01')) if period=='main' else(ms('2026-01-01'),ms('2026-09-01'));scheduled=[] if name=='EX_TREND' else cal['weekly_controls'] if name=='EX_WEEKLY' else [e['placebo'] for e in cal['events']] if name=='EX_PLACEBO' else cal['events'];expected={t:('daily',None) for t in range(start,end,DAY)}
  for event in scheduled:
   for role,t in [('enter',event['signal_start']),('exit',event['signal_end'])]:
    if start<=t<end:assert t not in expected;expected[t]=(role,event)
  assert [e['source_time'] for e in plan]==sorted(expected)
  for e in plan:
   t=e['source_time'];detail=e['detail'];role,event=expected[t];risk_day=t//DAY*DAY;assert detail['role']==role and detail['event']==event and detail['risk_day']==detail['risk_latest_close']==risk_day;over=role=='enter' and name!='EX_CLOCK';assert detail['override']==over;cash=name=='EX_ONLY' and role!='enter';i=dayidx[risk_day];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):
    assert e['weights']==({'BS':0.,'BP':0.} if cash else None);raw_signals[name,risk,t]=e;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6;direction=-1. if over and name=='EX_INV' else 1. if over else 0. if cash else max(0,score)
   assert detail['core_fallback']==(not over and name!='EX_ONLY');assert detail['score']==score and detail['signal']==direction;eqnum(detail['vol'],vol);eqnum(detail['risk'],w)
   for k,v in [('BS',max(direction,0)*w),('BP',min(direction,0)*w)]:eqnum(e['weights'][k],v)
   assert sum(abs(v) for v in e['weights'].values())<=1+1e-12;raw_signals[name,risk,t]=e;plans_checked+=1;event_plans+=int(role!='daily')
 print(json.dumps({'stage':'independent_calendar_and_plans','source_decisions':plans_checked,'intraday_event_plans':event_plans,'post_event_diagnostics':sum(map(len,event_returns.values()))}),flush=True)
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith(('features','reports','forecasts','labels')):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-risk{x['risk_target']:.2f}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  assert x['schedule_sha256']==sha(canonical(plan)) and x['implementation_sha256']==sha((ROOT/'tools/btc_expiry_study.py').read_bytes()) and x['ledger_sha256']==sha((ROOT/'tools/btc_target_ledger.py').read_bytes())
  assert x['calendar_sha256']==calendar_audit.CAL_SHA
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
 assert len(reports)==70
 summary=read(out/'summary.json');selection=read(out/'selection.json');a=summary['main-EX_LONG-base']['metrics'];b=summary['recent-EX_LONG-base']['metrics'];checks={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-EX_LONG-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):checks[c]=all(summary[p+'-EX_LONG-'+c]['metrics']['net_pnl']>0 for p in ('main','recent'))
 extra={}
 for name in ('EX_CLOCK','EX_PLACEBO','EX_WEEKLY','EX_TREND'):extra['net_beats_'+name+'_both']=all(summary[p+'-EX_LONG-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in ('main','recent'))
 extra['dd_no_worse_clock_both']=all(summary[p+'-EX_LONG-base']['metrics']['max_drawdown_pct']<=summary[p+'-EX_CLOCK-base']['metrics']['max_drawdown_pct'] for p in ('main','recent'))
 for c in ('base','cost_x2'):extra['event_only_'+c+'_positive_both']=all(summary[p+'-EX_ONLY-'+c]['metrics']['net_pnl']>0 for p in ('main','recent'))
 assert selection['checks']==checks and selection['information_increment']==extra and selection['passed']==(all(checks.values()) and all(extra.values()))
 identity=read(out/'control-identity.json')
 for period in ('main','recent'):
  a=read(out/f'{period}-EX_TREND-base.json.gz');b=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');assert len(a['daily'])==len(b['daily'])
  for x,y in zip(a['daily'],b['daily']):eqnum(x['equity'],y['equity'])
  for key in ('return_pct','max_drawdown_pct','fees','impact','funding'):eqnum(a['metrics'][key],b['metrics'][key])
 proof={'accounts':len(reports),'raw_archives':archive_count,'calendar_independent_audit':calendar_proof,'source_decisions':plans_checked,'intraday_event_plans':event_plans,'post_event_gross_months':sum(map(len,event_returns.values())),'event_bootstrap_draws_per_block':2000,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'selection_independently_checked':True,'trend_identity_independently_checked':True,'scope':'raw official UK holiday JSON and independent last-Friday/manual British DST calendar arithmetic, not actual CME calendar; raw BTC completed daily-risk signals, exact intraday sources/latencies; closed-form postcost qty/no-trade; Decimal accounts, mark/funding, hourlyDD, exposure, episodes, annual returns, volatility and margin; gross event diagnostics and monthly paired bootstrap independently checked'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
