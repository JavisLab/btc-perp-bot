"""Independent Decimal raw-archive liquidity aggregates; no trading imports/performance."""
import csv,gzip,hashlib,io,json,math,zipfile,datetime as dt
from decimal import Decimal,localcontext
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-liquidity-20261003';DAY=86400000;HOUR=3600000
D=Decimal
def sha(b):return hashlib.sha256(b).hexdigest()
def stamp(s):return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def audit(save=True):
 raw={};archives=0
 for p in sorted((ROOT/'data/archive-1448/spot').glob('????-??.zip'))+sorted((ROOT/'data/archive-1458/BTCUSDT/spot').glob('????-??.zip')):
  assert sha(p.read_bytes())==p.with_suffix('.CHECKSUM').read_text().split()[0];archives+=1
  with zipfile.ZipFile(p) as z:
   for s in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
    if not s[0].isdigit():continue
    t=int(s[0]);end=int(s[6]);t=t//1000 if t>10**14 else t;end=end//1000 if end>10**14 else end
    assert t not in raw;raw[t]={'ohlc':tuple(D(s[i]) for i in (1,2,3,4)),'end':end,'volume':D(s[5])}
 maskp=ROOT/'data/btc-venue-20261003/masks.json';assert sha(maskp.read_bytes())=='bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd';excluded=set(json.loads(maskp.read_text())['binance_spot_no_trade']);assert excluded=={t for t,r in raw.items() if r['volume']<=0}
 receipt=ROOT/'data/btc-cashflow-20261003/independent-audit.json';assert sha(receipt.read_bytes())=='68d4439905e4122e11bd29640450be8e222ccf5ef5f821b2a68d9032812bac37';invalid_dates=set(json.loads(receipt.read_text())['invalid_dates']['spot'])
 market_raw=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes());assert sha(market_raw)=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4';normalized={r[0]:r for r in json.loads(market_raw)['series']['BTCUSDT']['spot']}
 for t,r in normalized.items():assert tuple(D(str(r[j])) for j in (1,2,3,4))==raw[t]['ohlc'] and r[5]==raw[t]['end']
 compressed=(OUT/'daily.json.gz').read_bytes();b=gzip.decompress(compressed);assert sha(b)=='2b7c5a957845d2df07c1d71f7cefb0da2c536cdeec598478e34a3340f5703c3b';data=json.loads(b);assert [r['day'] for r in data['days']]==list(range(stamp('2020-01-01'),stamp('2026-09-01'),DAY))
 days={};checks=0;worst=0.;boundary=0;price_checks=0;normalization_differences=[]
 def near(a,b):
  nonlocal worst
  delta=abs(float(a)-float(b));worst=max(worst,delta);assert math.isclose(float(a),float(b),rel_tol=2e-9,abs_tol=2e-12),(a,b,delta)
 with localcontext() as ctx:
  ctx.prec=40;sqrt2=D(2).sqrt();den=D(3)-2*sqrt2
  for e in data['days']:
   t=e['day'];date=dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat();assert e['date']==date and e['end']==t+DAY
   times=[t+i*HOUR for i in range(24)];missing=[u for u in times if u not in raw];bad=[]
   for u in times:
    if u not in raw:continue
    a=raw[u];o,h,l,c=a['ohlc']
    if a['end']!=u+HOUR-1 or min(o,h,l,c)<=0 or not (l<=min(o,c)<=max(o,c)<=h):bad.append(u)
   masked=[u for u in times if u in excluded];prior=date not in invalid_dates;reasons=[]
   if missing:reasons.append('missing_hour')
   if bad:reasons.append('bad_clock_or_ohlc')
   if masked:reasons.append('no_trade_hour')
   if not prior:reasons.append('prior_day_quality')
   norm_missing=[u for u in times if u not in normalized];norm_bad=[]
   for u in times:
    if u not in normalized:continue
    n=normalized[u]
    if n[5]!=u+HOUR-1 or not all(math.isfinite(x) and x>0 for x in n[1:5]) or not (n[3]<=min(n[1],n[4])<=max(n[1],n[4])<=n[2]):norm_bad.append(u)
   norm_reasons=[]
   if norm_missing:norm_reasons.append('missing_hour')
   if norm_bad:norm_reasons.append('bad_clock_or_ohlc')
   if masked:norm_reasons.append('no_trade_hour')
   if not prior:norm_reasons.append('prior_day_quality')
   assert e['missing_hours']==norm_missing and e['bad_hours']==norm_bad and e['reasons']==norm_reasons
   assert e['no_trade_hours']==masked and e['prior_valid']==prior and e['valid']==(not reasons),(date,e['valid'],reasons)
   # The frozen canonical archive omits certain malformed/zero rows. Preserve the
   # normalized diagnostics separately; independently require the same day-invalid result.
   if e['missing_hours']!=missing or e['bad_hours']!=bad:
    omitted=set(e['missing_hours'])-set(missing)
    assert omitted<=set(bad)|set(masked),(date,omitted,bad,masked)
    assert set(missing)<=set(e['missing_hours']) and set(e['bad_hours'])<=set(bad)
    normalization_differences.append({'date':date,'canonical_missing':e['missing_hours'],'raw_missing':missing,'canonical_bad':e['bad_hours'],'raw_bad':bad,'both_invalid':not e['valid']})
   v={'day':t,'end':t+DAY,'valid':not reasons,'cs':None,'ar':None,'rv':None,'close':None}
   if reasons:
    assert e['pairs']==0 and all(e[n] is None for n in ('cs','ar','rv','close','cs_pairs','ar_pairs','cs_zero_pairs','ar_zero_pairs'));days[t]=v;continue
   bars=[raw[u]['ohlc'] for u in times];cs=[];ar=[]
   for x,y in zip(bars,bars[1:]):
    beta=(x[1].ln()-x[2].ln())**2+(y[1].ln()-y[2].ln())**2;gamma=(max(x[1],y[1]).ln()-min(x[2],y[2]).ln())**2;alpha=((2*beta).sqrt()-beta.sqrt())/den-(gamma/den).sqrt();ea=alpha.exp();c=max(D(0),2*(ea-1)/(ea+1));cs.append(c)
    mid1=(x[1]*x[2]).ln()/2;mid2=(y[1]*y[2]).ln()/2;z=4*(x[3].ln()-mid1)*(x[3].ln()-mid2);a=max(D(0),z).sqrt();ar.append(a)
    observed=e['cs_pairs'][len(cs)-1];near(observed,c);near(e['ar_pairs'][len(ar)-1],a);checks+=1
    if abs(alpha)>D('1e-12'):assert (observed==0)==(alpha<0)
    else:boundary+=1
   rv=sum(((c.ln()-o.ln())**2 for o,h,l,c in bars),D(0));v.update(cs=float(sum(cs)/23),ar=float(sum(ar)/23),rv=float(rv),close=float(bars[-1][3]));assert e['pairs']==23 and e['cs_zero_pairs']==e['cs_pairs'].count(0.) and e['ar_zero_pairs']==e['ar_pairs'].count(0.)
   for n in ('cs','ar','rv','close'):near(e[n],v[n])
   price_checks+=24;days[t]=v
 report={'raw_spot_archives':archives,'days':len(days),'valid_days':sum(x['valid'] for x in days.values()),'raw_hourly_ohlc_checks':price_checks,'all_normalized_ohlc_raw_matches':len(normalized),'decimal_pair_checks':checks,'near_zero_cs_sign_boundaries':boundary,'normalized_raw_invalid_diagnostics':normalization_differences,'max_absolute_numeric_error':worst,'canonical_sha256':sha(b),'gzip_sha256':sha(compressed),'prior_quality_receipt_sha256':sha(receipt.read_bytes()),'scope':'Independent raw BTC archive Decimal high/low/open/close and timestamps; 24-hour completeness, 23 within-day pairs, original algebraic CS and AR, OHLC RV; preserved historical quality receipt, no interpolation or new performance; proxies not actual quoted spreads'}
 if save:(OUT/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')))
 return days,report
if __name__=='__main__':print(json.dumps(audit()[1]))
