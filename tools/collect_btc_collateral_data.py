"""Frozen 80 UTC monthly public BTCUSD_PERP funding responses; no accounts/private endpoints."""
import argparse,datetime as dt,json,time,urllib.request,urllib.parse,urllib.error,os,math
from pathlib import Path
from decimal import Decimal
from btc_session_study import ROOT,DAY,HOUR,ms,sha,canonical,read,write

def normalize(body,start,end):
 rows=json.loads(body);assert isinstance(rows,list) and len(rows)<1000
 out=[];previous=None
 for r in rows:
  assert isinstance(r,dict) and r['symbol']=='BTCUSD_PERP';t=r['fundingTime'];assert type(t) is int and start<=t<end and (previous is None or t>previous);previous=t
  rate=Decimal(str(r['fundingRate']));assert rate.is_finite()
  out.append({'time':t,'rate':str(rate),'valid':r.get('rateType','Regular')=='Regular','raw':r})
 return out

def state(out,value):
 (out/'collection-state.json').write_bytes(canonical(value))

def run(out):
 out=Path(out).resolve();(out/'raw').mkdir(parents=True,exist_ok=True);(out/'failures').mkdir(exist_ok=True);sources=[];allrows=[];requests=[];began=dt.datetime.now(dt.timezone.utc).isoformat()
 for i in range(80):
  y,mo=2020+i//12,1+i%12;date=f'{y}-{mo:02d}-01';start=ms(date);end=ms(f'{y+(mo==12)}-{1 if mo==12 else mo+1:02d}-01');url='https://dapi.binance.com/dapi/v1/fundingRate?'+urllib.parse.urlencode({'symbol':'BTCUSD_PERP','startTime':start,'endTime':end-1,'limit':1000});path=out/'raw'/f'{y}-{mo:02d}.json';reused=False
  if i==30:
   old=ROOT/'data/btc-web-20261004/q319-btc-coin-funding-month-probe.json';body=old.read_bytes();assert sha(body)=='e4d7a26c6bbaf1cc86a40ffd40aba83d253838fe2c62d234832f940d5f70ef5b';path.write_bytes(body);reused=True
  elif path.exists():body=path.read_bytes();reused=True
  else:
   for attempt in range(3):
    if requests:time.sleep(max(0,requests[-1]+2-time.time()))
    requests.append(time.time())
    try:
     with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-Research/1.0 (public aggregate funding)'}),timeout=35) as r:body=r.read();assert r.status==200
     path.write_bytes(body);break
    except urllib.error.HTTPError as e:
     write(out/'failures'/f'{y}-{mo:02d}-{attempt}.json',{'at':time.time(),'url':url,'status':e.code,'body':e.read().decode(errors='replace')})
     if e.code==429 or e.code>=500:
      if attempt==2:raise
      time.sleep(max(120,float(e.headers.get('Retry-After','120'))))
     else:raise
  rows=normalize(body,start,end);sources.append({'month':f'{y}-{mo:02d}','start':start,'end_exclusive':end,'url':url,'path':str(path.relative_to(ROOT)),'sha256':sha(body),'rows':len(rows),'reused':reused,'observed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'retrieval_time_scope':'assembly time; current session request_times separately, prior cached response not assigned new retrieval time'});allrows.extend(rows)
  state(out,{'status':'running','pid':os.getpid(),'started':began,'completed_windows':len(sources),'requests':len(requests),'last_month':sources[-1]['month']});print(json.dumps({'month':sources[-1]['month'],'rows':len(rows),'done':i+1}),flush=True)
 assert len({r['time'] for r in allrows})==len(allrows)
 payload={'symbol':'BTCUSD_PERP','rows':allrows};write(out/'funding.json.gz',payload);write(out/'prepare-audit.json',{'sources':sources,'canonical_sha256':sha(canonical(payload)),'gzip_sha256':sha((out/'funding.json.gz').read_bytes()),'rows':len(allrows),'valid_rows':sum(r['valid'] for r in allrows),'empty_months':[s['month'] for s in sources if not s['rows']],'request_times':requests,'first':allrows[0]['time'] if allrows else None,'last':allrows[-1]['time'] if allrows else None,'vintage':'current API vintage, not original publication proof'})
 state(out,{'status':'completed','pid':os.getpid(),'started':began,'ended':dt.datetime.now(dt.timezone.utc).isoformat(),'completed_windows':80,'requests':len(requests)});print(json.dumps({'completed':80,'rows':len(allrows),'canonical_sha256':sha(canonical(payload))}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
