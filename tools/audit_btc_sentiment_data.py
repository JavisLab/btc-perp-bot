"""Independent Decimal parsing of frozen Alternative.me BTC index, no model/PnL calls."""
import json,datetime as dt,hashlib
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DAY=86400000

def audit(save=True):
 p=ROOT/'data/btc-sentiment-20261003';raw=(p/'raw-fng-history.json').read_bytes();assert hashlib.sha256(raw).hexdigest()=='67b25d3d98f5a46c90868cdc9f3119dc24d264989fa8347d35d9cbdaf174f4ff';j=json.loads(raw,parse_float=Decimal);series={}
 for r in j['data']:
  sec=Decimal(r['timestamp']);value=Decimal(r['value']);assert sec==sec.to_integral() and value==value.to_integral() and 0<=value<=100;t=int(sec)*1000;assert t%DAY==0 and t not in series;series[t]={'value':int(value),'classification':r['value_classification'],'raw_timestamp_seconds':int(sec)}
 latest=json.loads((p/'raw-fng-latest10.json').read_bytes());overlap=0
 for r in latest['data']:
  expected=series[int(r['timestamp'])*1000];assert expected=={'value':int(r['value']),'classification':r['value_classification'],'raw_timestamp_seconds':int(r['timestamp'])};overlap+=1
 normalized=json.loads((p/'daily.json').read_bytes());lo=int(dt.datetime(2020,1,1,tzinfo=dt.timezone.utc).timestamp()*1000);hi=int(dt.datetime(2026,9,1,tzinfo=dt.timezone.utc).timestamp()*1000);assert [r['day'] for r in normalized['days']]==list(range(lo,hi,DAY));bad=[]
 for r in normalized['days']:
  t=r['day'];v=series.get(t);assert r['valid']==(v is not None) and r['base_assumed_available']==t+2*DAY and r['date']==dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat()
  if v is not None:
   for key,value in v.items():assert r[key]==value
  else:assert r['value'] is None and r['classification'] is None and r['raw_timestamp_seconds'] is None;bad.append(r['date'])
 all_missing=[dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat() for t in range(min(series),max(series)+DAY,DAY) if t not in series];assert all_missing==['2018-04-14','2018-04-15','2018-04-16','2024-10-26']
 report={'provider':'Alternative.me','raw_rows':len(series),'normalized_rows':len(normalized['days']),'independent_value_checks':sum(r['valid'] for r in normalized['days']),'separate_api_overlap':overlap,'missing_dates_all_history':all_missing,'missing_dates_study':bad,'normalized_sha256':hashlib.sha256((p/'daily.json').read_bytes()).hexdigest(),'first_publication_clock_verified':False,'scope':'Independent raw Decimal/index/calendar/overlap checks, not independent reconstruction of proprietary component formula or historical first releases; no market performance computed'}
 if save:(p/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')))
 return series,report
if __name__=='__main__':print(json.dumps(audit()[1]))
