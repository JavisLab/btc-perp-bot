import unittest,math,copy
from types import SimpleNamespace
import numpy as np
import btc_bubble_study as s
class Fake:
 def __init__(self):
  self.rowmaps={'BS':{}};self.t=200*s.DAY
  for h in range(0,230*24):
   p=100*math.exp(.001*h+.005*math.sin(h*.3));t=h*s.HOUR;self.rowmaps['BS'][t]=[t,p,p,p,p,t+s.HOUR-1]
 def observation(self,t,risk=.2):return .5,risk*2,.5
 def daily(self,t,p):self.rowmaps['BS'][t-s.HOUR][4]=p

def flags(t,sign=1,field='bubble'):
 return [{'source':t,'valid':True,'bubble':sign if field=='bubble' else 0,'quadratic':sign if field=='quadratic' else 0}]
class Tests(unittest.TestCase):
 def test_positive_negative_fit_and_all_grid(self):
  idx=s.GRID.index((.1,.5,12.));curve=s.BASES[idx]@np.array([.1,-.4,.002,-.003]);p=np.exp(curve)*100;a=s.fit_curve(p);b=s.fit_curve(10000/p)
  self.assertEqual(a['best_index'],idx);self.assertEqual(a['bubble'],1);self.assertEqual(b['bubble'],-1);self.assertEqual(len(a['sse_all']),120);self.assertTrue(all(a['checks'].values()))
 def test_linear_is_not_bubble_and_quadratic_control(self):
  a=s.fit_curve(np.exp(.3*s.U)*100);self.assertEqual(a['bubble'],0);b=s.fit_curve(100*np.exp(.01*s.U+.2*s.U*s.U));self.assertEqual(b['quadratic'],1);self.assertEqual(b['bubble'],0)
 def test_raw_completed_window_and_future_perturb(self):
  m=Fake();t=m.t;a=s.features(m,t,t+s.DAY)[0]
  for k,r in m.rowmaps['BS'].items():
   if k>=t:r[4]*=100
  self.assertEqual(a,s.features(m,t,t+s.DAY)[0]);m.rowmaps['BS'][t-s.HOUR][5]=t;self.assertFalse(s.features(m,t,t+s.DAY)[0]['valid'])
 def test_missing_hour_and_nonpositive_price(self):
  m=Fake();t=m.t;del m.rowmaps['BS'][t-9*s.HOUR];self.assertFalse(s.features(m,t,t+s.DAY)[0]['valid']);m=Fake();m.rowmaps['BS'][t-200*s.HOUR][4]=0;self.assertFalse(s.features(m,t,t+s.DAY)[0]['valid'])
 def test_only_prior_day_and_seven_day_inclusive(self):
  m=Fake();t=m.t;m.daily(t,50);m.daily(t-s.DAY,100)
  self.assertEqual(s.states(m,flags(t),'BB_SWITCH',t,t+s.DAY)[t]['direction'],0)
  self.assertEqual(s.states(m,flags(t-s.DAY),'BB_SWITCH',t,t+s.DAY)[t]['direction'],-1)
  self.assertEqual(s.states(m,flags(t-7*s.DAY),'BB_SWITCH',t,t+s.DAY)[t]['direction'],-1)
  self.assertEqual(s.states(m,flags(t-8*s.DAY),'BB_SWITCH',t,t+s.DAY)[t]['direction'],0)
 def test_latest_flag_precedes_confirmation_and_no_future(self):
  m=Fake();t=m.t;m.daily(t,50);m.daily(t-s.DAY,100);f=flags(t-2*s.DAY)+flags(t-s.DAY,-1)+flags(t+s.DAY,1)
  self.assertEqual(s.states(m,f,'BB_SWITCH',t,t+s.DAY)[t]['direction'],0)
 def test_expiry_no_extension_or_reversal(self):
  m=Fake();t=m.t;m.daily(t-s.DAY,100);m.daily(t,50);f=flags(t-s.DAY)+flags(t+s.DAY,-1)
  a=s.states(m,f,'BB_SWITCH',t,t+9*s.DAY)
  for k in range(7):self.assertEqual(a[t+k*s.DAY]['direction'],-1);self.assertEqual(a[t+k*s.DAY]['expiry'],t+7*s.DAY)
  self.assertEqual(a[t+7*s.DAY]['direction'],1);self.assertTrue(a[t+7*s.DAY]['triggered'])
 def test_cash_quad_trend_and_risk(self):
  m=Fake();t=m.t;m.daily(t,50);m.daily(t-s.DAY,100);f=flags(t-s.DAY)
  a=s.schedule(m,f,'BB_SWITCH',t,t+s.DAY)[0];self.assertEqual(a['weights'],{'BS':0.,'BP':-.4});self.assertEqual(s.schedule(m,f,'BB_CASH',t,t+s.DAY)[0]['weights'],{'BS':0.,'BP':0.});self.assertEqual(s.schedule(m,f,'BB_TREND',t,t+s.DAY)[0]['weights'],{'BS':.2,'BP':0.});self.assertEqual(s.schedule(m,f,'BB_QUAD',t,t+s.DAY)[0]['weights'],{'BS':.2,'BP':0.});self.assertEqual(s.schedule(m,f,'BB_SWITCH',t,t+s.DAY,.1)[0]['weights']['BP'],-.2)
 def test_state_advances_when_risk_missing(self):
  m=Fake();t=m.t;m.daily(t,50);m.daily(t-s.DAY,100);m.observation=lambda t,risk:None;a=s.schedule(m,flags(t-s.DAY),'BB_SWITCH',t,t+9*s.DAY);self.assertIsNone(a[0]['weights']);self.assertEqual(a[0]['detail']['direction'],-1);self.assertEqual(a[7]['detail']['direction'],0)
 def test_independent_grid_kernel(self):
  from verify_btc_bubble_study import independently_fit
  idx=s.GRID.index((.1,.5,12.));prices=100*np.exp(s.BASES[idx]@np.array([.1,-.4,.002,-.003]));t=672*s.HOUR;raw={('BS',i*s.HOUR):(float(p),float(p)) for i,p in enumerate(prices)};clock={('BS',i*s.HOUR):(i+1)*s.HOUR-1 for i in range(672)};a=s.fit_curve(prices);b=independently_fit(raw,clock,t);self.assertEqual(a['best_index'],b['best_index']);self.assertEqual(a['bubble'],b['bubble']);self.assertLess(max(abs(x-y) for x,y in zip(a['beta'],b['beta'])),1e-8)
 def test_flat_price_costs_and_actual_funding_signs(self):
  m=Fake();start=200*s.DAY;end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'BB_SWITCH',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
if __name__=='__main__':unittest.main()
