"""Independent raw Decimal/calendar/probe audit of new public macro inputs; no strategy import."""
import argparse,calendar,datetime as dt,gzip,hashlib,json,urllib.parse
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def ms(s):return int(dt.datetime.combine(dt.date.fromisoformat(s),dt.time(),dt.timezone.utc).timestamp()*1000)
def audit(out):
 out=Path(out).resolve();payload=(out/'rates.json.gz').read_bytes();saved=json.loads(gzip.decompress(payload));a=json.loads((out/'prepare-audit.json').read_text());assert len(a['sources'])==162;rates={'SOFR':[],'EFFR':[]};raw_by_date={};stamps=[];empties=[]
 for i,s in enumerate(a['sources']):
  y,m=divmod(2019*12+11+i//2,12);m+=1;kind=['SOFR','EFFR'][i%2];start=f'{y}-{m:02d}-01';end=f'{y}-{m:02d}-{calendar.monthrange(y,m)[1]:02d}';part='secured/sofr' if kind=='SOFR' else 'unsecured/effr';url='https://markets.newyorkfed.org/api/rates/'+part+'/search.json?'+urllib.parse.urlencode({'startDate':start,'endDate':end});assert (s['start'],s['end'],s['type'],s['url'])==(start,end,kind,url);body=(ROOT/s['path']).read_bytes();meta=json.loads((ROOT/s['metadata_path']).read_text());assert sha(body)==s['sha256']==meta['sha256'] and meta['status']==200 and meta['url']==url;stamps.append(dt.datetime.fromisoformat(meta['at']).timestamp());raw=json.loads(body,parse_float=Decimal)['refRates'];assert isinstance(raw,list) and len(raw)==s['rows'] and len(raw)<=23
  if not raw:empties.append((start,kind))
  dates=[]
  for r in raw:
   date=r['effectiveDate'];d=dt.date.fromisoformat(date);value=Decimal(str(r['percentRate']));assert r['type']==kind and start<=date<=end and d.isoformat()==date and d.weekday()<5 and value.is_finite() and (kind,date) not in raw_by_date;raw_by_date[kind,date]=r;dates.append(date);flag=r.get('revisionIndicator','');foot=r.get('footnoteId');foot=str(foot) if foot is not None else None;rates[kind].append({'type':kind,'date':date,'time':ms(date),'rate':str(value),'revision':flag,'footnote':foot,'valid':flag in ('','Y') and foot in (None,'')})
  assert dates==sorted(set(dates),reverse=True)
 for k in rates:rates[k].sort(key=lambda r:r['time'])
 assert saved=={'series':rates};canonical=json.dumps(saved,sort_keys=True,separators=(',',':'),allow_nan=False).encode();assert sha(canonical)==a['canonical_sha256'] and sha(payload)==a['gzip_sha256'];assert a['rows']=={k:len(v) for k,v in rates.items()} and a['invalid_rows']=={k:sum(not r['valid'] for r in rr) for k,rr in rates.items()}
 probe=[]
 for name in ['q332-nyfed-sofr-public-probe','q336-nyfed-effr-public-probe','q339-nyfed-sofr-early-probe','q340-nyfed-effr-early-probe']:
  p=ROOT/'data/btc-web-20261004'/(name+'.json');meta=json.loads(p.with_name(name+'-meta.json').read_text());body=p.read_bytes();assert sha(body)==meta['sha256'] and meta['status']==200;rr=json.loads(body,parse_float=Decimal)['refRates'];assert all(raw_by_date[r['type'],r['effectiveDate']]==r for r in rr);probe.append({'name':name,'sha256':sha(body),'rows_exact':len(rr)})
 times=sorted(stamps);minimum=min(b-a for a,b in zip(times,times[1:]));assert minimum>=1.999
 sets={k:{r['date'] for r in v} for k,v in rates.items()};report={'canonical_sha256':sha(canonical),'gzip_sha256':sha(payload),'windows':162,'rows':a['rows'],'invalid_rows':a['invalid_rows'],'empty_windows':empties,'raw_rows_exact':True,'probe_overlap_exact':True,'probes':probe,'SOFR_only_dates':sorted(sets['SOFR']-sets['EFFR']),'EFFR_only_dates':sorted(sets['EFFR']-sets['SOFR']),'minimum_request_spacing_seconds':minimum,'initial_publication_vintage_proven':False,'scope':'Raw public monthly aggregates and exact same-provider probe equality; no individual repo/financial accounts, no revised-quarter statistics, no return calculation. Calendar-set mismatches retained for strict weekly invalidation.'};p=out/'independent-audit.json';b=json.dumps(report,sort_keys=True,separators=(',',':')).encode();assert not p.exists() or p.read_bytes()==b;p.write_bytes(b);print(json.dumps(report),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);audit(p.parse_args().out)
