"""Synthetic preregistered calendar-risk boundaries; no historical model fitting or PNL."""
import copy,math,unittest
import numpy as np
import btc_periodic_study as s

def sample(n=550):
 rng=np.random.default_rng(981);start=s.ms('2020-01-01');return [{'day':start+i*s.DAY,'end':start+(i+1)*s.DAY,'valid':True,'rv':float(math.exp(-8+.3*rng.normal()+.13*math.sin(i/12)))} for i in range(n)]
class FakeMarket:
 def __init__(self,score=.5,vol=.4):self.score,self.vol=score,vol
 def observation(self,t,target=.2):return self.score,min(1,target/self.vol) if self.vol else 0,self.vol
class Tests(unittest.TestCase):
 def setUp(self):self.rows=sample();self.ff=s.features(self.rows)
 def test_calendar_target_day_sum_zero(self):
  monday=s.ms('2024-01-01');a=np.array([s.calendar(monday+i*s.DAY) for i in range(7)]);np.testing.assert_equal(a.sum(axis=0),np.zeros(6));np.testing.assert_equal(a[:6],np.eye(6));np.testing.assert_equal(a[6],-np.ones(6));e=self.ff[350];self.assertEqual(e['weekday'],s.weekday(e['observed_day']+s.DAY));self.assertNotEqual(e['weekday'],s.weekday(e['observed_day']))
 def test_completed_22_days_and_log_mean_not_mean_log(self):
  e=self.ff[350];v=np.array([r['rv'] for r in self.rows[329:351]]);self.assertEqual(e['input_days'],[r['day'] for r in self.rows[329:351]]);np.testing.assert_allclose(e['log_rv_features'],np.log([v[-1],v[-5:].mean(),v.mean()]),atol=1e-14);self.assertNotAlmostEqual(e['log_rv_features'][2],np.log(v).mean(),6);self.assertEqual(e['truth'],self.rows[351]['rv'])
 def test_invalid_zero_nan_missing_and_incomplete_edges(self):
  for j in (329,330,346,350):
   for kind in ('zero','nan','invalid','clock','missing'):
    rows=copy.deepcopy(self.rows)
    if kind=='zero':rows[j]['rv']=0
    elif kind=='nan':rows[j]['rv']=float('nan')
    elif kind=='invalid':rows[j]['valid']=False
    elif kind=='clock':rows[j]['end']+=1
    else:del rows[j]
    e=next(x for x in s.features(rows) if x['observed_day']==self.rows[350]['day']) if kind!='missing' or j!=350 else None
    if e is not None:self.assertFalse(e['valid'],(j,kind))
 def test_future_rv_not_in_current_features_or_model(self):
  a=s.forecast_one(self.ff,450);rows=copy.deepcopy(self.rows)
  for r in rows[451:]:r['rv']*=100
  ff=s.features(rows);b=s.forecast_one(ff,450);self.assertEqual(a,b);self.assertEqual(ff[450]['features'],self.ff[450]['features']);self.assertNotEqual(ff[450]['truth'],self.ff[450]['truth'])
 def test_full_calendar_training_window_last_label_completed(self):
  p=s.forecast_one(self.ff,450);self.assertEqual(p['training_days'],[r['source'] for r in self.ff[85:450]]);self.assertEqual(p['training_label_end'],self.ff[450]['source']);self.assertEqual(sum(p['training_weekday_counts']),365);self.assertTrue(all(x['n']==365 for x in p['models'].values() if 'n' in x));ff=copy.deepcopy(self.ff);ff[449]['truth_end']+=1;q=s.forecast_one(ff,450);self.assertNotIn(ff[449]['source'],q['training_days'])
 def test_minimum300_and_weekday40_common_mask(self):
  self.assertTrue(all(s.forecast_one(self.ff,320)['models'][k]['prediction'] is None for k in s.FITS));self.assertTrue(all(s.forecast_one(self.ff,321)['models'][k]['prediction'] is not None for k in s.FITS));ff=copy.deepcopy(self.ff);idx=[i for i in range(85,450) if ff[i]['weekday']==0]
  for i in idx[:len(idx)-39]:ff[i]['valid']=False
  p=s.forecast_one(ff,450);self.assertGreater(p['training_n'],300);self.assertEqual(p['training_weekday_counts'][0],39);self.assertTrue(all(p['models'][k]['prediction'] is None for k in s.FITS))
 def test_smearing_mean_equals_arithmetic_variance(self):
  y=np.log([.0001,.0002,.003,.0007]);p=s.fit(np.empty((4,0)),y,np.empty(0));self.assertAlmostEqual(p['prediction'],np.exp(y).mean(),16);self.assertNotAlmostEqual(p['prediction'],math.exp(y.mean()),6);self.assertAlmostEqual(p['smearing'],np.exp(p['residuals']).mean(),14)
 def test_exact_log_calendar_regression_unrestricted(self):
  rng=np.random.default_rng(412);x=np.c_[rng.normal(size=(350,3)),[s.calendar(s.ms('2023-01-01')+i*s.DAY) for i in range(350)]];beta=np.array([-8,.3,-.2,.1,.13,-.06,.04,-.03,.07,-.09]);y=np.c_[np.ones(350),x]@beta;p=s.fit(x,y,x[-1]);np.testing.assert_allclose(p['beta'],beta,atol=2e-13);self.assertAlmostEqual(p['smearing'],1,13);self.assertAlmostEqual(p['prediction'],math.exp(y[-1]),15)
 def test_variance_unit_scaling_covariance(self):
  rows=copy.deepcopy(self.rows)
  for r in rows:r['rv']*=100
  a=s.forecast_one(self.ff,450);b=s.forecast_one(s.features(rows),450)
  for k in s.FITS+('PS_INV',):self.assertAlmostEqual(b['models'][k]['prediction']/a['models'][k]['prediction'],100,8)
 def test_rank_and_nonfinite_rejected(self):
  x=np.ones((310,2));self.assertIsNone(s.fit(x,np.ones(310),x[0])['prediction']);x[0,0]=float('nan');self.assertIsNone(s.fit(x,np.ones(310),x[1])['prediction']);x=np.arange(310).reshape(-1,1);self.assertIsNone(s.fit(x,np.ones(310),np.array([float('inf')]))['prediction'])
 def test_restore_floor_and_overflow_not_cap(self):
  p=s.restore(-1000,0);self.assertEqual(p['prediction'],1e-8);self.assertTrue(p['floor']);self.assertIsNone(s.restore(1000,0)['prediction']);self.assertIsNone(s.restore(float('inf'),0)['prediction'])
 def test_inverse_risk_factor_not_direction(self):
  p=s.forecast_one(self.ff,450);a,b,c=[p['models'][k]['prediction'] for k in ('PS_CAL','PS_HAR','PS_INV')];self.assertAlmostEqual(c,b*b/a,16);t=p['source']
  for k in s.IDS[:-1]:
   plan=s.schedule(FakeMarket(-.5),self.ff,[p],k,t,t+s.DAY);self.assertEqual(plan[0]['weights'],{'BS':0.,'BP':0.})
 def test_caps_and_risk_target_and_missing_hold(self):
  p=s.forecast_one(self.ff,450);t=p['source'];p['models']['PS_CAL']['prediction']=.16/365
  a=s.schedule(FakeMarket(),self.ff,[p],'PS_CAL',t,t+s.DAY)[0];b=s.schedule(FakeMarket(),self.ff,[p],'PS_CAL',t,t+s.DAY,.1)[0];self.assertAlmostEqual(a['weights']['BS'],.25);self.assertAlmostEqual(b['weights']['BS'],.125);p['models']['PS_CAL']['prediction']=1e-8;self.assertEqual(s.schedule(FakeMarket(),self.ff,[p],'PS_CAL',t,t+s.DAY)[0]['weights']['BS'],.5);p['models']['PS_CAL']['prediction']=None;self.assertIsNone(s.schedule(FakeMarket(),self.ff,[p],'PS_CAL',t,t+s.DAY)[0]['weights'])
 def test_trend_zero_vol_retains_original_no_risk_no_log_loss(self):
  ff=self.ff[450:451];p=s.forecast_one(self.ff,450);p['models']['PS_TREND']={'prediction':0.,'floor':False};t=p['source'];plan=s.schedule(FakeMarket(vol=0),ff,[p],'PS_TREND',t,t+s.DAY);self.assertEqual(plan[0]['weights']['BS'],0);fc=s.forecast_summary(ff,[p],t,t+s.DAY);self.assertEqual(fc['n'],0);self.assertIsNone(fc['models']['PS_CAL']['mse'])
 def test_qlike_uses_rv_not_log_rv_and_common_positive_set(self):
  t=self.ff[450]['source'];ff=[dict(self.ff[450],truth=.0004,truth_end=t+s.DAY)];p=dict(source=t,models={k:{'prediction':.0002,'floor':False} for k in s.IDS});fc=s.forecast_summary(ff,[p],t,t+s.DAY)
  for k in s.IDS:self.assertAlmostEqual(fc['models'][k]['qlike'],2-math.log(2)-1,14);self.assertAlmostEqual(fc['models'][k]['mse'],4e-8,18)
 def test_cost_delayed_fixed_target_hold_and_zero_funding(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+3*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR]}};plan=[{'source_time':start,'weights':{'BS':.3,'BP':0.}},{'source_time':start+s.DAY,'weights':None}]
  for delay in (0,1,24):
   a=s.ledger.simulate(m,'PS_CAL',start,end,plan,delay=delay);fills=[e for e in a['events'] if e['kind']=='fill'];self.assertEqual(len(fills),2);self.assertEqual(fills[0]['time'],start+(1+delay)*s.HOUR);self.assertEqual(fills[0]['source_time'],start);self.assertEqual(a['metrics']['funding'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']);q=.3*1000/(20000*(1+.3*(.00015+.00100015)));want=math.floor((q+1e-12)/.00001)*.00001;self.assertAlmostEqual(fills[0]['position'],want,14)
  b=s.ledger.simulate(m,'PS_CAL',start,end,plan,multiplier=2);self.assertGreater(b['metrics']['fees']+b['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
