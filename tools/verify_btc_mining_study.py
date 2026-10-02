"""Independent BTC mining-source, EMA/momentum, and account verification and analytic/Decimal target-account replay."""
import argparse,hashlib,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def audit_mining():
 p=ROOT/'data/btc-mining-20261002';audit=read(p/'prepare-audit.json');saved=read(p/'prepared.json');assert sha(canonical(saved))==audit['rows_sha256']=='1429ff3f1b56e977f0af6000b0956f62abdc1b9a5ac3f647e41b9e8b0a8f0d92'
 for n,h in audit['source_files'].items():assert sha((p/n).read_bytes())==h
 charts={n:{r['x']*1000:D(r['y']) for r in read(p/(n+'.json'))['values']} for n in ('hash-rate','difficulty','n-transactions','n-transactions-per-block')};cm={ms(e['time']):e for e in csv.DictReader((p/'btc-community.csv').open())};records={};patch_count=0;max_formula=0.
 for e in saved:
  t=e['day']
  if t in charts['hash-rate']:
   n=charts['n-transactions'][t]/charts['n-transactions-per-block'][t];cnt=int(n.to_integral_value());assert abs(n-cnt)<D('1e-8') and cnt>0;diff=charts['difficulty'][t];h=D(cnt)*diff*D(4294967296)/D(86400000000000000);err=abs(h/charts['hash-rate'][t]-1);assert err<D('1e-12');max_formula=max(max_formula,float(err));kind='blockchain-chart'
  else:
   date=dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat();blocks=sorted(read(p/f'blocks-day-{date}.json'),key=lambda b:b['height']);cnt=len(blocks);heights=[b['height'] for b in blocks];assert all(t<=b['time']*1000<t+DAY for b in blocks);assert heights==list(range(heights[0],heights[-1]+1));assert heights[0]//2016==heights[-1]//2016;difficulty=[]
   for b in (blocks[0],blocks[-1]):
    raw=bytes.fromhex((p/f'header-{b["height"]}.txt').read_text().strip());assert hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex()==b['hash'];assert int.from_bytes(raw[68:72],'little')==b['time'];bits=int.from_bytes(raw[72:76],'little');target=(bits & 0xffffff) << (8*((bits>>24)-3));difficulty.append(D(0xffff << 208)/D(target))
   assert difficulty[0]==difficulty[1];diff=difficulty[0];h=D(cnt)*diff*D(4294967296)/D(86400000000000000);kind='raw-block-header-gap-reconstruction';patch_count+=cnt;assert int(cm[t]['BlkCnt'])==cnt and abs(D(cm[t]['HashRate'])/h-1)<D('1e-7')
  alt=D(cm[t]['HashRate']) if t in cm and cm[t]['HashRate'] else h;assert e['source']==t+2*DAY and e['blocks']==cnt and e['provenance']==kind and abs(D(e['hashrate'])/h-1)<D('1e-12') and abs(D(e['hashrate_provider_cm'])/alt-1)<D('1e-12');records[t]={'base':float(h),'provider_cm':float(alt),'source':t+2*DAY}
 assert len(records)==2466 and list(records)==list(range(min(records),max(records)+DAY,DAY));return records,{'days':len(records),'raw_source_files':len(audit['source_files']),'patch_blocks':patch_count,'hash_verified_headers':6,'formula_relative_error':max_formula,'original_vintages_not_fully_recovered':True,'normalized_sha256':audit['rows_sha256']}

