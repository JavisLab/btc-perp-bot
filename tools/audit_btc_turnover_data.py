"""Independent Decimal source parsing, calendar and accounting identities; no model imports."""
import csv,datetime as dt,hashlib,json,math
from collections import defaultdict
from decimal import Decimal,getcontext
from pathlib import Path
getcontext().prec=60
ROOT=Path(__file__).resolve().parents[1];DAY=86400000
def digest(b):return hashlib.sha256(b).hexdigest()
def audit(save=True):
 p=ROOT/'data/btc-turnover-20261003';w=ROOT/'data/btc-web-20261003';expected={'raw-adjusted.json':'40d8396ab66e7550a5dbd725c0a5aaee8789f2e8bbb73b74017f8b6e0733575c','raw-raw.json':'891bb8a56244c2c9f57a5f2e0cd1a4876605509e8d4a04de8a1ac3ccc9c18225'}
 sources={};counts={}
 for filename,h in expected.items():
  b=(p/filename).read_bytes();assert digest(b)==h;j=json.loads(b,parse_float=Decimal);assert j['unit']=='BTC' and j['period']=='day' and j['status']=='ok';series=defaultdict(list)
  for r in j['values']:
   t=Decimal(r['x'])*1000;day=int(t//DAY)*DAY;series[day].append((t,Decimal(r['y'])))
  key=filename.removeprefix('raw-').removesuffix('.json');sources[key]=series;counts[key]=len(j['values'])
 supply=ROOT/'data/btc-valuation-20261002/coinmetrics.json';b=supply.read_bytes();assert digest(b)=='db696818880b69e8320e192c60eb5429a40db0ecf5845ece194a01b0524d4a61';sj=json.loads(b,parse_float=Decimal)['data'];S=defaultdict(list);cm={}
 for r in sj:
  t=dt.datetime.fromisoformat(r['time'].replace('Z','+00:00'));ms=int(t.timestamp()*1000);v=Decimal(r['SplyCur']);assert r['asset']=='btc' and Decimal(r['CapMrktCurUSD'])==Decimal(r['PriceUSD'])*v;S[ms//DAY*DAY].append((Decimal(ms),v));cm[r['time'][:10]]=v
 sources['supply']=S
 sp={'adjusted':w/'q157-blockchain-transfer-sample.json','raw':w/'q158-output-sample.json'};overlap={};bad_overlap=set();overlap_n=0
 for key,q in sp.items():
  j=json.loads(q.read_text(),parse_float=Decimal);map_={}
  for r in j['values']:
   t=Decimal(r['x'])*1000;day=int(t//DAY)*DAY;map_[day]=(t,Decimal(r['y']));overlap_n+=1
   if sources[key].get(day)!=[map_[day]]:bad_overlap.add((key,day))
  overlap[key]=map_
 normalized=json.loads((p/'daily.json').read_text());lo=int(dt.datetime(2020,1,1,tzinfo=dt.timezone.utc).timestamp()*1000);hi=int(dt.datetime(2026,9,1,tzinfo=dt.timezone.utc).timestamp()*1000);assert [r['day'] for r in normalized['days']]==list(range(lo,hi,DAY));raw={};invalid={};arithmetic=0;max_fraction=Decimal(0)
 for r in normalized['days']:
  t=r['day'];reasons=[];values={}
  for key in ('adjusted','raw','supply'):
   rr=sources[key].get(t,[]);assert r['counts'][key]==len(rr)
   if len(rr)!=1:reasons.append(key+'_missing_or_duplicate');values[key]=None;continue
   clock,v=rr[0];values[key]=v
   if clock!=t:reasons.append(key+'_bad_clock')
   if not v.is_finite() or v<=0:reasons.append(key+'_bad_value')
   if (key,t) in bad_overlap:reasons.append(key+'_sample_difference')
  if values['adjusted'] is not None and values['raw'] is not None and values['adjusted'].is_finite() and values['raw'].is_finite() and values['adjusted']>values['raw']:reasons.append('adjusted_exceeds_raw')
  assert r['reasons']==reasons and r['valid']==(not reasons) and r['end']==t+DAY and r['base_assumed_available']==t+2*DAY and r['date']==dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat()
  for key,val in values.items():
   if reasons:assert r[key] is None
   else:assert r[key]==float(val)
  if reasons:invalid[r['date']]=reasons
  else:
   A,O,Sv=(values[k] for k in ('adjusted','raw','supply'));assert 0<A/O<=1 and (A/Sv)/(O/Sv)==A/O or abs((A/Sv)/(O/Sv)-A/O)<Decimal('1e-26');max_fraction=max(max_fraction,A/O);arithmetic+=1
  raw[t]=dict(r,**{k:float(v) if not reasons else None for k,v in values.items()})
 # Existing, frozen independent-distribution snapshot; no new network request.
 q=ROOT/'data/btc-mining-20261002/btc-community.csv';assert digest(q.read_bytes())=='06495ff8e643432e6948b7b4686ce44fc106217287dabdc1b38351d9ddec46c3';common=0;differences=[]
 with q.open() as f:
  for r in csv.DictReader(f):
   if r['time'] in cm and r.get('SplyCur'):
    common+=1
    if Decimal(r['SplyCur'])!=cm[r['time']]:differences.append({'date':r['time'],'difference':str(cm[r['time']]-Decimal(r['SplyCur']))})
 proof={'raw_rows':counts,'normalized_days':len(raw),'valid_days':arithmetic,'invalid_dates':invalid,'separate_request_overlap_values':overlap_n,'overlap_differences':[(k,t) for k,t in sorted(bad_overlap)],'supply_cap_identities':len(sj),'supply_existing_snapshot_overlap':common,'supply_existing_snapshot_differences':differences,'max_adjusted_raw_fraction':str(max_fraction),'normalized_sha256':digest((p/'daily.json').read_bytes()),'scope':'Separate Decimal parsing/calendar/positive value/adjusted<=raw and normalization checks; exact supply cap identity and prior same-source distribution comparison. Not independent on-chain change heuristics or historical first-release proof. No private/address/transaction queries or PNL.'}
 if save:(p/'independent-audit.json').write_text(json.dumps(proof,sort_keys=True,separators=(',',':')))
 return raw,proof
if __name__=='__main__':
 proof=audit()[1];summary=dict(proof);summary['supply_existing_snapshot_differences']={'count':len(proof['supply_existing_snapshot_differences']),'unique_differences':sorted({str(Decimal(r['difference']).normalize()) for r in proof['supply_existing_snapshot_differences']})};print(json.dumps(summary))
