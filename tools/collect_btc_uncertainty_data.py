"""ALFRED date-vintage daily EPU observations for fixed Friday/weekly BTC information clocks."""
import csv,datetime as dt,hashlib,io,json,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-uncertainty-20261003'
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def run():
 raw=OUT/'vintages';raw.mkdir(parents=True,exist_ok=True);first=dt.date(2019,12,27);last=dt.date(2026,8,28);v=first;rows=[];receipts=[];last_start=0.
 while v<=last:
  lo=v-dt.timedelta(days=35);hi=v-dt.timedelta(days=1);date=v.isoformat();u='https://alfred.stlouisfed.org/graph/alfredgraph.csv?'+urllib.parse.urlencode({'id':'USEPUINDXD','cosd':lo.isoformat(),'coed':hi.isoformat(),'vintage_date':date});p=raw/(date+'.csv');mp=p.with_suffix('.meta.json')
  if p.exists():b=p.read_bytes();receipt=json.loads(mp.read_text());assert receipt['url']==u and sha(b)==receipt['sha256']
  else:
   for attempt in range(4):
    pause=max(0,1.-(time.monotonic()-last_start))
    if pause:time.sleep(pause)
    last_start=time.monotonic()
    try:
     with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'BTC-offline-research/1.0'}),timeout=35) as r:b=r.read();receipt={'url':u,'status':r.status,'final_url':r.url,'bytes':len(b),'sha256':sha(b),'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat()}
     assert receipt['status']==200;break
    except urllib.error.HTTPError as e:
     if e.code not in (429,500,502,503,504) or attempt==3:raise
     time.sleep(min(60,max(float(e.headers.get('Retry-After','2')),2**attempt)))
   p.write_bytes(b);mp.write_bytes(canonical(receipt))
  parser=csv.DictReader(io.StringIO(b.decode('utf-8-sig')));column='USEPUINDXD_'+v.strftime('%Y%m%d');assert parser.fieldnames==['observation_date',column],(date,parser.fieldnames);values={}
  for e in parser:
   day=dt.date.fromisoformat(e['observation_date']);assert lo<=day<=hi and e['observation_date'] not in values;value=e[column].strip();number=None if value in ('','.','NA') else Decimal(value);assert number is None or number.is_finite() and number>=0;values[e['observation_date']]=str(number) if number is not None else None
  all_dates=[(lo+dt.timedelta(days=i)).isoformat() for i in range(35)];missing=[d for d in all_dates if values.get(d) is None]
  rows.append({'vintage_date':date,'window_start':lo.isoformat(),'window_end':hi.isoformat(),'values':values,'missing_dates':missing});receipts.append({'vintage_date':date,'file':str(p.relative_to(OUT)),**receipt,'rows':len(values),'missing':len(missing)})
  (OUT/'collection-progress.json').write_bytes(canonical({'finished':False,'vintage_date':date,'snapshots':len(rows)}))
  if len(rows)%50==0:print(json.dumps({'snapshots':len(rows),'vintage_date':date,'missing':len(missing)}),flush=True)
  v+=dt.timedelta(days=7)
 payload={'series':'USEPUINDXD','frequency':'Daily','units':'Index, not seasonally adjusted','vintage_frequency':'fixed Fridays','periods':'Friday 2019-12-27 through 2026-08-28; trailing 35 calendar observations in each dated vintage','vintages':rows};b=canonical(payload);(OUT/'epu-vintages.json').write_bytes(b);(OUT/'archive-manifest.json').write_bytes(canonical(receipts));audit={'snapshots':len(rows),'observations':sum(len(r['values']) for r in rows),'snapshots_with_missing':sum(bool(r['missing_dates']) for r in rows),'missing_total':sum(len(r['missing_dates']) for r in rows),'sha256':sha(b),'scope':'Past dated ALFRED values, not current final observations; original intraday release time unknown; no BTC performance or features computed'};(OUT/'data-audit.json').write_bytes(canonical(audit));(OUT/'collection-progress.json').write_bytes(canonical({'finished':True,**audit}));print(json.dumps(audit),flush=True)
if __name__=='__main__':run()
