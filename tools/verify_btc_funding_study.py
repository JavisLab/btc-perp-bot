"""Independent BTC raw funding signals and Decimal impulse account verification.
Account-path audit reused from verify_btc_oi_study; no simulator imports.
"""
import argparse,csv,gzip,io,json,math,zipfile
from decimal import Decimal,ROUND_FLOOR
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,sha
ROOT=Path(__file__).resolve().parents[1];STEP=300000;D=lambda x:Decimal(str(x))
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def run(out):
 out=Path(out);raw=read(ROOT/'data/structure-1471/bars-repaired.json.gz')['rows'];rm={r[0]:r for r in raw};first=raw[0][0]
 resolution=read(ROOT/'data/structure-1471/resolution.json');assert sha(canonical(raw))==resolution['repaired_rows_sha256']
 hourly=[];funds={}
 for name in ('perp','funding'):
  for p in sorted((ROOT/f'data/archive-1448/{name}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{name}').glob('????-??.zip')):
   with zipfile.ZipFile(p) as z:
    for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
     if not r[0].isdigit():continue
     if name=='perp':hourly.append([int(r[0]),*map(float,r[1:6])])
     else:funds[int(r[0])//HOUR*HOUR]=(D(r[2]),int(r[0]))
 bars=[]
 for k in range(0,len(hourly),4):
  a=hourly[k:k+4];bars.append([a[0][0],a[0][1],max(x[2] for x in a),min(x[3] for x in a),a[-1][4]])
 arr=np.array(bars);idx={int(r[0])+4*HOUR:i for i,r in enumerate(arr)};tr=np.maximum(arr[:,2]-arr[:,3],np.maximum(abs(arr[:,2]-np.r_[arr[0,1],arr[:-1,4]]),abs(arr[:,3]-np.r_[arr[0,1],arr[:-1,4]])))
 atr=np.full(len(arr),np.nan);atr[20:]=np.lib.stride_tricks.sliding_window_view(tr,20)[:-1].mean(axis=1);impulses=[i for i in range(20,len(arr)) if abs(arr[i,4]-arr[i-1,4])>=atr[i] and atr[i]>0]
 variants={p.name:read(p) for p in out.glob('signals-*.json.gz')};signal_count=0
 for fn,v in variants.items():
  lag=v['availability_minutes']*60000;threshold=D(v['threshold']);expected={k:[] for k in v['plans']}
  for i in impulses:
   source=int(arr[i,0])+4*HOUR;end=source-lag;window=sorted(t for t in funds if end-DAY<=t<end)
   if len(window)!=3 or window[1]-window[0]!=8*HOUR or window[2]-window[1]!=8*HOUR or any(funds[t][1]>=end for t in window):continue
   total=sum(funds[t][0] for t in window);side=1 if arr[i,4]>arr[i-1,4] else -1
   for name in expected:
    if name=='F_JOIN' and side*total<threshold:continue
    if name=='F_CROWD' and side*total>-threshold:continue
    expected[name].append((source,side,i,float(total),window))
  for name,es in expected.items():
   actual=v['plans'][name];assert len(es)==len(actual),(fn,name,len(es),len(actual))
   for (source,side,i,total,window),e in zip(es,actual):
    assert (source,side)==(e['source'],e['side']);assert e['funding_buckets']==window and e['funding_raw_times']==[funds[t][1] for t in window]
    assert abs(e['known_funding']-total)<1e-12 and e['funding_endpoint']==source-lag
    assert abs(e['atr']-atr[i])<1e-7 and abs(e['stop']-(arr[i,4]-side*2*atr[i]))<1e-7 and e['target'] is None
    assert abs(e['price_change']-(arr[i,4]-arr[i-1,4]))<1e-7
    signal_count+=1
 market=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];marks={r[0]:D(r[1]) for r in market['mark']}
 worst=0.;n_events=n_trades=n_daily=n_path=0;diagnostics={};checked=[]
 for p in sorted(out.glob('*-F_*.json.gz'))+sorted(out.glob('*-P_*.json.gz')):
  x=read(p);start,end=x['start'],x['end'];conf=x['config'];name=x['family'];a=(start-first)//STEP;b=(end-first)//STEP;subset=raw[a:b];n=len(subset)
  inventory=np.zeros(n);flows=np.zeros(n);stock=D(1000);signed=D(0);opened=D(0);expected_fund=[];actual_fund=[]
  variant=variants[f"signals-a{x['funding_config']['availability_minutes']}-f{x['funding_config']['threshold']:.4f}.json.gz"]
  sources={e['source']:e for e in variant['plans'][name]}
  for trade in x['trades']:
   source=trade['source'];side=trade['side'];enter=trade['entry'];exit=trade['exit'];stop=trade['initial_stop'];target=trade['target']
   assert source in sources and enter==source+STEP+conf['delay'] and trade['deadline']==enter+5*DAY
   for t in range(source,enter,STEP):
    r=rm[t];assert r[5]==0 or (r[3]>stop if side==1 else r[2]<stop)
   for t in range(enter,min(exit+STEP,end),STEP):
    r=rm[t];n_path+=1;complete=t-STEP-conf['delay']
    if complete>source and complete in idx:
     i=idx[complete];new=min(arr[i-9:i+1,3])-.1*atr[i] if side==1 else max(arr[i-9:i+1,2])+.1*atr[i]
     stop=max(stop,new) if side==1 else min(stop,new)
    if t>enter and t in funds:expected_fund.append((t,side,D(trade['qty'])))
    if r[5]<=0:continue
    ref=reason=None
    if side*(r[1]-stop)<=0:ref,reason=r[1],'stop_gap'
    elif t>=trade['deadline']:ref,reason=r[1],'time'
    elif (r[3]<=stop if side==1 else r[2]>=stop):ref,reason=stop,'stop'
    elif target is not None and (r[2]>=target if side==1 else r[3]<=target):ref,reason=target,'target'
    if reason:
     assert t==exit and reason==trade['reason'] and abs(ref-trade['exit_reference'])<1e-7,(p.name,t,exit,reason);break
    assert t<exit or trade['reason']=='period_end'
   n_trades+=1
  for e in x['events']:
   kind=e['kind'];t=e['time'];i=min((t-start)//STEP,n-1)
   if kind=='trail':continue
   if kind=='funding':
    rate,rt=funds[t];amount=-signed*rate*marks[t];assert rate==D(e['rate']) and rt==e['raw_time']
    assert abs(amount-D(e['cashflow']))<D('1e-8');stock+=amount;flows[i]+=float(amount);actual_fund.append((t,e['side'],D(e['qty'])))
   else:
    r=rm[t if t<end else end-STEP];ref=D(e['reference']);q=D(e['qty']);side=e['side'];impact=D('.00015')*D(conf['cost']);fee=D('.0005')*D(conf['cost'])
    assert r[5]>0
    if kind=='entry':
     assert signed==0 and ref==D(r[1]);new=side*q;fill=ref*(1+side*impact);opened=fill
     stopped=D(e['stop'])*(1-side*(impact+D(conf['stop_extra'])));unit=side*(fill-stopped)+fee*(fill+stopped)
     upper=min(stock*D(conf['risk'])/unit,stock/fill);expectedq=(upper/D('.001')).to_integral_value(rounding=ROUND_FLOOR)*D('.001')
     assert abs(q-expectedq)<D('1e-9') and q*fill>=50,(p.name,t,q,expectedq)
    else:
     assert signed==side*q;new=-signed
     if e['phase']=='open':assert ref==D(r[1])
     if e['phase']=='close':assert ref==D(r[4])
     if e['reason'].startswith('stop'):impact+=D(conf['stop_extra'])
     fill=ref*(1-side*impact)
    charge=q*fill*fee;flow=-new*fill-charge
    assert abs(fill-D(e['fill']))<D('1e-7') and abs(charge-D(e['fee']))<D('1e-8')
    stock+=flow;signed+=new;flows[i]+=float(flow);inventory[i]+=float(new)
   worst=max(worst,float(abs(stock+signed*opened-D(e['cash']))));n_events+=1
  assert sorted(expected_fund)==sorted(actual_fund),(p.name,'funding boundaries')
  inv=np.cumsum(inventory);eq=1000+np.cumsum(flows)+inv*np.array([r[4] for r in subset]);peak=np.maximum.accumulate(np.r_[1000,eq])[1:];dd=float(np.max((1-eq/peak)*100))
  worst=max(worst,abs(dd-x['summary']['dd_pct']),abs(float(stock)-x['daily'][-1]['equity']))
  for d in x['daily']:worst=max(worst,abs(eq[(d['time']-start)//STEP-1]-d['equity']));n_daily+=1
  diagnostics[p.name]={'mean_notional_pct':float(np.mean(abs(inv)*np.array([r[4] for r in subset])/eq)*100),'gross_price_pnl':math.fsum(t['price_gross'] for t in x['trades']),'fixed_trade_costs':x['summary']['fees']+x['summary']['impact'],'funding':x['summary']['funding'],'conflict_held_bars':x['summary']['unresolved_archive_exposure_bars']}
  checked.append(p.name)
 assert worst<1e-7,worst
 result={'accounts':len(checked),'raw_funding_records':len(funds),'independent_raw_signals':signal_count,'events':n_events,'trades':n_trades,'held_5m_paths':n_path,'daily_equities':n_daily,'max_numeric_error':worst,'limitations':'Historical funding availability/vintages assumed; actual fills, intrabar paths, liquidation and future edge not proven.'}
 (out/'verification.json').write_bytes(canonical(result));(out/'diagnostics.json').write_bytes(canonical(diagnostics));print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
