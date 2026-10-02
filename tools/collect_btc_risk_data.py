"""BTC-only public 5m warmup archives; existing audited fine history is reused."""
import csv,concurrent.futures,gzip,io,json,math,urllib.request,zipfile
from pathlib import Path
from btc_perp_bot.research.archive import DAY,HOUR,canonical,sha,ms,utc
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-rv-20261002';STEP=300000

def get(month):
 base='https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-'+month+'.zip';p=OUT/'raw'/(month+'.zip');c=p.with_suffix('.CHECKSUM')
 if not p.exists():p.write_bytes(urllib.request.urlopen(base,timeout=35).read())
 if not c.exists():c.write_bytes(urllib.request.urlopen(base+'.CHECKSUM',timeout=35).read())
 body=p.read_bytes();assert sha(body)==c.read_text().split()[0]
 rows=[]
 with zipfile.ZipFile(io.BytesIO(body)) as z:
  for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
   if not r[0].isdigit():continue
   t,ct=int(r[0]),int(r[6]);v=[float(r[i]) for i in range(1,6)];o,h,l,cl,vol=v
   assert t<10**14 and t%STEP==0 and ct==t+STEP-1 and 0<l<=min(o,cl)<=max(o,cl)<=h and vol>=0
   assert all(math.isfinite(x) for x in v)
   rows.append([t,*v,ct,float(r[7]),int(r[8]),float(r[9]),float(r[10])])
 return {'month':month,'url':base,'sha256':sha(body),'rows':len(rows)},rows

def run():
 (OUT/'raw').mkdir(parents=True,exist_ok=True);months=[f'{y}-{m:02d}' for y in (2020,2021) for m in range(1,13) if y<2021 or m<=9];results=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(get,months));warm=[r for _,rows in results for r in rows];assert [r[0] for r in warm]==list(range(ms('2020-01-01'),ms('2021-10-01'),STEP));resolution=json.loads((ROOT/'data/structure-1471/resolution.json').read_text());old=json.loads(gzip.decompress((ROOT/'data/structure-1471/bars-repaired.json.gz').read_bytes()))['rows'];assert sha(canonical(old))==resolution['repaired_rows_sha256'];rows=warm+old
 hourly={r[0]:r for r in json.loads(gzip.decompress((ROOT/'runs/price-volume-1462/ohlcv.json.gz').read_bytes()))['rows']};conflicts=[];invalid=set()
 for i in range(0,len(warm),12):
  part=warm[i:i+12];t=part[0][0];h=hourly[t];ohlc=[part[0][1],max(r[2] for r in part),min(r[3] for r in part),part[-1][4]];verr=[math.fsum(r[k] for r in part)-h[k] for k in (5,7,9,10)];count=sum(r[8] for r in part)-h[8]
  if ohlc!=h[1:5] or any(abs(v)>1e-3 for v in verr) or count:
   conflicts.append({'time':utc(t),'ohlc_5m':ohlc,'ohlc_1h':h[1:5],'volume_errors':verr,'count_difference':count})
   if ohlc[3]!=h[4]:invalid.add(t//DAY*DAY)
 daily=[];prior=None
 for i in range(0,len(rows),288):
  part=rows[i:i+288];t=part[0][0];assert len(part)==288 and [r[0] for r in part]==list(range(t,t+DAY,STEP));rr=[]
  for r in part:
   if prior is not None:rr.append(math.log(r[4]/prior))
   prior=r[4]
  valid=len(rr)==288 and t not in invalid;up=math.fsum(x*x for x in rr if x>0);down=math.fsum(x*x for x in rr if x<0)
  daily.append({'day':t,'end':t+DAY,'rv':up+down if valid else None,'up':up if valid else None,'down':down if valid else None,'zero_bars':sum(r[5]==0 for r in part),'valid':valid})
 audit={'new_files':[r for r,_ in results],'new_rows':len(warm),'old_rows':len(old),'new_period':[utc(warm[0][0]),utc(warm[-1][0]+STEP)],'total_rows':len(rows),'daily_count':len(daily),'warmup_conflicts':conflicts,'invalid_close_days':sorted(invalid),'invalid_rv_days':[r['day'] for r in daily if not r['valid']],'zero_bars_new':sum(r[5]==0 for r in warm),'warmup_rows_sha256':sha(canonical(warm)),'daily_sha256':sha(canonical(daily)),'old_repaired_rows_sha256':resolution['repaired_rows_sha256'],'scope':'checksum/grid/OHLC/1h comparison for new21 months only; previously audited old59 months reused'}
 (OUT/'warmup-bars.json.gz').write_bytes(gzip.compress(canonical({'rows':warm}),mtime=0));(OUT/'daily-rv.json.gz').write_bytes(gzip.compress(canonical(daily),mtime=0));(OUT/'audit.json').write_bytes(canonical(audit));print(json.dumps({k:v for k,v in audit.items() if k!='new_files'}),flush=True)
if __name__=='__main__':run()
