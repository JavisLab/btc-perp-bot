"""Preregistered ordinary last-Friday clock; NOT a recovered actual CME expiry calendar."""
import calendar,datetime as dt,hashlib,json
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];UTC=dt.timezone.utc;LONDON=ZoneInfo('Europe/London')
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def make():
 p=ROOT/'data/btc-web-20261003/q76-uk-bankholidays.json';blob=p.read_bytes();assert sha(blob)=='538b3482c28b85ecd2db606a0d5ae6ad17248900b6498700ce0a48d26a3ecde6';raw=json.loads(blob);holidays={e['date']:e['title'] for e in raw['england-and-wales']['events']};events=[];skipped=[];weekly=[]
 def stamp(d):return int(dt.datetime.combine(d,dt.time(16),LONDON).timestamp()*1000)
 def row(d,kind,origin=None):return {'date':d.isoformat(),'local_time':'16:00 Europe/London','fixing_time':stamp(d),'signal_start':stamp(d)-6*3600000,'signal_end':stamp(d),'base_entry':stamp(d)-5*3600000,'base_exit':stamp(d)+3600000,'kind':kind,'origin':origin}
 for year in range(2022,2027):
  for month in range(1,13):
   if (year,month)>(2026,8):continue
   d=dt.date(year,month,calendar.monthrange(year,month)[1]);d-=dt.timedelta(days=(d.weekday()-4)%7)
   if d.isoformat() in holidays:skipped.append({'date':d.isoformat(),'reason':holidays[d.isoformat()]});continue
   assert (d.month,d.day) not in ((1,1),(6,19),(7,4),(11,11),(12,25)),'US fixed bank holiday';e=row(d,'ordinary_monthly');e['placebo']=row(d-dt.timedelta(days=7),'prior_week',d.isoformat());events.append(e)
 d=dt.date(2022,1,1)
 while d<dt.date(2026,9,1):
  if d.weekday()==4 and d.isoformat() not in holidays:weekly.append(row(d,'weekly_friday'))
  d+=dt.timedelta(days=1)
 assert len(events)==54 and [e['date'] for e in skipped]==['2024-03-29','2025-12-26'];assert sum(e['date']<'2026-01-01' for e in events)==46
 result={'scope':'ordinary non-UK-bank-holiday last Friday at 16 London; not exact historic CME expiry calendar; no US fixed bank holiday intersection','uk_holiday_input_sha256':sha(blob),'events':events,'excluded_months':skipped,'weekly_controls':weekly};out=ROOT/'data/btc-expiry-20261003';out.mkdir(exist_ok=True);(out/'calendar.json').write_bytes(canonical(result));meta={'file':'calendar.json','sha256':sha((out/'calendar.json').read_bytes()),'monthly':len(events),'main':46,'recent':8,'excluded':skipped,'weekly':len(weekly),'uk_raw_url':'https://www.gov.uk/bank-holidays.json','uk_raw_sha256':sha(blob)};(out/'data-audit.json').write_bytes(canonical(meta));print(json.dumps(meta))
if __name__=='__main__':make()
