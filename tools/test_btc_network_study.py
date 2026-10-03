"""Causality, aggregate windows, constrained nesting and calendar-week learning boundaries."""
import copy,math,unittest
import numpy as np
import btc_network_study as s
T=s.ms('2024-01-01')
class Fixed:
 def __init__(self):self.rowmaps={'BS':{t:[t,100.,100.,100.,100.,t+s.HOUR-1] for t in range(T-60*s.DAY,T+15*s.DAY,s.HOUR)}}
 def observation(self,t,risk=.2):return .5,min(1,risk/.5),.5

def fixtures():
 m=Fixed();counts={k:{t:10. for t in range(T-60*s.DAY,T+20*s.DAY,s.DAY)} for k in ('active','transactions')}
 for t in range(T-8*s.DAY,T-s.DAY,s.DAY):counts['active'][t]=20.;counts['transactions'][t]=30.
 return m,counts

def model(mu=.1,delta=.02,active=False):return {'NA_INFO':{'mu':mu,'se':.001,'constraint_active':active},'NA_ACTIVITY':{'mu':mu-delta,'se':.001},'NA_PRICE':{'mu':mu-.03,'se':.001},'NA_RAW':{'mu':mu,'se':.001,'constraint_active':active}}
def forecast(t,models):return {'source':t,'models':models,'training_n':90,'training_label_end':t-s.WEEK}
class Tests(unittest.TestCase):
 def test_frozen_inputs_missing_dates_and_no_future(self):
  c,z=s.inputs();self.assertEqual([len(c[k]) for k in ('active','transactions')],[2425,2430]);self.assertEqual(len(z),3);self.assertEqual(max(c['active']),s.ms('2026-08-29'));self.assertNotIn(s.ms('2026-08-19'),c['active']);self.assertNotIn(s.ms('2025-11-14'),c['transactions'])
 def test_completed_day_buffer_two_disjoint_windows(self):
  m,c=fixtures();f=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];self.assertTrue(f['valid']);self.assertEqual(f['last_observation_day'],T-2*s.DAY);self.assertEqual(f['last_assumed_available'],T);self.assertEqual(f['window_dates'][0],'2023-11-26');self.assertEqual(f['window_dates'][-1],'2023-12-30');self.assertEqual((f['active']['a7'],f['active']['a28']),(20,10));self.assertAlmostEqual(f['x'],math.log(2));self.assertAlmostEqual(f['z'],math.log(3))
 def test_seven_day_delay_both_counts_not_current_price(self):
  m,c=fixtures();a=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];b=s.features(m,c,set(),7,start=T,end=T+s.WEEK)[0];self.assertEqual(b['last_observation_day'],T-9*s.DAY);self.assertEqual(b['last_assumed_available'],T);self.assertEqual((b['x'],b['z']),(0,0));self.assertGreater(a['x'],0);self.assertEqual((a['r7'],a['r28']),(b['r7'],b['r28']))
 def test_future_or_unavailable_counts_and_target_prices_do_not_change_features(self):
  m,c=fixtures();a=s.features(m,c,set(),start=T,end=T+s.WEEK)
  for k in c:
   for t in c[k]:
    if t>T-2*s.DAY:c[k][t]=1e9
  for t,r in m.rowmaps['BS'].items():
   if t>=T:r[1:5]=[99999.]*4
  self.assertEqual(a,s.features(m,c,set(),start=T,end=T+s.WEEK))
 def test_missing_either_count_zero_or_negative_invalidates_common_row(self):
  for k in ('active','transactions'):
   for val in (None,0,-1):
    m,c=fixtures();t=T-4*s.DAY
    if val is None:del c[k][t]
    else:c[k][t]=val
    f=s.features(m,c,set(),start=T,end=T+s.WEEK)[0];self.assertFalse(f['valid']);self.assertIsNone(f['x' if k=='active' else 'z']);self.assertEqual(f[k]['missing_dates'] if val is None else f[k]['nonpositive_dates'],[s.date(t)])
 def test_completed_price_clock_and_no_trade_mask(self):
  m,c=fixtures();self.assertIsNone(s.close(m,T,{T-s.HOUR}));m.rowmaps['BS'][T-s.HOUR][-1]=T;self.assertIsNone(s.close(m,T));self.assertFalse(s.features(m,c,set(),start=T,end=T+s.WEEK)[0]['valid'])
 def test_negative_address_coefficient_nests_activity_exactly(self):
  rng=np.random.default_rng(20);a=rng.normal(size=(90,4));y=.1+a@np.array([.2,-.1,-.3,-.8])+rng.normal(size=90)*.01;weeks=np.arange(90)*s.WEEK;info=s.fit(a,y,weeks,a[-1],True);activity=s.fit(a[:,:3],y,weeks,a[-1,:3]);self.assertTrue(info['constraint_active']);self.assertEqual(info['beta'][-1],0);self.assertEqual(info['mu'],activity['mu']);self.assertEqual(info['se'],activity['se']);np.testing.assert_array_equal(np.array(info['covariance'])[:4,:4],activity['covariance']);self.assertTrue(np.all(np.array(info['covariance'])[-1]==0));self.assertLess(activity['beta'][-1],0);self.assertFalse(activity['constraint_active']);raw=s.fit(a[:,3:],y,weeks,a[-1,3:],True);self.assertTrue(raw['constraint_active']);self.assertAlmostEqual(raw['mu'],np.mean(y))
 def test_positive_slope_and_rank_rejection(self):
  rng=np.random.default_rng(7);a=rng.normal(size=(90,4));y=a@np.array([.1,.2,-.3,.9]);f=s.fit(a,y,np.arange(90)*s.WEEK,a[0],True);self.assertFalse(f['constraint_active']);self.assertGreater(f['beta'][-1],0);self.assertIsNone(s.fit(np.ones((90,4)),y,np.arange(90)*s.WEEK,a[0],True)['mu'])
 def test_calendar_week_hac_missing_weeks_not_compressed(self):
  weeks=np.array([0,1,3,4,8,10,11,15,18,19])*s.WEEK;Z=np.column_stack([np.ones(10),np.arange(10)]);res=np.array([.2,-.3,.5,.7,-.1,.8,-.2,.4,-.6,.1]);meat=np.zeros((2,2))
  for i in range(10):
   for j in range(10):
    lag=abs(weeks[i]-weeks[j])/s.WEEK
    if lag<=1:meat+=(1-lag/2)*np.outer(Z[i]*res[i],Z[j]*res[j])
  bread=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,weeks),10/8*bread@meat@bread,atol=1e-12);self.assertGreater(np.max(np.abs(s.hac(Z,res,weeks)-s.hac(Z,res,np.arange(10)*s.WEEK))),1e-5)
 def test_104_week_minimum52_purge_and_all_models_same_rows(self):
  rng=np.random.default_rng(40);z=rng.normal(size=(150,4));rows=[dict(source=T+i*s.WEEK,valid=True,**dict(zip(('r7','r28','z','x'),z[i]))) for i in range(150)];yy={r['source']:{'value':float(z[i]@np.array([.1,.2,-.3,.4])),'end':r['source']+s.WEEK} for i,r in enumerate(rows)};p=s.forecast_one(rows,yy,140);self.assertEqual(p['training_n'],104);self.assertEqual(p['training_weeks'][0],rows[35]['source']);self.assertEqual(p['training_weeks'][-1],rows[138]['source']);self.assertEqual(p['training_label_end'],rows[139]['source']);changed=copy.deepcopy(yy)
  for r in rows[139:]:changed[r['source']]['value']=1e6
  self.assertEqual(p,s.forecast_one(rows,changed,140));self.assertIsNotNone(s.forecast_one(rows,yy,53)['models']['NA_INFO']['mu']);self.assertIsNone(s.forecast_one(rows,yy,52)['models']['NA_INFO']['mu']);rows[138]['valid']=False;p=s.forecast_one(rows,yy,140);self.assertTrue(all(v['training_n']==103 for v in p['models'].values()));self.assertFalse(p['models']['NA_ACTIVITY']['constraint_active']);self.assertLess(p['models']['NA_ACTIVITY']['beta'][-1],0)
 def test_increment_constraint_inverse_cost_gate_and_separate_activity(self):
  self.assertEqual(s.decision('NA_INFO',model(),.5)[:2],(1.,True));self.assertEqual(s.decision('NA_INV',model(),.5)[:2],(-1.,True));self.assertEqual(s.decision('NA_TREND',model(),.5)[:2],(.5,False));self.assertEqual(s.decision('NA_INFO',model(delta=-.02),.5)[:2],(.5,False));self.assertEqual(s.decision('NA_INFO',model(active=True),.5)[2],0);self.assertEqual(s.threshold(s.LONG_GATE+.001,.001),0);self.assertEqual(s.decision('NA_INFO',model(mu=-.1,delta=-.02),.5)[:2],(-1.,True));self.assertEqual(s.decision('NA_ACTIVITY',model(mu=.1,delta=.3),.5)[:2],(-1.,True));self.assertEqual(s.decision('NA_PRICE',model(mu=.1,delta=.3),.5)[:2],(1.,True))
 def test_weekly_direction_daily_risk_and_period_start(self):
  m,c=fixtures();ff=s.features(m,c,set(),start=T,end=T+2*s.WEEK);pp=[forecast(T,model()),forecast(T+s.WEEK,model(mu=-.1,delta=-.02))];m.observation=lambda t,risk:(-.5,min(1,risk/(.5+(t-T)/s.DAY*.01)),.5+(t-T)/s.DAY*.01);p=s.schedule(m,ff,pp,'NA_INFO',T+3*s.DAY,T+9*s.DAY);self.assertEqual([r['detail']['signal'] for r in p],[1.,1.,1.,1.,-1.,-1.]);self.assertEqual(p[0]['detail']['week_source'],T);self.assertNotEqual(p[0]['weights']['BS'],p[1]['weights']['BS']);self.assertLess(p[-1]['weights']['BP'],0)
 def test_missing_week_reverts_core_and_missing_risk_hold(self):
  m,c=fixtures();ff=s.features(m,c,set(),start=T,end=T+2*s.WEEK);none={n:{'mu':None,'se':None} for n in s.MODELS};pp=[forecast(T,model()),forecast(T+s.WEEK,none)];p=s.schedule(m,ff,pp,'NA_INFO',T+6*s.DAY,T+8*s.DAY);self.assertTrue(p[0]['detail']['override']);self.assertFalse(p[1]['detail']['override']);self.assertEqual(p[1]['weights'],{'BS':.2,'BP':0.});m.observation=lambda *x:None;self.assertIsNone(s.schedule(m,ff,pp,'NA_INFO',T,T+s.DAY)[0]['weights'])
 def test_constant_prices_cost_funding_and_delayed_quantity(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'NA_INFO',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'NA_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'NA_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
