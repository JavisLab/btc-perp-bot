"""New daily integer trade counts from prior independently proven public hour tuples."""
import argparse,gzip,json,math
from decimal import Decimal,getcontext
from pathlib import Path
from btc_perp_bot.research.archive import canonical,sha,DAY,HOUR
getcontext().prec=60
ROOT=Path(__file__).resolve().parents[1]
SOURCE_SHA='b7bcc90d73a29cf1f2d84dcd752025a6034d356ab337d7ce48eab82f09869d5f'
RECEIPT_SHA='67d0cf710240cfd75409d31300fcb35f4c1502c2289bb1657f7abe55e9fd7250'
def aggregate(e):
 d=e['day'];hours=e['hours'];times=[h['time'] for h in hours]
 if len(times)!=len(set(times)):raise ValueError('duplicate public hour')
 reasons=[]
 if e['end']!=d+DAY:reasons.append('day_end')
 if not e['valid']:reasons.append('prior_quality')
 if times!=list(range(d,d+DAY,HOUR)):reasons.append('hour_grid')
 vals=[]
 for h in hours:
  if h['end']!=h['time']+HOUR-1 or not h['valid']:reasons.append('hour_clock_or_quality')
  try:n=Decimal(h['trades'])
  except Exception:n=Decimal('NaN')
  if not n.is_finite() or n!=n.to_integral_value():reasons.append('noninteger_count');vals.append(None)
  else:
   vals.append(int(n))
   if n<=0:reasons.append('nonpositive_count')
 count=sum(vals) if all(n is not None for n in vals) else None
 return {'day':d,'end':e['end'],'valid':not reasons,'count':count,'invalid_reasons':sorted(set(reasons))}
def run(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);p=ROOT/'data/btc-pressure-20261004';b=gzip.decompress((p/'daily.json.gz').read_bytes());assert sha(b)==SOURCE_SHA;receipt=(p/'independent-audit.json').read_bytes();assert sha(receipt)==RECEIPT_SHA
 src=json.loads(b);rows=[aggregate(e) for e in src['rows']];payload={'rows':rows,'pressure_source_sha256':SOURCE_SHA,'scope':'Public matching-engine trade counts, not distinct orders/traders/information events; prior raw tuple receipt reused, not a new full archive audit'};body=canonical(payload);packed=gzip.compress(body,mtime=0);(out/'daily.json.gz').write_bytes(packed)
 audit={'source_canonical_sha256':SOURCE_SHA,'prior_source_receipt_sha256':RECEIPT_SHA,'daily_sha256':sha(body),'gzip_sha256':sha(packed),'days':len(rows),'valid_days':sum(r['valid'] for r in rows),'invalid_days':[r['day'] for r in rows if not r['valid']],'hour_rows':sum(len(r['hours']) for r in src['rows']),'initial_publication_vintage_proven':False};(out/'prepare-audit.json').write_bytes(canonical(audit));print(json.dumps(audit),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
