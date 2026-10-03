"""Causal 29-boundary price paths, exact signed-count interaction and financial ledger boundaries."""
import copy,math,unittest
import numpy as np
import btc_continuity_study as s
class FakeMarket:
 def __init__(self,t):
  self.rowmaps={'BS':{u-s.HOUR:[u-s.HOUR,100.,101.,99.,100*math.exp(i/900+.01*math.sin(i/4)),u-1] for i,u in enumerate(range(t-120*s.DAY,t+30*s.DAY,s.DAY))}}
 def observation(self,t,risk):return .5,min(1,risk/.4),.4
def pred(mu,se=0.,beta=.5):return {'mu':mu,'se':se,'beta':[0.,beta]}
def models(info=.03,count=.01,eff=-.02,price=0.,beta=.5):return dict(zip(s.MODELS,[pred(info,beta=beta),pred(count,beta=beta),pred(eff,beta=beta),pred(price)]))
class Tests(unittest.TestCase):
 def setUp(self):self.t=s.ms('2024-01-08');self.m=FakeMarket(self.t)
 def feature(self,m=None,excluded=None,lag=0):return s.features(self.m if m is None else m,set() if excluded is None else excluded,lag,self.t,self.t+s.WEEK)[0]
 def with_returns(self,rr):
  self.assertEqual(len(rr),28);price=100.
  for i,u in enumerate(range(self.t-28*s.DAY,self.t+s.DAY,s.DAY)):
   if i:price*=math.exp(rr[i-1])
   self.m.rowmaps['BS'][u-s.HOUR][4]=price
  return self.feature()
 def test_all29_completed_boundaries_lag7_same_clock(self):
  a=self.feature();b=self.feature(lag=7);self.assertTrue(a['valid']);self.assertEqual(a['last_market_close'],self.t);self.assertEqual(a['price_times'],list(range(self.t-28*s.DAY,self.t+s.DAY,s.DAY)));self.assertEqual(b['price_times'],[u-7*s.DAY for u in a['price_times']]);self.assertEqual(b['last_market_close'],self.t-7*s.DAY)
 def test_exact_same_cumulative_return_different_path_counts(self):
  a=self.with_returns([.01]*28);b=self.with_returns([-.005]*27+[.415]);self.assertAlmostEqual(a['r28'],b['r28'],13);self.assertEqual(a['q'],1.);self.assertEqual(b['q'],-26/28);self.assertGreater(a['z'],0);self.assertLess(b['z'],0);self.assertLess(a['information_discreteness'],b['information_discreteness']);self.assertAlmostEqual(a['efficiency'],1.,13)
 def test_signed_interaction_not_return_times_absolute_q(self):
  a=self.with_returns([-.005]*27+[.415]);self.assertGreater(a['r28'],0);self.assertLess(a['q'],0);self.assertAlmostEqual(a['z'],abs(a['r28'])*a['q'],14);self.assertNotAlmostEqual(a['z'],a['r28']*abs(a['q']),10)
 def test_downward_smooth_same_sign_continuity_negative_z(self):
  a=self.with_returns([-.01]*28);self.assertEqual(a['q'],-1.);self.assertEqual(a['continuity'],1.);self.assertEqual(a['information_discreteness'],-1.);self.assertLess(a['z'],0);self.assertLess(a['e'],0);self.assertAlmostEqual(a['z'],a['r28'],13)
 def test_zero_days_in_denominator_no_drop(self):
  a=self.with_returns([.01]*7+[-.01]*7+[0.]*14);self.assertEqual(a['positive_days'],7);self.assertEqual(a['negative_days'],7);self.assertEqual(a['zero_days'],14);self.assertEqual(a['q'],0);self.assertEqual(a['z'],0);self.assertTrue(a['valid'])
 def test_zero_path_invalid_without_epsilon(self):
  a=self.with_returns([0.]*28);self.assertFalse(a['valid']);self.assertEqual(a['path_absolute_return'],0);self.assertIsNone(a['efficiency']);self.assertIsNone(a['e'])
 def test_boundary_missing_bad_clock_nonpositive_mask_invalidate(self):
  for kind in ('missing','clock','zero','nan','mask'):
   m=copy.deepcopy(self.m);u=self.t-13*s.DAY-s.HOUR
   if kind=='missing':del m.rowmaps['BS'][u]
   elif kind=='clock':m.rowmaps['BS'][u][5]+=1
   elif kind=='zero':m.rowmaps['BS'][u][4]=0
   elif kind=='nan':m.rowmaps['BS'][u][4]=float('nan')
   e=self.feature(m=m,excluded={u} if kind=='mask' else set());self.assertFalse(e['valid'],kind);self.assertEqual(e['bad_price_times'],[u+s.HOUR])
 def test_unneeded_intraday_missing_not_imported_as_daily_mask(self):
  a=self.feature();self.assertEqual(a,self.feature(excluded={self.t-3*s.DAY+14*s.HOUR}))
 def test_future_bars_irrelevant_current_completed_close_required(self):
  a=self.feature()
  for u,r in self.m.rowmaps['BS'].items():
   if u>=self.t:r[4]=1e30;r[5]=0
  self.assertEqual(a,self.feature());self.m.rowmaps['BS'][self.t-s.HOUR][5]=self.t;self.assertFalse(self.feature()['valid'])
 def test_unit_scale_and_return_sum_invariance(self):
  a=self.feature()
  for r in self.m.rowmaps['BS'].values():r[4]*=10000
  b=self.feature()
  for k in s.FEATURE_COLS+('efficiency','continuity','information_discreteness'):self.assertAlmostEqual(a[k],b[k],12)
  self.assertAlmostEqual(sum(b['daily_returns']),b['r28'],12)
 def test_common_calendar_training_rows_purge_minimum(self):
  rng=np.random.default_rng(8);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;x=rng.normal(size=4);r7,r28,q,e=x;ff.append(dict(source=t,valid=i!=100,r7=r7,r28=r28,q=q,z=abs(r28)*q,e=e));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);want=[f['source'] for f in ff[44:148] if f['valid']];self.assertEqual(a['training_weeks'],want);self.assertTrue(all(p['training_n']==len(want) for p in a['models'].values()));self.assertEqual(a['training_label_end'],ff[148]['source']);yy[ff[148]['source']]['value']=100;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()))
 def test_unconstrained_negative_slope_retained_not_fitted_away(self):
  rng=np.random.default_rng(81);x=rng.normal(size=(104,4));beta=np.array([.01,-.02,.03,-.05]);p=s.fit(x,.003+x@beta,np.arange(104)*s.WEEK,x[0]);np.testing.assert_allclose(p['beta'],np.r_[.003,beta],atol=1e-12);self.assertFalse(p['constraint_active'])
 def test_positive_interaction_same_inverse_events(self):
  self.assertEqual(s.decision('CT_INFO',models(),.5)[:2],(1.,True));self.assertEqual(s.decision('CT_INV',models(),.5)[:2],(-1.,True))
  for beta in (0.,-.5):
   for name in ('CT_INFO','CT_INV','CT_COUNT','CT_EFF'):self.assertEqual(s.decision(name,models(beta=beta),.5)[:2],(.5,False))
  self.assertEqual(s.decision('CT_INFO',models(info=-.03,count=-.01),.5)[:2],(-1.,True))
 def test_count_eff_positive_but_no_info_increment_requirement(self):
  p=models(info=.04,count=.06,eff=.03);self.assertEqual(s.decision('CT_INFO',p,.5)[:2],(.5,False))
  for name in ('CT_COUNT','CT_EFF'):self.assertEqual(s.decision(name,p,.5)[:2],(1.,True))
  p['CT_INFO']=pred(None,None);self.assertTrue(s.decision('CT_COUNT',p,.5)[1]);self.assertTrue(s.decision('CT_EFF',p,.5)[1]);self.assertFalse(s.decision('CT_INV',p,.5)[1])
 def test_cost_uncertainty_increment_price_no_coefficient_gate(self):
  self.assertEqual(s.decision('CT_INFO',models(info=.03,count=.04),.5)[:2],(.5,False));self.assertEqual(s.decision('CT_INFO',models(info=.03,count=.03),.5)[:2],(.5,False));self.assertEqual(s.threshold(.001,0),0);self.assertEqual(s.threshold(.03,.04),0);self.assertEqual(s.threshold(-.001,0),0);self.assertEqual(s.decision('CT_PRICE',models(price=-.03,beta=-1),.5)[:2],(-1.,True))
 def test_rank_and_common_invalid_current_features(self):
  x=np.ones((70,4));self.assertIsNone(s.fit(x,np.arange(70),np.arange(70)*s.WEEK,x[0])['mu']);ff=[dict(source=self.t,valid=False)];yy={self.t:{'end':self.t+s.WEEK,'value':.1}};p=s.forecast_one(ff,yy,0);self.assertTrue(all(v['mu'] is None for v in p['models'].values()))
 def test_calendar_hac_not_compressed_gaps(self):
  rng=np.random.default_rng(12);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];M=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:M+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,dates),10/6*B@M@B,rtol=1e-10,atol=1e-12)
 def test_partial_week_same_direction_daily_risk(self):
  ff=[dict(source=self.t,valid=True)];pp=[dict(source=self.t,models=models(),training_n=70,training_label_end=self.t-s.WEEK)];a=s.schedule(self.m,ff,pp,'CT_INFO',self.t+2*s.DAY,self.t+6*s.DAY);self.assertTrue(all(e['detail']['week_source']==self.t and e['weights']=={'BS':.5,'BP':0.} for e in a));b=s.schedule(self.m,ff,pp,'CT_INFO',self.t+2*s.DAY,self.t+6*s.DAY,.1);self.assertTrue(all(e['weights']['BS']==.25 for e in b))
 def test_invalid_data_core_missing_risk_hold(self):
  mm={k:pred(None,None) for k in s.MODELS};self.assertEqual(s.decision('CT_INFO',mm,.5)[:2],(.5,False));ff=[dict(source=self.t,valid=False)];pp=[dict(source=self.t,models=mm,training_n=0,training_label_end=None)];self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'CT_INFO',self.t,self.t+s.DAY)[0]['weights'])
 def test_constant_prices_fees_funding_delay(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'CT_INFO',start,end,plan);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'CT_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);self.assertEqual(first['source_time'],start);c=s.ledger.simulate(m,'CT_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])


if __name__=='__main__':unittest.main()
