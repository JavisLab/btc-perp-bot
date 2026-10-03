"""Independent Decimal input/UTC/bin/fee-atom/probe/reuse audit. No strategy imports or performance."""
import datetime as dt,hashlib,json,urllib.parse
from collections import Counter
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'data/btc-congestion-20261003';DAY=86400000;STEP=900000
sha=lambda b:hashlib.sha256(b).hexdigest()
ms=lambda d:int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def parse(meta,base,unit,period):
 blob=(base/meta['file']).read_bytes();assert sha(blob)==meta['sha256'] and len(blob)==meta['bytes'];data=json.loads(blob,parse_float=Decimal);assert data['status']=='ok' and data['unit']==unit and data['period']==period;rows={}
 for row in data['values']:
  t=Decimal(row['x']);v=Decimal(row['y']);assert t==int(t) and v.is_finite() and v>=0 and int(t)*1000 not in rows;rows[int(t)*1000]=v
 assert list(rows)==sorted(rows) and len(rows)==meta['rows'];return rows

def run(write=True):
 manifest=json.loads((BASE/'archive-manifest.json').read_text());norm=json.loads((BASE/'congestion-daily.json').read_text());start,end=ms('2020-01-01'),ms('2026-08-30');series={};overlaps={};modal_steps={}
 for key,metric,unit,period,stride,limit in [('queue','mempool-size','Bytes','minute',STEP,14),('fee','transaction-fees','BTC','day',DAY,180)]:
  raw={};seen={};cursor=start;overlaps[key]=0;modal_steps[key]=[]
  for meta in manifest[key]:
   url=urllib.parse.urlsplit(meta['url']);q=urllib.parse.parse_qs(url.query);assert url.scheme=='https' and url.netloc=='api.blockchain.info' and url.path=='/charts/'+metric and q['sampled']==['false'] and q['format']==['json'];lo=ms(q['start'][0]);n=int(q['timespan'][0].removesuffix('days'));hi=lo+n*DAY;assert lo==cursor and 0<n<=limit and hi<=end;rr=parse(meta,BASE,unit,period);ts=list(rr)
   if len(ts)>1:
    gaps=Counter(b-a for a,b in zip(ts,ts[1:]));modal=gaps.most_common(1)[0][0];assert modal==stride,(meta['file'],'unexpected source sampling',gaps);modal_steps[key].append(modal)
   for t,v in rr.items():
    assert lo<=t<=hi and t%stride==0
    if t in seen:assert seen[t]==v;overlaps[key]+=1
    seen[t]=v
    if t<hi:raw[t]=v
   cursor=hi
  assert cursor==end;series[key]=raw
 reuse=manifest['transactions_reused'];blob=(BASE/reuse['file']).read_bytes();assert sha(blob)==reuse['sha256']=='7a2b322ec2b2c0d4e297eb0c3afa6204f5beaa3d15dcf0531b4b61e2abdeb44a' and len(blob)==reuse['bytes'] and blob==(ROOT/reuse['original_path']).read_bytes() and reuse['network_refetch'] is False;txraw=json.loads(blob,parse_float=Decimal);assert [r['day'] for r in txraw['days']]==list(range(start,end,DAY));tx={}
 for r in txraw['days']:
  if r['transactions'] is not None:
   v=Decimal(r['transactions']);assert v==int(v) and v>0;tx[r['day']]=v
 fee_sats={};worst=Decimal(0)
 for t,v in series['fee'].items():
  exact=v*Decimal(100000000);nearest=int(exact+Decimal('.5'));err=abs(exact-nearest);assert err<=Decimal('.0001');worst=max(worst,err);fee_sats[t]=nearest
 means={};missing_slots=[];incomplete=[];observed_count={}
 for t in range(start,end,DAY):
  wanted=range(t,t+DAY,STEP);absent=[u for u in wanted if u not in series['queue']];missing_slots+=absent;observed_count[t]=96-len(absent)
  if absent:incomplete.append(t)
  else:means[t]=sum(series['queue'][u] for u in wanted)/Decimal(96)
 assert norm['asset']=='BTC' and norm['start']==start and norm['end_exclusive']==end and norm['mempool_sampling_ms']==STEP and [r['day'] for r in norm['days']]==list(range(start,end,DAY))
 for r in norm['days']:
  t=r['day'];actual=None if r['mempool_mean_source_bytes'] is None else Decimal(r['mempool_mean_source_bytes']);assert actual==means.get(t) and r['mempool_observations']==observed_count[t] and r['fee_total_sats']==fee_sats.get(t) and r['transactions']==tx.get(t)
 probe_counts={};probe_folder=BASE/'probes'
 for entry in json.loads((probe_folder/'manifest.json').read_text()):
  metric=entry['metric']
  if metric not in ('mempool-size','transaction-fees'):continue
  meta=dict(entry,file=metric+'.json');pr=parse(meta,probe_folder,'Bytes' if metric=='mempool-size' else 'BTC','minute' if metric=='mempool-size' else 'day');source=series['queue' if metric=='mempool-size' else 'fee'];assert all(source[t]==v for t,v in pr.items());probe_counts[metric]=len(pr)
 for entry in json.loads((probe_folder/'mempool-clock-manifest.json').read_text()):
  pr=parse(dict(entry,file=entry['name']+'.json'),probe_folder,'Bytes','minute');assert all(series['queue'][t]==v for t,v in pr.items());probe_counts[entry['name']]=len(pr)
 gap_probes=json.loads((BASE/'gap-probe-manifest.json').read_text());gap_checks=[]
 for item in gap_probes:
  meta=item['meta'];isqueue=item['metric']=='mempool-size';rr=parse(meta,BASE,'Bytes' if isqueue else 'BTC','minute' if isqueue else 'day');url=urllib.parse.urlsplit(meta['url']);q=urllib.parse.parse_qs(url.query);lo=ms(q['start'][0]);hi=lo+int(q['timespan'][0].removesuffix('days'))*DAY;assert url.path=='/charts/'+item['metric'] and q['sampled']==['false'];stride=STEP if isqueue else DAY;native=series['queue' if isqueue else 'fee'];assert all(lo<=t<=hi and native.get(t)==v for t,v in rr.items());wanted=range(lo,hi if isqueue else hi+DAY,stride);absent=[t for t in wanted if t not in rr];assert absent==item['missing'] and all(t not in native for t in absent);gap_checks.append({'file':meta['file'],'observations':len(rr),'missing_confirmed':len(absent)})
 assert len(gap_checks)==4
 report={'gap_probes':gap_checks,'queue_responses':len(manifest['queue']),'queue_observations':len(series['queue']),'fee_responses':len(manifest['fee']),'fee_observations':len(series['fee']),'calendar_days':len(norm['days']),'complete_queue_days':len(means),'incomplete_queue_days':incomplete,'missing_queue_slots':missing_slots,'missing_fee_days':[t for t in range(start,end,DAY) if t not in fee_sats],'missing_tx_days':[t for t in range(start,end,DAY) if t not in tx],'overlaps_equal':overlaps,'source_modal_steps_ms':{k:sorted(set(v)) for k,v in modal_steps.items()},'zero_queue_observations':sum(v==0 for v in series['queue'].values()),'zero_fee_days':sum(v==0 for v in fee_sats.values()),'probe_equal_observations':probe_counts,'max_fee_satoshi_rounding':str(worst),'input_sha256':sha((BASE/'congestion-daily.json').read_bytes()),'scope':'Independent Decimal raw aggregate node queue/900-second spacing/96-slot UTC daily means, native fee satoshi rounding, original reused transactions, exact overlapping probes. Current historical aggregates are not first vintages; assumed completion buffer, unknown historical node/aggregation policy; no individual address or transaction queries.'}
 if write:
  (BASE/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')));print(json.dumps({**{k:v for k,v in report.items() if k not in ('incomplete_queue_days','missing_queue_slots')},'incomplete_queue_days_count':len(incomplete),'missing_queue_slots_count':len(missing_slots)},indent=2))
 return {'mempool':means,'fee_sats':fee_sats,'transactions':tx},report
if __name__=='__main__':run()
