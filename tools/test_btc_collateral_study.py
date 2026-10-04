"""Causal cross-contract funding difference, delayed-source boundary and pure-perp tests."""
import copy,json,math,unittest
from types import SimpleNamespace
import numpy as np
import btc_collateral_study as s
from btc_continuity_study import hac
from collect_btc_collateral_data import normalize
from verify_btc_collateral_study import independent_fit
D=s.DAY;H=s.HOUR;T=s.ms('2024-01-08')
def fixture():
 m=SimpleNamespace(rowmaps={'BP':{u-H:[u-H,100.,102.,99.,100*math.exp(.001*i+.01*math.sin(i)),u-1] for i,u in enumerate(range(T-120*D,T+30*D,D))}},funds={'BP':{u:[u,8,.0001+1e-7*i,u+47] for i,u in enumerate(range(T-120*D,T+30*D,8*H))}},observation=lambda t,risk:(-2/3,min(1,risk/.4),.4))
 raw=[{'symbol':'BTCUSD_PERP','fundingTime':u+23,'fundingRate':str(.0002+1e-6*i),'markPrice':'','rateType':'Regular'} for i,u in enumerate(range(T-120*D,T+30*D,8*H))];return m,normalize(json.dumps(raw).encode(),T-120*D,T+30*D)
def pred(mu=.03,beta=-.4,se=0):return {'mu':mu,'se':se,'beta':[0,beta]}
def models():return {'CD_INFO':pred(),'CD_FUND':pred(.01,-.4),'CD_COIN':pred(-.02),'CD_PRICE':pred(.02,.5)}
def market():
 rows={};marks={}
 for k in ('BS','BP'):
  rows[k]={t:[t,100000.,110000.,90000.,100000.,t+H-1] for t in range(0,3*D,H)};marks[k]={t:r.copy() for t,r in rows[k].items()}
 return SimpleNamespace(rowmaps=rows,markmaps=marks,funds={'BP':{D:[D,8,.001,D+47],2*D:[2*D,8,.001,2*D+23]}})
def plan(weights):return [{'source_time':t,'weights':{'BS':0.,'BP':w},'hedge':False,'rebalance':True,'detail':{}} for t,w in weights]

