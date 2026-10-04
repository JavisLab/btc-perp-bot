"""Frozen public monthly SOFR/EFFR aggregates for BTC information only; no trades/accounts."""
import argparse,datetime as dt,json,time,urllib.request,urllib.parse,urllib.error,os,calendar
from pathlib import Path
from decimal import Decimal
from btc_session_study import ROOT,ms,canonical,sha,write
KINDS={'SOFR':'secured/sofr','EFFR':'unsecured/effr'}
def normalize(body,kind,start,end):
 native=json.loads(body);exact=json.loads(body,parse_float=Decimal);rows=exact['refRates'];assert isinstance(rows,list) and len(rows)<=23;out=[];dates=[]
 for r in rows:
  date=r['effectiveDate'];d=dt.date.fromisoformat(date);assert d.isoformat()==date and d.weekday()<5 and r['type']==kind and start<=date<=end;dates.append(date);rate=Decimal(str(r['percentRate']));assert rate.is_finite();flag=r.get('revisionIndicator','');foot=r.get('footnoteId');foot=str(foot) if foot is not None else None;out.append({'type':kind,'date':date,'time':ms(date),'rate':str(rate),'revision':flag,'footnote':foot,'valid':flag in ('','Y') and foot in (None,'')})
 assert len(set(dates))==len(dates) and dates==sorted(dates,reverse=True);return sorted(out,key=lambda r:r['time'])
def state(out,obj):(out/'collection-state.json').write_bytes(canonical(obj))
def run(out):
 out=Path(out).resolve();(out/'raw').mkdir(parents=True,exist_ok=True);(out/'failures').mkdir(exist_ok=True);sources=[];series={k:[] for k in KINDS};request_times=[];began=dt.datetime.now(dt.timezone.utc).isoformat()
 for i in range(81):
  y,m=divmod(2019*12+11+i,12);m+=1;start=f'{y}-{m:02d}-01';end=f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]:02d}'
  for kind,part in KINDS.items():
   path=out/'raw'/f'{start[:7]}-{kind}.json';meta_path=path.with_name(path.stem+'-meta.json');url='https://markets.newyorkfed.org/api/rates/'+part+'/search.json?'+urllib.parse.urlencode({'startDate':start,'endDate':end})
   if path.exists():
    body=path.read_bytes();meta=json.loads(meta_path.read_text());assert meta['url']==url and meta['sha256']==sha(body) and meta['status']==200
   else:
    for attempt in range(3):
     if request_times:time.sleep(max(0,request_times[-1]+2-time.time()))
     request_times.append(time.time());meta={'url':url,'at':dt.datetime.now(dt.timezone.utc).isoformat()}
     try:
      with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-Research/1.0 (public macro reference rates)'}),timeout=35) as r:body=r.read();assert r.status==200;meta.update(status=r.status,sha256=sha(body),bytes=len(body))
      path.write_bytes(body);meta_path.write_bytes(canonical(meta));break
     except urllib.error.HTTPError as e:
      meta.update(status=e.code,body=e.read().decode(errors='replace'));write(out/'failures'/f'{start[:7]}-{kind}-{attempt}.json',meta)
      if (e.code==429 or e.code>=500) and attempt<2:time.sleep(max(120,float(e.headers.get('Retry-After','120'))))
      else:raise
   rr=normalize(body,kind,start,end);series[kind].extend(rr);sources.append({'type':kind,'start':start,'end':end,'url':url,'path':str(path.relative_to(ROOT)),'metadata_path':str(meta_path.relative_to(ROOT)),'sha256':sha(body),'rows':len(rr)});state(out,{'status':'running','pid':os.getpid(),'started':began,'completed_windows':len(sources),'requests_this_session':len(request_times),'last':f'{start[:7]}-{kind}'});print(json.dumps({'done':len(sources),'month':start[:7],'type':kind,'rows':len(rr)}),flush=True)
 for k,rr in series.items():assert len({r['date'] for r in rr})==len(rr) and rr==sorted(rr,key=lambda r:r['date'])
 payload={'series':series};write(out/'rates.json.gz',payload);write(out/'prepare-audit.json',{'sources':sources,'canonical_sha256':sha(canonical(payload)),'gzip_sha256':sha((out/'rates.json.gz').read_bytes()),'rows':{k:len(v) for k,v in series.items()},'invalid_rows':{k:sum(not r['valid'] for r in v) for k,v in series.items()},'request_times':request_times,'vintage':'Current NYFed published-rate API; not quarterly revised statistics or proven original first vintage'});state(out,{'status':'completed','pid':os.getpid(),'started':began,'ended':dt.datetime.now(dt.timezone.utc).isoformat(),'completed_windows':162,'requests_this_session':len(request_times)});print(json.dumps({'completed':162,'rows':{k:len(v) for k,v in series.items()},'canonical_sha256':sha(canonical(payload))}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
