"""Independent Decimal reparse/selection of only the newly collected public BTC margin windows."""
import argparse,datetime as dt,gzip,hashlib,json,urllib.parse
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];MIN=60000;HOUR=60*MIN;DAY=24*HOUR
FIRST=int(dt.datetime(2019,12,22,tzinfo=dt.timezone.utc).timestamp()*1000);LAST=int(dt.datetime(2026,8,30,tzinfo=dt.timezone.utc).timestamp()*1000)
def audit(out):
 out=Path(out).resolve();payload=(out/'snapshots.json.gz').read_bytes();saved=json.loads(gzip.decompress(payload));a=json.loads((out/'prepare-audit.json').read_text());expected=[(c,s) for c in range(FIRST,LAST+1,7*DAY) for s in ('long','short')];assert [(e['cutoff'],e['side']) for e in a['sources']]==expected and [(e['cutoff'],e['side']) for e in saved['snapshots']]==expected;total=valid=missing=bad=failed=0
 for source,actual in zip(a['sources'],saved['snapshots']):
  c,side=source['cutoff'],source['side'];query=urllib.parse.urlencode({'start':c-HOUR,'end':c-1,'sort':1,'limit':100});url=f'https://api-pub.bitfinex.com/v2/stats1/pos.size:1m:tBTCUSD:{side}/hist?'+query;assert source['url']==url;meta=json.loads((ROOT/source['metadata_path']).read_text());assert meta['url']==url;parsed=[];invalid=[]
  if source['path'] is not None:
   b=(ROOT/source['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==source['sha256']==meta['sha256'] and meta['status']==200;raw=json.loads(b,parse_float=Decimal);assert isinstance(raw,list);seen=set()
   for row in raw:
    assert len(row)==2 and isinstance(row[0],int) and not isinstance(row[0],bool);t=row[0];assert t%MIN==0 and c-HOUR<=t<c and t not in seen;seen.add(t);value=Decimal(row[1]);parsed.append([t,str(value)])
    if not(value.is_finite() and value>0):invalid.append(t)
   assert [r[0] for r in parsed]==sorted(seen)
  else:assert meta['status']!=200;failed+=1
  bytime={t:q for t,q in parsed};selected=[c-MIN,bytime[c-MIN]] if c-MIN in bytime else None;ok=selected is not None and (c-MIN not in invalid);absent=[u for u in range(c-HOUR,c,MIN) if u not in bytime];check={'cutoff':c,'side':side,'rows':parsed,'selected':selected,'valid':ok,'invalid_minutes':invalid,'missing_minutes':absent};assert check==actual;assert source['selected_valid']==ok and source['rows']==len(parsed);total+=len(parsed);valid+=ok;missing+=len(absent);bad+=len(invalid)
 canonical=json.dumps(saved,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=hashlib.sha256(canonical).hexdigest();assert digest==a['canonical_sha256'] and hashlib.sha256(payload).hexdigest()==a['gzip_sha256'];assert total==a['rows'] and valid==a['valid_snapshots'] and a['windows']==len(expected)==700
 request_times={}
 for meta_path in list((out/'raw').glob('*-meta.json'))+list((out/'failures').glob('*.json')):
  r=json.loads(meta_path.read_text())
  if r.get('reused_probe'):continue
  stamp=dt.datetime.fromisoformat(r['at']).timestamp();request_times[r['url'],r['at']]=stamp
 times=sorted(request_times.values());maximum=max((sum(0<=v-u<60 for v in times) for u in times),default=0);assert maximum<=15
 minimum=min((b-a for a,b in zip(times,times[1:])),default=None)
 report={'canonical_sha256':digest,'gzip_sha256':a['gzip_sha256'],'windows':700,'new_network_requests':len(times),'maximum_requests_per_60_seconds':maximum,'minimum_request_spacing_seconds':minimum,'minute_rows':total,'valid_snapshots':valid,'invalid_snapshots':700-valid,'missing_minutes':missing,'invalid_minutes':bad,'failed_windows':failed,'raw_rows_exact':True,'selection_exact_last_minute':True,'initial_publication_vintage_proven':False,'scope':'Independent Decimal raw reconstruction and exact snapshot clocks; only newly collected BTCUSD aggregate positions, no account performance'};p=out/'independent-audit.json';encoded=json.dumps(report,sort_keys=True,separators=(',',':')).encode();assert not p.exists() or p.read_bytes()==encoded;p.write_bytes(encoded);print(report,flush=True);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);audit(p.parse_args().out)