class CollateralTests(unittest.TestCase):
 def setUp(self):self.m,self.c=fixture()
 def feature(self,lag=0):return s.features(self.m,self.c,lag,T,T+s.WEEK)[0]
 def test_exact_actual_clock_and_dimensionless_difference(self):
  a=self.feature();self.assertTrue(a['valid']);self.assertEqual(len(a['coin_rows']),21);self.assertTrue(all(T-s.WEEK<=r['time']<T for r in a['coin_rows']));self.assertAlmostEqual(a['coin'],365/7*sum(float(r['rate']) for r in a['coin_rows']));self.assertAlmostEqual(a['spread'],a['coin']-a['funding'])
 def test_new_information_not_same_UM_or_price(self):
  a=self.feature();next(r for r in self.c if r['time']==T-8*H+23)['rate']='.005';b=self.feature();self.assertEqual(a['funding'],b['funding']);self.assertEqual(a['r7'],b['r7']);self.assertNotEqual(a['spread'],b['spread'])
 def test_future_coin_UM_price_cannot_change_current(self):
  a=copy.deepcopy(self.feature())
  for r in self.c:
   if r['time']>=T:r['rate']='100'
  for r in self.m.funds['BP'].values():
   if r[3]>=T:r[2]=100.
  for u,r in self.m.rowmaps['BP'].items():
   if u>=T:r[4]=1e20
  self.assertEqual(a,self.feature())
 def test_exact_T_and_Tplus_excluded_Tminus_included(self):
  target=next(r for r in self.c if r['time']==T-8*H+23);target['time']=T;self.assertFalse(self.feature()['coin_valid']);target['time']=T+1;self.assertFalse(self.feature()['coin_valid']);target['time']=T-1;self.assertTrue(self.feature()['coin_valid'])
 def test_delayed_spread_not_current_funding_or_price(self):
  a,b=self.feature(),self.feature(7);self.assertEqual(a['funding_rows'],b['funding_rows']);self.assertEqual(a['price_times'],b['price_times']);self.assertEqual(a['funding'],b['funding']);self.assertEqual(b['collateral_cutoff'],T-7*D);self.assertTrue(all(r['time']<T-7*D for r in b['coin_rows']));self.assertTrue(all(r[3]<T-7*D for r in b['reference_funding_rows']));self.assertAlmostEqual(b['spread'],b['coin']-365/7*sum(r[2] for r in b['reference_funding_rows']))
 def test_future_of_delayed_cutoff_does_not_change_spread(self):
  a=self.feature(7)
  for r in self.c:
   if r['time']>=T-7*D:r['rate']='1e8'
  b=self.feature(7);self.assertEqual(a,b)
 def test_missing_coin_no_interpolation_or_zero(self):
  self.c=[r for r in self.c if r['time']!=T-8*H+23];a=self.feature();self.assertFalse(a['valid']);self.assertIsNone(a['coin']);self.assertIsNone(a['spread']);self.assertTrue(a['funding_valid'])
 def test_duplicate_timestamp_hardfail(self):
  self.c.append(copy.deepcopy(self.c[-1]))
  with self.assertRaises(AssertionError):self.feature()
 def test_multiple_bucket_not_treated_as_one(self):
  r=copy.deepcopy(next(r for r in self.c if r['time']==T-8*H+23));r['time']+=1;self.c.append(r);self.assertFalse(self.feature()['coin_valid'])
 def test_irregular_period_invalid_not_clipped(self):
  r=next(r for r in self.c if r['time']==T-8*H+23);r['valid']=False;self.assertFalse(self.feature()['valid'])
 def test_zero_negative_rate_valid(self):
  for r in self.c:r['rate']='0'
  a=self.feature();self.assertTrue(a['valid']);self.assertEqual(a['coin'],0.)
  for r in self.c:r['rate']='-.001'
  self.assertLess(self.feature()['coin'],0)
 def test_raw_empty_mark_is_not_missing_funding(self):
  raw={'symbol':'BTCUSD_PERP','fundingTime':T+23,'fundingRate':'0.0000000000000000000123456789','markPrice':''};n=normalize(json.dumps([raw]).encode(),T,T+D);self.assertTrue(n[0]['valid']);self.assertEqual(n[0]['rate'],'1.23456789E-20');self.assertEqual(normalize(b'[]',T,T+D),[])
 def test_raw_duplicate_outside_wrong_symbol_nonfinite(self):
  r={'symbol':'BTCUSD_PERP','fundingTime':T,'fundingRate':'0.0001'}
  for arr in ([r,r],[dict(r,fundingTime=T-1)],[dict(r,symbol='OTHER')],[dict(r,fundingTime=float(T))],[dict(r,fundingRate='NaN')]):
   with self.assertRaises(AssertionError):normalize(json.dumps(arr).encode(),T,T+D)
 def test_current_funding_actual_clock_missing_and_duplicate(self):
  a=self.feature();self.assertNotIn(self.m.funds['BP'][T],a['funding_rows']);self.m.funds['BP'][T-8*H][3]=T+1;self.assertFalse(self.feature()['funding_valid']);self.m,self.c=fixture();self.m.funds['BP'][T-8*H+1]=[T-8*H+1,8,.01,T-8*H+1];self.assertFalse(self.feature()['valid'])
 def test_invalid_price_boundary_no_fill(self):
  self.m.rowmaps['BP'][T-10*D-H][5]+=1;self.assertFalse(self.feature()['valid'])
 def test_purge_common_training_and_future_labels(self):
  rng=np.random.default_rng(901);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;vals=rng.normal(size=5);ff.append(dict(source=t,valid=i!=100,**dict(zip(s.FEATURE_COLS,vals))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);self.assertEqual(a['training_weeks'],[f['source'] for f in ff[44:148] if f['valid']]);self.assertTrue(all(p['training_n']==103 for p in a['models'].values()));yy[ff[148]['source']]['value']=1e20;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()));ff[149]['valid']=False;self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,149)['models'].values()))
 def test_unrestricted_and_independent_fit_not_beta_clipping(self):
  rng=np.random.default_rng(51);x=rng.normal(size=(104,5));b=np.array([1,2,-.3,.4,.7]);dates=np.arange(104)*s.WEEK;y=.001+x@b+rng.normal(size=104)*.01;p=s.fit(x,y,dates,x[0]);q=independent_fit(np.c_[np.ones(104),x],y,dates,np.r_[1,x[0]],False);self.assertGreater(p['beta'][-1],0);np.testing.assert_allclose(p['beta'],q['beta'],atol=1e-12);np.testing.assert_allclose(p['covariance'],q['covariance'],atol=1e-12);self.assertFalse(p['constraint_active']);self.assertIsNone(s.fit(np.ones((70,5)),np.ones(70),np.arange(70)*s.WEEK,np.ones(5))['mu'])
 def test_negative_spread_increment_and_inverse(self):
  p=models();self.assertEqual(s.decision('CD_INFO',p,-.5)[:2],(1.,True));self.assertEqual(s.decision('CD_INV',p,-.5)[:2],(-1.,True));p['CD_INFO']['beta'][-1]=0;self.assertEqual(s.decision('CD_INFO',p,-.5)[:2],(-.5,False));p=models();p['CD_FUND']['mu']=.04;self.assertFalse(s.decision('CD_INFO',p,-.5)[1]);self.assertTrue(s.decision('CD_FUND',p,-.5)[1]);p['CD_FUND']['beta'][-1]=.1;self.assertFalse(s.decision('CD_FUND',p,-.5)[1]);self.assertTrue(s.decision('CD_COIN',p,-.5)[1]);p['CD_COIN']['beta'][-1]=.1;self.assertFalse(s.decision('CD_COIN',p,-.5)[1])
 def test_symmetric_strict_cost_se_and_signed_fallback(self):
  self.assertEqual(s.threshold(s.GATE,0),0);self.assertEqual(s.threshold(-s.GATE,0),0);self.assertEqual(s.threshold(.03,.04),0);p=models();p['CD_INFO']['mu']=None;self.assertTrue(s.decision('CD_COIN',p,-.5)[1]);self.assertTrue(s.decision('CD_PRICE',p,-.5)[1]);self.assertEqual(s.decision('CD_INFO',p,-.5)[:2],(-.5,False));self.assertEqual(s.decision('CD_TREND',p,-.5)[:2],(-.5,False))
 def test_perp_both_directions_week_and_risk_hold(self):
  pp=[{'source':T,'models':models(),'training_n':80,'training_label_end':T-s.WEEK}];ff=[self.feature()];a=s.schedule(self.m,ff,pp,'CD_INFO',T+2*D,T+6*D);self.assertTrue(all(e['weights']=={'BS':0.,'BP':.5} for e in a));b=s.schedule(self.m,ff,pp,'CD_INV',T,T+D,.1);self.assertEqual(b[0]['weights'],{'BS':0.,'BP':-.25});self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'CD_INFO',T,T+D)[0]['weights'])
 def test_hac_calendar_gap_not_observation_gap(self):
  rng=np.random.default_rng(13);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];A=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:A+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(hac(Z,res,dates),10/6*B@A@B,rtol=1e-10,atol=1e-12)
 def test_long_short_funding_and_final_exit(self):
  x=s.ledger.simulate(market(),'CD_INFO',0,3*D,plan([(0,.5),(D,-.5)]));fund=[e for e in x['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertLess(fund[0]['cashflow'],0);self.assertGreater(fund[1]['cashflow'],0);self.assertEqual(fund[0]['observed_time'],D+47);self.assertTrue(all(e['instrument']=='BP' for e in x['events']));self.assertEqual(x['events'][-1]['reason'],'end_of_experiment');self.assertAlmostEqual(x['metrics']['initial']+x['metrics']['gross_pnl']+x['metrics']['funding']-x['metrics']['fees']-x['metrics']['impact'],x['metrics']['equity'])
 def test_frozen_delay_and_quantity_minimum(self):
  x=s.ledger.simulate(market(),'CD_INFO',0,3*D,plan([(0,.5)]),delay=1);self.assertEqual(x['events'][0]['time'],2*H);self.assertEqual(x['events'][0]['source_time'],0);self.assertAlmostEqual(x['events'][0]['position']/.001,round(x['events'][0]['position']/.001));z=s.ledger.simulate(market(),'CD_INFO',0,3*D,plan([(0,.01)]));self.assertEqual(z['metrics']['fills'],0)
 def test_missing_execution_does_not_invent_fill(self):
  m=market();m.rowmaps['BP'].pop(H);x=s.ledger.simulate(m,'CD_INFO',0,3*D,plan([(0,.5)]));self.assertEqual(x['metrics']['fills'],0);self.assertEqual(x['skips'][0]['reason'],'missing_execution_bar')
 def test_margin_uses_long_low_and_short_high(self):
  a=s.ledger.simulate(market(),'CD_INFO',0,3*D,plan([(0,.5)]));b=s.ledger.simulate(market(),'CD_INFO',0,3*D,plan([(0,-.5)]));self.assertIsNotNone(a['metrics']['min_adverse_margin_ratio']);self.assertIsNotNone(b['metrics']['min_adverse_margin_ratio']);self.assertNotEqual(a['metrics']['min_adverse_margin_ratio'],b['metrics']['min_adverse_margin_ratio'])
if __name__=='__main__':unittest.main()
