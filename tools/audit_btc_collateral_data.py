"""Independent Decimal and UTC calendar audit of new aggregate funding, no study import."""
import argparse,json,gzip,hashlib,datetime as dt,urllib.parse
from pathlib import Path
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
def digest(b):return hashlib.sha256(b).hexdigest()
def audit(out):
 out=Path(out).resolve();audit=json.loads((out/'prepare-audit.json').read_text());body=(out/'funding.json.gz').read_bytes();saved=json.loads(gzip.decompress(body));assert len(audit['sources'])==80;rows=[];empty=[];times=[]
 for i,s in enumerate(audit['sources']):
  y,m=divmod(i,12);y+=2020;m+=1;start=int(dt.datetime(y,m,1,tzinfo=dt.timezone.utc).timestamp()*1000);end=int(dt.datetime(y+(m==12),1 if m==12 else m+1,1,tzinfo=dt.timezone.utc).timestamp()*1000);assert s['month']==f'{y}-{m:02d}' and s['start']==start and s['end_exclusive']==end
  assert s['url']=='https://dapi.binance.com/dapi/v1/fundingRate?'+urllib.parse.urlencode({'symbol':'BTCUSD_PERP','startTime':start,'endTime':end-1,'limit':1000});raw=(ROOT/s['path']).read_bytes();assert digest(raw)==s['sha256'];seq=json.loads(raw);assert isinstance(seq,list) and len(seq)<1000 and len(seq)==s['rows'];prior=None
  if not seq:empty.append(s['month'])
  for r in seq:
   t=r['fundingTime'];d=Decimal(r['fundingRate']);assert r['symbol']=='BTCUSD_PERP' and type(t) is int and start<=t<end and (prior is None or t>prior) and d.is_finite();prior=t;times.append(t);rows.append({'time':t,'rate':str(d),'valid':r.get('rateType','Regular')=='Regular','raw':r})
 assert len(set(times))==len(times) and saved=={'symbol':'BTCUSD_PERP','rows':rows};canonical=json.dumps(saved,sort_keys=True,separators=(',',':'),allow_nan=False).encode();assert digest(canonical)==audit['canonical_sha256'] and digest(body)==audit['gzip_sha256'];assert len(rows)==audit['rows'] and sum(r['valid'] for r in rows)==audit['valid_rows'] and empty==audit['empty_months']
 bucket=8*3600000;occupied={t//bucket*bucket for t in times};missing=[u for u in range(min(occupied),max(occupied)+bucket,bucket) if u not in occupied];counts={u:0 for u in occupied}
 for t in times:counts[t//bucket*bucket]+=1
 req=audit['request_times'];minimum=min((b-a for a,b in zip(req,req[1:])),default=None);assert minimum is None or minimum>=1.999
 result={'canonical_sha256':digest(canonical),'gzip_sha256':digest(body),'months':80,'funding_rows':len(rows),'valid_rows':sum(r['valid'] for r in rows),'empty_months':empty,'raw_rows_exact':True,'first_actual_time':min(times),'last_actual_time':max(times),'missing_internal_8h_buckets':missing,'multiple_8h_buckets':[u for u,n in counts.items() if n!=1],'actual_clock_offsets_ms':{'min':min(t%bucket for t in times),'max':max(t%bucket for t in times)},'last_session_requests':len(req),'last_session_minimum_spacing_seconds':minimum,'retrieval_clock_limit':'First two fetched bodies reused after local path/state errors; no duplicate network requests. Initial request instants not separately logged; current-vintage only. Prior Q319 full-July response reused.','initial_publication_vintage_proven':False}
 b=json.dumps(result,sort_keys=True,separators=(',',':')).encode();p=out/'independent-audit.json';assert not p.exists() or p.read_bytes()==b;p.write_bytes(b);print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);audit(p.parse_args().out)
