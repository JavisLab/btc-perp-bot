import unittest,copy
from btc_mining_study import features,schedule,direction,DAY
class Fake:
 def observation(self,t,risk):return (.5,risk,1.)
def rows():return [dict(day=j*DAY,source=(j+2)*DAY,hashrate=100+j,hashrate_provider_cm=300-j) for j in range(180)]
class Tests(unittest.TestCase):
 def test_completed_information_delay(self):
  f=features(rows());a=schedule(Fake(),f,'HG_REC',100*DAY,101*DAY)[0];b=schedule(Fake(),f,'HG_REC',100*DAY,101*DAY,lag=9)[0];self.assertEqual(a['detail']['observed_day'],98*DAY);self.assertEqual(b['detail']['observed_day'],91*DAY);self.assertLessEqual(b['detail']['information_time'],b['source_time'])
 def test_future_hash_cannot_change_past(self):
  r=rows();a=schedule(Fake(),features(r),'HG_REC',100*DAY,101*DAY)
  for e in r[99:]:e['hashrate']*=100
  self.assertEqual(a,schedule(Fake(),features(r),'HG_REC',100*DAY,101*DAY))
 def test_provider_control_changes_only_hash(self):
  a=schedule(Fake(),features(rows()),'HG_REC',100*DAY,101*DAY)[0];b=schedule(Fake(),features(rows(),'provider_cm'),'HG_REC',100*DAY,101*DAY)[0];self.assertEqual(a['detail']['gate'],1);self.assertEqual(b['detail']['gate'],0);self.assertEqual(a['detail']['score'],b['detail']['score'])
 def test_missing_cash_not_stale_good(self):
  r=rows();del r[98];p=schedule(Fake(),features(r),'HG_REC',100*DAY,101*DAY)[0];self.assertEqual(p['weights'],{'BS':0.,'BP':0.});self.assertFalse(p['detail']['common_valid']);self.assertFalse(features(r)[99*DAY]['valid'])
 def test_disjoint_state_and_inverse(self):
  for P in (0,1/3,1):
   for G in (0,1):self.assertAlmostEqual(direction('HG_REC',P,G)+direction('HG_STRESS',P,G),P);self.assertEqual(direction('HG_INV',P,G),-direction('HG_REC',P,G))
 def test_scale_invariance_and_equality(self):
  r=rows();a=features(r)
  for e in r:e['hashrate']*=1e6
  b=features(r);self.assertEqual(a[100*DAY]['h30']>=a[100*DAY]['h60'],b[100*DAY]['h30']>=b[100*DAY]['h60'])
  for e in r:e['hashrate']=10
  self.assertEqual(schedule(Fake(),features(r),'HG_REC',100*DAY,101*DAY)[0]['detail']['gate'],1)
 def test_price_risk_missing_holds(self):
  class Missing:
   def observation(self,*args):return None
  self.assertIsNone(schedule(Missing(),features(rows()),'HG_REC',100*DAY,101*DAY)[0]['weights'])
 def test_full_sixty_calendar_days_required(self):
  f=features(rows());self.assertFalse(f[58*DAY]['valid']);self.assertTrue(f[59*DAY]['valid'])
 def test_future_price_risk_and_ema(self):
  import numpy as np
  from btc_persistence_study import Market,ema
  m=Market.__new__(Market);m.days=np.arange(250)*DAY;m.index={int(t):i for i,t in enumerate(m.days)};m.close=np.array([100+i*.2+np.sin(i) for i in range(250)]);m.ema={k:ema(m.close,k) for k in (8,16,32,64,128)};t=170*DAY;a=schedule(m,features(rows()),'HG_REC',t,t+DAY);m.close[170:]*=100;m.ema={k:ema(m.close,k) for k in (8,16,32,64,128)};self.assertEqual(a,schedule(m,features(rows()),'HG_REC',t,t+DAY))
if __name__=='__main__':unittest.main()
