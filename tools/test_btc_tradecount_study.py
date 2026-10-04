"""Causal trade-count increment and independent synthetic accounting boundaries, pre-PNL."""
import copy,math,unittest
from types import SimpleNamespace
import numpy as np
import btc_tradecount_study as s
from prepare_btc_tradecount_data import aggregate
D=s.DAY;H=s.HOUR

def fixture(n=710):
 f=[];v=[];c=[]
 for i in range(n):
  f.append({'day':i*D,'end':(i+1)*D,'valid':True,'quote':1e8*math.exp(.21*math.sin(i/4)+i*.0001),'net':.025+.02*math.sin(i/9),'gross':.12+.05*math.sin(i/7)})
  v.append({'day':i*D,'end':(i+1)*D,'valid':True,'rv':math.exp(-8+.4*math.sin(i/5)+.15*math.cos(i/19))})
  c.append({'day':i*D,'end':(i+1)*D,'valid':True,'count':100000+round(25000*math.cos(i/3)+19000*math.sin(i/23))})
 return f,v,c

def hourly():return {'day':0,'end':D,'valid':True,'hours':[{'time':i*H,'end':(i+1)*H-1,'valid':True,'trades':'17'} for i in range(24)]}
class Observation:
 def observation(self,t,risk=.2):return (-2/3,min(1,risk/.4),.4)
def market():
 rows={};marks={}
 for k in ('BS','BP'):
  rows[k]={t:[t,100000.,110000.,90000.,100000.,t+H-1] for t in range(0,3*D,H)};marks[k]={t:r.copy() for t,r in rows[k].items()}
 return SimpleNamespace(rowmaps=rows,markmaps=marks,funds={'BP':{D:[D,8,.001,D+47],2*D:[2*D,8,.001,2*D+23]}})
