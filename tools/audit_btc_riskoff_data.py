"""Separate Decimal source/calendar audit; no study or normalization imports."""
import csv,datetime as dt,hashlib,io,json
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DAY=86400000

def audit(save=True):
 w=ROOT/'data/btc-web-20261003';p=ROOT/'data/btc-riskoff-20261003';raw_c=(w/'q148-cboe-vix-history.csv').read_bytes();raw_f=(w/'q148-fred-vix.csv').read_bytes()
 assert hashlib.sha256(raw_c).hexdigest()=='6edc3e3928c4b164b9e4ed1ec874e0ed53c7d52997557adebb7d6b7451db565a';assert hashlib.sha256(raw_f).hexdigest()=='84f279d69e35eacf918b939875bf0ed7e0ad78d176cd289b24f2ebf364221510'
 cboe={};fred={};holidays=[];raw_count=0;old_bad=[]
 for r in csv.DictReader(io.StringIO(raw_c.decode('utf-8-sig'))):
  date=dt.datetime.strptime(r['DATE'],'%m/%d/%Y').replace(tzinfo=dt.timezone.utc);t=int(date.timestamp())*1000;v={k:Decimal(r[k]) for k in ('OPEN','HIGH','LOW','CLOSE')};raw_count+=1
  good=all(z.is_finite() and z>0 for z in v.values()) and v['LOW']<=v['OPEN']<=v['HIGH'] and v['LOW']<=v['CLOSE']<=v['HIGH']
  if not good:old_bad.append(date.date().isoformat())
  if dt.datetime(2019,1,1,tzinfo=dt.timezone.utc)<=date<dt.datetime(2026,9,1,tzinfo=dt.timezone.utc):
   assert t not in cboe and good and date.weekday()<5;cboe[t]=v['CLOSE']
 for r in csv.DictReader(io.StringIO(raw_f.decode('utf-8-sig'))):
  if not '2019-01-01'<=r['observation_date']<'2026-09-01':continue
  if not r['VIXCLS'] or r['VIXCLS']=='.':holidays.append(r['observation_date']);continue
  date=dt.datetime.fromisoformat(r['observation_date']).replace(tzinfo=dt.timezone.utc);t=int(date.timestamp())*1000;assert t not in fred;fred[t]=Decimal(r['VIXCLS']);assert fred[t].is_finite() and fred[t]>0
 assert cboe==fred
 b=(p/'observations.json').read_bytes();obj=json.loads(b);rows=obj['observations'];assert [r['day'] for r in rows]==sorted(cboe)
 for r in rows:
  t=r['day'];assert r['valid'] and r['reasons']==[] and r['cboe_rows']==r['fred_rows']==1 and r['base_assumed_available']==t+2*DAY and r['date']==dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat() and Decimal(str(r['value']))==cboe[t]
 assert sorted(holidays)==obj['fred_blank_dates'];gaps=[(b-a)//DAY for a,b in zip(sorted(cboe),sorted(cboe)[1:])]
 proof={'raw_cboe_rows':raw_count,'cboe_selected':len(cboe),'fred_selected':len(fred),'decimal_matches':len(rows),'fred_blank_dates':sorted(holidays),'reference_max_calendar_gap':max(gaps),'unused_raw_ohlc_bad_dates':old_bad,'normalized_sha256':hashlib.sha256(b).hexdigest(),'first_publication_clock_verified':False,'scope':'Independent Decimal parsing and calendar agreement of same-source feeds; neither historical first releases nor independent SPX options reconstruction'}
 if save:(p/'independent-audit.json').write_text(json.dumps(proof,sort_keys=True,separators=(',',':')))
 return {r['day']:dict(r,value=float(cboe[r['day']])) for r in rows},proof
if __name__=='__main__':print(json.dumps(audit()[1]))