def run(out):
 out=Path(out);mining,data_proof=audit_mining();payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={};rawvolume={};rawmarks={};archive_count=0
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
      rawprice[(key,t)]=(D(rr[1]),D(rr[4]));rawvolume[(key,t)]=D(rr[5])
      if key=='BS' and t%DAY==23*HOUR and t>=ms('2020-02-01'):spot[t+HOUR]=float(rr[4])
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
 source_features={};feature_checks=0;saved_features=read(out/'features.json.gz')
 for variant in ('base','provider_cm'):
  records={}
  for e in saved_features[variant]:
   t=e['day'];h=[mining.get(t-j*DAY,{}).get(variant) for j in range(60)];valid=all(v is not None and math.isfinite(v) and v>0 for v in h);assert valid==e['valid'] and e['source']==t+2*DAY
   if valid:
    short=math.fsum(h[:30])/30;long=math.fsum(h)/60;assert abs(short/e['h30']-1)<1e-11 and abs(long/e['h60']-1)<1e-11;records[t]=(short,long);feature_checks+=1
   else:assert e['h30'] is None and e['h60'] is None
  source_features[variant]=records
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];tail=p.name.split('-plan-')[1];variant=tail.split('-lag')[0];lag=int(tail.split('-lag')[1].split('-risk')[0]);risk=float(tail.split('-risk')[1].removesuffix('.json.gz'))
  for e in plan:
   t=e['source_time'];i=dayidx[t];hist=daily[i-20:i+1]
   if i<128 or not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   ret=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(ret)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in ret)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;sign=lambda v:int(v>0)-int(v<0);score=(sum(sign(daily[i]-daily[i-n]) for n in (20,60,120))+sum(sign(em[a][i]-em[b][i]) for a,b in ((8,32),(16,64),(32,128))))/6;P=max(0,score);h=source_features[variant].get(t-lag*DAY);valid=h is not None;G=int(h[0]>=h[1]) if valid else None;s=0
   if valid:s={'HG_REC':P*G,'HG_STRESS':P*(1-G),'HG_HASH':G,'HG_INV':-P*G}[name]
   assert e['detail']['signal']==s and e['detail']['common_valid']==valid and e['detail']['score']==score and e['detail']['gate']==G
   if valid:assert e['detail']['observed_day']==t-lag*DAY and e['detail']['information_time']==t-(lag-2)*DAY and e['detail']['usable_time']==t
   for k,v in [('BS',max(s,0)*w),('BP',min(s,0)*w)]:assert abs(e['weights'][k]-v)<1e-9
   raw_signals[(name,variant,lag,risk,t)]=e;plans_checked+=1
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith('features'):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-{x['input_variant']}-lag{x['source_lag_days']}-risk{x['risk_target']:.2f}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
  for e in x['events']:bytime[e['time']].append(e)
  def equal(a,b):
   nonlocal worst
   delta=float(abs(D(a)-D(b)));worst=max(worst,delta);assert delta<1e-7,(p.name,a,b)
  def value(prices):return cash+sum(q[k]*D(prices[k]) for k in KEYS)
  def observe(prices):
   nonlocal peak,dd
   eq=value(prices);peak=max(peak,eq);dd=max(dd,(1-eq/peak)*100);return eq
  def fill(e):
   nonlocal cash,fee_sum,impact_sum
   k=e['instrument'];t=e['time'];dq=D(e['delta']);ref=rawprice[(k,end-HOUR)][1] if t==end else rawprice[(k,t)][0];slip=D(model['impact_bps'])/10000;px=ref*(1+(slip if dq>0 else -slip));charge=abs(dq)*px*D(model['fee_bps'][k])/10000;loss=abs(dq)*ref*slip
   equal(ref,e['reference']);equal(px,e['price']);equal(charge,e['fee']);equal(loss,e['impact']);assert rawvolume[(k,end-HOUR if t==end else t)]>0
   if t<end:
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['input_variant'],x['source_lag_days'],x['risk_target'],e['source_time']) in raw_signals
    step=D('.00001' if k=='BS' else '.001');equal(D(e['position'])/step,round(float(D(e['position'])/step)));reducing=q[k]*dq<0 and abs(D(e['position']))<abs(q[k]);assert abs(dq)*px>=D(5 if k=='BS' else 50)-D('1e-7') or(k=='BP' and reducing)
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
   observe(op);eq=observe(cl)
   if not q['BP']:assert cash>=D('-1e-7')
   if t+HOUR in daily_map:
    d=daily_map[t+HOUR]
    if t+HOUR==end:
     for e in bytime[end]:fill(e)
     eq=observe({k:rawprice[(k,end-HOUR)][1] for k in KEYS})
    equal(eq,d['equity']);equal(cash,d['cash']);equal(fee_sum,d['fees']);equal(impact_sum,d['impact']);equal(fund_sum,d['funding']);equal((1-eq/peak)*100,d['drawdown_pct'])
    for k in KEYS:equal(q[k],d['positions'][k])
  equal(cash,x['metrics']['equity']);equal(dd,x['metrics']['max_drawdown_pct']);side={k:{**{a:float(v) for a,v in z.items()},'net':float(z['gross']-z['fees']-z['impact']+z['funding'])} for k,z in sides.items()};equal(sum(z['net'] for z in side.values()),x['metrics']['net_pnl']);diag[p.name]={'sides':side,'skips':x['skips']};reports.append({'file':p.name,'events':len(x['events']),'daily':len(x['daily'])})
 proof={'accounts':len(reports),'raw_hash_feature_windows':feature_checks,'data':data_proof,'raw_archives':archive_count,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'independent chart count ratios/Decimal hashrate formula and block/header gap reconstruction; separate raw BTC spot EMA/momentum/volatility and lag/provider gates; piecewise closed-form post-cost targets/no-trade; raw positive-volume fills, mark and actual funding; Decimal inventory/cash/hourlyDD'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path);p.add_argument('--data-only',action='store_true');a=p.parse_args()
 if a.data_only:
  _,proof=audit_mining();print(json.dumps(proof))
 else:run(a.out)
