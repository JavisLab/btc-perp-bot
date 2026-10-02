import unittest,math,copy
from btc_shock_study import features,schedule,event_signal,BLOCK,HOUR,DAY,Market

def fake():
 m=Market.__new__(Market);m.conflicts=set();m.hourly={t:[t,100,101,99,100*math.exp(.001*math.sin(t/HOUR/7)+.00002*(t/HOUR)),1.,t+HOUR-1,100,1,.5,50] for t in range(0,1000*HOUR,HOUR)};return m
class Tests(unittest.TestCase):
 def test_exact_tail_and_partition(self):
  for r in (-4.,-3.,-1.,0.,1.,3.,4.):
   a=event_signal(r,1.,'SH_REV');b=event_signal(r,1.,'SH_SMALL');self.assertEqual(a+b,event_signal(r,1.,'SH_ALL'));self.assertEqual(a,-event_signal(r,1.,'SH_MOM'))
  self.assertEqual(event_signal(3.,1.,'SH_REV'),-1);self.assertEqual(event_signal(-3.,1.,'SH_REV'),1)
 def test_current_shock_excluded_sigma(self):
  m=fake();t=850*HOUR;a={e['source']:e for e in features(m)}[t];m.hourly[t-HOUR][4]*=1.2;b={e['source']:e for e in features(m)}[t];self.assertEqual(a['sigma'],b['sigma']);self.assertGreater(abs(b['r']),abs(a['r']));self.assertEqual(a['annual_vol'],b['annual_vol'])
 def test_future_prices_do_not_change_past(self):
  m=fake();t=850*HOUR;a=schedule(features(m),'SH_REV',t,t+BLOCK)
  for ts,r in m.hourly.items():
   if ts>=t:r[4]*=5
  self.assertEqual(a,schedule(features(m),'SH_REV',t,t+BLOCK))
 def test_two_hour_boundary_and_previous_daily_risk(self):
  m=fake();t=850*HOUR;e={e['source']:e for e in features(m)}[t];self.assertEqual(e['current_start'],t-2*HOUR);self.assertEqual(e['training_last'],t-2*HOUR);self.assertEqual(e['training_first'],t-720*HOUR);self.assertEqual(e['risk_end'],840*HOUR);self.assertAlmostEqual(e['r'],math.log(m.hourly[t-HOUR][4]/m.hourly[t-3*HOUR][4]))
 def test_missing_expires_to_cash(self):
  m=fake();t=850*HOUR;m.hourly[t-HOUR][5]=0;e=schedule(features(m),'SH_REV',t,t+BLOCK)[0];self.assertEqual(e['weight'],0);self.assertFalse(e['detail']['common_valid'])
 def test_warmup_and_constant_prices_cash(self):
  m=fake();a=schedule(features(m),'SH_REV',100*HOUR,102*HOUR)[0];self.assertEqual(a['weight'],0)
  for r in m.hourly.values():r[4]=100
  self.assertEqual(schedule(features(m),'SH_REV',850*HOUR,852*HOUR)[0]['weight'],0)
if __name__=='__main__':unittest.main()
