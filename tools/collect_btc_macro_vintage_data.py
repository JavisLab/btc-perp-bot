"""Await first public historical vintage, preserving missing holiday observations."""
import datetime as dt,json,urllib.request,urllib.parse,concurrent.futures
from pathlib import Path
from collect_btc_macro_data import parse_csv,sha,ROOT
OUT=ROOT/'data/btc-macro-vintage-20261002';OLD=ROOT/'data/btc-macro-20261002'
def first_available(day,get):
 attempts=[];last=None
 for lag in range(1,8):
  v=(day+dt.timedelta(days=lag)).isoformat();b,meta=get(v);z=parse_csv(b,v,day);attempts.append(dict(meta,vintage_date=v,valid=z is not None))
  if z is not None:
   source=int(dt.datetime.combine(dt.date.fromisoformat(v)+dt.timedelta(days=2),dt.time(),tzinfo=dt.timezone.utc).timestamp()*1000)
   return {'event':day.isoformat(),'vintage_date':v,'source_time':source,'valid':True,**z,'attempts':attempts}
 return {'event':day.isoformat(),'vintage_date':v,'source_time':int(dt.datetime.combine(day+dt.timedelta(days=9),dt.time(),tzinfo=dt.timezone.utc).timestamp()*1000),'valid':False,'attempts':attempts}
def run():
 (OUT/'vintages').mkdir(parents=True,exist_ok=True);old=json.loads((OLD/'events.json').read_text())
 def one(e):
  d=dt.date.fromisoformat(e['event'])
  def get(v):
   p=OUT/'vintages'/f'{d.isoformat()}-{v}.csv';u='https://alfred.stlouisfed.org/graph/alfredgraph.csv?'+urllib.parse.urlencode({'id':'DGS2','cosd':(d-dt.timedelta(days=7)).isoformat(),'coed':d.isoformat(),'vintage_date':v})
   if not p.exists():p.write_bytes((ROOT/e['file']).read_bytes() if v==e['vintage_date'] else urllib.request.urlopen(u,timeout=30).read())
   b=p.read_bytes();return b,{'url':u,'file':str(p.relative_to(ROOT)),'sha256':sha(b),'bytes':len(b)}
  z=first_available(d,get);print(json.dumps({'event':z['event'],'valid':z['valid'],'vintage':z['vintage_date'],'attempts':len(z['attempts'])}),flush=True);return z
 rows=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(one,old));rows.sort(key=lambda x:x['event']);b=json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode();(OUT/'events.json').write_bytes(b);audit={'event_count':len(rows),'valid_count':sum(e['valid'] for e in rows),'vintage_files':sum(len(e['attempts']) for e in rows),'events_sha256':sha(b),'calendar_sha256':sha((OLD/'official-web-2.json').read_bytes()),'predecessor_events_sha256':sha((OLD/'events.json').read_bytes()),'availability':'first d+1..d+7 complete ALFRED vintage v; decision v+2 days 00UTC; missing-day files retained','downloaded_utc':dt.datetime.now(dt.timezone.utc).isoformat()};(OUT/'audit.json').write_text(json.dumps(audit,sort_keys=True,indent=2));print(json.dumps(audit),flush=True)
if __name__=='__main__':run()