def plan(weights):return [{'source_time':t,'weights':{'BS':0.,'BP':w},'hedge':False,'rebalance':True,'detail':{}} for t,w in weights]
class TradeCountTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.flow,cls.rv,cls.counts=fixture();cls.ff=s.features(cls.flow,cls.rv,cls.counts)
 def test_integer_aggregate_and_prior_mask(self):
  a=hourly();self.assertEqual(aggregate(a)['count'],408);self.assertTrue(aggregate(a)['valid']);a['valid']=False;self.assertFalse(aggregate(a)['valid'])
 def test_noninteger_nan_nonpositive_are_invalid(self):
  for val in ('1.5','NaN','0','-2'):
   a=hourly();a['hours'][3]['trades']=val;self.assertFalse(aggregate(a)['valid'])
 def test_exact_grid_clock_and_duplicate(self):
  a=hourly();a['hours'].pop();self.assertFalse(aggregate(a)['valid']);a=hourly();a['hours'][4]['end']+=1;self.assertFalse(aggregate(a)['valid']);a=hourly();a['hours'].append(a['hours'][0]);self.assertRaises(ValueError,aggregate,a)
 def test_same_money_pressure_distinct_count(self):
  c=copy.deepcopy(self.counts);c[600]['count']*=2;e=s.features(self.flow,self.rv,c)[600];self.assertEqual(e['features'][:6],self.ff[600]['features'][:6]);self.assertAlmostEqual(e['features'][6]-self.ff[600]['features'][6],math.log(2))
 def test_count_unit_scale_invariant(self):
  c=[dict(x,count=x['count']*7) for x in self.counts];np.testing.assert_allclose(s.features(self.flow,self.rv,c)[600]['features'],self.ff[600]['features'],atol=1e-14)
 def test_completed_clocks(self):
  e=self.ff[600];self.assertEqual(e['count_day'],600*D);self.assertEqual(e['count_days'],list(range(572*D,601*D,D)));self.assertEqual(e['flow_days'],e['count_days']);self.assertEqual(e['rv_days'],list(range(579*D,601*D,D)));self.assertEqual(e['truth_end'],602*D)
 def test_current_count_excluded_from_denominator(self):
  x=math.log(self.counts[600]['count']/(sum(c['count'] for c in self.counts[572:600])/28));self.assertAlmostEqual(self.ff[600]['features'][-1],x)
 def test_delay7_only_count_not_pressure_risk_target(self):
  e=s.features(self.flow,self.rv,self.counts,7)[600];self.assertEqual(e['features'][:6],self.ff[600]['features'][:6]);self.assertEqual(e['flow_day'],600*D);self.assertEqual(e['count_day'],593*D);self.assertEqual(e['truth'],self.ff[600]['truth']);self.assertAlmostEqual(e['features'][-1],math.log(self.counts[593]['count']/(sum(x['count'] for x in self.counts[565:593])/28)))
 def test_future_count_cannot_change_current(self):
  c=copy.deepcopy(self.counts)
  for x in c[601:]:x['count']=10**40
  self.assertEqual(s.features(self.flow,self.rv,c)[600],self.ff[600])
 def test_future_pressure_cannot_change_current(self):
  f=copy.deepcopy(self.flow)
  for x in f[601:]:x.update(quote=1e99,net=.9,gross=1.)
  self.assertEqual(s.features(f,self.rv,self.counts)[600],self.ff[600])
 def test_future_target_cannot_change_fit(self):
  v=copy.deepcopy(self.rv)
  for x in v[601:]:x['rv']=1e9
  self.assertEqual(s.forecast_one(self.ff,600),s.forecast_one(s.features(self.flow,v,self.counts),600))
 def test_count_missing_zero_bool_fraction_clock(self):
  for val in (0,True,12.5,None):
   c=copy.deepcopy(self.counts);c[600]['count']=val;self.assertFalse(s.features(self.flow,self.rv,c)[600]['valid'])
  c=copy.deepcopy(self.counts);c[572]['end']+=1;self.assertFalse(s.features(self.flow,self.rv,c)[600]['valid']);c=copy.deepcopy(self.counts);c.pop(581);self.assertFalse(s.features(self.flow,self.rv,c)[600]['valid'])
 def test_invalid_pressure_or_rv_not_rescued(self):
  f=copy.deepcopy(self.flow);f[572]['valid']=False;self.assertFalse(s.features(f,self.rv,self.counts)[600]['valid']);v=copy.deepcopy(self.rv);v[579]['rv']=0;self.assertFalse(s.features(self.flow,v,self.counts)[600]['valid'])
 def test_common_training_and_min300(self):
  p=s.forecast_one(self.ff,600);self.assertEqual(p['training_days'],[x['source'] for x in self.ff[235:600]]);self.assertEqual(p['training_n'],365);self.assertEqual(p['training_label_end'],self.ff[600]['source']);self.assertTrue(all(p['models'][k]['n']==365 for k in s.COLS));self.assertTrue(all(s.forecast_one(self.ff,320)['models'][k]['prediction'] is None for k in s.COLS))
 def test_target_one_millisecond_late_is_not_training(self):
  f=copy.deepcopy(self.ff);f[599]['truth_end']=f[600]['source']+1;p=s.forecast_one(f,600);self.assertEqual(p['training_n'],364);self.assertNotIn(f[599]['source'],p['training_days'])
 def test_control_columns_remove_only_new_information(self):
  self.assertEqual(s.COLS['TC_INFO'],(0,1,2,3,4,5,6));self.assertEqual(s.COLS['TC_FLOW'],(0,1,2,3,4,5));self.assertEqual(s.COLS['TC_COUNT'],(0,1,2,6));self.assertEqual(s.COLS['TC_HAR'],(0,1,2))
 def test_negative_coefficient_and_independent_normal_equations(self):
  rng=np.random.default_rng(717);x=rng.normal(size=(340,7));y=2+x@np.array([1,-1,.4,1,.3,.2,-2]);p=s.fit(x,y,np.zeros(7));X=np.c_[np.ones(len(x)),x];np.testing.assert_allclose(p['beta'],np.linalg.solve(X.T@X,X.T@y),atol=2e-13);self.assertAlmostEqual(p['beta'][-1],-2)
 def test_smearing_training_not_future(self):
  rng=np.random.default_rng(884);x=rng.normal(size=(330,2));y=.3+x[:,0]+rng.normal(size=330)*.4;p=s.fit(x,y,np.zeros(2));self.assertAlmostEqual(p['smearing'],np.exp(np.array(p['residuals'])).mean());self.assertAlmostEqual(p['prediction'],math.exp(p['log_point'])*p['smearing'])
 def test_inverse_risk_and_floor_overflow(self):
  p=s.forecast_one(self.ff,600);a,b=p['models']['TC_INFO']['prediction'],p['models']['TC_FLOW']['prediction'];self.assertAlmostEqual(p['models']['TC_INV']['prediction'],b*b/a);self.assertIsNone(s.fit(np.ones((310,2)),np.zeros(310),np.ones(2))['prediction']);self.assertIsNone(s.restore(10000,0)['prediction']);self.assertTrue(s.restore(-1000,0)['floor'])
 def test_only_perp_signed_direction_preserved(self):
  p=s.forecast_one(self.ff,600);p['models']['TC_TREND']={'prediction':.16/365,'floor':False};r=s.schedule(Observation(),[self.ff[600]],[p],'TC_INFO',600*D,602*D)[0];self.assertEqual(r['weights']['BS'],0);self.assertEqual(r['detail']['signal'],-2/3);self.assertLess(r['weights']['BP'],0);self.assertLessEqual(abs(r['weights']['BP']),1)
 def test_missing_model_holds(self):
  p=s.forecast_one(self.ff,3);r=s.schedule(Observation(),[self.ff[3]],[p],'TC_INFO',0,6*D)[0];self.assertIsNone(r['weights'])
 def test_long_short_funding_and_final_exit(self):
  x=s.ledger.simulate(market(),'TC_INFO',0,3*D,plan([(0,.5),(D,-.5)]));fund=[e for e in x['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertLess(fund[0]['cashflow'],0);self.assertGreater(fund[1]['cashflow'],0);self.assertEqual(fund[0]['observed_time'],D+47);self.assertTrue(all(e['instrument']=='BP' for e in x['events']));self.assertEqual(x['events'][-1]['reason'],'end_of_experiment');self.assertAlmostEqual(x['metrics']['initial']+x['metrics']['gross_pnl']+x['metrics']['funding']-x['metrics']['fees']-x['metrics']['impact'],x['metrics']['equity'])
 def test_delay_and_quantity_minimum(self):
  x=s.ledger.simulate(market(),'TC_INFO',0,3*D,plan([(0,.5)]),delay=1);self.assertEqual(x['events'][0]['time'],2*H);self.assertEqual(x['events'][0]['source_time'],0);self.assertAlmostEqual(x['events'][0]['position']/.001,round(x['events'][0]['position']/.001));z=s.ledger.simulate(market(),'TC_INFO',0,3*D,plan([(0,.01)]));self.assertEqual(z['metrics']['fills'],0)
 def test_missing_execution_does_not_invent_fill(self):
  m=market();m.rowmaps['BP'].pop(H);x=s.ledger.simulate(m,'TC_INFO',0,3*D,plan([(0,.5)]));self.assertEqual(x['metrics']['fills'],0);self.assertEqual(x['skips'][0]['reason'],'missing_execution_bar')
 def test_adverse_margin_both_directions(self):
  a=s.ledger.simulate(market(),'TC_INFO',0,3*D,plan([(0,.5)]));b=s.ledger.simulate(market(),'TC_INFO',0,3*D,plan([(0,-.5)]));self.assertIsNotNone(a['metrics']['min_adverse_margin_ratio']);self.assertIsNotNone(b['metrics']['min_adverse_margin_ratio']);self.assertNotEqual(a['metrics']['min_adverse_margin_ratio'],b['metrics']['min_adverse_margin_ratio'])
if __name__=='__main__':unittest.main()
