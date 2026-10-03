"""Causal aggregate windows, joint-growth quadrants, unrestricted component controls and account boundaries."""
import copy,math,unittest
import numpy as np
import btc_congestion_study as s
T=s.ms('2024-01-01')
class Fixed:
 def __init__(self):self.rowmaps={'BS':{t:[t,100.,100.,100.,100.,t+s.HOUR-1] for t in range(T-60*s.DAY,T+15*s.DAY,s.HOUR)}}
 def observation(self,t,risk=.2):return .5,min(1,risk/.5),.5

def fixtures():
 m=Fixed();c={k:{t:v for t in range(T-60*s.DAY,T+20*s.DAY,s.DAY)} for k,v in [('mempool',1e6),('fee_sats',1000.),('transactions',10.)]}
 for t in range(T-8*s.DAY,T-s.DAY,s.DAY):c['mempool'][t]=2e6;c['fee_sats'][t]=6000.;c['transactions'][t]=30.
 return m,c

def model(mu=.1,delta=.02):return {n:{'mu':mu-delta if n=='BQ_ADD' else mu,'se':.001,'constraint_active':False} for n in s.MODELS}
def forecast(t,models):return {'source':t,'models':models,'training_n':90,'training_label_end':t-s.WEEK}
class Tests(unittest.TestCase):
 def test_completed_daily_buffer_disjoint_windows_and_native_fee_per_tx(self):
  m,c=fixtures();f=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];self.assertTrue(f['valid']);self.assertEqual(f['last_observation_day'],T-2*s.DAY);self.assertEqual(f['last_assumed_available'],T);self.assertEqual((f['window_dates'][0],f['window_dates'][-1]),('2023-11-26','2023-12-30'));self.assertEqual((f['fee_per_tx7'],f['fee_per_tx28']),(200,100));self.assertAlmostEqual(f['q'],math.log(3)-math.log(2));self.assertAlmostEqual(f['f'],math.log(2));self.assertAlmostEqual(f['z'],math.log(3));self.assertAlmostEqual(f['x'],(math.log(3)-math.log(2))*math.log(2))
 def test_joint_growth_not_both_shrinking_or_single_pressure(self):
  self.assertEqual(s.interaction(2,3),6)
  for q,f in ((-2,-3),(-2,3),(2,-3),(0,3),(2,0)):self.assertEqual(s.interaction(q,f),0)
 def test_native_fee_unit_scale_invariance(self):
  m,c=fixtures();a=s.features(m,c,set(),start=T,end=T+s.WEEK)[0]
  for t in c['fee_sats']:c['fee_sats'][t]*=1e8
  b=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];self.assertEqual((a['q'],a['f'],a['z'],a['x']),(b['q'],b['f'],b['z'],b['x']));self.assertEqual(b['fee_per_tx7'],a['fee_per_tx7']*1e8)
 def test_seven_day_delay_all_aggregates_not_current_price(self):
  m,c=fixtures();a=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];b=s.features(m,c,set(),7,start=T,end=T+s.WEEK)[0];self.assertEqual(b['last_observation_day'],T-9*s.DAY);self.assertEqual(b['last_assumed_available'],T);self.assertEqual(b['last_base_assumed_available'],T-7*s.DAY);self.assertEqual((b['q'],b['f'],b['z'],b['x']),(0,0,0,0));self.assertGreater(a['x'],0);self.assertEqual((a['r7'],a['r28']),(b['r7'],b['r28']))
 def test_future_aggregates_and_target_prices_cannot_change_features(self):
  m,c=fixtures();a=s.features(m,c,set(),start=T,end=T+s.WEEK)
  for k in c:
   for t in c[k]:
    if t>T-2*s.DAY:c[k][t]=1e12
  for t,r in m.rowmaps['BS'].items():
   if t>=T:r[1:5]=[99999.]*4
  self.assertEqual(a,s.features(m,c,set(),start=T,end=T+s.WEEK))
 def test_missing_any_component_and_zero_count_invalidate_common_week(self):
  for k in ckeys():
   m,c=fixtures();del c[k][T-4*s.DAY];f=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];self.assertFalse(f['valid']);self.assertEqual(f[k]['missing_dates'],[s.date(T-4*s.DAY)])
  m,c=fixtures();c['transactions'][T-4*s.DAY]=0;self.assertFalse(s.features(m,c,set(),start=T,end=T+s.WEEK)[0]['valid'])
 def test_zero_queue_and_single_zero_fee_allowed_but_zero_fee_window_not(self):
  m,c=fixtures();c['mempool'][T-4*s.DAY]=0;c['fee_sats'][T-4*s.DAY]=0;self.assertTrue(s.features(m,c,set(),start=T,end=T+s.WEEK)[0]['valid'])
  for t in range(T-8*s.DAY,T-s.DAY,s.DAY):c['fee_sats'][t]=0
  f=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];self.assertIsNone(f['f']);self.assertFalse(f['valid'])
 def test_completed_price_clock_and_no_trade_mask(self):
  m,c=fixtures();self.assertIsNone(s.close(m,T,{T-s.HOUR}));m.rowmaps['BS'][T-s.HOUR][-1]=T;self.assertIsNone(s.close(m,T));self.assertFalse(s.features(m,c,set(),start=T,end=T+s.WEEK)[0]['valid'])
 def test_both_interaction_coefficient_signs_are_free_and_rank_rejected(self):
  rng=np.random.default_rng(7);a=rng.normal(size=(90,5));a=np.column_stack([a,[s.interaction(q,f) for q,f in a[:,3:5]]]);dates=np.arange(90)*s.WEEK
  for gamma in (-.9,.9):
   y=a@np.array([.1,.2,-.3,.4,.5,gamma]);fit=s.fit(a,y,dates,a[0]);self.assertFalse(fit['constraint_active']);self.assertAlmostEqual(fit['beta'][-1],gamma);self.assertEqual(fit['free_columns'],list(range(7)))
  self.assertIsNone(s.fit(np.ones((90,6)),y,dates,a[0])['mu'])
 def test_calendar_week_hac_missing_weeks_not_compressed(self):
  weeks=np.array([0,1,3,4,8,10,11,15,18,19])*s.WEEK;Z=np.column_stack([np.ones(10),np.arange(10)]);res=np.array([.2,-.3,.5,.7,-.1,.8,-.2,.4,-.6,.1]);meat=np.zeros((2,2))
  for i in range(10):
   for j in range(10):
    lag=abs(weeks[i]-weeks[j])/s.WEEK
    if lag<=1:meat+=(1-lag/2)*np.outer(Z[i]*res[i],Z[j]*res[j])
  bread=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,weeks),10/8*bread@meat@bread,atol=1e-12);self.assertGreater(np.max(np.abs(s.hac(Z,res,weeks)-s.hac(Z,res,np.arange(10)*s.WEEK))),1e-5)
 def test_104_week_minimum52_purge_and_six_models_same_rows(self):
  rng=np.random.default_rng(40);z=rng.normal(size=(150,5));z=np.column_stack([z,[s.interaction(q,f) for q,f in z[:,3:5]]]);rows=[dict(source=T+i*s.WEEK,valid=True,**dict(zip(('r7','r28','z','q','f','x'),z[i]))) for i in range(150)];yy={r['source']:{'value':float(z[i]@np.array([.1,.2,-.3,.4,.5,-.9])),'end':r['source']+s.WEEK} for i,r in enumerate(rows)};p=s.forecast_one(rows,yy,140);self.assertEqual(p['training_n'],104);self.assertEqual((p['training_weeks'][0],p['training_weeks'][-1]),(rows[35]['source'],rows[138]['source']));self.assertEqual(p['training_label_end'],rows[139]['source']);changed=copy.deepcopy(yy)
  for r in rows[139:]:changed[r['source']]['value']=1e6
  self.assertEqual(p,s.forecast_one(rows,changed,140));self.assertIsNotNone(s.forecast_one(rows,yy,53)['models']['BQ_INFO']['mu']);self.assertIsNone(s.forecast_one(rows,yy,52)['models']['BQ_INFO']['mu']);rows[138]['valid']=False;p=s.forecast_one(rows,yy,140);self.assertEqual(len(p['models']),6);self.assertTrue(all(v['training_n']==103 and not v['constraint_active'] for v in p['models'].values()));self.assertLess(p['models']['BQ_INFO']['beta'][-1],0)
 def test_increment_inverse_cost_gate_and_component_controls(self):
  self.assertEqual(s.decision('BQ_INFO',model(),.5)[:2],(1.,True));self.assertEqual(s.decision('BQ_INV',model(),.5)[:2],(-1.,True));self.assertEqual(s.decision('BQ_TREND',model(),.5)[:2],(.5,False));self.assertEqual(s.decision('BQ_INFO',model(delta=-.02),.5)[:2],(.5,False));self.assertEqual(s.decision('BQ_INFO',model(delta=0),.5)[:2],(.5,False));self.assertEqual(s.threshold(s.LONG_GATE+.001,.001),0);self.assertEqual(s.decision('BQ_INFO',model(mu=-.1,delta=-.02),.5)[:2],(-1.,True));m=model();m['BQ_FEE']['mu']=-.1;self.assertEqual(s.decision('BQ_FEE',m,.5)[:2],(-1.,True));self.assertEqual(s.decision('BQ_QUEUE',m,.5)[:2],(1.,True))
 def test_weekly_direction_daily_risk_and_period_start(self):
  m,c=fixtures();ff=s.features(m,c,set(),start=T,end=T+2*s.WEEK);pp=[forecast(T,model()),forecast(T+s.WEEK,model(mu=-.1,delta=-.02))];m.observation=lambda t,risk:(-.5,min(1,risk/(.5+(t-T)/s.DAY*.01)),.5+(t-T)/s.DAY*.01);p=s.schedule(m,ff,pp,'BQ_INFO',T+3*s.DAY,T+9*s.DAY);self.assertEqual([r['detail']['signal'] for r in p],[1.,1.,1.,1.,-1.,-1.]);self.assertEqual(p[0]['detail']['week_source'],T);self.assertNotEqual(p[0]['weights']['BS'],p[1]['weights']['BS']);self.assertLess(p[-1]['weights']['BP'],0)
 def test_missing_week_reverts_core_and_missing_risk_holds(self):
  m,c=fixtures();ff=s.features(m,c,set(),start=T,end=T+2*s.WEEK);none={n:{'mu':None,'se':None} for n in s.MODELS};pp=[forecast(T,model()),forecast(T+s.WEEK,none)];p=s.schedule(m,ff,pp,'BQ_INFO',T+6*s.DAY,T+8*s.DAY);self.assertTrue(p[0]['detail']['override']);self.assertFalse(p[1]['detail']['override']);self.assertEqual(p[1]['weights'],{'BS':.2,'BP':0.});m.observation=lambda *x:None;self.assertIsNone(s.schedule(m,ff,pp,'BQ_INFO',T,T+s.DAY)[0]['weights'])
 def test_constant_prices_cost_funding_and_delayed_quantity(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'BQ_INFO',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'BQ_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'BQ_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])

def ckeys():return ('mempool','fee_sats','transactions')
if __name__=='__main__':unittest.main()
