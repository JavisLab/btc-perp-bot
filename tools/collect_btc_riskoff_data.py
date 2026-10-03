"""Freeze previously fetched official VIX closes; no requests, model, or PNL calls."""
import csv,datetime as dt,hashlib,io,json,math
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-riskoff-20261003';WEB=ROOT/'data/btc-web-20261003';DAY=86400000
CBOE_SHA='6edc3e3928c4b164b9e4ed1ec874e0ed53c7d52997557adebb7d6b7451db565a';FRED_SHA='84f279d69e35eacf918b939875bf0ed7e0ad78d176cd289b24f2ebf364221510'
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def stamp(d):return int(dt.datetime.combine(d,dt.time(),dt.timezone.utc).timestamp()*1000)
def normalize(cboe_text,fred_text,start='2019-01-01',end='2026-09-01'):
 cb=defaultdict(list);fr=defaultdict(list);blanks=[];all_cboe=0;all_fred=0
 for r in csv.DictReader(io.StringIO(cboe_text)):
  d=dt.datetime.strptime(r['DATE'],'%m/%d/%Y').date().isoformat();all_cboe+=1
  if start<=d<end:cb[d].append({k:float(r[k]) for k in ('OPEN','HIGH','LOW','CLOSE')})
 for r in csv.DictReader(io.StringIO(fred_text)):
  d=r['observation_date'];all_fred+=1
  if not start<=d<end:continue
  if r['VIXCLS'] in ('','.'):blanks.append(d)
  else:fr[d].append(float(r['VIXCLS']))
 out=[]
 for date in sorted(set(cb)|set(fr)):
  cc=cb.get(date,[]);ff=fr.get(date,[]);d=dt.date.fromisoformat(date);t=stamp(d);reasons=[]
  if len(cc)!=1:reasons.append('cboe_missing_or_duplicate')
  if len(ff)!=1:reasons.append('fred_missing_or_duplicate')
  if d.weekday()>=5:reasons.append('nonweekday')
  if len(cc)==1:
   r=cc[0]
   if not all(math.isfinite(v) and v>0 for v in r.values()) or not r['LOW']<=min(r['OPEN'],r['CLOSE'])<=max(r['OPEN'],r['CLOSE'])<=r['HIGH']:reasons.append('cboe_bad_ohlc')
  if len(ff)==1 and (not math.isfinite(ff[0]) or ff[0]<=0):reasons.append('fred_bad_close')
  if len(cc)==len(ff)==1 and cc[0]['CLOSE']!=ff[0]:reasons.append('cross_feed_difference')
  out.append({'date':date,'day':t,'valid':not reasons,'reasons':reasons,'value':cc[0]['CLOSE'] if not reasons else None,'base_assumed_available':t+2*DAY,'cboe_rows':len(cc),'fred_rows':len(ff)})
 return out,sorted(blanks),{'cboe_all_rows':all_cboe,'fred_all_rows':all_fred}
def run():
 cb=(WEB/'q148-cboe-vix-history.csv').read_bytes();fr=(WEB/'q148-fred-vix.csv').read_bytes();assert sha(cb)==CBOE_SHA and sha(fr)==FRED_SHA
 out,blank,counts=normalize(cb.decode('utf-8-sig'),fr.decode('utf-8-sig'));data={'scope':'Current official CBOE VIX vintage checked against FRED same-source feed; only BTC external predictor; no original-vintage or options reconstruction proof','source_attribution':'Chicago Board Options Exchange, CBOE Volatility Index: VIX [VIXCLS], via official CBOE history and FRED, Federal Reserve Bank of St. Louis; retrieved 2026-10-03','urls':['https://www.cboe.com/tradable-products/vix/vix-historical-data','https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv','https://fred.stlouisfed.org/series/VIXCLS'],'raw_cboe_sha256':CBOE_SHA,'raw_fred_sha256':FRED_SHA,'start':'2019-01-01','end_exclusive':'2026-09-01','units':'index percentage points, daily close','observations':out,'fred_blank_dates':blank};b=canonical(data);OUT.mkdir(exist_ok=True);(OUT/'observations.json').write_bytes(b)
 report=dict(counts,observations=len(out),valid=sum(r['valid'] for r in out),invalid_dates=[r['date'] for r in out if not r['valid']],fred_blank_dates=blank,normalized_sha256=sha(b),scope='Normalization only, no BTC linkage, model features or performance');(OUT/'prepare-audit.json').write_bytes(canonical(report));print(json.dumps(report))
if __name__=='__main__':run()
