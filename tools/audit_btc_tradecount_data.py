"""Independent Decimal count reconstruction; no strategy or account calculations/import."""
import argparse,gzip,json
from decimal import Decimal,localcontext
from pathlib import Path
from btc_perp_bot.research.archive import canonical,sha,DAY,HOUR
ROOT=Path(__file__).resolve().parents[1]
def run(out):
 out=Path(out);raw=gzip.decompress((ROOT/'data/btc-pressure-20261004/daily.json.gz').read_bytes());assert sha(raw)=='b7bcc90d73a29cf1f2d84dcd752025a6034d356ab337d7ce48eab82f09869d5f';receipt=(ROOT/'data/btc-pressure-20261004/independent-audit.json').read_bytes();assert sha(receipt)=='67d0cf710240cfd75409d31300fcb35f4c1502c2289bb1657f7abe55e9fd7250';old=json.loads(raw);packed=(out/'daily.json.gz').read_bytes();body=gzip.decompress(packed);new=json.loads(body);assert [r['day'] for r in new['rows']]==[r['day'] for r in old['rows']];hours=0;valid=0
 with localcontext() as ctx:
  ctx.prec=60
  for a,b in zip(old['rows'],new['rows']):
   times=[h['time'] for h in a['hours']];assert len(times)==len(set(times));ok=a['valid'] and a['end']==a['day']+DAY and sorted(times)==list(range(a['day'],a['day']+DAY,HOUR)) and times==sorted(times);values=[]
   for h in a['hours']:
    hours+=1
    try:n=Decimal(h['trades'])
    except Exception:n=Decimal('NaN')
    integer=n.is_finite() and n==n.to_integral_value();values.append(n if integer else None);ok=ok and integer and n>0 and h['valid'] and h['end']==h['time']+HOUR-1
   exact=sum(values,Decimal(0)) if all(x is not None for x in values) else None
   assert b['day']==a['day'] and b['end']==a['end'] and b['valid']==bool(ok) and b['count']==exact and bool(b['invalid_reasons'])==not_bool(ok)
   if ok:valid+=1
 report={'raw_daily_counts':len(new['rows']),'raw_hours':hours,'valid_days':valid,'invalid_days':len(new['rows'])-valid,'daily_sha256':sha(body),'gzip_sha256':sha(packed),'raw_counts_exact':True,'max_count_error':0,'prior_raw_tuple_receipt_sha256':sha(receipt),'scope':'Separate Decimal daily aggregation from fixed raw-hour strings; old original ZIP audit reused, no new performance calculation'};(out/'independent-audit.json').write_bytes(canonical(report));print(json.dumps(report),flush=True)
def not_bool(x):return not bool(x)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
