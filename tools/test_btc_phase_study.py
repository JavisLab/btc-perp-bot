import unittest,copy,math
import numpy as np
import btc_phase_study as s
class Fixed:
 def __init__(self,score=.5):self.score=score
 def observation(self,t,risk=.2):return self.score,min(1,risk/.5),.5

def feature(t,known=True,down=False,shift=False):return [dict(source=t,known=known,phase=down,shift_phase=shift,height=630000 if known else None)]
class Tests(unittest.TestCase):
 def test_four_raw_headers_and_corruption(self):
  events=s.headers();self.assertEqual([x['height'] for x in events],[210000,420000,630000,840000]);h=s.read(s.ROOT/'data/btc-phase-20261002/halvings.json')['events'][0]['sources'][0]['header'];h=copy.deepcopy(h);h['nonce']+=1
  with self.assertRaises(AssertionError):s.validate_header(h)
 def test_calendar_clamp_leap_and_time(self):
  self.assertEqual(s.months(s.ms('2023-08-31')+12345,6),s.ms('2024-02-29')+12345);self.assertEqual(s.months(s.ms('2023-08-31')+12345,18),s.ms('2025-02-28')+12345)
 def test_half_open_bounds(self):
  events=s.headers();h=events[2];a,b=s.months(h['time'],18),s.months(h['time'],30)
  self.assertFalse(s.phase(events,a-1)['phase']);self.assertTrue(s.phase(events,a)['phase']);self.assertTrue(s.phase(events,b-1)['phase']);self.assertFalse(s.phase(events,b)['phase'])
 def test_new_event_availability_and_no_future_clock(self):
  e=s.headers();h=e[3];t=h['time']+s.DAY;self.assertEqual(s.phase(e,t-1)['height'],630000);self.assertEqual(s.phase(e,t)['height'],840000);self.assertEqual(s.phase(e,t-1),s.phase(e[:3],t-1))
 def test_seven_day_lag_boundary(self):
  e=s.headers();t=e[3]['time']+7*s.DAY;self.assertEqual(s.phase(e,t-1,7*s.DAY)['height'],630000);self.assertEqual(s.phase(e,t,7*s.DAY)['height'],840000)
 def test_no_available_event(self):
  e=s.headers();a=s.phase(e,e[0]['time']);self.assertFalse(a['known']);self.assertEqual(s.signal('PH_CONFIRM',1,a),0);self.assertEqual(s.signal('PH_CLOCK',1,a),0);self.assertEqual(s.signal('PH_PRICE',1,a),1)
 def test_direction_conflict_and_cash(self):
  t=s.ms('2022-01-01');m=Fixed(.5);f=feature(t,down=True);a=s.schedule(m,f,'PH_CONFIRM',t,t+s.DAY)[0];self.assertEqual(a['weights'],{'BS':0.,'BP':0.});m.score=-.5;a=s.schedule(m,f,'PH_CONFIRM',t,t+s.DAY)[0];self.assertEqual(a['weights'],{'BS':0.,'BP':-.2});m.score=0;self.assertEqual(s.schedule(m,f,'PH_CONFIRM',t,t+s.DAY)[0]['weights'],{'BS':0.,'BP':0.})
 def test_controls_do_not_inherit_gate(self):
  t=s.ms('2022-01-01');m=Fixed(.5);f=feature(t,down=True,shift=False)
  self.assertEqual(s.schedule(m,f,'PH_PRICE',t,t+s.DAY)[0]['weights']['BS'],.2);self.assertEqual(s.schedule(m,f,'PH_LONG',t,t+s.DAY)[0]['weights']['BS'],.2);self.assertEqual(s.schedule(m,f,'PH_CLOCK',t,t+s.DAY)[0]['weights']['BP'],-.4);self.assertEqual(s.schedule(m,f,'PH_SHIFT',t,t+s.DAY)[0]['weights']['BS'],.2)
 def test_risk10_and_missing_hold_target(self):
  t=s.ms('2022-01-01');m=Fixed(-.5);f=feature(t,down=True);self.assertEqual(s.schedule(m,f,'PH_CONFIRM',t,t+s.DAY,.1)[0]['weights']['BP'],-.1);m.observation=lambda *x:None;a=s.schedule(m,f,'PH_CONFIRM',t,t+s.DAY)[0];self.assertIsNone(a['weights']);self.assertTrue(a['detail']['phase'])
 def test_future_prices_and_completed_current_day(self):
  m=s.Market();t=s.ms('2024-01-01');a=m.observation(t);idx=m.index[t];m.close[idx:]*=100
  from btc_persistence_study import ema
  m.ema={span:ema(m.close,span) for span in (8,16,32,64,128)};self.assertEqual(m.observation(t),a);self.assertNotEqual(m.observation(t+s.DAY),a)
 def test_reordered_and_future_event_invariant(self):
  e=s.headers();t=s.ms('2022-01-01');self.assertEqual(s.phase(e,t),s.phase(list(reversed(e)),t));self.assertEqual(s.phase(e,t),s.phase(e+[{'height':1050000,'time':s.ms('2099-01-01'),'hash':'unused'}],t))
 def test_costs_funding_signs_and_delayed_first_fill(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'PH_CONFIRM',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'PH_CONFIRM',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'PH_CONFIRM',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
