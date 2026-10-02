"""Public FOMC calendar and original-date ALFRED DGS2 vintages; no BTC performance."""
import csv,io,json,re,hashlib,datetime as dt,urllib.request,urllib.parse,concurrent.futures
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-macro-20261002'
def sha(b):return hashlib.sha256(b).hexdigest()
def parse_csv(body,vintage,event):
 rows=list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))));key='DGS2_'+vintage.replace('-','');seen=set();values={}
 assert rows and set(rows[0])=={'observation_date',key}
 for r in rows:
  d=dt.date.fromisoformat(r['observation_date']);assert d not in seen and d<=event;seen.add(d)
  if r[key] not in ('','.'):values[d]=float(r[key]);assert -10<values[d]<50
 current=values.get(event);prior=max((d for d in values if d<event),default=None)
 if current is None or prior is None or(event-prior).days>7:return None
 return {'rate':current,'previous_rate':values[prior],'previous_date':prior.isoformat(),'delta_percentage_points':current-values[prior]}
def run():
 OUT.mkdir(exist_ok=True);raw=OUT/'vintages';raw.mkdir(exist_ok=True)
 snap=json.loads((OUT/'official-web-2.json').read_text());page=json.loads(snap['result']['value']);assert not page['truncated'] and page['status']==200;text=page['text']
 dates=sorted({dt.datetime.strptime(x,'%Y%m%d').date() for x in re.findall(r'fomcminutes(\d{8})\.htm',text) if '20220101'<=x<'20260901'})
 assert len(dates)==37 and {y:sum(d.year==y for d in dates) for y in range(2022,2027)}=={2022:8,2023:8,2024:8,2025:8,2026:5}
 def get(day):
  v=(day+dt.timedelta(days=1)).isoformat();url='https://alfred.stlouisfed.org/graph/alfredgraph.csv?'+urllib.parse.urlencode({'id':'DGS2','cosd':(day-dt.timedelta(days=7)).isoformat(),'coed':day.isoformat(),'vintage_date':v});p=raw/(day.isoformat()+'.csv')
  if not p.exists():p.write_bytes(urllib.request.urlopen(url,timeout=30).read())
  b=p.read_bytes();z=parse_csv(b,v,day);row={'event':day.isoformat(),'vintage_date':v,'source_time':int(dt.datetime.combine(day+dt.timedelta(days=3),dt.time(),tzinfo=dt.timezone.utc).timestamp()*1000),'url':url,'file':str(p.relative_to(ROOT)),'sha256':sha(b),'bytes':len(b),'valid':z is not None,**(z or {})};print(json.dumps({'event':row['event'],'valid':row['valid']}),flush=True);return row
 events=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(get,dates));events.sort(key=lambda x:x['event'])
 b=json.dumps(events,sort_keys=True,separators=(',',':'),allow_nan=False).encode();(OUT/'events.json').write_bytes(b)
 audit={'event_count':len(events),'valid_count':sum(x['valid'] for x in events),'events_sha256':sha(b),'calendar_sha256':sha((OUT/'official-web-2.json').read_bytes()),'by_year':{str(y):sum(x['event'].startswith(str(y)) for x in events) for y in range(2022,2027)},'units':'DGS2 annual percent; delta .01 percentage-point = 1bp','availability':'each d+1 calendar-date ALFRED vintage used only d+3 00UTC; not original intraday reception proof','downloaded_utc':dt.datetime.now(dt.timezone.utc).isoformat()};(OUT/'audit.json').write_text(json.dumps(audit,sort_keys=True,indent=2));print(json.dumps(audit),flush=True)
if __name__=='__main__':run()
