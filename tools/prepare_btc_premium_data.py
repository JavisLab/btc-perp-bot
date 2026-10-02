"""BTC-only official premium-index archive; no trading returns calculated."""
import calendar,csv,gzip,hashlib,io,json,math,urllib.request,zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data/btc-premium-20261002';H=3600000

def digest(b):return hashlib.sha256(b).hexdigest()
def put(p,b):
 if p.exists():assert p.read_bytes()==b,('immutable',str(p))
 else:p.write_bytes(b)
def fetch(month):
 n=f'BTCUSDT-1h-{month}.zip';u='https://data.binance.vision/data/futures/um/monthly/premiumIndexKlines/BTCUSDT/1h/'+n
 p=OUT/n;c=OUT/(n+'.CHECKSUM')
 if not p.exists():put(p,urllib.request.urlopen(u,timeout=40).read())
 if not c.exists():put(c,urllib.request.urlopen(u+'.CHECKSUM',timeout=40).read())
 b=p.read_bytes();assert digest(b)==c.read_text().split()[0],n
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  assert len(z.namelist())==1;raw=list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))
 header=bool(raw and raw[0][0]=='open_time')
 if header:raw=raw[1:]
 y,m=map(int,month.split('-'));start=int(datetime(y,m,1,tzinfo=timezone.utc).timestamp()*1000);size=calendar.monthrange(y,m)[1]*24
 rows=[]
 for a in raw:
  assert len(a)==12,(n,a);t=int(a[0]);o,h,l,c=map(float,a[1:5]);end=int(a[6]);cnt=int(a[8]);assert all(math.isfinite(x) for x in [o,h,l,c]) and l<=min(o,c)<=max(o,c)<=h and end==t+H-1 and cnt>=0,(n,t)
  assert all(float(a[k])==0 for k in [5,7,9,10,11]),(n,'nonzero ignore volume')
  rows.append([t,o,h,l,c,end,cnt])
 assert [a[0] for a in rows]==sorted({a[0] for a in rows}) and all(start<=a[0]<start+size*H for a in rows),(n,'duplicate/order/out-of-month')
 missing=sorted(set(start+i*H for i in range(size))-set(a[0] for a in rows))
 return rows,{'file':n,'url':u,'sha256':digest(b),'rows':len(rows),'header':header,'missing_hours':missing,'count_values':sorted({a[6] for a in rows})}

def run():
 OUT.mkdir(exist_ok=True);months=[f'{y}-{m:02}' for y in range(2020,2027) for m in range(1,13) if (y,m)<=(2026,8)]
 with ThreadPoolExecutor(max_workers=4) as pool:got=list(pool.map(fetch,months))
 rows=[a for part,_ in got for a in part];assert all(b[0]>a[0] for a,b in zip(rows,rows[1:]));raw=json.dumps(rows,separators=(',',':'),allow_nan=False).encode();put(OUT/'rows.json.gz',gzip.compress(raw,mtime=0))
 audit={'symbol':'BTCUSDT','series':'premiumIndexKlines','months':len(months),'rows':len(rows),'start':rows[0][0],'end_close':rows[-1][5],'raw_rows_sha256':digest(raw),'missing_hours':[t for _,x in got for t in x['missing_hours']],'zero_count_rows':[a[0] for a in rows if a[6]==0],'zero_close':sum(a[4]==0 for a in rows),'negative_close':sum(a[4]<0 for a in rows),'count_values':sorted({a[6] for a in rows}),'source_files':[x for _,x in got],'availability':'bar close plus research execution buffer; first-received historical vintage not fully proven; count is sampling count, volume fields are placeholders, this is not trade OHLCV'}
 put(OUT/'audit.json',json.dumps(audit,sort_keys=True,separators=(',',':')).encode());print(json.dumps({k:v for k,v in audit.items() if k!='source_files'}))
if __name__=='__main__':run()
