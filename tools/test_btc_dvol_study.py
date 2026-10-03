"""Causal risk-forecast and execution boundaries, before research performance."""
import copy,math,unittest
import numpy as np
import btc_dvol_study as s
T=s.ms('2024-01-01')
class Fixed:
 def __init__(self):self.rowmaps={'BS':{t:[t,100.,100.,100.,100*math.exp((t+s.HOUR-T)/s.DAY*.01),t+s.HOUR-1] for t in range(T-40*s.DAY,T+40*s.DAY,s.HOUR)}}
 def observation(self,t,risk=.2):return .5,min(1,risk/.5),.5
def pred(iv=.25,pv=.16):return {'VI_INFO':{'variance':iv},'VI_PRICE':{'variance':pv}}
def fixture():return Fixed(),{T-j*s.DAY:90. for j in range(0,12)}
class Tests(unittest.TestCase):
 def test_frozen_unit_days_and_exclusion(self):
  d,z=s.inputs();self.assertEqual(len(d),1979);self.assertEqual(min(d),s.ms('2021-04-01'));self.assertEqual(len(z),3);m=Fixed();f=s.features(m,{s.ms('2021-03-31'):90.},set(),start=s.ms('2021-04-02'),end=s.ms('2021-04-03'))[0];self.assertIsNone(f['q'])
 def test_units_completed_day_plus_buffer(self):
  m,d=fixture();f=s.features(m,d,set(),start=T,end=T+s.DAY)[0];self.assertAlmostEqual(f['q'],.81);self.assertEqual(f['dvol_bar'],T-2*s.DAY);self.assertEqual(f['dvol_end'],T-s.DAY);self.assertEqual(f['assumed_available'],T);self.assertAlmostEqual(f['past_variance'],365*.01**2)
 def test_additional7_days_only_dvol_not_price(self):
  m,d=fixture();d[T-9*s.DAY]=50.;a=s.features(m,d,set(),start=T,end=T+s.DAY)[0];b=s.features(m,d,set(),7,start=T,end=T+s.DAY)[0];self.assertEqual(b['dvol_bar'],T-9*s.DAY);self.assertEqual(a['past_variance'],b['past_variance']);self.assertEqual(b['q'],.25)
 def test_future_prices_and_index_do_not_change_past_feature(self):
  m,d=fixture();a=s.features(m,d,set(),start=T,end=T+s.DAY)
  for t,r in m.rowmaps['BS'].items():
   if t>=T:r[4]=999999.
  for t in (T-s.DAY,T,T+s.DAY):d[t]=99999.
  self.assertEqual(a,s.features(m,d,set(),start=T,end=T+s.DAY))
 def test_missing_no_forward_fill(self):
  m,d=fixture();del d[T-2*s.DAY];f=s.features(m,d,set(),start=T,end=T+s.DAY)[0];self.assertFalse(f['valid']);self.assertIsNone(f['q']);d[T-2*s.DAY]=0.;self.assertFalse(s.features(m,d,set(),start=T,end=T+s.DAY)[0]['valid'])
 def test_completed_price_mask_and_thirty_returns(self):
  m,d=fixture();self.assertAlmostEqual(s.variance(m,T),365*.01**2);self.assertIsNone(s.variance(m,T,{T-s.HOUR}));m.rowmaps['BS'][T-s.HOUR][-1]=T;self.assertIsNone(s.close(m,T));self.assertIsNone(s.variance(m,T))
 def test_future_label_separate_from_features(self):
  m,d=fixture();a=s.features(m,d,set(),start=T,end=T+s.DAY);yy=s.labels(m,start=T,end=T+s.DAY);m.rowmaps['BS'][T+30*s.DAY-s.HOUR][4]*=2;self.assertEqual(a,s.features(m,d,set(),start=T,end=T+s.DAY));self.assertNotEqual(yy,s.labels(m,start=T,end=T+s.DAY));self.assertEqual(yy[T]['end'],T+30*s.DAY)
 def test_negative_slope_nests_price_and_smearing(self):
  rng=np.random.default_rng(33);x=rng.normal(size=(400,2));y=.1+x@np.array([.6,-.7])+rng.normal(size=400)*.1;a=s.fit(x,y,x[0],True);b=s.fit(x[:,:1],y,x[0,:1]);self.assertTrue(a['constraint_active']);self.assertEqual(a['beta'][-1],0.);self.assertEqual(a['variance'],b['variance']);self.assertAlmostEqual(a['variance'],math.exp(a['log_mean'])*a['smearing']);self.assertGreater(a['smearing'],1.)
 def test_positive_slope_rank_and_training_only_smearing(self):
  rng=np.random.default_rng(42);x=rng.normal(size=(400,2));y=.2+x@np.array([.3,.7])+rng.normal(size=400)*.1;a=s.fit(x,y,x[0],True);b=s.fit(x,y,x[1],True);self.assertFalse(a['constraint_active']);self.assertEqual(a['smearing'],b['smearing']);self.assertIsNone(s.fit(np.ones((400,2)),y,x[0],True)['variance']);beta=np.linalg.solve(np.column_stack([np.ones(400),x]).T@np.column_stack([np.ones(400),x]),np.column_stack([np.ones(400),x]).T@y);np.testing.assert_allclose(a['beta'],beta,atol=1e-12)
 def test_365_minimum_730_calendar_and_31_day_purge(self):
  rng=np.random.default_rng(71);x=rng.normal(size=(850,2));ff=[dict(source=T+i*s.DAY,valid=True,log_r=x[i,0],log_q=x[i,1]) for i in range(850)];yy={r['source']:{'value':math.exp(x[i]@np.array([.2,.5])),'end':r['source']+30*s.DAY} for i,r in enumerate(ff)};p=s.forecast_one(ff,yy,800);self.assertEqual(p['training_n'],730);self.assertEqual(p['training_days'][0],ff[40]['source']);self.assertEqual(p['training_days'][-1],ff[769]['source']);self.assertEqual(p['training_label_end'],ff[799]['source']);self.assertIsNone(s.forecast_one(ff,yy,394)['models']['VI_INFO']['variance']);self.assertIsNotNone(s.forecast_one(ff,yy,395)['models']['VI_INFO']['variance']);changed=copy.deepcopy(yy)
  for r in ff[770:]:changed[r['source']]['value']=999999.
  self.assertEqual(p,s.forecast_one(ff,changed,800));ff[769]['valid']=False;self.assertEqual(s.forecast_one(ff,yy,800)['training_n'],729)
 def test_inverse_risk_not_short_cap_and_fallback(self):
  f={'q':.81};self.assertEqual(s.weight('VI_INFO',f,pred(),.2,.3),( .4,False));self.assertEqual(s.weight('VI_PRICE',f,pred(),.2,.3),(.5,False));self.assertEqual(s.weight('VI_INV',f,pred(),.2,.3),(.625,False));self.assertAlmostEqual(s.weight('VI_RAW',f,pred(),.2,.3)[0],.2/.9);self.assertEqual(s.weight('VI_INFO',f,pred(.0001,.01),.2,.3),(1.,False));self.assertEqual(s.weight('VI_TREND',f,pred(),.2,.3),(.3,True));self.assertEqual(s.weight('VI_INFO',f,pred(None,None),.2,.3),(.3,True))
 def test_daily_core_direction_all_spot_or_cash(self):
  m,d=fixture();ff=s.features(m,d,set(),start=T,end=T+s.DAY);pp=[{'source':T,'models':pred(),'training_n':500,'training_label_end':T-s.DAY}]
  for n in s.IDS:
   plan=s.schedule(m,ff,pp,n,T,T+s.DAY);self.assertEqual(plan[0]['weights']['BP'],0);self.assertGreaterEqual(plan[0]['weights']['BS'],0)
  m.observation=lambda t,risk:(-.5,.4,.5);self.assertEqual(s.schedule(m,ff,pp,'VI_INFO',T,T+s.DAY)[0]['weights'],{'BS':0.,'BP':0.});m.observation=lambda *args:None;self.assertIsNone(s.schedule(m,ff,pp,'VI_INFO',T,T+s.DAY)[0]['weights'])
 def test_calendar_bootstrap_missing_retained(self):
  values=[.1,float('nan'),.3]*100;r=s.calendar_bootstrap(values,30);self.assertEqual(r['calendar_days'],300);self.assertEqual(r['valid_days'],200);self.assertAlmostEqual(r['mean'],.2);self.assertEqual(r,s.calendar_bootstrap(values,30))
 def test_spot_costs_funding_zero_and_delay_quantity(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.1,start+8*s.HOUR]}};plan=[{'source_time':start,'weights':{'BS':.3,'BP':0.}}];a=s.ledger.simulate(m,'VI_INFO',start,end,plan);self.assertEqual(a['metrics']['funding'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']);self.assertLess(a['metrics']['net_pnl'],0);b=s.ledger.simulate(m,'VI_INFO',start,end,plan,delay=24);self.assertEqual(next(e for e in b['events'] if e['kind']=='fill')['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'VI_INFO',start,end,plan,multiplier=2);self.assertLess(c['metrics']['net_pnl'],a['metrics']['net_pnl'])
if __name__=='__main__':unittest.main()
