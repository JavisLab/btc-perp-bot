"""Only public BTC daily aggregate activity; no individual address or wallet queries."""
import datetime as dt,hashlib,json,time,urllib.request,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-network-20261003';DAY=86400000
ms=lambda d:int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
sha=lambda b:hashlib.sha256(b).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False))
def fetch(metric,start,days,name):
 p=OUT/'raw'/(name+'.json');meta=p.with_suffix('.meta.json')
 if p.exists() and meta.exists():
  m=json.loads(meta.read_text());assert sha(p.read_bytes())==m['sha256'];return json.loads(p.read_bytes()),m
 query={'start':dt.datetime.fromtimestamp(start/1000,dt.timezone.utc).date().isoformat(),'timespan':f'{days}days','sampled':'false','format':'json'};url='https://api.blockchain.info/charts/'+metric+'?'+urllib.parse.urlencode(query)
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-aggregate-offline-research/1.0'}),timeout=45) as r:b=r.read();status=r.status
 data=json.loads(b);assert status==200 and data['status']=='ok' and data['period']=='day';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);m={'file':str(p.relative_to(OUT)),'url':url,'status':status,'bytes':len(b),'sha256':sha(b),'retrieved':dt.datetime.now(dt.timezone.utc).isoformat(),'rows':len(data['values'])};dump(meta,m);time.sleep(1.05);return data,m

def run():
 start,end=ms('2020-01-01'),ms('2026-08-30');manifest=[];active={};seen={};cursor=start
 while cursor<end:
  stop=min(end,cursor+180*DAY);data,meta=fetch('n-unique-addresses',cursor,(stop-cursor)//DAY,'active-'+str(cursor));assert data['unit']=='Unique Addresses';manifest.append(meta)
  for row in data['values']:
   t=int(row['x'])*1000;value=row['y'];assert cursor<=t<=stop and t%DAY==0
   assert t not in seen or seen[t]==value;seen[t]=value
   if t<stop:active[t]=value
  print(json.dumps({'end':stop,'active_days':len(active),'responses':len(manifest)}),flush=True);cursor=stop
 p=ROOT/'data/btc-mining-20261002/n-transactions.json';b=p.read_bytes();reuse=OUT/'raw/transactions-reused.json';reuse.write_bytes(b);data=json.loads(b);assert data['status']=='ok' and data['period']=='day' and data['unit']=='Transactions';tx={int(r['x'])*1000:r['y'] for r in data['values'] if start<=int(r['x'])*1000<end};reused={'file':str(reuse.relative_to(OUT)),'original_path':str(p.relative_to(ROOT)),'sha256':sha(b),'bytes':len(b),'rows':len(data['values']),'network_refetch':False}
 probe,meta=fetch('n-transactions',ms('2026-08-01'),7,'tx-clock-probe');assert probe['unit']=='Transactions'
 for r in probe['values']:assert tx[int(r['x'])*1000]==r['y']
 normalized={'asset':'BTC','start':start,'end_exclusive':end,'unit':'daily aggregate counts, not persons or BTC units','days':[{'day':t,'active':str(active[t]) if t in active else None,'transactions':str(tx[t]) if t in tx else None} for t in range(start,end,DAY)],'missing_active':[t for t in range(start,end,DAY) if t not in active],'missing_transactions':[t for t in range(start,end,DAY) if t not in tx]};dump(OUT/'archive-manifest.json',{'active':manifest,'transactions_reused':reused,'transactions_probe':meta});dump(OUT/'network-daily.json',normalized);print(json.dumps({'days':len(normalized['days']),'active_missing':normalized['missing_active'],'tx_missing':normalized['missing_transactions'],'sha256':sha((OUT/'network-daily.json').read_bytes())}),flush=True)
if __name__=='__main__':run()
