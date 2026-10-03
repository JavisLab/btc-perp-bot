"""Public BTC DVOL only, historical responses are not first-publication vintages."""
import datetime as dt,hashlib,json,time,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-dvol-20261003';DAY=86400000
ms=lambda d:int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def sha(b):return hashlib.sha256(b).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False))
def fetch(name,start,end,res):
 p=OUT/'raw'/f'{name}.json';meta=p.with_suffix('.meta.json')
 if p.exists() and meta.exists():
  m=json.loads(meta.read_text());assert sha(p.read_bytes())==m['sha256'];return json.loads(p.read_bytes()),m
 query={'currency':'BTC','start_timestamp':start,'end_timestamp':end,'resolution':res};url='https://www.deribit.com/api/v2/public/get_volatility_index_data?'+urllib.parse.urlencode(query)
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-offline-research/1.0'}),timeout=45) as r:b=r.read();status=r.status
 data=json.loads(b);assert status==200 and 'error' not in data and 'result' in data
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);m={'file':str(p.relative_to(OUT)),'url':url,'status':status,'bytes':len(b),'sha256':sha(b),'retrieved':dt.datetime.now(dt.timezone.utc).isoformat(),'rows':len(data['result']['data'])};dump(meta,m);time.sleep(1.05);return data,m

def run():
 start,end=ms('2021-04-01'),ms('2026-09-01');manifest=[];rows={};cursor=start
 while cursor<end:
  stop=min(end,cursor+180*DAY);last=stop-1;page=0
  while True:
   name=f'daily-{cursor}-{page}';data,meta=fetch(name,cursor,last,'1D');manifest.append(meta);result=data['result']
   for row in result['data']:
    t=row[0];assert cursor<=t<stop and t%DAY==0
    assert t not in rows or rows[t]==row;rows[t]=row
   continuation=result.get('continuation')
   if continuation is None or continuation<cursor:break
   assert cursor<=continuation<last,(cursor,last,continuation);last=continuation;page+=1
  print(json.dumps({'end':stop,'daily_rows':len(rows),'responses':len(manifest)}),flush=True);cursor=stop
 probes=[]
 for date in ('2021-04-01','2022-01-01','2024-02-29'):
  data,meta=fetch('hourly-'+date,ms(date),ms(date)+DAY-1,'3600');assert data['result'].get('continuation') is None;probes.append(meta)
 dump(OUT/'archive-manifest.json',manifest);dump(OUT/'clock-probe-manifest.json',probes)
 normalized={'currency':'BTC','unit':'annualized_volatility_percent','interval':'1D','start':start,'end_exclusive':end,'publication_exclusion':'before 2021-04-01 excluded; current historical response is not a first-release vintage','rows':[[r[0]]+[str(x) for x in r[1:]] for _,r in sorted(rows.items())],'missing_days':[t for t in range(start,end,DAY) if t not in rows]};dump(OUT/'dvol-daily.json',normalized);print(json.dumps({'rows':len(rows),'missing_days':normalized['missing_days'],'sha256':sha((OUT/'dvol-daily.json').read_bytes())}),flush=True)
if __name__=='__main__':run()
