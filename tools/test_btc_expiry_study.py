"""Calendar/DST and completed daily-risk clocks, paired controls and actual delayed quantities/costs."""
import copy,datetime as dt,unittest
import btc_expiry_study as s
T=s.ms('2022-01-28')
class Fixed:
 def __init__(self):
  r={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(T-45*s.DAY,T+4*s.DAY,s.HOUR)};self.rowmaps={'BS':r,'BP':r};self.markmaps=self.rowmaps;self.calls=[];self.funds={'BP':{T+12*s.HOUR:[T+12*s.HOUR,8,.001,T+12*s.HOUR],T+16*s.HOUR:[T+16*s.HOUR,8,-.001,T+16*s.HOUR]}}
 def observation(self,t,risk=.2):
  self.calls.append(t);row=self.rowmaps['BS'].get(t-s.HOUR)
  if row is None:return None
  vol=.5+(row[4]-20000)/100000;return .5,min(1,risk/vol),vol
class Tests(unittest.TestCase):
 def test_frozen_calendar_and_holiday_exclusion_counts(self):
  cal=s.inputs();self.assertEqual(len(cal['events']),54);self.assertEqual(len(cal['weekly_controls']),236);self.assertEqual([e['date'] for e in cal['excluded_months']],['2024-03-29','2025-12-26']);self.assertEqual(sum(e['date']<'2026-01-01' for e in cal['events']),46)
 def test_actual_dst_boundaries_and_local_week_not_elapsed_week(self):
  d={e['date']:e for e in s.inputs()['events']};self.assertEqual(d['2022-03-25']['fixing_time'],s.ms('2022-03-25')+16*s.HOUR);self.assertEqual(d['2023-03-31']['fixing_time'],s.ms('2023-03-31')+15*s.HOUR);self.assertEqual(d['2023-03-31']['fixing_time']-d['2023-03-31']['placebo']['fixing_time'],167*s.HOUR);self.assertEqual(d['2025-10-31']['fixing_time']-d['2025-10-31']['placebo']['fixing_time'],169*s.HOUR)
 def test_last_friday_no_following_friday_in_month(self):
  for e in s.inputs()['events']:
   d=dt.date.fromisoformat(e['date']);self.assertEqual(d.weekday(),4);self.assertNotEqual((d+dt.timedelta(days=7)).month,d.month);self.assertEqual(e['base_exit']-e['base_entry'],6*s.HOUR);self.assertEqual(e['base_entry'],e['signal_start']+s.HOUR);self.assertEqual(e['base_exit'],e['signal_end']+s.HOUR)
 def test_monthly_timing_exit_returns_core(self):
  m=Fixed();p=s.schedule(m,s.inputs(),'EX_LONG',T,T+s.DAY);self.assertEqual([e['detail']['role'] for e in p],['daily','enter','exit']);self.assertEqual([e['source_time'] for e in p],[T,T+10*s.HOUR,T+16*s.HOUR]);self.assertEqual([e['weights']['BS'] for e in p],[.2,.4,.2]);self.assertEqual([e['detail']['override'] for e in p],[False,True,False])
 def test_risk_only_completed_daily_not_event_hour_or_future_prices(self):
  m=Fixed();cal=s.inputs();a=s.schedule(m,cal,'EX_LONG',T,T+s.DAY);self.assertEqual(set(m.calls),{T})
  for t,r in m.rowmaps['BS'].items():
   if t>=T:r[1:5]=[99999.]*4
  self.assertEqual(a,s.schedule(m,cal,'EX_LONG',T,T+s.DAY));m.rowmaps['BS'][T-s.HOUR][4]=30000.;b=s.schedule(m,cal,'EX_LONG',T,T+s.DAY);self.assertNotEqual(a[1]['weights'],b[1]['weights']);self.assertEqual(b[0]['detail']['risk'],b[1]['detail']['risk']);self.assertEqual(b[1]['detail']['risk'],b[2]['detail']['risk'])
 def test_pure_event_inverse_and_rebalancing_control(self):
  m=Fixed();cal=s.inputs();only=s.schedule(m,cal,'EX_ONLY',T,T+s.DAY);inv=s.schedule(m,cal,'EX_INV',T,T+s.DAY);clock=s.schedule(m,cal,'EX_CLOCK',T,T+s.DAY);trend=s.schedule(m,cal,'EX_TREND',T,T+s.DAY);self.assertEqual([e['weights']['BS'] for e in only],[0.,.4,0.]);self.assertEqual(inv[1]['weights'],{'BS':0.,'BP':-.4});self.assertEqual(len(trend),1);self.assertEqual([e['weights']['BS'] for e in clock],[.2,.2,.2]);self.assertTrue(all(not e['detail']['override'] for e in clock))
 def test_placebo_and_weekly_are_fixed_not_performance_selected(self):
  cal=s.inputs();self.assertEqual(len(s.events(cal,'EX_PLACEBO')),54);self.assertEqual(len(s.events(cal,'EX_WEEKLY')),236);self.assertEqual(s.events(cal,'EX_TREND'),[])
  for e,p in zip(cal['events'],s.events(cal,'EX_PLACEBO')):self.assertEqual((dt.date.fromisoformat(e['date'])-dt.date.fromisoformat(p['date'])).days,7)
 def test_period_boundaries_never_add_outside_signals(self):
  m=Fixed();p=s.schedule(m,s.inputs(),'EX_LONG',T,T+10*s.HOUR);self.assertEqual(len(p),1);p=s.schedule(m,s.inputs(),'EX_LONG',T,T+16*s.HOUR);self.assertEqual(len(p),2);self.assertEqual(p[-1]['detail']['role'],'enter')
 def test_missing_risk_does_not_extend_event_only_position(self):
  m=Fixed();m.observation=lambda *a:None;cal=s.inputs();p=s.schedule(m,cal,'EX_ONLY',T,T+s.DAY);self.assertEqual(p[0]['weights'],{'BS':0.,'BP':0.});self.assertIsNone(p[1]['weights']);self.assertEqual(p[2]['weights'],{'BS':0.,'BP':0.});q=s.schedule(m,cal,'EX_LONG',T,T+s.DAY);self.assertTrue(all(e['weights'] is None for e in q))
 def test_risk10_not_leverage_search_and_no_two_legs(self):
  m=Fixed();cal=s.inputs()
  for n in s.IDS:
   a=s.schedule(m,cal,n,T,T+s.DAY);b=s.schedule(m,cal,n,T,T+s.DAY,.1)
   for x,y in zip(a,b):
    self.assertLessEqual(sum(abs(w) for w in x['weights'].values()),1);self.assertFalse(x['weights']['BS'] and x['weights']['BP']);self.assertAlmostEqual(y['weights']['BS'],x['weights']['BS']/2);self.assertAlmostEqual(y['weights']['BP'],x['weights']['BP']/2)
 def test_actual_entry_exit_shifted_together_and_flat_price_fee_loss(self):
  m=Fixed();cal=s.inputs();end=T+3*s.DAY;p=s.schedule(m,cal,'EX_ONLY',T,end)
  for delay in (0,1,24):
   a=s.ledger.simulate(m,'EX_ONLY',T,end,p,delay=delay);fills=[e for e in a['events'] if e['kind']=='fill'];self.assertEqual(len(fills),2);self.assertEqual([e['time'] for e in fills],[T+(11+delay)*s.HOUR,T+(17+delay)*s.HOUR]);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']);self.assertEqual(a['metrics']['round_trips'],1)
  base=s.ledger.simulate(m,'EX_ONLY',T,end,p);double=s.ledger.simulate(m,'EX_ONLY',T,end,p,multiplier=2);self.assertGreater(double['metrics']['fees']+double['metrics']['impact'],base['metrics']['fees']+base['metrics']['impact'])
 def test_inverse_funding_sign_and_cost_quantity_accounting(self):
  m=Fixed();m.observation=lambda *a:(0.,.4,.5);p=s.schedule(m,s.inputs(),'EX_INV',T,T+s.DAY);a=s.ledger.simulate(m,'EX_INV',T,T+s.DAY,p);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertGreater(fund[0],0);self.assertLess(fund[1],0);self.assertAlmostEqual(a['metrics']['net_pnl'],a['metrics']['funding']-a['metrics']['fees']-a['metrics']['impact']);self.assertLess(a['metrics']['net_pnl'],0)
if __name__=='__main__':unittest.main()
