"""Official daily-only supplementation for missing or zero-count monthly BTC premium bars."""
import calendar,csv,gzip,hashlib,io,json,math,urllib.request,urllib.error,zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
from pathlib import Path
from prepare_btc_premium_data import OUT,H,put,digest

def fetch_day(day):
 n=f'BTCUSDT-1h-{day}.zip';u='https://data.binance.vision/data/futures/um/daily/premiumIndexKlines/BTCUSDT/1h/'+n;p=OUT/'daily'/n;c=p.with_suffix('.zip.CHECKSUM')
 try:
  if not p.exists():put(p,urllib.request.urlopen(u,timeout=30).read())
  if not c.exists():put(c,urllib.request.urlopen(u+'.CHECKSUM',timeout=30).read())
 except urllib.error.HTTPError as e:
  if e.code==404:return {},{'file':n,'url':u,'status':404}
  raise
 b=p.read_bytes();assert digest(b)==c.read_text().split()[0];rows={};base=int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()*1000)
 with zipfile.ZipFile(io.BytesIO(b)) as z:
  assert len(z.namelist())==1
  for a in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
   if a[0]=='open_time':continue
   t=int(a[0]);o,h,l,c=map(float,a[1:5]);end=int(a[6]);cnt=int(a[8]);assert all(math.isfinite(v) for v in [o,h,l,c]) and l<=min(o,c)<=max(o,c)<=h and end==t+H-1 and base<=t<base+24*H and cnt>=0 and t not in rows
   rows[t]=[t,o,h,l,c,end,cnt]
 return rows,{'file':n,'url':u,'sha256':digest(b),'rows':len(rows),'status':200}

def run():
 (OUT/'daily').mkdir(exist_ok=True);audit=json.loads((OUT/'audit.json').read_text());original=json.loads(gzip.decompress((OUT/'rows.json.gz').read_bytes()));data={r[0]:r for r in original};problem=set(audit['missing_hours']+audit['zero_count_rows']);days=sorted({datetime.fromtimestamp(t/1000,timezone.utc).strftime('%Y-%m-%d') for t in problem});patched=[];conflicts=[]
 with ThreadPoolExecutor(max_workers=4) as pool:got=list(pool.map(fetch_day,days))
 for rows,_ in got:
  for t,r in rows.items():
   if t in problem and r[6]>0:
    patched.append({'time':t,'previous':data.get(t),'daily':r});data[t]=r
   elif t in data and data[t]!=r:conflicts.append({'time':t,'monthly':data[t],'daily':r})
 first=audit['start'];end=audit['end_close']+1;missing=[t for t in range(first,end,H) if t not in data];zero=[t for t in range(first,end,H) if t in data and data[t][6]==0];raw=json.dumps([data[t] for t in sorted(data)],separators=(',',':'),allow_nan=False).encode();put(OUT/'rows-repaired.json.gz',gzip.compress(raw,mtime=0));o={'policy':'monthly first; fill only missing or zero-count with positive-count official daily; never overwrite positive monthly rows; remaining invalid is missing/cash','original_sha256':audit['raw_rows_sha256'],'raw_rows_sha256':digest(raw),'rows':len(data),'problem_dates':days,'daily_sources':[x for _,x in got],'patched':patched,'remaining_missing':missing,'remaining_zero':zero,'other_conflicts':conflicts};put(OUT/'repair-audit.json',json.dumps(o,sort_keys=True,separators=(',',':')).encode());print(json.dumps({k:v for k,v in o.items() if k not in ['daily_sources','patched','other_conflicts']}));print({'patches':len(patched),'other_conflicts':len(conflicts)})
if __name__=='__main__':run()
