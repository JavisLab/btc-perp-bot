"""Preregistered 700 small public aggregate BTCUSD margin snapshot windows; no performance."""
import argparse,datetime as dt,fcntl,json,os,shutil,time,urllib.error,urllib.parse,urllib.request
from decimal import Decimal
from pathlib import Path
from btc_session_study import ROOT,DAY,HOUR,ms,sha,canonical,write
FIRST=ms('2019-12-22');LAST=ms('2026-08-30');MIN=60000;WEB=ROOT/'data/btc-web-20261004'
PROBES={(FIRST,'long'):'q246-btc-margin-2019-12-22-long-probe',(FIRST,'short'):'q247-btc-margin-2019-12-22-short-probe',(LAST,'long'):'q248-btc-margin-2026-08-30-long-probe',(LAST,'short'):'q249-btc-margin-2026-08-30-short-probe'}
def utc():return dt.datetime.now(dt.timezone.utc).isoformat()
def normalize(raw,cutoff,side):
 rows=json.loads(raw,parse_float=Decimal);assert isinstance(rows,list),type(rows)
 seen=set();result=[];invalid=[]
 for r in rows:
  assert isinstance(r,list) and len(r)==2 and isinstance(r[0],int) and not isinstance(r[0],bool),r
  t=r[0];assert t not in seen,('duplicate',side,cutoff,t);seen.add(t)
  assert cutoff-HOUR<=t<cutoff and t%MIN==0,('timestamp',t,cutoff)
  v=Decimal(r[1]);ok=v.is_finite() and v>0;result.append([t,str(v)])
  if not ok:invalid.append(t)
 assert [r[0] for r in result]==sorted(seen),('order',side,cutoff)
 matches=[r for r in result if r[0]==cutoff-MIN];selected=matches[0] if matches else None;valid=selected is not None and selected[0] not in invalid
 return {'cutoff':cutoff,'side':side,'rows':result,'selected':selected,'valid':valid,'invalid_minutes':invalid,'missing_minutes':sorted(set(range(cutoff-HOUR,cutoff,MIN))-seen)}
def run(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True);lock=(out/'collection.lock').open('a+');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 state={'started_utc':utc(),'pid':os.getpid(),'prereg_commit':'d08d271','expected_windows':700,'status':'running','processed_windows':0,'network_requests':0,'reused_probes':0};last_request=-1000.;sources=[];snapshots=[]
 def state_save():
  p=out/'collection-state.json';p.write_text(json.dumps(state,sort_keys=True,separators=(',',':')))
 state_save()
 try:
  for cutoff in range(FIRST,LAST+1,7*DAY):
   date=dt.datetime.fromtimestamp(cutoff/1000,dt.timezone.utc).strftime('%Y-%m-%d')
   for side in ('long','short'):
    url='https://api-pub.bitfinex.com/v2/stats1/pos.size:1m:tBTCUSD:'+side+'/hist?'+urllib.parse.urlencode({'start':cutoff-HOUR,'end':cutoff-1,'sort':1,'limit':100});p=out/'raw'/f'{date}-{side}.json';meta=p.with_name(p.stem+'-meta.json');p.parent.mkdir(parents=True,exist_ok=True);probe=PROBES.get((cutoff,side));b=None
    if p.exists():
     b=p.read_bytes();m=json.loads(meta.read_text());assert sha(b)==m['sha256'] and m['url']==url
    elif probe:
     source=WEB/(probe+'.json');origin=json.loads((WEB/(probe+'-meta.json')).read_text());b=source.read_bytes();assert origin['url']==url and sha(b)==origin['sha256'] and origin['status']==200;p.write_bytes(b);m=dict(origin,reused_probe=str(source.relative_to(ROOT)));write(meta,m);state['reused_probes']+=1
    else:
     for attempt in range(3):
      delay=max(0.,4.5-(time.monotonic()-last_request))
      if delay:time.sleep(delay)
      last_request=time.monotonic();state['network_requests']+=1;m={'url':url,'at':utc(),'attempt':attempt+1};headers={};raw=b''
      try:
       with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-public-aggregate-research/1.0'}),timeout=40) as r:raw=r.read();status=r.status;headers=dict(r.headers);m['final_url']=r.geturl()
      except urllib.error.HTTPError as e:status=e.code;raw=e.read();headers=dict(e.headers)
      except (urllib.error.URLError,TimeoutError,OSError) as e:status=None;m['error']=str(e)
      m.update(status=status,bytes=len(raw),sha256=sha(raw),content_type=headers.get('Content-Type',headers.get('content-type')),retry_after=headers.get('Retry-After',headers.get('retry-after')))
      if status==200:
       b=raw;p.write_bytes(b);write(meta,m);break
      fail=out/'failures'/f'{date}-{side}-attempt{attempt+1}';fail.parent.mkdir(parents=True,exist_ok=True);fail.with_suffix('.body').write_bytes(raw);write(fail.with_suffix('.json'),m);print({'request_failure':m},flush=True)
      if attempt<2 and (status is None or status==429 or (status is not None and 500<=status<600)):
       try:retry=float(m.get('retry_after') or 0)
       except ValueError:retry=120.
       state.update(waiting_reason=f'HTTP{status}',retry_not_before_utc=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=max(120.,retry))).isoformat());state_save();time.sleep(max(120.,retry));state.pop('waiting_reason',None);state.pop('retry_not_before_utc',None)
      else:break
     if b is None:write(meta,m)
    if b is None:snapshot={'cutoff':cutoff,'side':side,'rows':[],'selected':None,'valid':False,'invalid_minutes':[],'missing_minutes':list(range(cutoff-HOUR,cutoff,MIN))}
    else:snapshot=normalize(b,cutoff,side)
    snapshots.append(snapshot);sources.append({'cutoff':cutoff,'side':side,'path':str(p.relative_to(ROOT)) if b is not None else None,'metadata_path':str(meta.relative_to(ROOT)),'url':url,'sha256':sha(b) if b is not None else None,'rows':len(snapshot['rows']),'selected_valid':snapshot['valid']});state.update(processed_windows=len(sources),last_cutoff=cutoff,last_side=side,last_update_utc=utc());state_save()
    if len(sources)%20==0:print({k:state[k] for k in ('processed_windows','network_requests','last_update_utc')},flush=True)
  assert len(snapshots)==700;data={'snapshots':snapshots,'scope':'BTCUSD aggregate margin base-BTC positions only; exact last-minute snapshots with one-day assumed publication buffer; current vintage not historical publication proof; no account performance'};write(out/'snapshots.json.gz',data);audit={'canonical_sha256':sha(canonical(data)),'gzip_sha256':sha((out/'snapshots.json.gz').read_bytes()),'sources':sources,'windows':len(sources),'rows':sum(len(x['rows']) for x in snapshots),'valid_snapshots':sum(x['valid'] for x in snapshots),'initial_publication_vintage_proven':False};write(out/'prepare-audit.json',audit);state.update(status='completed',finished_utc=utc(),canonical_sha256=audit['canonical_sha256']);state_save();print({k:v for k,v in audit.items() if k!='sources'},flush=True)
 except BaseException as e:
  state.update(status='failed',error=repr(e),failed_utc=utc());state_save();raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
