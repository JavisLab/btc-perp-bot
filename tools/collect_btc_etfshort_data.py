"""Public FINRA aggregate archives: retain only three BTC ETFs, never orders or account data."""
import concurrent.futures,datetime as dt,hashlib,json,re,urllib.request,urllib.parse,urllib.error,time,threading,email.utils
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-etfshort-20261002';SYMBOLS={'IBIT','FBTC','GBTC'}
BASE='https://www.finra.org/finra-data/browse-catalog/short-sale-volume-data/daily-short-sale-volume-files'
LOCK=threading.Lock();LAST={};TRACE=OUT/'http-trace.jsonl'
def fetch(url):
 host=urllib.parse.urlsplit(url).netloc;spacing=4. if host=='www.finra.org' else .5
 for attempt in range(4):
  with LOCK:
   delay=max(0,LAST.get(host,0)+spacing-time.monotonic())
   if delay:time.sleep(delay)
   LAST[host]=time.monotonic()
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTCResearch/1.0 public-only noncommercial BTC aggregate audit'}),timeout=40) as r:return r.read()
  except urllib.error.HTTPError as e:
   retry=e.headers.get('Retry-After');record={'url':url,'status':e.code,'retry_after':retry,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
   with LOCK:
    with TRACE.open('a') as f:f.write(json.dumps(record)+'\n')
   if e.code!=429:raise
   wait=60.
   if retry:
    try:wait=max(wait,float(retry))
    except ValueError:wait=max(wait,(email.utils.parsedate_to_datetime(retry)-dt.datetime.now(dt.timezone.utc)).total_seconds())
   print('SERVER_RATE_LIMIT',host,'wait_seconds',wait,flush=True)
   with LOCK:LAST[host]=max(LAST.get(host,0),time.monotonic()+wait)
   while wait>0:
    part=min(wait,60);time.sleep(part);wait-=part
 raise RuntimeError('Public provider remains rate-limited; cached inputs retained, no evasion')
def sha(data):return hashlib.sha256(data).hexdigest()
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,t,a):
  u=dict(a).get('href','')
  if t=='a' and u.startswith('https://cdn.finra.org/equity/regsho/daily/CNMSshvol'):self.links.append(u)
def index(ym):
 year,month=ym;url=BASE+'?'+urllib.parse.urlencode({'custom_month[month]':f'{month:02d}','custom_year[year]':str(2026-year)})
 path=OUT/'indices'/f'{year}-{month:02d}.html';raw=path.read_bytes() if path.exists() else fetch(url)
 if not path.exists():path.write_bytes(raw)
 parser=Links();parser.feed(raw.decode());urls=sorted(set(parser.links));assert urls,(ym,'no official archive links')
 dates=[re.search(r'CNMSshvol(\d{8})',u).group(1) for u in urls];assert all(d.startswith(f'{year}{month:02d}') for d in dates),(ym,dates)
 return {'year':year,'month':month,'url':url,'sha256':sha(raw),'files':urls,'updated_mentions':raw.decode().lower().count('updated')}
def day(url):
 filename=url.rsplit('/',1)[-1];date=re.search(r'CNMSshvol(\d{8})',filename).group(1);meta=OUT/'raw'/(filename+'.meta.json');path=OUT/'raw'/filename
 if meta.exists():return json.loads(meta.read_text())
 raw=fetch(url);lines=raw.decode().splitlines();assert lines[0]=='Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market';assert lines[-1].isdigit() and int(lines[-1])==len(lines)-2,(filename,'footer rowcount')
 chosen=[];symbols=[]
 for line in lines[1:-1]:
  a=line.split('|')
  if a[1] not in SYMBOLS:continue
  assert len(a)==6 and a[0]==date
  short,exempt,total=map(Decimal,a[2:5]);assert 0<=exempt<=short<=total and total>0,(filename,a)
  chosen.append(line);symbols.append(a[1])
 assert len(symbols)==len(set(symbols)),(filename,'duplicate BTC ETF symbols')
 subset=('\n'.join([lines[0]]+chosen)+'\n').encode();path.write_bytes(subset)
 item={'date':date,'url':url,'filename':filename,'full_response_sha256':sha(raw),'full_response_bytes':len(raw),'source_trailer_records':int(lines[-1]),'retained_symbols':symbols,'retained_rows':len(chosen),'subset_sha256':sha(subset),'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'BTC ETF three-symbol exact text subset; global source footer verified before non-BTC rows discarded; daily short sale volume is not short interest; ShortVolume includes ShortExemptVolume'};meta.write_text(json.dumps(item,sort_keys=True)+'\n');return item

def run():
 for d in ('indices','raw'):(OUT/d).mkdir(parents=True,exist_ok=True)
 months=[(y,m) for y in (2024,2025,2026) for m in range(1,13) if (y,m)<=(2026,8)];indices=[];failures=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
  jobs={pool.submit(index,ym):ym for ym in months}
  for future in concurrent.futures.as_completed(jobs):
   try:indices.append(future.result())
   except Exception as e:failures.append({'index':jobs[future],'error':str(e)})
 (OUT/'indices-manifest.json').write_text(json.dumps({'fetched_at':dt.datetime.now(dt.timezone.utc).isoformat(),'indices':sorted(indices,key=lambda x:(x['year'],x['month'])),'errors':failures},indent=2)+'\n');assert not failures,failures
 urls=sorted(set(u for row in indices for u in row['files'] if '20240111'<=re.search(r'CNMSshvol(\d{8})',u).group(1)<='20260831'));records=[]
 print('ARCHIVE_URLS',len(urls),flush=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  jobs={pool.submit(day,u):u for u in urls}
  for future in concurrent.futures.as_completed(jobs):
   try:records.append(future.result())
   except Exception as e:failures.append({'url':jobs[future],'error':str(e)})
   if (len(records)+len(failures))%50==0:print('ARCHIVE_PROGRESS',len(records),len(failures),flush=True)
 (OUT/'archive-manifest.json').write_text(json.dumps({'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'records':sorted(records,key=lambda r:r['filename']),'errors':failures},indent=2)+'\n');print('ARCHIVE_COMPLETE',len(records),'failures',failures,flush=True)
if __name__=='__main__':run()
