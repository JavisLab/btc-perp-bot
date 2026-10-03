"""Fetch only two public BTC daily aggregates and freeze them; no features/model/PNL."""
import argparse,datetime as dt,hashlib,json,math,urllib.request,urllib.parse
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-turnover-20261003';WEB=ROOT/'data/btc-web-20261003';DAY=86400000
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def ms(s):return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def date(t):return dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat()
NAMES={'adjusted':'estimated-transaction-volume','raw':'output-volume'}
def fetch():
 OUT.mkdir(exist_ok=True);meta=[]
 for key,name in NAMES.items():
  url='https://api.blockchain.info/charts/'+name+'?'+urllib.parse.urlencode({'timespan':'2435days','start':'2020-01-01','format':'json','sampled':'false'});p=OUT/('raw-'+key+'.json')
  if p.exists():raise RuntimeError('Refusing unchanged source recollection: '+str(p))
  at=dt.datetime.now(dt.timezone.utc).isoformat()
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BTC-public-research/1.0'}),timeout=50) as r:b=r.read();row={'url':url,'at':at,'status':r.status,'final_url':r.url,'bytes':len(b),'sha256':sha(b)}
  p.write_bytes(b);meta.append(dict(row,file=p.name));print(json.dumps(meta[-1]),flush=True)
 (OUT/'source.json').write_bytes(canonical(meta))
def group(j):
 assert j['status']=='ok' and j['unit']=='BTC' and j['period']=='day';out=defaultdict(list)
 for r in j['values']:
  t=float(r['x'])*1000;assert math.isfinite(t);d=int(t//DAY)*DAY;out[d].append((t,r['y']))
 return out
def normalize(a,o,supply,samples,start,end):
 series={'adjusted':group(a),'raw':group(o)};ss=defaultdict(list)
 for r in supply['data']:
  assert r['asset']=='btc';t=ms(r['time'].replace('Z','+00:00'));ss[t//DAY*DAY].append((t,float(r['SplyCur'])))
 overlap={k:group(v) for k,v in samples.items()};days=[];mismatches=[]
 for t in range(start,end,DAY):
  reasons=[];v={};counts={}
  for key,values in list(series.items())+[('supply',ss)]:
   rr=values.get(t,[]);counts[key]=len(rr)
   if len(rr)!=1:reasons.append(key+'_missing_or_duplicate');v[key]=None;continue
   clock,x=rr[0];v[key]=x
   if clock!=t:reasons.append(key+'_bad_clock')
   if not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0:reasons.append(key+'_bad_value')
   if key in overlap and t in overlap[key] and rr!=overlap[key][t]:reasons.append(key+'_sample_difference');mismatches.append([key,date(t)])
  if all(v[k] is not None and math.isfinite(v[k]) for k in ('adjusted','raw')) and v['adjusted']>v['raw']:reasons.append('adjusted_exceeds_raw')
  valid=not reasons;days.append({'day':t,'date':date(t),'end':t+DAY,'base_assumed_available':t+2*DAY,'valid':valid,'reasons':reasons,'counts':counts,**{k:v[k] if valid else None for k in v}})
 return days,mismatches
def run():
 source=json.loads((OUT/'source.json').read_text())
 for r in source:assert sha((OUT/r['file']).read_bytes())==r['sha256']
 q=ROOT/'data/btc-valuation-20261002/coinmetrics.json';raw=q.read_bytes()
 assert sha(raw)=='db696818880b69e8320e192c60eb5429a40db0ecf5845ece194a01b0524d4a61'
 samplepaths={'adjusted':WEB/'q157-blockchain-transfer-sample.json','raw':WEB/'q158-output-sample.json'};samples={k:json.loads(p.read_text()) for k,p in samplepaths.items()}
 a,o=(json.loads((OUT/('raw-'+k+'.json')).read_text()) for k in ('adjusted','raw'))
 days,differences=normalize(a,o,json.loads(raw),samples,ms('2020-01-01'),ms('2026-09-01'));data={'scope':'BTC public estimated transfer excluding change versus all outputs; not verified economic payments or first-vintage heuristics','sources':source,'reused_supply_sha256':sha(raw),'samples':{k:sha(p.read_bytes()) for k,p in samplepaths.items()},'units':'BTC native units; supply interval-end stock, estimated/raw daily flows','start':ms('2020-01-01'),'end_exclusive':ms('2026-09-01'),'days':days};b=canonical(data);(OUT/'daily.json').write_bytes(b)
 report={'raw_rows':{'adjusted':len(a['values']),'raw':len(o['values'])},'days':len(days),'valid_days':sum(r['valid'] for r in days),'invalid_dates':{r['date']:r['reasons'] for r in days if not r['valid']},'overlap_rows':{k:len(j['values']) for k,j in samples.items()},'overlap_differences':differences,'normalized_sha256':sha(b),'source_sha256':sha((OUT/'source.json').read_bytes()),'scope':'Data only, no strategy features/fitting/performance; no filling from other providers'};(OUT/'prepare-audit.json').write_bytes(canonical(report));print(json.dumps(report),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--fetch',action='store_true');a=p.parse_args()
 if a.fetch:fetch()
 run()
