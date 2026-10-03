"""Independent Decimal public DVOL response/clock audit; no study imports or performance."""
import datetime as dt,hashlib,json,urllib.parse
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'data/btc-dvol-20261003';DAY=86400000;HOUR=3600000
sha=lambda b:hashlib.sha256(b).hexdigest()
ms=lambda d:int(dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def raw(meta,folder=BASE):
 b=(folder/meta['file']).read_bytes();assert len(b)==meta['bytes'] and sha(b)==meta['sha256'];d=json.loads(b,parse_float=Decimal);assert 'error' not in d;query=urllib.parse.parse_qs(urllib.parse.urlsplit(meta['url']).query);assert query['currency']==['BTC'];return d['result'],query

def run(write=True):
 norm=json.loads((BASE/'dvol-daily.json').read_text());manifest=json.loads((BASE/'archive-manifest.json').read_text());rows={};request_ranges=[]
 for meta in manifest:
  result,q=raw(meta);assert q['resolution']==['1D'];lo,hi=int(q['start_timestamp'][0]),int(q['end_timestamp'][0]);assert hi-lo<180*DAY;request_ranges.append((lo,hi));rr=result['data'];assert len(rr)==meta['rows'];times=[]
  for r in rr:
   t=r[0];times.append(t);v=list(map(Decimal,r[1:]));assert lo<=t<=hi and t%DAY==0 and len(v)==4 and all(x.is_finite() and x>0 for x in v);o,h,l,c=v;assert l<=min(o,c)<=max(o,c)<=h
   assert t not in rows or rows[t]==v;rows[t]=v
  assert times==sorted(set(times));assert result.get('continuation') is None,'continuation unexpectedly present: inspect before accepting archive'
 assert request_ranges[0][0]==ms('2021-04-01') and request_ranges[-1][1]==ms('2026-09-01')-1
 for a,b in zip(request_ranges,request_ranges[1:]):assert a[1]+1==b[0]
 assert norm['currency']=='BTC' and norm['unit']=='annualized_volatility_percent' and norm['interval']=='1D';assert norm['start']==ms('2021-04-01') and norm['end_exclusive']==ms('2026-09-01');assert {r[0]:list(map(Decimal,r[1:])) for r in norm['rows']}==rows;assert len(norm['rows'])==len(rows)
 absent=[t for t in range(norm['start'],norm['end_exclusive'],DAY) if t not in rows];assert absent==norm['missing_days'];checks=[]
 probes=json.loads((BASE/'clock-probe-manifest.json').read_text())
 for meta in probes:
  result,q=raw(meta);t=int(q['start_timestamp'][0]);assert q['resolution']==['3600'] and int(q['end_timestamp'][0])==t+DAY-1;rr=result['data'];assert [r[0] for r in rr]==list(range(t,t+DAY,HOUR));assert result.get('continuation') is None;agg=[Decimal(rr[0][1]),max(Decimal(r[2]) for r in rr),min(Decimal(r[3]) for r in rr),Decimal(rr[-1][4])];assert agg==rows[t],(t,agg,rows[t]);checks.append({'day':t,'hours':24,'equal':True})
 folder=BASE/'probes';meta=json.loads((folder/'recent-hourly.meta.json').read_text());blob=(folder/'recent-hourly.json').read_bytes();assert sha(blob)==meta['sha256'];rr=json.loads(blob,parse_float=Decimal)['result']['data'];t=ms('2026-08-30');rr=[r for r in rr if t<=r[0]<t+DAY];assert [r[0] for r in rr]==list(range(t,t+DAY,HOUR));agg=[Decimal(rr[0][1]),max(Decimal(r[2]) for r in rr),min(Decimal(r[3]) for r in rr),Decimal(rr[-1][4])];assert agg==rows[t];checks.append({'day':t,'hours':24,'equal':True})
 report={'daily_responses':len(manifest),'daily_observations':len(rows),'missing_days':absent,'clock_probes':checks,'first_included_day':'2021-04-01','current_historical_not_first_vintage':True,'input_sha256':sha((BASE/'dvol-daily.json').read_bytes()),'scope':'Independent Decimal payload/URL/overlap/range/unit/OHLC/UTC timestamps and four native24h-to-day aggregations; not a historical first-release or original index construction proof'}
 if write:(BASE/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')));print(json.dumps(report,indent=2))
 return rows,report
if __name__=='__main__':run()
