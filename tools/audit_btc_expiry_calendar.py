"""Independent ordinary-Friday/UK-bank-holiday and manual British summer time calendar proof."""
import datetime as dt,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HOUR=3600000;DAY=24*HOUR
CAL_SHA='6aa1f877a7ee6d0a8e59f3e0eed4f251dcfb85231427a7836f3f35498261b8b9'
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def fixing(date):
 # UK clock since 1996: summer offset between last Sunday in March and October.
 spring=dt.date(date.year,3,31);spring-=dt.timedelta(days=(spring.weekday()+1)%7);autumn=dt.date(date.year,10,31);autumn-=dt.timedelta(days=(autumn.weekday()+1)%7);hour=15 if spring<=date<autumn else 16
 return int(dt.datetime.combine(date,dt.time(hour),dt.timezone.utc).timestamp()*1000)
def run():
 p=ROOT/'data/btc-web-20261003/q76-uk-bankholidays.json';blob=p.read_bytes();assert sha(blob)=='538b3482c28b85ecd2db606a0d5ae6ad17248900b6498700ce0a48d26a3ecde6';holiday={e['date']:e['title'] for e in json.loads(blob)['england-and-wales']['events']};p=ROOT/'data/btc-expiry-20261003/calendar.json';assert sha(p.read_bytes())==CAL_SHA;actual=json.loads(p.read_text());monthly=[];weekly=[];missing=[];date=dt.date(2022,1,1)
 def record(d,kind,origin=None):
  t=fixing(d);return {'date':d.isoformat(),'local_time':'16:00 Europe/London','fixing_time':t,'signal_start':t-6*HOUR,'signal_end':t,'base_entry':t-5*HOUR,'base_exit':t+HOUR,'kind':kind,'origin':origin}
 while date<dt.date(2026,9,1):
  if date.weekday()==4:
   last=(date+dt.timedelta(days=7)).month!=date.month
   if date.isoformat() in holiday:
    if last:missing.append({'date':date.isoformat(),'reason':holiday[date.isoformat()]})
   else:
    weekly.append(record(date,'weekly_friday'))
    if last:
     assert (date.month,date.day) not in {(1,1),(6,19),(7,4),(11,11),(12,25)}
     e=record(date,'ordinary_monthly');e['placebo']=record(date-dt.timedelta(days=7),'prior_week',date.isoformat());monthly.append(e)
  date+=dt.timedelta(days=1)
 assert actual['events']==monthly and actual['weekly_controls']==weekly and actual['excluded_months']==missing;assert actual['uk_holiday_input_sha256']==sha(blob);assert len(monthly)==54 and len(weekly)==236;switches=[{'date':e['date'],'elapsed_hours':(e['fixing_time']-e['placebo']['fixing_time'])//HOUR} for e in monthly if e['fixing_time']-e['placebo']['fixing_time']!=7*DAY];report={'monthly':len(monthly),'main_months':sum(e['date']<'2026-01-01' for e in monthly),'recent_months':sum(e['date']>='2026-01-01' for e in monthly),'weekly':len(weekly),'excluded_months':missing,'calendar_sha256':CAL_SHA,'independent_dst':'manual last Sunday March/October; no ZoneInfo or builder import','local_week_not_utc_168h_cases':switches,'scope':'ordinary non-holiday last-Friday clock; not recovered actual CME calendar'};(ROOT/'data/btc-expiry-20261003/independent-audit.json').write_bytes(canonical(report));print(json.dumps(report));return actual,report
if __name__=='__main__':run()
