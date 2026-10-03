"""Synthetic causal/dimensional boundaries for spent-cohort age; no historical forecasts or PNL."""
import copy,math,unittest
import numpy as np
import btc_dormancy_study as s
class FakeMarket:
 def __init__(self):
  self.rowmaps={'BS':{}}
  for t in range(s.ms('2017-01-01'),s.ms('2028-01-01'),s.DAY):self.rowmaps['BS'][t-s.HOUR]=[t-s.HOUR,100,101,99,100+math.sin(t/s.DAY/27)*8+(t/s.DAY%300)/100,t-1]
 def observation(self,t,risk):return .5,min(1,risk/.4),.4

def sample(t):
 d={}
 for i,u in enumerate(range(t-70*s.DAY,t+20*s.DAY,s.DAY)):
  b=1000.+i*200;a=2.+(i%7);d[u]={'cdd':b*a,'spent':b,'dormancy':a,'valid':True}
 return d
def pred(mu,se=0.):return {'mu':mu,'se':se}
def models(info=.03,flow=.01,age=-.02,price=0):return dict(zip(s.MODELS,[pred(info),pred(flow),pred(age),pred(price)]))
class Tests(unittest.TestCase):
 def setUp(self):self.m=FakeMarket();self.t=s.ms('2024-01-08');self.d=sample(self.t)
 def feature(self,data=None,lag=0):return s.features(self.m,self.d if data is None else data,set(),lag,self.t,self.t+s.WEEK)[0]
 def test_six_day_availability_disjoint_seven_28_windows(self):
  a=self.feature();b=self.feature(lag=7);self.assertEqual(a['last_observation_day'],self.t-6*s.DAY);self.assertEqual(b['last_observation_day'],self.t-13*s.DAY);self.assertEqual(b['last_assumed_available'],self.t);self.assertEqual(a['recent']['window_dates'],[s.date(x) for x in range(self.t-12*s.DAY,self.t-5*s.DAY,s.DAY)]);self.assertEqual(a['previous']['window_dates'],[s.date(x) for x in range(self.t-40*s.DAY,self.t-12*s.DAY,s.DAY)]);self.assertEqual(set(a['recent']['window_dates'])&set(a['previous']['window_dates']),set())
 def test_ratio_of_sums_not_mean_dormancy(self):
  e=self.feature();rows=[self.d[u] for u in range(self.t-12*s.DAY,self.t-5*s.DAY,s.DAY)];a=sum(r['cdd'] for r in rows)/sum(r['spent'] for r in rows);self.assertAlmostEqual(a,e['recent']['age_days'],14);self.assertNotAlmostEqual(a,sum(r['dormancy'] for r in rows)/7,8)
 def test_common_value_unit_scaling_invariance(self):
  d=copy.deepcopy(self.d)
  for v in d.values():v['spent']*=100000000;v['cdd']*=100000000
  a,b=self.feature(),self.feature(d)
  for k in ('x','f'):self.assertAlmostEqual(a[k],b[k],14)
 def test_log1p_age_zero_valid_spent_positive(self):
  d=copy.deepcopy(self.d)
  for t,v in d.items():
   if self.t-12*s.DAY<=t<=self.t-6*s.DAY:v.update(cdd=0.,dormancy=0.)
  e=self.feature(d);self.assertTrue(e['valid']);self.assertEqual(e['recent']['age_days'],0);self.assertAlmostEqual(e['x'],-math.log1p(e['previous']['age_days']))
 def test_age_and_volume_separate_units(self):
  d=copy.deepcopy(self.d)
  for t,v in d.items():
   if self.t-12*s.DAY<=t<=self.t-6*s.DAY:v['spent']*=2;v['cdd']*=2
  a,b=self.feature(),self.feature(d);self.assertAlmostEqual(a['x'],b['x']);self.assertAlmostEqual(b['f']-a['f'],math.log(2))
 def test_future_age_and_target_dont_change_current_feature(self):
  a=self.feature();d=copy.deepcopy(self.d)
  for t,v in d.items():
   if t>self.t-6*s.DAY:v.update(cdd=1e18,spent=1,dormancy=1e18)
  self.m.rowmaps['BS'][self.t+s.WEEK-s.HOUR][4]*=10;self.assertEqual(a,self.feature(d))
 def test_window_edges_missing_count_conflict_and_nan(self):
  for day in (40,13,12,6):
   for mode in ('missing','zero','invalid','ratio','nan'):
    d=copy.deepcopy(self.d);t=self.t-day*s.DAY
    if mode=='missing':del d[t]
    elif mode=='zero':d[t]['spent']=0
    elif mode=='invalid':d[t]['valid']=False
    elif mode=='ratio':d[t]['dormancy']+=1
    else:d[t]['cdd']=float('nan')
    self.assertFalse(self.feature(d)['valid'],(day,mode))
 def test_completed_price_mask_and_early_absent_days(self):
  self.m.rowmaps['BS'][self.t-s.HOUR][5]=self.t;self.assertIsNone(s.close(self.m,self.t));self.m.rowmaps['BS'][self.t-s.HOUR][5]=self.t-1;self.assertIsNone(s.close(self.m,self.t,{self.t-s.HOUR}));self.assertFalse(self.feature({})['valid'])
 def test_unrestricted_positive_and_negative_age_slopes(self):
  rng=np.random.default_rng(2049);x=rng.normal(size=(90,4));days=np.arange(90)*s.WEEK
  for b in (-.04,.04):
   beta=np.array([.01,.03,-.02,b]);p=s.fit(x,.007+x@beta,days,x[0]);np.testing.assert_allclose(p['beta'],np.r_[.007,beta],atol=1e-12);self.assertFalse(p['constraint_active'])
 def test_rank_deficient_is_missing(self):
  x=np.ones((70,4));p=s.fit(x,np.arange(70),np.arange(70)*s.WEEK,x[0]);self.assertIsNone(p['mu'])
 def test_calendar_hac_not_compressed_gaps(self):
  rng=np.random.default_rng(15);Z=np.c_[np.ones(10),rng.normal(size=(10,2))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];M=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:M+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,dates),10/7*B@M@B,rtol=1e-10,atol=1e-12)
 def test_training_calendar_purge_common_rows_future_label(self):
  rng=np.random.default_rng(31);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;r=dict(zip(('r7','r28','f','x'),rng.normal(size=4)));ff.append(dict(source=t,valid=i!=100,**r));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  p=s.forecast_one(ff,yy,149);want=[r['source'] for r in ff[44:148] if r['valid']];self.assertEqual(p['training_weeks'],want);self.assertLessEqual(p['training_label_end'],ff[149]['source']-s.DAY);self.assertTrue(all(v['training_n']==len(want) for v in p['models'].values()));old=copy.deepcopy(p);yy[ff[149]['source']]['value']=100;yy[ff[148]['source']]['value']=100;self.assertEqual(old,s.forecast_one(ff,yy,149));self.assertTrue(all(v['mu'] is None for v in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(v['mu'] is not None for v in s.forecast_one(ff,yy,53)['models'].values()))
 def test_cost_gate_and_only_incremental_direction(self):
  m=models();self.assertEqual(s.decision('DA_INFO',m,.5)[:2],(1.,True));self.assertEqual(s.decision('DA_INV',m,.5)[:2],(-1.,True));self.assertEqual(s.decision('DA_AGE',m,.5)[:2],(-1.,True));self.assertEqual(s.decision('DA_TREND',m,.5)[:2],(.5,False));self.assertEqual(s.decision('DA_INFO',models(info=.03,flow=.04),.5)[:2],(.5,False));self.assertEqual(s.threshold(.001,0),0);self.assertEqual(s.decision('DA_INFO',models(info=-.03,flow=-.01),.5)[:2],(-1.,True));self.assertEqual(s.decision('DA_INFO',models(info=.01,flow=.01),.5)[:2],(.5,False))
 def test_weekly_direction_daily_risk_partial_week(self):
  week=self.t;ff=[dict(source=week,valid=True)];pp=[dict(source=week,models=models(),training_n=70,training_label_end=week-s.WEEK)];out=s.schedule(self.m,ff,pp,'DA_INFO',week+2*s.DAY,week+6*s.DAY);self.assertTrue(all(e['detail']['week_source']==week and e['weights']=={'BS':.5,'BP':0.} for e in out));lo=s.schedule(self.m,ff,pp,'DA_INFO',week+2*s.DAY,week+6*s.DAY,.1);self.assertTrue(all(e['weights']['BS']==.25 for e in lo))
 def test_missing_model_core_and_missing_risk_hold(self):
  mm={k:pred(None,None) for k in s.MODELS};self.assertEqual(s.decision('DA_INFO',mm,-.5)[:2],(0.,False));ff=[dict(source=self.t,valid=False)];pp=[dict(source=self.t,models=mm,training_n=0,training_label_end=None)];self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'DA_INFO',self.t,self.t+s.DAY)[0]['weights'])
 def test_constant_prices_cost_funding_delayed_quantity(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'DA_INFO',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'DA_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'DA_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
