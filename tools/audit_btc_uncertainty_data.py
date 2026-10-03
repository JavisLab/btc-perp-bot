"""Independent dated-vintage CSV audit; never imports the collector or computes BTC performance."""
import csv,datetime as dt,hashlib,io,json,urllib.parse
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-uncertainty-20261003'
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def run():
 normalized=json.loads((OUT/'epu-vintages.json').read_text());manifest=json.loads((OUT/'archive-manifest.json').read_text());frozen={v['vintage_date']:v for v in normalized['vintages']};expected=[];date=dt.date(2019,12,27)
 while date<=dt.date(2026,8,28):expected.append(date.isoformat());date+=dt.timedelta(days=7)
 assert [v['vintage_date'] for v in normalized['vintages']]==expected and [e['vintage_date'] for e in manifest]==expected
 observations=0;missing=[];revisions=0;comparisons=0;maximum=Decimal(0);examples=[];previous=None;series={}
 for meta in manifest:
  vintage=meta['vintage_date'];v=dt.date.fromisoformat(vintage);assert v.weekday()==4;query=urllib.parse.parse_qs(urllib.parse.urlsplit(meta['url']).query);assert query['id']==['USEPUINDXD'] and query['vintage_date']==[vintage] and query['cosd']==[(v-dt.timedelta(days=35)).isoformat()] and query['coed']==[(v-dt.timedelta(days=1)).isoformat()]
  p=OUT/meta['file'];b=p.read_bytes();assert sha(b)==meta['sha256'] and len(b)==meta['bytes'];reader=csv.reader(io.StringIO(b.decode('utf-8-sig')));header=next(reader);assert header==['observation_date','USEPUINDXD_'+vintage.replace('-','')];actual={}
  for d,value in reader:
   day=dt.date.fromisoformat(d);assert v-dt.timedelta(days=35)<=day<v and d not in actual;val=None if value in ('','.','NA') else Decimal(value);assert val is None or val.is_finite() and val>=0;actual[d]=val
  series[vintage]=actual;stored=frozen[vintage];assert stored['window_start']==(v-dt.timedelta(days=35)).isoformat() and stored['window_end']==(v-dt.timedelta(days=1)).isoformat();assert {d:None if x is None else Decimal(x) for d,x in stored['values'].items()}==actual;wanted=[(v-dt.timedelta(days=35)+dt.timedelta(days=i)).isoformat() for i in range(35)];absent=[d for d in wanted if actual.get(d) is None];assert stored['missing_dates']==absent and meta['rows']==len(actual) and meta['missing']==len(absent);observations+=len(actual)
  if absent:missing.append({'vintage_date':vintage,'dates':absent})
  if previous is not None:
   for d in sorted(actual.keys()&previous.keys()):
    a,b=previous[d],actual[d]
    if a is None or b is None:continue
    comparisons+=1;change=abs(a-b)
    if change:
     revisions+=1;maximum=max(maximum,change)
     if len(examples)<5:examples.append({'observation_date':d,'later_vintage':vintage,'prior':str(a),'later':str(b)})
  previous=actual
 report={'snapshots':len(frozen),'independent_csv_observations':observations,'missing_snapshots':missing,'adjacent_vintage_common_observations':comparisons,'revised_common_observations':revisions,'maximum_absolute_index_revision':str(maximum),'illustrative_revisions':sorted(examples,key=lambda x:(x['later_vintage'],x['observation_date'])),'input_sha256':sha((OUT/'epu-vintages.json').read_bytes()),'scope':'Each historical Friday-vintage CSV independently checked in Decimal, dates/header/URL/payload/missingness; not first intraday release proof, no BTC features/performance'};(OUT/'independent-audit.json').write_bytes(canonical(report));print(json.dumps(report,indent=2))
if __name__=='__main__':run()
