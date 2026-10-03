"""Derive preregistered BTC daily range/liquidity aggregates from frozen public OHLC; no PNL."""
import gzip,json,math,datetime as dt,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-liquidity-20261003';DAY=86400000;HOUR=3600000
MARKET_SHA='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4';QUALITY_SHA='30fc996715649844cb1dc224a88b60f07e6cf9e0e211722b44ec8579252190cf';MASK_SHA='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd'
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def date(t):return dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat()
def ms(s):return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def aggregate(day,rows,quality,excluded):
 expected=list(range(day,day+DAY,HOUR));bars=[rows.get(t) for t in expected];missing=[t for t,r in zip(expected,bars) if r is None];bad=[]
 for t,r in zip(expected,bars):
  if r is not None and (r[0]!=t or r[5]!=t+HOUR-1 or not all(isinstance(v,(int,float)) and math.isfinite(v) and v>0 for v in r[1:5]) or not (r[3]<=min(r[1],r[4])<=max(r[1],r[4])<=r[2])):bad.append(t)
 reasons=[]
 if missing:reasons.append('missing_hour')
 if bad:reasons.append('bad_clock_or_ohlc')
 masked=sorted(t for t in expected if t in excluded)
 if masked:reasons.append('no_trade_hour')
 if not quality:reasons.append('prior_day_quality')
 result={'day':day,'date':date(day),'end':day+DAY,'valid':not reasons,'reasons':reasons,'missing_hours':missing,'bad_hours':bad,'no_trade_hours':masked,'prior_valid':bool(quality),'pairs':23 if not reasons else 0,'cs':None,'ar':None,'rv':None,'close':None,'cs_pairs':None,'ar_pairs':None,'cs_zero_pairs':None,'ar_zero_pairs':None}
 if reasons:return result
 cs=[];ar=[]
 for x,y in zip(bars,bars[1:]):
  a=math.log(x[2]/x[3]);b=math.log(y[2]/y[3]);g=math.log(max(x[2],y[2])/min(x[3],y[3]));alpha=(math.sqrt(2)+1)*(math.sqrt(a*a+b*b)-g);cs.append(max(0.,2*math.tanh(alpha/2)))
  midx=(math.log(x[2])+math.log(x[3]))/2;midy=(math.log(y[2])+math.log(y[3]))/2;c=math.log(x[4]);ar.append(math.sqrt(max(0.,4*(c-midx)*(c-midy))))
 rv=math.fsum(math.log(r[4]/r[1])**2 for r in bars);result.update(cs=math.fsum(cs)/23,ar=math.fsum(ar)/23,rv=rv,close=bars[-1][4],cs_pairs=cs,ar_pairs=ar,cs_zero_pairs=cs.count(0.),ar_zero_pairs=ar.count(0.));return result

def run():
 p=ROOT/'data/search-1458/market.json.gz';compressed=p.read_bytes();raw=gzip.decompress(compressed);assert sha(raw)==MARKET_SHA
 allrows=json.loads(raw)['series']['BTCUSDT']['spot'];rows={r[0]:r for r in allrows};assert len(rows)==len(allrows)
 p=ROOT/'data/btc-cashflow-20261003/daily.json';b=p.read_bytes();assert sha(b)==QUALITY_SHA;q={r['day']:r['valid'] for r in json.loads(b)['series']['spot']}
 p=ROOT/'data/btc-venue-20261003/masks.json';b=p.read_bytes();assert sha(b)==MASK_SHA;excluded=set(json.loads(b)['binance_spot_no_trade'])
 days=[aggregate(t,rows,q.get(t,False),excluded) for t in range(ms('2020-01-01'),ms('2026-09-01'),DAY)];data={'scope':'BTC completed hourly OHLC range proxies; not actual spreads or point-in-time archive vintages; no forward fill or trading performance','start':ms('2020-01-01'),'end':ms('2026-09-01'),'source_market_sha256':MARKET_SHA,'prior_quality_sha256':QUALITY_SHA,'mask_sha256':MASK_SHA,'units':{'cs':'dimensionless range proxy','ar':'log-price approximation','rv':'sum of 24 squared open-close log returns'},'days':days};b=canonical(data);OUT.mkdir(exist_ok=True);(OUT/'daily.json.gz').write_bytes(gzip.compress(b,mtime=0))
 report={'days':len(days),'valid_days':sum(d['valid'] for d in days),'invalid_dates':[d['date'] for d in days if not d['valid']],'pairs':sum(d['pairs'] for d in days),'canonical_sha256':sha(b),'gzip_sha256':sha((OUT/'daily.json.gz').read_bytes()),'source_gzip_sha256':sha(compressed),'source_canonical_sha256':MARKET_SHA,'scope':'Data derivation only, no new strategy features/fits or performance'};(OUT/'prepare-audit.json').write_bytes(canonical(report));print(json.dumps(report))
if __name__=='__main__':run()
