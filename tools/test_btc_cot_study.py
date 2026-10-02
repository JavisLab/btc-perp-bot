import unittest,copy,numpy as np
from btc_cot_study import features,schedule,risk_observation,DAY,HOUR,ms
from prepare_btc_cot_data import release_overrides
class Fake:
 def __init__(self):
  start=ms('2022-01-01');self.index={start+i*DAY:i for i in range(120)};self.close=np.array([100+i*.2+np.sin(i) for i in range(120)]);self.rowmaps={'BS':{}}
  for i in range(120):
   t=start+(i+1)*DAY;c=float(self.close[i]);self.rowmaps['BS'][t-HOUR]=[t-HOUR,c,c,c,c,t-1]
def rows():
 a=ms('2022-02-01');b=a+7*DAY
 return [dict(report_date='2022-02-01',report_time=a,source=a+10*DAY,expiry=a+21*DAY,long=100,short=200,oi=1000),dict(report_date='2022-02-08',report_time=b,source=b+10*DAY,expiry=b+21*DAY,long=150,short=220,oi=1200)]
class Tests(unittest.TestCase):
 def test_sign_and_units(self):
  f=features(Fake(),rows());self.assertFalse(f[0]['valid']);self.assertEqual(f[1]['short_signal'],-1);self.assertEqual(f[1]['net_signal'],1);self.assertAlmostEqual(f[1]['short_change_scaled'],-.02);self.assertAlmostEqual(f[1]['net_change_scaled'],.03)
 def test_not_known_at_report_date(self):
  m=Fake();f=features(m,rows());e=f[1];p=schedule(m,f,'COT_SHORT',e['report_time'],e['source']);self.assertTrue(all(x['detail']['report_date']!=e['report_date'] for x in p));self.assertEqual(schedule(m,f,'COT_SHORT',e['source'],e['source']+DAY)[0]['detail']['signal'],-1)
 def test_future_position_cannot_change_past(self):
  m=Fake();rr=rows();f=features(m,rr);t=rr[1]['source'];before=schedule(m,f,'COT_SHORT',t-5*DAY,t);rr[1]['short']=0;after=schedule(m,features(m,rr),'COT_SHORT',t-5*DAY,t);self.assertEqual(before,after)
 def test_expiry_and_stale_arrival(self):
  m=Fake();rr=rows();f=features(m,rr);t=f[1]['expiry'];p=schedule(m,f,'COT_SHORT',t-DAY,t+DAY);self.assertEqual(p[0]['detail']['signal'],-1);self.assertEqual(p[1]['detail']['signal'],0);rr[1]['source']=t+2*DAY;f=features(m,rr);self.assertEqual(schedule(m,f,'COT_SHORT',t+2*DAY,t+3*DAY)[0]['detail']['signal'],0)
 def test_zero_inverse_and_common_missing(self):
  m=Fake();rr=rows();rr[1]['short']=rr[0]['short'];f=features(m,rr);t=f[1]['source'];self.assertEqual(schedule(m,f,'COT_SHORT',t,t+DAY)[0]['detail']['signal'],0);rr=rows();f=features(m,rr);self.assertEqual(schedule(m,f,'COT_INV',t,t+DAY)[0]['detail']['signal'],1);del m.rowmaps['BS'][rr[1]['report_time']+DAY-HOUR];f=features(m,rr)
  for n in ('COT_SHORT','COT_NET','COT_PRICE','COT_INV'):self.assertEqual(schedule(m,f,n,t,t+DAY)[0]['detail']['signal'],0)
 def test_risk_only_completed_prices(self):
  m=Fake();t=ms('2022-02-18');r=risk_observation(m,t,.2);m.close[m.index[t]:]*=100;self.assertEqual(risk_observation(m,t,.2),r)
 def test_official_outage_parsing(self):
  d=release_overrides();self.assertEqual(len(d),21);self.assertEqual(d['2023-01-31'],'2023-02-24');self.assertEqual(d['2023-03-07'],'2023-03-16');self.assertEqual(d['2025-11-10'],'2025-12-10');self.assertEqual(d['2025-01-07'],'2025-01-13')
if __name__=='__main__':unittest.main()
