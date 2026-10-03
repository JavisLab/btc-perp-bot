"""Prepare only public BTCUSDT spot/UM candle aggregates from existing checked archives."""
import csv,datetime as dt,hashlib,io,json,time,urllib.request,zipfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-cashflow-20261003';H=3600000;DAY=24*H
D=Decimal
FIELDS={'base':5,'quote':7,'trades':8,'buy_base':9,'buy_quote':10}
def sha(b):return hashlib.sha256(b).hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def stamp(s):return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def date(t):return dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat()
def decode(b):
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  assert len(z.namelist())==1
  for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
   if r and r[0].isdigit():yield r

def normclock(v):
 t=int(v);return t//1000 if t>10**14 else t

def run():
 OUT.mkdir(exist_ok=True);(OUT/'probes').mkdir(exist_ok=True);start,end=stamp('2020-01-01'),stamp('2026-09-01');series={};archives=[];probes=[];coverage={};issues={}
 mask_path=ROOT/'data/btc-venue-20261003/masks.json';mask_bytes=mask_path.read_bytes();spot_bad=set(json.loads(mask_bytes)['binance_spot_no_trade']);res_path=ROOT/'data/structure-1471/resolution.json';res_bytes=res_path.read_bytes();res=json.loads(res_bytes);perp_bad={stamp(x['time'].replace('Z','+00:00')) for x in res['unresolved'] if any(abs(v)>1e-3 for v in x['volume_errors'])}
 old={'spot':spot_bad,'perp':perp_bad};raw={};days={}
 for kind in ('spot','perp'):
  rr={};dupes=0;units={};bad={}
  paths=sorted((ROOT/f'data/archive-1448/{kind}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{kind}').glob('????-??.zip'))
  for p in paths:
   b=p.read_bytes();digest=sha(b);assert digest==p.with_suffix('.CHECKSUM').read_text().split()[0];archives.append({'kind':kind,'file':str(p.relative_to(ROOT)),'sha256':digest,'bytes':len(b)})
   for row in decode(b):
    t=normclock(row[0]);unit='microseconds' if int(row[0])>10**14 else 'milliseconds';units[unit]=units.get(unit,0)+1
    if not start<=t<end:continue
    assert len(row)>=11,(p,t)
    if kind=='spot':assert unit==('microseconds' if t>=stamp('2025-01-01') else 'milliseconds')
    else:assert unit=='milliseconds'
    vals={k:D(row[i]) for k,i in FIELDS.items()};ohlc=[D(row[i]) for i in (1,2,3,4)];reasons=[]
    if t%H!=0 or normclock(row[6])!=t+H-1:reasons.append('irregular_clock')
    if not all(v.is_finite() for v in [*vals.values(),*ohlc]):reasons.append('nonfinite')
    else:
     o,h,l,c=ohlc
     if not(0<l<=o<=h and l<=c<=h):reasons.append('ohlc')
     if not(vals['base']>0 and vals['quote']>0):reasons.append('nonpositive_volume')
     if not(0<=vals['buy_base']<=vals['base'] and 0<=vals['buy_quote']<=vals['quote']):reasons.append('buyer_bounds')
     if vals['trades']<0 or vals['trades']!=int(vals['trades']):reasons.append('trade_count')
    if t in old[kind]:reasons.append('prior_zero_volume' if kind=='spot' else 'prior_unresolved_volume')
    clean={'open_time':t,'close_time':normclock(row[6]),'ohlc':[str(v) for v in ohlc],**{k:str(v) for k,v in vals.items()}}
    if t in rr:dupes+=1;assert rr[t]==clean,('conflicting_duplicate',kind,t)
    rr[t]=clean
    if reasons:bad[t]=reasons
  dd=[]
  for day in range(start,end,DAY):
   present=[rr[t] for t in range(day,day+DAY,H) if t in rr];missing=[t for t in range(day,day+DAY,H) if t not in rr];bad_hours={str(t):bad[t] for t in range(day,day+DAY,H) if t in bad};sums={k:str(sum((D(r[k]) for r in present),D(0))) for k in FIELDS}
   dd.append({'day':day,'date':date(day),'valid':not missing and not bad_hours,'missing_hours':missing,'bad_hours':bad_hours,'native_probe_failed':False,**sums})
  raw[kind]=rr;days[kind]=dd;coverage[kind]={'archives':len(paths),'hours':len(rr),'duplicates_equal':dupes,'units':units,'missing_hours':len(set(range(start,end,H))-rr.keys()),'bad_hours':len(bad)};issues[kind]={str(t):v for t,v in bad.items()}
 # Fixed 1d probes, only BTCUSDT. No private endpoints or external code.
 for kind in ('spot','perp'):
  prefix='spot' if kind=='spot' else 'futures/um'
  for date_str in ('2020-01-01','2022-01-01','2023-03-24','2025-01-01','2026-08-31'):
   name=f'{kind}-{date_str}';fn=f'BTCUSDT-1d-{date_str}.zip';url=f'https://data.binance.vision/data/{prefix}/daily/klines/BTCUSDT/1d/{fn}';p=OUT/'probes'/(name+'.zip');cp=p.with_suffix('.CHECKSUM')
   receipts=[]
   for path,u in [(p,url),(cp,url+'.CHECKSUM')]:
    mp=Path(str(path)+'.meta.json')
    if path.exists():b=path.read_bytes();r=json.loads(mp.read_text());assert sha(b)==r['sha256'] and r['url']==u
    else:
     with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'BTC-public-aggregate-research/1.0'}),timeout=45) as response:b=response.read();r={'url':u,'status':response.status,'bytes':len(b),'sha256':sha(b),'retrieved':dt.datetime.now(dt.timezone.utc).isoformat()}
     path.write_bytes(b);mp.write_bytes(canon(r));time.sleep(.25)
    receipts.append(r)
   assert sha(p.read_bytes())==cp.read_text().split()[0];native=list(decode(p.read_bytes()));assert len(native)==1;nr=native[0];day=stamp(date_str);assert normclock(nr[0])==day and normclock(nr[6])==day+DAY-1
   rr=[raw[kind].get(t) for t in range(day,day+DAY,H)];complete=all(x is not None for x in rr);checks={};errors={}
   if complete:
    agg=[D(rr[0]['ohlc'][0]),max(D(x['ohlc'][1]) for x in rr),min(D(x['ohlc'][2]) for x in rr),D(rr[-1]['ohlc'][3])];checks['ohlc']=agg==[D(nr[i]) for i in (1,2,3,4)]
    for k,i in FIELDS.items():
     a=sum(D(x[k]) for x in rr);b=D(nr[i]);err=abs(a-b);errors[k]=str(err);tol=D(0) if k=='trades' else max(D('0.00000001' if 'base' in k else '0.000001'),abs(b)*D('0.00000001'));checks[k]=err<=tol
   passed=complete and all(checks.values());e=days[kind][(day-start)//DAY];e['native_probe_failed']=not passed;e['valid']=e['valid'] and passed;probes.append({'kind':kind,'date':date_str,'file':str(p.relative_to(OUT)),'sha256':sha(p.read_bytes()),'complete':complete,'checks':checks,'absolute_errors':errors,'passed':passed});print(json.dumps(probes[-1]),flush=True)
 for kind in days:coverage[kind]['valid_days']=sum(e['valid'] for e in days[kind]);coverage[kind]['invalid_days']=[e['date'] for e in days[kind] if not e['valid']]
 payload={'start':start,'end':end,'units':{'base':'BTC','quote':'USDT','trades':'count'},'series':days,'clock':'UTC complete day; D+2 availability assumption, not first vintage'};(OUT/'daily.json').write_bytes(canon(payload));report={'sha256':sha(canon(payload)),'archives':archives,'coverage':coverage,'invalid_hours':issues,'native_probes':probes,'prior_masks':{'spot_sha256':sha(mask_bytes),'resolution_sha256':sha(res_bytes),'spot_hours':sorted(spot_bad),'perp_hours':sorted(perp_bad)},'scope':'Only public aggregate BTCUSDT klines; no performance, individual trades, accounts or orders'};(OUT/'prepare-audit.json').write_bytes(canon(report));print(json.dumps({'input_sha256':report['sha256'],'archives':len(archives),'coverage':coverage}),flush=True)
if __name__=='__main__':run()
