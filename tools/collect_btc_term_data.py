"""Only official public BTC COIN-M dated hourly aggregates. No performance computation."""
import argparse,concurrent.futures,csv,datetime as dt,io,json,math,shutil,urllib.request,urllib.parse,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
from btc_session_study import ROOT,DAY,HOUR,ms,sha,read,write,canonical
S3='https://s3-ap-northeast-1.amazonaws.com/data.binance.vision'
WEB=ROOT/'data/btc-web-20261004';END=ms('2026-09-01')
def download(url,p):
 if p.exists():return p.read_bytes()
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-public-aggregate-research/1.0'}),timeout=40) as r:
  assert r.status==200,(r.status,url);b=r.read()
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);return b
def valid(r):
 try:
  t=int(r[0]);end=int(r[6]);o,h,l,c,v,base,n,bv,bb=[float(r[j]) for j in (1,2,3,4,5,7,8,9,10)]
  return len(r)==12 and t%HOUR==0 and end==t+HOUR-1 and all(math.isfinite(x) for x in (o,h,l,c,v,base,n,bv,bb)) and 0<l<=o<=h and l<=c<=h and v>0 and base>0 and n>0 and n==int(n) and 0<=bv<=v and 0<=bb<=base
 except (ValueError,IndexError):return False

def run(out):
 out=Path(out).resolve();initial=WEB/'q197-binance-btc-quarter-list.html';assert sha(initial.read_bytes())=='090c9c582fe274b0e12f86584fa81a3c299e4cec3f1aa653cdb2ca697e21bd2c';tree=ET.fromstring(initial.read_bytes());assert tree.find('{*}IsTruncated').text=='false';symbols=sorted(n.text.rstrip('/').split('/')[-1] for n in tree.findall('{*}CommonPrefixes/{*}Prefix') if n.text.rstrip('/').split('/')[-1]!='BTCUSD_PERP');assert len(symbols)==26
 def listing(sym):
  p=out/'listings'/(sym+'.xml');old={'BTCUSD_220325':'q199-binance-220325-hourly-list.html','BTCUSD_200925':'q201-binance-200925-hourly-list.html','BTCUSD_261225':'q202-binance-261225-hourly-list.html'}.get(sym)
  if old and not p.exists():p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(WEB/old,p)
  prefix='data/futures/cm/monthly/klines/'+sym+'/1h/';url=S3+'?'+urllib.parse.urlencode({'prefix':prefix,'max-keys':1000});b=download(url,p);x=ET.fromstring(b);assert x.find('{*}IsTruncated').text=='false';keys=[e.text for e in x.findall('{*}Contents/{*}Key')];jobs=[];expiry=dt.datetime.strptime(sym[-6:],'%y%m%d').replace(tzinfo=dt.timezone.utc);assert expiry.weekday()==4
  for key in keys:
   if not key.endswith('.zip'):continue
   month=key.rsplit('/',1)[-1][-11:-4]
   if '2020-01'<=month<='2026-08' and month<=expiry.strftime('%Y-%m'):assert key+'.CHECKSUM' in keys;jobs.append((sym,month,key))
  return {'symbol':sym,'expiry_date_proxy':int(expiry.timestamp()*1000),'listing':str(p.relative_to(ROOT)),'listing_sha256':sha(b),'url':url,'jobs':jobs}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:contracts=list(ex.map(listing,symbols))
 jobs=[job for c in contracts for job in c['jobs']];print({'stage':'listings','contracts':len(contracts),'archives':len(jobs)},flush=True)
 def archive(job):
  sym,month,key=job;url='https://data.binance.vision/'+key;p=out/'raw'/sym/(month+'.zip');meta={'symbol':sym,'month':month,'path':str(p.relative_to(ROOT)),'url':url};reused=[]
  for suffix in ('','.CHECKSUM'):
   q=p if not suffix else p.with_suffix('.CHECKSUM');old=WEB/('q203-'+key.rsplit('/',1)[-1]+suffix)
   if old.exists() and not q.exists():q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(old,q);reused.append(str(old.relative_to(ROOT)))
   b=download(url+suffix,q)
   if not suffix:raw=b;meta.update(sha256=sha(b),bytes=len(b))
   else:assert meta['sha256']==b.decode().split()[0]
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   assert len(z.namelist())==1;rr=[r for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())) if r and r[0].isdigit()]
  rows=[]
  for r in rr:
   assert len(r)==12 and int(r[0])<10**14 and int(r[0])<END and dt.datetime.fromtimestamp(int(r[0])/1000,dt.timezone.utc).strftime('%Y-%m')==month
   rows.append({'raw':r,'valid':valid(r)})
  meta.update(rows=len(rows),invalid=sum(not r['valid'] for r in rows),reused=reused);return meta,rows
 try:
  with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:records=list(ex.map(archive,jobs))
 except Exception as e:
  write(out/'collection-failure.json',{'error':str(e),'scope':'Partial public aggregate files preserved, no retry loop or performance'});raise
 bysym={s:[] for s in symbols};sources=[]
 for a,rows in records:sources.append(a);bysym[a['symbol']].extend(rows)
 result=[]
 for c in contracts:
  rows=sorted(bysym[c['symbol']],key=lambda r:int(r['raw'][0]));assert len({r['raw'][0] for r in rows})==len(rows);first=min((int(r['raw'][0]) for r in rows if r['valid']),default=None);result.append({'symbol':c['symbol'],'expiry_date_proxy':c['expiry_date_proxy'],'first_valid_open':first,'rows':rows})
 data={'contracts':result,'scope':'BTCUSD dated hourly rows; date proxy expiry not exact delivery time; current archive not initial vintage; no performance'};write(out/'contracts.json.gz',data);audit={'canonical_sha256':sha(canonical(data)),'gzip_sha256':sha((out/'contracts.json.gz').read_bytes()),'contracts':[{k:v for k,v in c.items() if k!='jobs'} for c in contracts],'sources':sources,'archives':len(sources),'hours':sum(len(c['rows']) for c in result),'valid_hours':sum(r['valid'] for c in result for r in c['rows'])};write(out/'prepare-audit.json',audit);print({k:v for k,v in audit.items() if k not in ('contracts','sources')},flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
