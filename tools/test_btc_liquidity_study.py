"""Synthetic liquidity-clock, measurement, coefficient and ledger boundaries; no historical performance."""
import copy,math,unittest
import numpy as np
import btc_liquidity_study as s
from collect_btc_liquidity_data import aggregate
class FakeMarket:
 def observation(self,t,risk):return .5,min(1,risk/.4),.4

def sample(t):
 return {d:{'day':d,'end':d+s.DAY,'valid':True,'cs':.0001*(1+i%9),'ar':.0002*(1+i%7),'rv':.00003*(1+i%11),'close':100*math.exp(.01*math.sin(i/3)+i/500)} for i,d in enumerate(range(t-100*s.DAY,t+20*s.DAY,s.DAY))}
def pred(mu,se=0.,beta=.5):return {'mu':mu,'se':se,'beta':[0.,beta]}
def models(info=.03,risk=.01,alt=-.02,price=0.,beta=.5):return dict(zip(s.MODELS,[pred(info,beta=beta),pred(risk),pred(alt,beta=beta),pred(price)]))
class Tests(unittest.TestCase):
 def setUp(self):self.t=s.ms('2024-01-08');self.m=FakeMarket();self.d=sample(self.t)
 def feature(self,d=None,lag=0):return s.features(self.m,self.d if d is None else d,set(),lag,self.t,self.t+s.WEEK)[0]
 def bars(self):
  return {t:[t,110.,121.,100.,121.,t+s.HOUR-1] for t in range(self.t,self.t+s.DAY,s.HOUR)}
 def test_two_bar_algebra_scale_and_rv_open_close(self):
  rows=self.bars();e=aggregate(self.t,rows,True,set());self.assertTrue(e['valid']);self.assertEqual(e['pairs'],23);self.assertAlmostEqual(e['cs'],2*.21/2.21,14);self.assertAlmostEqual(e['ar'],math.log(1.21),13);self.assertAlmostEqual(e['rv'],24*math.log(1.1)**2,13)
  for r in rows.values():
   for j in (1,2,3,4):r[j]*=1000000
  f=aggregate(self.t,rows,True,set())
  for k in ('cs','ar','rv'):self.assertAlmostEqual(e[k],f[k],12)
 def test_daily_pairs_do_not_include_next_day(self):
  rows=self.bars();a=aggregate(self.t,rows,True,set());rows[self.t+s.DAY]=[self.t+s.DAY,1e9,2e9,1.,2.,self.t+s.DAY+s.HOUR-1];self.assertEqual(a,aggregate(self.t,rows,True,set()))
 def test_no_volume_threshold_or_forward_fill(self):
  rows=self.bars()
  for kind in ('missing','late','bounds','nonpositive','mask','quality'):
   r=copy.deepcopy(rows);t=self.t+12*s.HOUR;mask=set();quality=True
   if kind=='missing':del r[t]
   elif kind=='late':r[t][5]+=1
   elif kind=='bounds':r[t][3]=150.
   elif kind=='nonpositive':r[t][1]=0.
   elif kind=='mask':mask.add(t)
   else:quality=False
   e=aggregate(self.t,r,quality,mask);self.assertFalse(e['valid'],kind);self.assertIsNone(e['cs']);self.assertIsNone(e['rv'])
 def test_negative_cs_and_ar_products_clipped_not_absolute(self):
  rows={t:[t,math.exp(i/10),math.exp(i/10+.01),math.exp(i/10-.01),math.exp(i/10+.005),t+s.HOUR-1] for i,t in enumerate(range(self.t,self.t+s.DAY,s.HOUR))}
  e=aggregate(self.t,rows,True,set());self.assertEqual(e['cs'],0.);self.assertEqual(e['ar'],0.)
 def test_completed_Dplus1_lag7_exact_35_days(self):
  a=self.feature();b=self.feature(lag=7);self.assertEqual(a['last_observation_day'],self.t-s.DAY);self.assertEqual(a['last_market_close'],self.t);self.assertEqual(b['last_observation_day'],self.t-8*s.DAY);self.assertEqual(b['last_assumed_available'],self.t);self.assertEqual(a['input_days'],list(range(self.t-35*s.DAY,self.t,s.DAY)))
 def test_nonoverlapping7_prior28_and_bp_units(self):
  e=self.feature();x=e['daily_inputs'];self.assertAlmostEqual(e['cs'],math.log1p(1e4*sum(x['cs'][-7:])/7)-math.log1p(1e4*sum(x['cs'][:28])/28),14)
  a=copy.deepcopy(self.d);a[self.t-8*s.DAY]['cs']*=4;self.assertLess(self.feature(a)['cs'],e['cs']);a=copy.deepcopy(self.d);a[self.t-7*s.DAY]['cs']*=4;self.assertGreater(self.feature(a)['cs'],e['cs'])
 def test_r7_r28_and_rv_mean_not_mean_log(self):
  e=self.feature();x=e['daily_inputs'];self.assertAlmostEqual(e['r7'],math.log(x['close'][-1]/x['close'][-8]),14);self.assertAlmostEqual(e['r28'],math.log(x['close'][-1]/x['close'][-29]),14)
  for n in (1,7,28):self.assertAlmostEqual(e['v'+str(n)],math.log(sum(x['rv'][-n:])/n),14)
 def test_zero_liquidity_is_valid_no_epsilon(self):
  for r in self.d.values():r['cs']=r['ar']=0.
  e=self.feature();self.assertTrue(e['valid']);self.assertEqual(e['cs'],0);self.assertEqual(e['ar'],0)
 def test_zero_current_rv_invalid_but_old_zero_can_average(self):
  a=copy.deepcopy(self.d);a[self.t-s.DAY]['rv']=0.;self.assertFalse(self.feature(a)['valid']);a=copy.deepcopy(self.d);a[self.t-7*s.DAY]['rv']=0.;self.assertTrue(self.feature(a)['valid'])
 def test_price_units_and_future_independence(self):
  a=self.feature()
  for r in self.d.values():r['close']*=1000000
  b=self.feature()
  for k in s.MARKET_COLS+('cs','ar'):self.assertAlmostEqual(a[k],b[k],13)
  for t,r in self.d.items():
   if t>=self.t:r.update(close=1e20,cs=10,ar=100,rv=20,valid=False)
  self.assertEqual(b,self.feature())
 def test_missing_quality_and_end_clock_invalidate_common_row(self):
  for kind in ('missing','valid','end','negative','nan'):
   a=copy.deepcopy(self.d);t=self.t-35*s.DAY
   if kind=='missing':del a[t]
   elif kind=='valid':a[t]['valid']=False
   elif kind=='end':a[t]['end']+=1
   elif kind=='negative':a[t]['ar']=-1
   else:a[t]['rv']=float('nan')
   e=self.feature(a);self.assertFalse(e['valid']);self.assertIn(t,e['bad_days'])
 def test_all_unconstrained_slopes_and_training_common_purge(self):
  rng=np.random.default_rng(8);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;ff.append(dict(source=t,valid=i!=100,**dict(zip(s.MARKET_COLS+('cs','ar'),rng.normal(size=7)))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);want=[f['source'] for f in ff[44:148] if f['valid']];self.assertEqual(a['training_weeks'],want);self.assertTrue(all(p['training_n']==len(want) for p in a['models'].values()));self.assertEqual(a['training_label_end'],ff[148]['source']);yy[ff[148]['source']]['value']=100;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()))
  x=rng.normal(size=(100,6));beta=np.array([.01,-.02,.005,.009,-.03,-.04]);p=s.fit(x,.004+x@beta,np.arange(100)*s.WEEK,x[0]);np.testing.assert_allclose(p['beta'],np.r_[.004,beta],atol=1e-12);self.assertFalse(p['constraint_active'])
 def test_positive_compensation_beta_and_same_inverse_events(self):
  for name in ('LQ_INFO','LQ_ALT'):
   self.assertTrue(s.decision(name,models(alt=.03),.5)[1])
   for beta in (0.,-.5):self.assertEqual(s.decision(name,models(beta=beta,alt=.03),.5)[:2],(.5,False))
  self.assertEqual(s.decision('LQ_INV',models(),.5)[:2],(-1.,True));self.assertEqual(s.decision('LQ_INV',models(beta=-1),.5)[:2],(.5,False));self.assertEqual(s.decision('LQ_INFO',models(info=-.03,risk=-.01),.5)[:2],(-1.,True))
 def test_cost_uncertainty_and_increment_sign(self):
  self.assertEqual(s.decision('LQ_INFO',models(info=.03,risk=.04),.5)[:2],(.5,False));self.assertEqual(s.decision('LQ_ALT',models(alt=.03,risk=.04),.5)[:2],(.5,False));self.assertEqual(s.threshold(.001,0),0);self.assertEqual(s.threshold(.03,.04),0);self.assertEqual(s.threshold(-.001,0),0);self.assertEqual(s.decision('LQ_RISK',models(risk=-.03,beta=-1),.5)[:2],(-1.,True))
 def test_rank_deficient_and_invalid_common_features(self):
  x=np.ones((70,8));self.assertIsNone(s.fit(x,np.arange(70),np.arange(70)*s.WEEK,x[0])['mu']);ff=[dict(source=self.t,valid=False)];yy={self.t:{'end':self.t+s.WEEK,'value':.1}};p=s.forecast_one(ff,yy,0);self.assertTrue(all(v['mu'] is None for v in p['models'].values()))
 def test_calendar_hac_not_compressed_gaps(self):
  rng=np.random.default_rng(12);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];M=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:M+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,dates),10/6*B@M@B,rtol=1e-10,atol=1e-12)
 def test_same_week_direction_partial_week_and_daily_risk(self):
  ff=[dict(source=self.t,valid=True)];pp=[dict(source=self.t,models=models(),training_n=70,training_label_end=self.t-s.WEEK)];a=s.schedule(self.m,ff,pp,'LQ_INFO',self.t+2*s.DAY,self.t+6*s.DAY);self.assertTrue(all(e['detail']['week_source']==self.t and e['weights']=={'BS':.5,'BP':0.} for e in a));b=s.schedule(self.m,ff,pp,'LQ_INFO',self.t+2*s.DAY,self.t+6*s.DAY,.1);self.assertTrue(all(e['weights']['BS']==.25 for e in b))
 def test_invalid_data_core_but_missing_risk_hold(self):
  models_none={k:pred(None,None) for k in s.MODELS};self.assertEqual(s.decision('LQ_INFO',models_none,.5)[:2],(.5,False));ff=[dict(source=self.t,valid=False)];pp=[dict(source=self.t,models=models_none,training_n=0,training_label_end=None)];self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'LQ_INFO',self.t,self.t+s.DAY)[0]['weights'])
 def test_constant_prices_fees_funding_delay(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'LQ_INFO',start,end,plan);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'LQ_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);self.assertEqual(first['source_time'],start);c=s.ledger.simulate(m,'LQ_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
