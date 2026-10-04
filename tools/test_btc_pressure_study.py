"""Synthetic chronology, economic-control, and pure-futures boundaries before history."""
import copy,math,unittest
from types import SimpleNamespace
import numpy as np
import btc_pressure_study as s
from collect_btc_pressure_data import aggregate

D=s.DAY;H=s.HOUR

def fixture(n=710):
 flow=[];rv=[]
 for i in range(n):
  flow.append({'day':i*D,'end':(i+1)*D,'valid':True,'quote':1e8*math.exp(.21*math.sin(i/4)+i*.0001),'net':.025+.02*math.sin(i/9),'gross':.12+.05*math.sin(i/7)})
  rv.append({'day':i*D,'end':(i+1)*D,'valid':True,'rv':math.exp(-8+.4*math.sin(i/5)+.15*math.cos(i/19))})
 return flow,rv

class Observation:
 def observation(self,t,risk=.2):return (-2/3,min(1,risk/.4),.4)

def market():
 rows={};marks={}
 for k in ('BS','BP'):
  rows[k]={t:[t,100000.,110000.,90000.,100000.,t+H-1] for t in range(0,3*D,H)};marks[k]={t:r.copy() for t,r in rows[k].items()}
 return SimpleNamespace(rowmaps=rows,markmaps=marks,funds={'BP':{D:[D,8,.001,D+47],2*D:[2*D,8,.001,2*D+23]}})

def plan(weights):return [{'source_time':t,'weights':{'BS':0.,'BP':w},'hedge':False,'rebalance':True,'detail':{}} for t,w in weights]

class PressureTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.flow,cls.rv=fixture();cls.ff=s.features(cls.flow,cls.rv)
 def test_gross_cancellation_not_daily_net(self):
  r=[{'quote':'100','buy_quote':'100','valid':True} if i%2 else {'quote':'100','buy_quote':'0','valid':True} for i in range(24)];e=aggregate(r,True);self.assertEqual((e['net'],e['gross']),(0,1))
 def test_balanced_and_scale_and_sign(self):
  r=[{'quote':'100','buy_quote':str(i*4),'valid':True} for i in range(24)];a=aggregate(r,True);b=aggregate([dict(x,quote='700',buy_quote=str(float(x['buy_quote'])*7)) for x in r],True);c=aggregate([dict(x,buy_quote=str(100-float(x['buy_quote']))) for x in r],True)
  self.assertAlmostEqual(a['gross'],b['gross']);self.assertAlmostEqual(a['gross'],c['gross']);self.assertAlmostEqual(a['net'],c['net']);self.assertAlmostEqual(a['signed'],-c['signed']);self.assertEqual(aggregate([dict(x,buy_quote='50') for x in r],True)['gross'],0)
 def test_completed_clocks(self):
  e=self.ff[600];self.assertEqual(e['flow_day'],600*D);self.assertEqual(e['flow_days'],list(range(572*D,601*D,D)));self.assertEqual(e['rv_days'],list(range(579*D,601*D,D)));self.assertEqual(e['truth_end'],602*D)
 def test_29_flow_days_not_current_in_volume_denominator(self):
  e=self.ff[600];expected=math.log(self.flow[600]['quote']/(sum(r['quote'] for r in self.flow[572:600])/28));self.assertAlmostEqual(e['features'][3],expected)
 def test_delay7_only_moves_flow(self):
  e=s.features(self.flow,self.rv,7)[600];self.assertEqual(e['features'][:3],self.ff[600]['features'][:3]);self.assertEqual(e['flow_day'],593*D);self.assertEqual(e['truth'],self.ff[600]['truth'])
 def test_future_flow_cannot_change_current(self):
  f=copy.deepcopy(self.flow)
  for x in f[601:]:x.update(quote=1e99,net=.9,gross=1.)
  self.assertEqual(s.features(f,self.rv)[600],self.ff[600])
 def test_future_label_cannot_change_fit(self):
  rv=copy.deepcopy(self.rv)
  for x in rv[601:]:x['rv']=1e9
  a=s.forecast_one(self.ff,600);b=s.forecast_one(s.features(self.flow,rv),600);self.assertEqual(a,b)
 def test_bad_flow_and_rv_are_common_missing(self):
  f=copy.deepcopy(self.flow);f[572]['valid']=False;self.assertFalse(s.features(f,self.rv)[600]['valid']);rv=copy.deepcopy(self.rv);rv[579]['rv']=0;self.assertFalse(s.features(self.flow,rv)[600]['valid'])
 def test_bad_nesting_and_boundary_end(self):
  f=copy.deepcopy(self.flow);f[600]['net']=.9;f[600]['gross']=.1;self.assertFalse(s.features(f,self.rv)[600]['valid']);f=copy.deepcopy(self.flow);f[600]['end']+=1;self.assertFalse(s.features(f,self.rv)[600]['valid'])
 def test_365_common_and_min300(self):
  p=s.forecast_one(self.ff,600);self.assertEqual(p['training_days'],[x['source'] for x in self.ff[235:600]]);self.assertEqual(p['training_n'],365);self.assertEqual(p['training_label_end'],self.ff[600]['source']);self.assertTrue(all(p['models'][k]['n']==365 for k in s.COLS));self.assertTrue(all(s.forecast_one(self.ff,320)['models'][k]['prediction'] is None for k in s.COLS))
 def test_future_training_label_removed(self):
  f=copy.deepcopy(self.ff);f[599]['truth_end']=f[600]['source']+1;p=s.forecast_one(f,600);self.assertEqual(p['training_n'],364);self.assertNotIn(f[599]['source'],p['training_days'])
 def test_unconstrained_negative_and_inverse(self):
  rng=np.random.default_rng(717);x=rng.normal(size=(340,6));y=2+x@np.array([1,-1,.4,1,.3,-2]);p=s.fit(x,y,np.zeros(6));self.assertAlmostEqual(p['beta'][-1],-2);r=s.forecast_one(self.ff,600);a,b=r['models']['TP_INFO']['prediction'],r['models']['TP_NET']['prediction'];self.assertAlmostEqual(r['models']['TP_INV']['prediction'],b*b/a)
 def test_rank_overflow_floor(self):
  self.assertIsNone(s.fit(np.ones((310,2)),np.zeros(310),np.ones(2))['prediction']);self.assertIsNone(s.restore(10000,0)['prediction']);self.assertTrue(s.restore(-1000,0)['floor'])
 def test_only_perp_score_preserved(self):
  p=s.forecast_one(self.ff,600);p['models']['TP_TREND']={'prediction':.16/365,'floor':False};r=s.schedule(Observation(),[self.ff[600]],[p],'TP_INFO',600*D,602*D)[0];self.assertEqual(r['weights']['BS'],0);self.assertLess(r['weights']['BP'],0);self.assertEqual(r['detail']['signal'],-2/3);self.assertLessEqual(abs(r['weights']['BP']),1)
 def test_missing_model_holds(self):
  p=s.forecast_one(self.ff,3);r=s.schedule(Observation(),[self.ff[3]],[p],'TP_INFO',0,6*D)[0];self.assertIsNone(r['weights'])
 def test_long_short_funding_and_final_exit(self):
  x=s.ledger.simulate(market(),'TP_INFO',0,3*D,plan([(0,.5),(D,-.5)]));fund=[e for e in x['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertLess(fund[0]['cashflow'],0);self.assertGreater(fund[1]['cashflow'],0);self.assertEqual(fund[0]['observed_time'],D+47);self.assertTrue(all(e['instrument']=='BP' for e in x['events']));self.assertEqual(x['events'][-1]['reason'],'end_of_experiment');self.assertAlmostEqual(x['metrics']['initial']+x['metrics']['gross_pnl']+x['metrics']['funding']-x['metrics']['fees']-x['metrics']['impact'],x['metrics']['equity'])
 def test_frozen_delay_and_quantity_minimum(self):
  x=s.ledger.simulate(market(),'TP_INFO',0,3*D,plan([(0,.5)]),delay=1);self.assertEqual(x['events'][0]['time'],2*H);self.assertEqual(x['events'][0]['source_time'],0);self.assertAlmostEqual(x['events'][0]['position']/.001,round(x['events'][0]['position']/.001));z=s.ledger.simulate(market(),'TP_INFO',0,3*D,plan([(0,.01)]));self.assertEqual(z['metrics']['fills'],0)
 def test_missing_execution_does_not_invent_fill(self):
  m=market();m.rowmaps['BP'].pop(H);x=s.ledger.simulate(m,'TP_INFO',0,3*D,plan([(0,.5)]));self.assertEqual(x['metrics']['fills'],0);self.assertEqual(x['skips'][0]['reason'],'missing_execution_bar')
 def test_margin_uses_long_low_and_short_high(self):
  a=s.ledger.simulate(market(),'TP_INFO',0,3*D,plan([(0,.5)]));b=s.ledger.simulate(market(),'TP_INFO',0,3*D,plan([(0,-.5)]));self.assertIsNotNone(a['metrics']['min_adverse_margin_ratio']);self.assertIsNotNone(b['metrics']['min_adverse_margin_ratio']);self.assertNotEqual(a['metrics']['min_adverse_margin_ratio'],b['metrics']['min_adverse_margin_ratio'])
if __name__=='__main__':unittest.main()
