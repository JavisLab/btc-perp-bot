"""Public BTC aggregate queue and fee charts only. No addresses, wallets, raw transactions or trades."""
import datetime as dt,hashlib,json,time,urllib.request,urllib.parse
from decimal import Decimal,ROUND_HALF_EVEN
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-congestion-20261003';DAY=86400000;STEP=900000
ms=lambda d:int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
sha=lambda b:hashlib.sha256(b).hexdigest()
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False))
def fetch(metric,start,days,name):
 p=OUT/'raw'/(name+'.json');mp=p.with_suffix('.meta.json')
 if p.exists() and mp.exists():
  m=json.loads(mp.read_text());assert sha(p.read_bytes())==m['sha256'];return json.loads(p.read_bytes(),parse_float=Decimal),m
 query={'start':dt.datetime.fromtimestamp(start/1000,dt.timezone.utc).date().isoformat(),'timespan':f'{days}days','sampled':'false','format':'json'};url='https://api.blockchain.info/charts/'+metric+'?'+urllib.parse.urlencode(query)
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-aggregate-offline-research/1.0'}),timeout=40) as r:b=r.read();status=r.status;final=r.url
  d=json.loads(b,parse_float=Decimal);assert status==200 and d['status']=='ok';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);m={'file':str(p.relative_to(OUT)),'url':url,'final_url':final,'status':status,'sha256':sha(b),'bytes':len(b),'rows':len(d['values']),'retrieved':dt.datetime.now(dt.timezone.utc).isoformat()};dump(mp,m);time.sleep(1.05);return d,m
 except Exception as e:
  dump(OUT/'collection-failure.json',{'url':url,'name':name,'error_type':type(e).__name__,'error':str(e),'at':dt.datetime.now(dt.timezone.utc).isoformat()});raise

def collect(metric,unit,period,stride,chunk_days,start,end):
 cursor=start;series={};seen={};manifest=[]
 while cursor<end:
  hi=min(end,cursor+chunk_days*DAY);d,m=fetch(metric,cursor,(hi-cursor)//DAY,metric+'-'+str(cursor));assert d['unit']==unit and d['period']==period;manifest.append(m);last=None
  for row in d['values']:
   rawt=Decimal(row['x']);v=Decimal(row['y']);assert rawt==rawt.to_integral_value() and v.is_finite() and v>=0;t=int(rawt)*1000;assert cursor<=t<=hi and t%stride==0 and(last is None or t>last);last=t;assert t not in seen or seen[t]==v;seen[t]=v
   if t<hi:series[t]=v
  cursor=hi;state={'stage':metric,'end':hi,'responses':len(manifest),'observations':len(series),'complete':False};dump(OUT/'collection-state.json',state)
  if len(manifest)%10==0 or hi==end:print(json.dumps(state),flush=True)
 return series,manifest

def run():
 start,end=ms('2020-01-01'),ms('2026-08-30');queue,qmeta=collect('mempool-size','Bytes','minute',STEP,14,start,end);fee,fmeta=collect('transaction-fees','BTC','day',DAY,180,start,end);p=ROOT/'data/btc-network-20261003/network-daily.json';b=p.read_bytes();assert sha(b)=='7a2b322ec2b2c0d4e297eb0c3afa6204f5beaa3d15dcf0531b4b61e2abdeb44a';raw=json.loads(b);tx={r['day']:int(Decimal(r['transactions'])) for r in raw['days'] if r['transactions'] is not None};(OUT/'raw/transactions-source-reused.json').write_bytes(b);reuse={'file':'raw/transactions-source-reused.json','original_path':str(p.relative_to(ROOT)),'sha256':sha(b),'bytes':len(b),'network_refetch':False};days=[];sats={};worst=Decimal(0)
 for t,v in fee.items():
  a=v*100000000;rounded=a.to_integral_value(rounding=ROUND_HALF_EVEN);error=abs(a-rounded);assert error<=Decimal('.0001');worst=max(worst,error);sats[t]=int(rounded)
 for t in range(start,end,DAY):
  vv=[queue.get(u) for u in range(t,t+DAY,STEP)];count=sum(v is not None for v in vv);mean=sum(vv)/96 if count==96 else None;days.append({'day':t,'mempool_mean_source_bytes':str(mean) if mean is not None else None,'mempool_observations':count,'fee_total_sats':sats.get(t),'transactions':tx.get(t)})
 norm={'asset':'BTC','start':start,'end_exclusive':end,'mempool_sampling_ms':STEP,'days':days};dump(OUT/'congestion-daily.json',norm);dump(OUT/'archive-manifest.json',{'queue':qmeta,'fee':fmeta,'transactions_reused':reuse});state={'complete':True,'queue_responses':len(qmeta),'queue_observations':len(queue),'fee_responses':len(fmeta),'fee_observations':len(fee),'calendar_days':len(days),'missing_queue_slots':(end-start)//STEP-len(queue),'incomplete_queue_days':sum(r['mempool_observations']!=96 for r in days),'missing_fee_days':sum(r['fee_total_sats'] is None for r in days),'missing_tx_days':sum(r['transactions'] is None for r in days),'max_fee_satoshi_rounding':str(worst),'normalized_sha256':sha((OUT/'congestion-daily.json').read_bytes())};dump(OUT/'collection-state.json',state);print(json.dumps(state),flush=True)
if __name__=='__main__':run()
