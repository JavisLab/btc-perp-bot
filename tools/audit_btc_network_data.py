"""Independent Decimal audit of BTC aggregate chart payloads, dates, units and reuse. No performance."""
import datetime as dt,hashlib,json,urllib.parse
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'data/btc-network-20261003';DAY=86400000
sha=lambda b:hashlib.sha256(b).hexdigest()
ms=lambda d:int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def parse(meta,metric):
 b=(BASE/meta['file']).read_bytes();assert sha(b)==meta['sha256'] and len(b)==meta['bytes'];d=json.loads(b,parse_float=Decimal);assert d['status']=='ok' and d['period']=='day' and d['unit']==('Unique Addresses' if metric=='active' else 'Transactions');series={}
 for r in d['values']:
  t=Decimal(r['x']);v=Decimal(r['y']);assert t==t.to_integral_value() and int(t)*1000%DAY==0 and v.is_finite() and v>=0 and v==v.to_integral_value() and int(t)*1000 not in series;series[int(t)*1000]=v
 assert list(series)==sorted(series) and len(series)==meta['rows'];return series

def run(write=True):
 manifest=json.loads((BASE/'archive-manifest.json').read_text());norm=json.loads((BASE/'network-daily.json').read_text());start,end=ms('2020-01-01'),ms('2026-08-30');active={};seen={};cursor=start;overlaps=0
 for meta in manifest['active']:
  q=urllib.parse.parse_qs(urllib.parse.urlsplit(meta['url']).query);assert urllib.parse.urlsplit(meta['url']).path=='/charts/n-unique-addresses' and q['sampled']==['false'] and q['format']==['json'];lo=ms(q['start'][0]);days=int(q['timespan'][0].removesuffix('days'));hi=lo+days*DAY;assert lo==cursor and 0<days<=180 and hi<=end;rr=parse(meta,'active')
  for t,v in rr.items():
   assert lo<=t<=hi
   if t in seen:assert seen[t]==v;overlaps+=1
   seen[t]=v
   if t<hi:active[t]=v
  cursor=hi
 assert cursor==end;reuse=manifest['transactions_reused'];alltx=parse(reuse,'transactions');assert not reuse['network_refetch'];original=ROOT/reuse['original_path'];assert original.read_bytes()==(BASE/reuse['file']).read_bytes();old=json.loads((ROOT/'data/btc-mining-20261002/prepare-audit.json').read_text());assert reuse['sha256']==old['source_files']['n-transactions.json'];tx={t:v for t,v in alltx.items() if start<=t<end}
 probe=manifest['transactions_probe'];q=urllib.parse.parse_qs(urllib.parse.urlsplit(probe['url']).query);assert q['start']==['2026-08-01'] and q['timespan']==['7days'] and q['sampled']==['false'] and urllib.parse.urlsplit(probe['url']).path=='/charts/n-transactions';pr=parse(probe,'transactions');assert list(pr)==list(range(ms('2026-08-01'),ms('2026-08-09'),DAY));assert all(tx[t]==v for t,v in pr.items())
 original_active=json.loads((ROOT/'data/btc-web-20261003/q88-active-probe.json').read_text(),parse_float=Decimal)['values'];assert len(original_active)==8 and all(active[r['x']*1000]==Decimal(r['y']) for r in original_active)
 assert norm['asset']=='BTC' and norm['start']==start and norm['end_exclusive']==end and [r['day'] for r in norm['days']]==list(range(start,end,DAY))
 for r in norm['days']:
  for k,s in [('active',active),('transactions',tx)]:assert (None if r[k] is None else Decimal(r[k]))==s.get(r['day'])
 missing={k:[t for t in range(start,end,DAY) if t not in rr] for k,rr in [('active',active),('transactions',tx)]};assert norm['missing_active']==missing['active'] and norm['missing_transactions']==missing['transactions'];zero={k:[t for t,v in rr.items() if v==0] for k,rr in [('active',active),('transactions',tx)]}
 gaps=json.loads((BASE/'gap-probe-manifest.json').read_text());confirmed=[];gap_observations=0
 for item in gaps:
  meta=item['meta'];q=urllib.parse.parse_qs(urllib.parse.urlsplit(meta['url']).query);assert urllib.parse.urlsplit(meta['url']).path=='/charts/n-unique-addresses' and q['sampled']==['false'] and q['format']==['json'];lo=ms(q['start'][0]);hi=lo+int(q['timespan'][0].removesuffix('days'))*DAY;rr=parse(meta,'active');assert all(lo<=t<=hi and active.get(t)==v for t,v in rr.items());absent=[t for t in range(lo,hi+DAY,DAY) if t not in rr];assert absent==item['missing_days'];confirmed.extend(absent);gap_observations+=len(rr)
 assert sorted(confirmed)==missing['active'] and len(gaps)==5
 report={'active_responses':len(manifest['active']),'gap_probe_responses':len(gaps),'gap_probe_observations':gap_observations,'confirmed_active_gap_dates':sorted(confirmed),'calendar_days':len(norm['days']),'active_observations':len(active),'transactions_observations':len(tx),'reused_transaction_raw_days':len(alltx),'boundary_overlaps_equal':overlaps,'probe_observations':len(pr)+len(original_active),'missing':missing,'zeros':zero,'reused_transaction_raw_sha256':reuse['sha256'],'input_sha256':sha((BASE/'network-daily.json').read_bytes()),'scope':'Public BTC daily aggregate counts only; independent Decimal integer/unit/UTC/range/overlap/probe/reuse audit. No wallet/address contents. D+2 availability remains assumption, not first release or immutable historical vintage.'}
 if write:(BASE/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')));print(json.dumps(report,indent=2))
 return {'active':active,'transactions':tx},report
if __name__=='__main__':run()
