"""Independent raw BTC incremental-option normal equations/clocks/signals and analytic/Decimal target-account replay."""
import argparse,csv,datetime as dt,gzip,io,itertools,json,math,re,zipfile
from collections import defaultdict
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical,sha
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));KEYS=('BS','BP')
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
from verify_btc_cot_study import audit_cot
def audit_positions():
 cot,proof=audit_cot();folder=ROOT/'data/btc-cot-20261002';fut=read(folder/'btc-futures-only.json');raw=(folder/'btc-combined.json').read_bytes();assert sha(raw)=='78400a9a963b3e0ba14957842cfbd2157512b68fd940410f0fdade15a8dd655f';combo=json.loads(raw);assert len(combo)==len(cot);errors=[]
 for j,(r,f,c) in enumerate(zip(cot,fut,combo)):
  assert r['date']==c['report_date_as_yyyy_mm_dd'][:10] and c['cftc_contract_market_code']=='133741' and c['commodity_name']=='BITCOIN' and c['futonly_or_combined']=='Combined' and c['contract_units']=='(5 Bitcoins)'
  r['F']=int(f['asset_mgr_positions_long'])-int(f['asset_mgr_positions_short']);r['O']=int(c['asset_mgr_positions_long'])-int(c['asset_mgr_positions_short'])-r['F']
  # Gross long/short each include spreads, which must cancel from net exposures.
  assert r['O']==(int(c['asset_mgr_positions_long'])+int(c['asset_mgr_positions_spread'])-int(c['asset_mgr_positions_short'])-int(c['asset_mgr_positions_spread']))-(int(f['asset_mgr_positions_long'])+int(f['asset_mgr_positions_spread'])-int(f['asset_mgr_positions_short'])-int(f['asset_mgr_positions_spread']))
  oi=int(c['open_interest_all']);spread=sum(int(c[k]) for k in ('dealer_positions_spread_all','asset_mgr_positions_spread','lev_money_positions_spread','other_rept_positions_spread'))
  for side,total in [('long','tot_rept_positions_long_all'),('short','tot_rept_positions_short')]:
   error=spread+sum(int(c[k]) for k in ('dealer_positions_'+side+'_all','asset_mgr_positions_'+side,'lev_money_positions_'+side,'other_rept_positions_'+side,'nonrept_positions_'+side+'_all'))-oi;assert abs(error)<=5;errors.append(error);assert int(c[total])+int(c['nonrept_positions_'+side+'_all'])==oi
  if j:assert cot[j-1]['report']<r['report'] and cot[j-1]['source']<=r['source']
 proof.update(combined_raw_sha256=sha(raw),category_sum_error_counts={str(e):errors.count(e) for e in sorted(set(errors))},max_category_sum_error=max(map(abs,errors)),net_option_nonzero_reports=sum(e['O']!=0 for e in cot),delta_equivalent_not_new_trades=True)
 return cot,proof

def independent_predictions(cot,spot,phase):
 rows=[]
 for i,e in enumerate(cot):
  z=dict(e,valid=False,truth=None,truth_end=e['source']+7*DAY,models={});a,b=spot.get(e['source']),spot.get(z['truth_end'])
  if a is not None and b is not None:z['truth']=math.log(b/a)
  if i:
   prev=cot[i-1];a,b=spot.get(prev['report']+DAY),spot.get(e['report']+DAY);z['valid']=prev['source']<=e['source'] and e['report']+DAY<=e['source'] and prev['oi']>0 and a is not None and b is not None
   if z['valid']:z['x']=[math.log(b/a),(e['F']-prev['F'])/prev['oi'],(e['O']-prev['O']+phase*((-1)**i-(-1)**(i-1)))/prev['oi']]
  rows.append(z)
 for i,e in enumerate(rows):
  train=[j for j in range(max(0,i-104),i) if rows[j]['valid'] and rows[j]['truth'] is not None and rows[j]['truth_end']<=e['source']]
  for name,k in [('OP_INC',3),('OP_FUT',2),('OP_PRICE',1)]:
   p={'mu':None,'se':None,'training_n':len(train)};e['models'][name]=p
   if not e['valid'] or len(train)<78:continue
   a=np.array([rows[j]['x'][:k] for j in train]);y=np.array([rows[j]['truth'] for j in train]);center=np.array([math.fsum(a[:,h])/len(a) for h in range(k)]);sd=np.array([math.sqrt(math.fsum((v-center[h])**2 for v in a[:,h])/len(a)) for h in range(k)]);sd[sd<1e-12]=1.;Z=np.column_stack([np.ones(len(a)),(a-center)/sd])
   if np.linalg.matrix_rank(Z)<k+1:continue
   gram=Z.T@Z;coef=np.linalg.solve(gram,Z.T@y);current=np.r_[1.,(np.array(e['x'][:k])-center)/sd];mu=float(current@coef);res=y-Z@coef;s2=math.fsum(v*v for v in res)/(len(a)-k-1);se=math.sqrt(max(0,s2*float(current@np.linalg.solve(gram,current))));beta=np.r_[coef[0]-sum(coef[1:]*center/sd),coef[1:]/sd]
   p.update(mu=mu,se=se,beta=beta.tolist(),training_indices=train,training_label_end=max(rows[j]['truth_end'] for j in train))
 return rows


