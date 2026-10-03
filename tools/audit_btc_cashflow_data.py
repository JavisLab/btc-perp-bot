"""Independent Decimal reconstruction of raw BTC spot/perpetual daily flow aggregates."""
import csv,datetime as dt,hashlib,io,json,zipfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-cashflow-20261003';H=3600000;DAY=86400000
D=lambda x:Decimal(str(x))
def digest(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(p.read_bytes())
def write_json(p,x):p.write_text(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False))
def rows(p):
 with zipfile.ZipFile(p) as z:
  assert len(z.infolist())==1
  for r in csv.reader(io.StringIO(z.read(z.infolist()[0]).decode())):
   if r and r[0].isdigit():yield r
def clock(v):
 n=int(v);return n//1000 if len(str(n))>=16 else n

def run(write=True):
 payload=read(OUT/'daily.json');meta=read(OUT/'prepare-audit.json');assert digest((OUT/'daily.json').read_bytes())==meta['sha256'];start,end=payload['start'],payload['end'];assert end-start==2435*DAY;original={};reconstructed={};zero=set();invalid={};checks=0;native_checks=[];proof={'raw_archives':0,'raw_hours':0}
 mask=read(ROOT/'data/btc-venue-20261003/masks.json');res=read(ROOT/'data/structure-1471/resolution.json');prior={'spot':set(mask['binance_spot_no_trade']),'perp':set()}
 for e in res['unresolved']:
  if any(abs(D(v))>D('.001') for v in e['volume_errors']):prior['perp'].add(int(dt.datetime.fromisoformat(e['time']).timestamp()*1000))
 assert sorted(prior['spot'])==meta['prior_masks']['spot_hours'] and sorted(prior['perp'])==meta['prior_masks']['perp_hours']
 for path,key in [('data/btc-venue-20261003/masks.json','spot_sha256'),('data/structure-1471/resolution.json','resolution_sha256')]:assert digest((ROOT/path).read_bytes())==meta['prior_masks'][key]
 for kind in ('spot','perp'):
  rr={};problems={};paths=sorted((ROOT/f'data/archive-1448/{kind}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{kind}').glob('????-??.zip'));manifest={e['file']:e for e in meta['archives'] if e['kind']==kind};assert set(manifest)=={str(p.relative_to(ROOT)) for p in paths}
  for p in paths:
   b=p.read_bytes();sh=digest(b);assert sh==p.with_suffix('.CHECKSUM').read_text().split()[0]==manifest[str(p.relative_to(ROOT))]['sha256'];assert len(b)==manifest[str(p.relative_to(ROOT))]['bytes'];proof['raw_archives']+=1
   for r in rows(p):
    t=clock(r[0])
    if not start<=t<end:continue
    assert (len(r[0])>=16)==(kind=='spot' and t>=1735689600000)
    v={k:D(r[i]) for k,i in [('base',5),('quote',7),('trades',8),('buy_base',9),('buy_quote',10)]};o,h,l,c=[D(r[i]) for i in range(1,5)];errors=[]
    if t%H or clock(r[6])+1!=t+H:errors.append('irregular_clock')
    if not all(x.is_finite() for x in [*v.values(),o,h,l,c]):errors.append('nonfinite')
    else:
     if min(l,o,c,h)<=0 or h<max(o,l,c) or l>min(o,c):errors.append('ohlc')
     if min(v['base'],v['quote'])<=0:errors.append('nonpositive_volume')
     if not(0<=v['buy_base']<=v['base'] and 0<=v['buy_quote']<=v['quote']):errors.append('buyer_bounds')
     if v['trades']<0 or v['trades'].as_integer_ratio()[1]!=1:errors.append('trade_count')
    if t in prior[kind]:errors.append('prior_zero_volume' if kind=='spot' else 'prior_unresolved_volume')
    if kind=='spot' and v['base']<=0:zero.add(t)
    clean={'row':r,'values':v,'ohlc':(o,h,l,c)}
    if t in rr:assert rr[t]==clean
    rr[t]=clean
    if errors:problems[t]=errors
  assert {str(t):e for t,e in problems.items()}==meta['invalid_hours'][kind];proof['raw_hours']+=len(rr);original[kind]=rr;invalid[kind]=problems;out={}
  for day in range(start,end,DAY):
   selected=[rr[t] for t in range(day,day+DAY,H) if t in rr];totals={k:sum((r['values'][k] for r in selected),D(0)) for k in ('base','quote','trades','buy_base','buy_quote')};miss=[t for t in range(day,day+DAY,H) if t not in rr];bad={str(t):problems[t] for t in range(day,day+DAY,H) if t in problems};out[day]={'totals':totals,'missing':miss,'bad':bad,'probe_failed':False,'valid':not miss and not bad}
  reconstructed[kind]=out
 for e in meta['native_probes']:
  p=OUT/e['file'];assert digest(p.read_bytes())==p.with_suffix('.CHECKSUM').read_text().split()[0]==e['sha256'];r=list(rows(p));assert len(r)==1;r=r[0];t=clock(r[0]);assert dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat()==e['date'] and clock(r[6])==t+DAY-1;kind=e['kind'];rr=original[kind];complete=all(x in rr for x in range(t,t+DAY,H));tests={};errors={}
  if complete:
   chunk=[rr[x] for x in range(t,t+DAY,H)];tests['ohlc']=[chunk[0]['ohlc'][0],max(v['ohlc'][1] for v in chunk),min(v['ohlc'][2] for v in chunk),chunk[-1]['ohlc'][3]]==[D(r[i]) for i in range(1,5)]
   for k,i in [('base',5),('quote',7),('trades',8),('buy_base',9),('buy_quote',10)]:
    native=D(r[i]);err=abs(reconstructed[kind][t]['totals'][k]-native);errors[k]=err;tol=D(0) if k=='trades' else max(D('1e-8') if 'base' in k else D('1e-6'),abs(native)*D('1e-8'));tests[k]=err<=tol
  ok=complete and all(tests.values());assert e['complete']==complete and e['checks']==tests and e['passed']==ok;assert {k:D(v) for k,v in e['absolute_errors'].items()}==errors;reconstructed[kind][t]['probe_failed']=not ok;reconstructed[kind][t]['valid']&=ok;native_checks.append({'kind':kind,'day':t,'passed':ok});checks+=len(tests)
 for kind in ('spot','perp'):
  saved=payload['series'][kind];assert [e['day'] for e in saved]==list(reconstructed[kind])
  for e in saved:
   t=e['day'];r=reconstructed[kind][t];assert e['date']==dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat();assert (e['valid'],e['missing_hours'],e['bad_hours'],e['native_probe_failed'])==(r['valid'],r['missing'],r['bad'],r['probe_failed'])
   for k,v in r['totals'].items():assert D(e[k])==v,(kind,t,k)
  assert sum(e['valid'] for e in saved)==meta['coverage'][kind]['valid_days']
 assert zero==prior['spot'];assert len(native_checks)==10 and checks==6*sum(e['complete'] for e in meta['native_probes'])
 normalized={kind:{t:dict(r['totals'],valid=r['valid']) for t,r in dd.items()} for kind,dd in reconstructed.items()}
 report={**proof,'daily_values':2*2435*5,'days_per_market':2435,'native_probes':native_checks,'native_value_checks':checks,'invalid_dates':{kind:[dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat() for t,r in dd.items() if not r['valid']] for kind,dd in reconstructed.items()},'input_sha256':meta['sha256'],'scope':'Independent original checksum/Decimal BTC and USDT totals, buy bounds, UTC completed clocks/microseconds, historical unresolved masks, missing hours, fixed native 1d comparisons. No individual trade or private data; current archive not first vintage.'}
 if write:write_json(OUT/'independent-audit.json',report);print(json.dumps(report),flush=True)
 return normalized,report
if __name__=='__main__':run()
