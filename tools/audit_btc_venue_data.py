"""Independent Decimal raw-candle audit, fixed daily-clock samples and explicit unusable observations."""
import csv,datetime as dt,gzip,hashlib,io,json,time,urllib.parse,urllib.request,zipfile
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-venue-20261003';H=3600000;DAY=24*H
D=lambda x:Decimal(str(x))
def read(p):return json.loads(p.read_bytes(),parse_float=Decimal)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def raw_rows(name,blob):
 data=json.loads(blob,parse_float=Decimal);rows=data if isinstance(data,list) else data['data']['ohlc']
 for x in rows:
  if name.startswith('coinbase'):yield int(x[0])*1000,*[D(x[i]) for i in (3,2,1,4,5)]
  else:yield int(x['timestamp'])*1000,*[D(x[i]) for i in ('open','high','low','close','volume')]
def run():
 saved=read(OUT/'candles.json');manifest=read(OUT/'archive-manifest.json');start,end=saved['start'],saved['end'];raw={n:{} for n in saved['series']};mask={n:set() for n in raw};duplicates=0;conflicts=[]
 for e in manifest:
  p=OUT/e['file'];b=p.read_bytes();assert sha(b)==e['sha256'] and len(b)==e['bytes'];name=e['series'];rr=list(raw_rows(name,b));assert len(rr)==e['rows'];assert e['url'].startswith(('https://api.exchange.coinbase.com/products/','https://www.bitstamp.net/api/v2/ohlc/'))
  for t,*values in rr:
   if not start<=t<end:continue
   assert t%H==0 and all(v.is_finite() for v in values);op,hi,lo,cl,vol=values
   if not(0<lo<=op<=hi and lo<=cl<=hi and vol>0):mask[name].add(t)
   if t in raw[name]:
    duplicates+=1
    if raw[name][t]!=values:mask[name].add(t);conflicts.append([name,t])
   else:raw[name][t]=values
 counts={}
 for n,rows in saved['series'].items():
  seen={r[0]:list(map(D,r[1:])) for r in rows};assert len(seen)==len(rows) and seen==raw[n]
  missing=set(range(start,end,H))-seen.keys();counts[n]={'hourly_rows':len(rows),'missing':len(missing),'first':min(seen),'last':max(seen),'nonpositive_or_conflicting_hours':len(mask[n])}
 dates=['2021-05-01','2022-01-01','2022-11-09','2023-03-11','2024-01-11','2026-08-31'];checks=[];sample_dir=OUT/'daily-probes';sample_dir.mkdir(exist_ok=True)
 for name in raw:
  for date in dates:
   t=int(dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc).timestamp()*1000);p=sample_dir/(name+'-'+date+'.json');mp=p.with_suffix('.meta.json')
   if name.startswith('coinbase'):
    product='BTC-USD' if 'btcusd' in name else 'USDT-USD';params={'granularity':86400,'start':date+'T00:00:00Z','end':dt.datetime.fromtimestamp((t+DAY-1000)/1000,dt.timezone.utc).isoformat()};url='https://api.exchange.coinbase.com/products/'+product+'/candles?'+urllib.parse.urlencode(params)
   else:url='https://www.bitstamp.net/api/v2/ohlc/btcusd/?'+urllib.parse.urlencode({'step':86400,'limit':1,'end':(t+DAY-1000)//1000,'exclude_current_candle':'true'})
   if p.exists():
    receipt=read(mp);b=p.read_bytes();assert receipt['url']==url and sha(b)==receipt['sha256']
   else:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-offline-research/1.0'}),timeout=30) as r:b=r.read();receipt={'url':url,'status':r.status,'sha256':sha(b),'bytes':len(b),'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    p.write_bytes(b);mp.write_bytes(canonical(receipt));time.sleep(.25)
   dd={q:list(v) for q,*v in raw_rows(name,b)};native=dd.get(t);rr=[raw[name].get(q) for q in range(t,t+DAY,H)];hourly_complete=all(r is not None for r in rr);bad=not hourly_complete or native is None;entry={'series':name,'date':date,'sha256':sha(b),'hourly_complete':hourly_complete,'native':list(map(str,native)) if native else None,'native_day_missing':native is None}
   if not bad:
    agg=[rr[0][0],max(v[1] for v in rr),min(v[2] for v in rr),rr[-1][3],sum(v[4] for v in rr)];eq=agg[:4]==native[:4];volume_error=abs(agg[4]-native[4]);vol_ok=volume_error<=max(D('0.000001'),abs(native[4])*D('0.00000001'));entry.update(aggregated=list(map(str,agg)),ohlc_equal=eq,volume_error=str(volume_error),volume_within_tolerance=vol_ok);bad=not eq or not vol_ok
   entry['masked_full_day']=bad
   if bad:mask[name].update(range(t,t+DAY,H))
   checks.append(entry)
 zero=set();spot_archives=[]
 for folder in (ROOT/'data/archive-1448/spot',ROOT/'data/archive-1458/BTCUSDT/spot'):
  for p in sorted(folder.glob('????-??.zip')):
   b=p.read_bytes();assert sha(b)==p.with_suffix('.CHECKSUM').read_text().split()[0];spot_archives.append({'file':str(p.relative_to(ROOT)),'sha256':sha(b)})
   with zipfile.ZipFile(io.BytesIO(b)) as z:
    for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
     if not r[0].isdigit():continue
     t=int(r[0]);t=t//1000 if t>10**14 else t
     if D(r[5])<=0:zero.add(t)
 masks={'external':{n:sorted(v) for n,v in mask.items()},'binance_spot_no_trade':sorted(zero)};(OUT/'masks.json').write_bytes(canonical(masks))
 report={'independent_hourly_rows':sum(v['hourly_rows'] for v in counts.values()),'series':counts,'raw_responses':len(manifest),'duplicate_comparisons':duplicates,'conflicts':conflicts,'daily_clock_checks':checks,'binance_spot_archives':spot_archives,'binance_spot_no_trade_hours':len(zero),'candles_sha256':sha((OUT/'candles.json').read_bytes()),'mask_sha256':sha((OUT/'masks.json').read_bytes()),'mask_hour_counts':{n:len(v) for n,v in mask.items()},'scope':'Independent Decimal raw API parses and fixed current-vintage native-daily comparisons; no original historical availability or publisher checksums for API data; no performance calculated'};(OUT/'independent-audit.json').write_bytes(canonical(report));print(json.dumps({k:v for k,v in report.items() if k not in ('daily_clock_checks','binance_spot_archives')},indent=2));print('DAILY',json.dumps(checks),flush=True)
if __name__=='__main__':run()