def run(out):
 out=Path(out);cot,data_proof=audit_positions();payload=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];rows={'BS':{r[0]:r for r in payload['spot']},'BP':{r[0]:r for r in payload['perp']}};marks={'BS':rows['BS'],'BP':{r[0]:r for r in payload['mark']}};funds={};spot={};rawprice={};rawvolume={};rawmarks={};archive_count=0
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
 predictions={};predictions_checked=0;prediction_error=0.
 for variant,phase in [('base',0),('rounding_plus',1),('rounding_minus',-1)]:
  rr=independent_predictions(cot,spot,phase);predictions[variant]=rr;recorded=read(out/f'features-{variant}.json.gz');assert len(recorded)==len(rr)
  for e,z in zip(recorded,rr):
   assert e['report_date']==z['date'] and e['valid']==z['valid'] and e['truth_end']==z['truth_end'] and e['truth']==z['truth']
   if z['valid']:
    for k,v in zip(('r','f','o'),z['x']):assert abs(e[k]-v)<1e-13
   for name,p in z['models'].items():
    a=e['models'][name];assert a['training_n']==p['training_n']
    if p['mu'] is None:assert a['mu'] is None;continue
    assert a['training_indices']==p['training_indices'] and a['training_label_end']==p['training_label_end']<=e['source']
    for k in ('mu','se'):
     error=abs(a[k]-p[k]);prediction_error=max(prediction_error,error);assert error<1e-10
    assert np.allclose(a['beta'],p['beta'],atol=1e-9,rtol=1e-9);predictions_checked+=1
 plans_checked=0;raw_signals={}
 for p in out.glob('*-plan-*.json.gz'):
  plan=read(p);name=p.name.split('-')[1];variant=p.name.split('-plan-')[1].split('-risk')[0];risk=float(p.name.split('-risk')[1].removesuffix('.json.gz'))
  for e in plan:
   t=e['source_time'];i=dayidx[t];hist=daily[i-20:i+1]
   if not np.all(np.isfinite(hist)):assert e['weights'] is None;continue
   returns=[math.log(b/a) for a,b in zip(hist,hist[1:])];mean=math.fsum(returns)/20;vol=math.sqrt(math.fsum((r-mean)**2 for r in returns)/19*365);w=min(1,risk/vol) if vol>1e-12 else 0;known=[r for r in predictions[variant] if r['source']<=t];last=max(known,key=lambda r:r['report']) if known else None;valid=last is not None and last['valid'] and t<last['expiry'];s=0
   if valid:
    pred=last['models']['OP_INC' if name=='OP_INV' else name]
    if pred['mu'] is not None:s=(1 if pred['mu']>math.log1p(.0023)+pred['se'] else -1 if pred['mu']<-math.log1p(.0013)-pred['se'] else 0)*(-1 if name=='OP_INV' else 1)
   assert e['detail']['signal']==s and e['detail']['common_valid']==valid
   if last:assert e['detail']['report_date']==last['date'] and e['detail']['information_time']==last['source'] and e['detail']['age_days']==(t-last['report'])//DAY
   else:assert e['detail']['report_date'] is None
   for k,v in [('BS',max(s,0)*w),('BP',min(s,0)*w)]:assert abs(e['weights'][k]-v)<1e-9
   raw_signals[(name,variant,risk,t)]=e;plans_checked+=1
 reports=[];worst=0.;diag={};quantities=0;no_trade=0;raw_funding_events=0
 for p in sorted(out.glob('*.json.gz')):
  if '-plan-' in p.name or p.name.startswith('features-'):continue
  x=read(p);model=x['model'];start,end=ms(x['start']),ms(x['end']);q={k:D(0) for k in KEYS};cash=D(1000);fee_sum=impact_sum=fund_sum=D(0);peak=D(1000);dd=D(0);daily_map={d['time']:d for d in x['daily']};bytime=defaultdict(list);latest={};sides={k:{'gross':D(0),'fees':D(0),'impact':D(0),'funding':D(0)} for k in KEYS};plan=read(out/f"{x['period']}-{x['strategy']}-plan-{x['input_variant']}-risk{x['risk_target']:.2f}.json.gz");planned={e['source_time']+HOUR*(1+model['extra_delay_hours']):e for e in plan}
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
    assert t==e['source_time']+HOUR*(1+model['extra_delay_hours']) and (x['strategy'],x['input_variant'],x['risk_target'],e['source_time']) in raw_signals
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
 proof={'accounts':len(reports),'independent_predictions':predictions_checked,'max_prediction_error':prediction_error,'data':data_proof,'raw_archives':archive_count,'raw_daily_decisions':plans_checked,'independent_target_quantities':quantities,'no_trade_decisions':no_trade,'raw_mark_funding_events':raw_funding_events,'events':sum(r['events'] for r in reports),'daily_equities':sum(r['daily'] for r in reports),'max_numeric_error':worst,'scope':'independent CFTC combined-minus-futures AM net/balances/disclosure clocks; raw BTC spot features/mature labels; centered normal-equation mean/SE and paired forecasts; raw spot volatility/signals; piecewise closed-form post-cost targets/no-trade; raw positive-volume fills, mark and actual funding; Decimal inventory/cash/hourlyDD'}
 (out/'verification.json').write_bytes(canonical(proof));(out/'diagnostics.json').write_bytes(canonical(diag));print(json.dumps(proof),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path);p.add_argument('--data-only',action='store_true');a=p.parse_args()
 if a.data_only:
  _,proof=audit_positions();print(json.dumps(proof))
 else:run(a.out)
