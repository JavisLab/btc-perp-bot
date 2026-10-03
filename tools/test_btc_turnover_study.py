"""Causal, unit, missing-data and decision boundaries of the preregistered transfer-share study."""
import copy,math,unittest
import numpy as np
import btc_turnover_study as s
from collect_btc_turnover_data import normalize
class FakeMarket:
 def __init__(self,t):
  self.rowmaps={'BS':{u-s.HOUR:[u-s.HOUR,100.,101.,99.,100*math.exp(i/900+.01*math.sin(i/4)),u-1] for i,u in enumerate(range(t-120*s.DAY,t+30*s.DAY,s.DAY))}}
 def observation(self,t,risk):return .5,min(1,risk/.4),.4
def sample(t):return {u:{'day':u,'end':u+s.DAY,'base_assumed_available':u+2*s.DAY,'valid':True,'adjusted':200.+i,'raw':2000.+2*i,'supply':1000000.+10*i} for i,u in enumerate(range(t-100*s.DAY,t+20*s.DAY,s.DAY))}
def pred(mu,se=0.,beta=.5):return {'mu':mu,'se':se,'beta':[0.,beta]}
def models(info=.03,raw=.01,adj=-.02,price=0.,beta=.5):return dict(zip(s.MODELS,[pred(info,beta=beta),pred(raw,beta=beta),pred(adj,beta=beta),pred(price)]))
class Tests(unittest.TestCase):
 def setUp(self):self.t=s.ms('2024-01-08');self.m=FakeMarket(self.t);self.d=sample(self.t)
 def feature(self,d=None,m=None,excluded=None,lag=0):return s.features(self.m if m is None else m,self.d if d is None else d,set() if excluded is None else excluded,lag,self.t,self.t+s.WEEK)[0]
 def test_Dplus2_completed28_and_lag7_all_inputs(self):
  a=self.feature();b=self.feature(lag=7);self.assertTrue(a['valid']);self.assertEqual(a['last_observation_day'],self.t-2*s.DAY);self.assertEqual(a['input_days'],list(range(self.t-29*s.DAY,self.t-s.DAY,s.DAY)));self.assertEqual(a['last_market_close'],self.t-s.DAY);self.assertEqual(a['last_assumed_available'],self.t);self.assertEqual(b['last_observation_day'],self.t-9*s.DAY);self.assertEqual(b['price_times'],[u-7*s.DAY for u in a['price_times']]);self.assertEqual(b['last_assumed_available'],self.t)
 def test_native_ratio_identity_not_average_ratios_or_supply(self):
  a=self.feature();A=sum(a['daily_inputs']['adjusted']);O=sum(a['daily_inputs']['raw']);S=a['daily_inputs']['supply'][-1];self.assertAlmostEqual(a['raw'],math.log(O/S),14);self.assertAlmostEqual(a['share'],math.log(A/O),14);self.assertAlmostEqual(a['adjusted'],a['raw']+a['share'],14);self.assertNotAlmostEqual(a['raw'],math.log(O/(sum(a['daily_inputs']['supply'])/28)),9)
 def test_price_boundaries_only_and_no_29_day_mask(self):
  a=self.feature();times=a['price_times'];self.assertEqual(times,[self.t-s.DAY,self.t-8*s.DAY,self.t-29*s.DAY]);self.assertAlmostEqual(a['r7'],math.log(a['price_closes'][0]/a['price_closes'][1]),14)
  del self.m.rowmaps['BS'][self.t-4*s.DAY-s.HOUR];self.assertEqual(a,self.feature())
 def test_missing_boundary_bad_close_time_and_no_trade(self):
  for kind in ('missing','clock','zero','nan','mask'):
   m=copy.deepcopy(self.m);u=self.t-8*s.DAY-s.HOUR
   if kind=='missing':del m.rowmaps['BS'][u]
   elif kind=='clock':m.rowmaps['BS'][u][5]+=1
   elif kind=='zero':m.rowmaps['BS'][u][4]=0.
   elif kind=='nan':m.rowmaps['BS'][u][4]=float('nan')
   e=self.feature(m=m,excluded={u} if kind=='mask' else set());self.assertFalse(e['valid'],kind)
 def test_missing_or_invalid_daily_inside_window_not_skipped(self):
  for kind in ('missing','quality','clock','available','zero','negative','nan','AgtO'):
   d=copy.deepcopy(self.d);u=self.t-15*s.DAY
   if kind=='missing':del d[u]
   elif kind=='quality':d[u]['valid']=False
   elif kind=='clock':d[u]['end']+=1
   elif kind=='available':d[u]['base_assumed_available']+=1
   elif kind=='AgtO':d[u]['adjusted']=2*d[u]['raw']
   else:d[u]['supply']={'zero':0.,'negative':-1.,'nan':float('nan')}[kind]
   e=self.feature(d=d);self.assertFalse(e['valid'],kind);self.assertEqual(e['bad_days'],[u])
 def test_future_inputs_and_prices_irrelevant(self):
  a=self.feature()
  for u,r in self.d.items():
   if u>self.t-2*s.DAY:r.update(adjusted=1e30,raw=1.,valid=False)
  for u,r in self.m.rowmaps['BS'].items():
   if u>=self.t-s.DAY:r[4]=1e40
  self.assertEqual(a,self.feature())
 def test_unit_scale_invariance_all_native_and_price(self):
  a=self.feature()
  for r in self.d.values():
   for k in ('adjusted','raw','supply'):r[k]*=1e8
  for r in self.m.rowmaps['BS'].values():r[4]*=10000
  b=self.feature()
  for k in s.FEATURE_COLS:self.assertAlmostEqual(a[k],b[k],13)
 def test_supply_day_stock_not_price_and_share_independent(self):
  a=self.feature();self.d[self.t-2*s.DAY]['supply']*=2;b=self.feature();self.assertEqual(a['share'],b['share']);self.assertAlmostEqual(a['raw']-b['raw'],math.log(2),14);self.assertAlmostEqual(a['adjusted']-b['adjusted'],math.log(2),14)
 def test_raw_and_estimate_proportional_share_unchanged(self):
  a=self.feature()
  for r in self.d.values():r['adjusted']*=2;r['raw']*=2
  b=self.feature();self.assertAlmostEqual(a['share'],b['share'],14);self.assertAlmostEqual(b['raw']-a['raw'],math.log(2),14)
 def test_parser_daily_duplicate_clock_sample_mismatch(self):
  t=self.t;row={'x':t//1000,'y':20.};A={'status':'ok','unit':'BTC','period':'day','values':[row]};O=copy.deepcopy(A);O['values'][0]['y']=100.;S={'data':[{'asset':'btc','time':'2024-01-08T00:00:00.000000000Z','SplyCur':'19000000'}]}
  def check(a,o,samples={}):return normalize(a,o,S,samples,t,t+s.DAY)[0][0]
  self.assertTrue(check(A,O)['valid'])
  for kind in ('duplicate','clock','zero','nan','AgtO','missing'):
   a=copy.deepcopy(A)
   if kind=='duplicate':a['values'].append(row)
   elif kind=='missing':a['values']=[]
   elif kind=='clock':a['values'][0]['x']+=1
   else:a['values'][0]['y']={'zero':0.,'nan':float('nan'),'AgtO':101.}[kind]
   e=check(a,O);self.assertFalse(e['valid'],kind);self.assertIsNone(e['supply'])
  q=copy.deepcopy(A);q['values'][0]['y']+=1;self.assertIn('adjusted_sample_difference',check(A,O,{'adjusted':q})['reasons'])
 def test_common_training_rows_purge_and_minimum(self):
  rng=np.random.default_rng(8);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;x=rng.normal(size=4);ff.append(dict(source=t,valid=i!=100,**dict(zip(('r7','r28','raw','share'),x)),adjusted=x[2]+x[3]));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);want=[f['source'] for f in ff[44:148] if f['valid']];self.assertEqual(a['training_weeks'],want);self.assertTrue(all(p['training_n']==len(want) for p in a['models'].values()));self.assertEqual(a['training_label_end'],ff[148]['source']);yy[ff[148]['source']]['value']=100;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()))
 def test_unconstrained_negative_beta_retained_not_changed_to_positive(self):
  rng=np.random.default_rng(81);x=rng.normal(size=(104,4));beta=np.array([.01,-.02,.03,-.05]);p=s.fit(x,.003+x@beta,np.arange(104)*s.WEEK,x[0]);np.testing.assert_allclose(p['beta'],np.r_[.003,beta],atol=1e-12);self.assertFalse(p['constraint_active'])
 def test_positive_share_same_inverse_events_and_no_flip(self):
  self.assertEqual(s.decision('NV_INFO',models(),.5)[:2],(1.,True));self.assertEqual(s.decision('NV_INV',models(),.5)[:2],(-1.,True))
  for beta in (0.,-.5):
   for name in ('NV_INFO','NV_INV','NV_RAW','NV_ADJ'):self.assertEqual(s.decision(name,models(beta=beta),.5)[:2],(.5,False))
  self.assertEqual(s.decision('NV_INFO',models(info=-.03,raw=-.01),.5)[:2],(-1.,True))
 def test_raw_adj_require_own_positive_beta_but_not_info_delta(self):
  p=models(info=.04,raw=.06,adj=.03);self.assertEqual(s.decision('NV_INFO',p,.5)[:2],(.5,False))
  for name in ('NV_RAW','NV_ADJ'):self.assertEqual(s.decision(name,p,.5)[:2],(1.,True))
  p['NV_INFO']=pred(None,None);self.assertTrue(s.decision('NV_RAW',p,.5)[1]);self.assertTrue(s.decision('NV_ADJ',p,.5)[1]);self.assertFalse(s.decision('NV_INV',p,.5)[1])
 def test_cost_uncertainty_increment_sign_and_price_independent(self):
  self.assertEqual(s.decision('NV_INFO',models(info=.03,raw=.04),.5)[:2],(.5,False));self.assertEqual(s.decision('NV_INFO',models(info=.03,raw=.03),.5)[:2],(.5,False));self.assertEqual(s.threshold(.001,0),0);self.assertEqual(s.threshold(.03,.04),0);self.assertEqual(s.threshold(-.001,0),0);self.assertEqual(s.decision('NV_PRICE',models(price=-.03,beta=-1),.5)[:2],(-1.,True))
 def test_rank_deficient_invalid_all_models_common_row(self):
  x=np.ones((70,4));self.assertIsNone(s.fit(x,np.arange(70),np.arange(70)*s.WEEK,x[0])['mu']);ff=[dict(source=self.t,valid=False)];yy={self.t:{'end':self.t+s.WEEK,'value':.1}};p=s.forecast_one(ff,yy,0);self.assertTrue(all(v['mu'] is None for v in p['models'].values()))
 def test_calendar_hac_not_compressed_gaps(self):
  rng=np.random.default_rng(12);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];M=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:M+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,dates),10/6*B@M@B,rtol=1e-10,atol=1e-12)
 def test_partial_week_same_direction_daily_risk(self):
  ff=[dict(source=self.t,valid=True)];pp=[dict(source=self.t,models=models(),training_n=70,training_label_end=self.t-s.WEEK)];a=s.schedule(self.m,ff,pp,'NV_INFO',self.t+2*s.DAY,self.t+6*s.DAY);self.assertTrue(all(e['detail']['week_source']==self.t and e['weights']=={'BS':.5,'BP':0.} for e in a));b=s.schedule(self.m,ff,pp,'NV_INFO',self.t+2*s.DAY,self.t+6*s.DAY,.1);self.assertTrue(all(e['weights']['BS']==.25 for e in b))
 def test_invalid_data_core_missing_risk_hold(self):
  mm={k:pred(None,None) for k in s.MODELS};self.assertEqual(s.decision('NV_INFO',mm,.5)[:2],(.5,False));ff=[dict(source=self.t,valid=False)];pp=[dict(source=self.t,models=mm,training_n=0,training_label_end=None)];self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'NV_INFO',self.t,self.t+s.DAY)[0]['weights'])
 def test_constant_prices_fees_funding_delay(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'NV_INFO',start,end,plan);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'NV_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);self.assertEqual(first['source_time'],start);c=s.ledger.simulate(m,'NV_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])

if __name__=='__main__':unittest.main()
