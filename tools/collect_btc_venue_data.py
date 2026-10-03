"""Public BTC and USD-numeraire candles only. Cached raw responses; no account/auth APIs."""
import datetime as dt,hashlib,json,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-venue-20261003';H=3600
START=int(dt.datetime(2021,5,1,tzinfo=dt.timezone.utc).timestamp());END=int(dt.datetime(2026,9,1,tzinfo=dt.timezone.utc).timestamp())
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def iso(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat().replace('+00:00','Z')
def run():
 raw=OUT/'raw';raw.mkdir(parents=True,exist_ok=True);manifest=[];data={};audits={};last_request=0.
 for name,product in [('coinbase-btcusd','BTC-USD'),('coinbase-usdtusd','USDT-USD'),('bitstamp-btcusd','btcusd')]:
  span=240 if name.startswith('coinbase') else 960;by_time={};dup=0;conflict=[];out_of_range=0;empty=[];response_orders={};no_volume=[];bad=[]
  for a in range(START,END,span*H):
   b=min(a+span*H,END);first=max(START,a-H);n=(b-first)//H
   if name.startswith('coinbase'):
    u='https://api.exchange.coinbase.com/products/'+product+'/candles?'+urllib.parse.urlencode({'granularity':H,'start':iso(first),'end':iso(b-H)})
   else:u='https://www.bitstamp.net/api/v2/ohlc/'+product+'/?'+urllib.parse.urlencode({'step':H,'limit':n,'end':b-H,'exclude_current_candle':'true'})
   p=raw/(name+'-'+str(a)+'.json');mp=p.with_suffix('.meta.json')
   if p.exists():
    m=json.loads(mp.read_text());bb=p.read_bytes();assert m['url']==u and m['sha256']==sha(bb)
   else:
    # <= 4 req/s globally, much below both published public limits; honour Retry-After.
    for attempt in range(4):
     pause=max(0,.25-(time.monotonic()-last_request))
     if pause:time.sleep(pause)
     last_request=time.monotonic()
     try:
      with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'BTC-offline-research/1.0'}),timeout=30) as r:
       bb=r.read();m={'url':u,'status':r.status,'final_url':r.url,'retrieved_at':dt.datetime.now(dt.timezone.utc).isoformat(),'sha256':sha(bb),'bytes':len(bb),'content_type':r.headers.get('Content-Type')}
      assert m['status']==200 and bb;json.loads(bb);break
     except urllib.error.HTTPError as e:
      if e.code not in (429,500,502,503,504) or attempt==3:raise
      pause=max(float(e.headers.get('Retry-After','2')),2**attempt);time.sleep(min(pause,60))
    p.write_bytes(bb);mp.write_bytes(canonical(m))
   entries=json.loads(bb,parse_float=Decimal);entries=entries if isinstance(entries,list) else entries['data']['ohlc'];times=[]
   if not entries:empty.append({'start':a,'end':b})
   for e in entries:
    if name.startswith('coinbase'):t=int(e[0]);lo,hi,op,cl,vol=map(Decimal,map(str,e[1:]))
    else:t=int(e['timestamp']);op,hi,lo,cl,vol=(Decimal(e[k]) for k in ('open','high','low','close','volume'))
    times.append(t)
    if not (first<=t<b):out_of_range+=1
    if not START<=t<END:continue
    assert t%H==0 and all(x.is_finite() for x in (op,hi,lo,cl,vol))
    row=[t*1000,str(op),str(hi),str(lo),str(cl),str(vol)]
    valid=0<lo<=min(op,cl)<=max(op,cl)<=hi and vol>=0
    if not valid:bad.append(row)
    if vol==0:no_volume.append(t*1000)
    if t in by_time:
     dup+=1
     if by_time[t]!=row:conflict.append({'time':t*1000,'first':by_time[t],'later':row,'request':p.name})
    else:by_time[t]=row
   order='ascending' if times==sorted(times) else 'descending' if times==sorted(times,reverse=True) else 'unordered';response_orders[order]=response_orders.get(order,0)+1
   manifest.append({'series':name,'start':a,'end':b,'file':str(p.relative_to(OUT)),**m,'rows':len(entries)})
   (OUT/'collection-progress.json').write_bytes(canonical({'last':p.name,'raw_responses':len(manifest),'finished':False}))
  data[name]=[by_time[t] for t in sorted(by_time)];missing=[t*1000 for t in range(START,END,H) if t not in by_time]
  audits[name]={'rows':len(by_time),'expected':(END-START)//H,'missing_hours':missing,'zero_volume_hours':sorted(set(no_volume)),'duplicate_rows':dup,'conflicts':conflict,'invalid_ohlc_rows':bad,'out_of_request_range':out_of_range,'empty_responses':empty,'response_orders':response_orders}
  print(name,json.dumps({k:v if not isinstance(v,list) else len(v) for k,v in audits[name].items()}),flush=True)
 payload={'start':START*1000,'end':END*1000,'columns':['open_time_ms','open','high','low','close','base_volume'],'interval_ms':H*1000,'availability':'bar open + 1 hour completion + 1 hour assumed publication buffer; current vintage only; extra delay specified before study','series':data}
 (OUT/'candles.json').write_bytes(canonical(payload));(OUT/'archive-manifest.json').write_bytes(canonical(manifest));(OUT/'data-audit.json').write_bytes(canonical({'series':audits,'input_sha256':sha(canonical(payload)),'raw_responses':len(manifest),'scope':'current official public API vintage, no publisher checksums; SHA receipt integrity only; no fill/return computation; conflicting/invalid/no-tick observations excluded by frozen rule'}));(OUT/'collection-progress.json').write_bytes(canonical({'finished':True,'raw_responses':len(manifest),'input_sha256':sha(canonical(payload))}));print('FINISHED',sha(canonical(payload)),flush=True)
if __name__=='__main__':run()
