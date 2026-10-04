"""Synthetic causal semivariance composition and same-return/RV/count counterfactuals."""
import copy,math,unittest
from types import SimpleNamespace
import numpy as np
import btc_upside_study as s
from btc_continuity_study import hac
from verify_btc_upside_study import independent_fit
D=s.DAY;H=s.HOUR;T=s.ms('2024-01-08')
def fixture():
 prices={u:100*math.exp(.000005*i+.03*math.sin(i*.17)+.02*math.cos(i*.063)) for i,u in enumerate(range(T-120*D,T+30*D,H))};rows={u-H:[u-H,p,p,p,p,u-1] for u,p in prices.items()};hours={u-H:{'time':u-H,'end':u-1,'ohlc':[str(p)]*4,'base':'5'} for u,p in prices.items()};m=SimpleNamespace(rowmaps={'BP':rows},funds={'BP':{u:[u,8,.0001,u+47] for u in range(T-120*D,T+30*D,8*H)}},observation=lambda t,risk:(-2/3,min(1,risk/.4),.4));return m,hours

def pred(mu=.03,beta=.4,se=0):return {'mu':mu,'se':se,'beta':[0,beta]}
def models():return {'UV_INFO':pred(),'UV_COUNT':pred(.01,.4),'UV_SEMI':pred(-.02,.4),'UV_PRICE':pred(.02,-.5)}
def market():
 rows={};marks={}
 for k in ('BS','BP'):
  rows[k]={t:[t,100000.,110000.,90000.,100000.,t+H-1] for t in range(0,3*D,H)};marks[k]={t:r.copy() for t,r in rows[k].items()}
 return SimpleNamespace(rowmaps=rows,markmaps=marks,funds={'BP':{D:[D,8,.001,D+47],2*D:[2*D,8,.001,2*D+23]}})
def plan(weights):return [{'source_time':t,'weights':{'BS':0.,'BP':w},'hedge':False,'rebalance':True,'detail':{}} for t,w in weights]

class UpsideTests(unittest.TestCase):
 def setUp(self):self.m,self.c=fixture()
 def feature(self,lag=0):return s.features(self.m,self.c,lag,T,T+s.WEEK)[0]
 def test_exact_169_closes_168_returns_completed(self):
  a=self.feature();self.assertTrue(a['valid']);self.assertEqual(a['state_cutoff'],T);self.assertEqual(a['hour_boundaries'],list(range(T-s.WEEK,T+H,H)));self.assertEqual(len(a['hour_closes']),169);self.assertEqual(len(a['hour_returns']),168);self.assertTrue(all(a['hour_valid']));self.assertEqual(sum(a['counts'].values()),168)
 def test_same_return_variance_count_different_composition(self):
  x=[.03,.01,-.02,-.02]*42;y=[.02,.02,-.03,-.01]*42;a=s.decompose(x);b=s.decompose(y);self.assertAlmostEqual(math.fsum(x),math.fsum(y));self.assertAlmostEqual(a['variance'],b['variance']);self.assertEqual(a['counts'],b['counts']);self.assertEqual(a['count'],b['count']);self.assertGreater(a['asymmetry'],0);self.assertAlmostEqual(a['asymmetry'],-b['asymmetry'])
 def test_partition_sign_reversal_and_order_invariance(self):
  a=self.feature();x=a['hour_returns'];b=s.decompose([-r for r in x]);c=s.decompose(x[::-1]);self.assertAlmostEqual(a['positive_variance']+a['negative_variance'],a['variance']);self.assertAlmostEqual(a['asymmetry'],-b['asymmetry']);self.assertAlmostEqual(a['count'],-b['count']);self.assertAlmostEqual(a['log_rv'],b['log_rv']);self.assertEqual(s.decompose(x),c)
 def test_zero_returns_in_denominator_and_zero_variance_invalid(self):
  a=s.decompose([.01,-.01,0.,0.]*42);self.assertEqual(a['counts']['zero'],84);self.assertEqual(a['count'],0);self.assertEqual(s.decompose([.01,0,0,0]*42)['count'],.25)
  for r in self.c.values():r['ohlc']=['100']*4
  b=self.feature();self.assertFalse(b['valid']);self.assertEqual(b['variance'],0);self.assertIsNone(b['asymmetry']);self.assertIsNone(b['log_rv'])
 def test_missing_internal_or_first_boundary_not_time_compressed(self):
  self.c.pop(T-4*D-H);a=self.feature();self.assertFalse(a['valid']);self.assertIsNone(a['hour_returns']);self.m,self.c=fixture();self.c.pop(T-s.WEEK-H);self.assertFalse(self.feature()['valid'])
 def test_no_volume_and_clock_shift_not_filled(self):
  self.c[T-3*H]['base']='0';self.assertFalse(self.feature()['valid']);self.c[T-3*H]['base']='5';self.c[T-3*H]['end']+=1;self.assertFalse(self.feature()['valid'])
 def test_price_unit_scaling_no_feature_change(self):
  a=self.feature()
  for r in self.c.values():r['ohlc']=[str(float(v)*1000) for v in r['ohlc']]
  b=self.feature()
  for key in ('variance','asymmetry','count','log_rv'):self.assertAlmostEqual(a[key],b[key],places=11)
  self.assertEqual(a['r7'],b['r7']);self.assertEqual(a['funding'],b['funding'])
 def test_lag_moves_state_only_not_price_or_funding(self):
  a=self.feature();b=self.feature(7);self.assertEqual(a['price_times'],b['price_times']);self.assertEqual(a['r7'],b['r7']);self.assertEqual(a['funding_rows'],b['funding_rows']);self.assertEqual(b['state_cutoff'],T-7*D);self.assertEqual(b['hour_boundaries'],[u-7*D for u in a['hour_boundaries']])
 def test_future_hour_price_funding_cannot_change_features(self):
  a=copy.deepcopy(self.feature())
  for u,r in self.c.items():
   if u>=T:r['ohlc']=['1e20']*4
  for u,r in self.m.rowmaps['BP'].items():
   if u>=T:r[4]=1e20
  for r in self.m.funds['BP'].values():
   if r[3]>=T:r[2]=10.
  self.assertEqual(a,self.feature())
 def test_actual_funding_clock_not_rounded_archive_clock(self):
  a=self.feature();self.m.funds['BP'][T-8*H][3]=T+1;self.assertFalse(self.feature()['funding_valid']);self.assertNotIn(self.m.funds['BP'][T],a['funding_rows'])
 def test_duplicate_and_missing_funding_invalidate(self):
  u=T-16*H;self.m.funds['BP'][u+1]=[u+1,8,.01,u+1];self.assertFalse(self.feature()['valid']);self.m.funds['BP'].pop(u+1);self.m.funds['BP'].pop(u);self.assertFalse(self.feature()['funding_valid'])
 def test_invalid_daily_boundary_no_fill(self):
  u=T-10*D-H;self.m.rowmaps['BP'][u][5]+=1;self.assertFalse(self.feature()['valid']);self.m.rowmaps['BP'][u][5]-=1;self.m.rowmaps['BP'].pop(u);self.assertFalse(self.feature()['valid'])
 def test_purge_common_training_and_future_labels(self):
  rng=np.random.default_rng(901);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;vals=rng.normal(size=6);ff.append(dict(source=t,valid=i!=100,**dict(zip(s.FEATURE_COLS,vals))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);self.assertEqual(a['training_weeks'],[f['source'] for f in ff[44:148] if f['valid']]);self.assertTrue(all(p['training_n']==103 for p in a['models'].values()));yy[ff[148]['source']]['value']=1e20;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()));ff[149]['valid']=False;self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,149)['models'].values()))
 def test_unrestricted_and_independent_fit_not_beta_clipping(self):
  rng=np.random.default_rng(51);x=rng.normal(size=(104,6));b=np.array([1,2,-.3,.4,.7,.5]);dates=np.arange(104)*s.WEEK;y=.001+x@b+rng.normal(size=104)*.01;p=s.fit(x,y,dates,x[0]);q=independent_fit(np.c_[np.ones(104),x],y,dates,np.r_[1,x[0]],False);self.assertGreater(p['beta'][-1],0);np.testing.assert_allclose(p['beta'],q['beta'],atol=1e-12);np.testing.assert_allclose(p['covariance'],q['covariance'],atol=1e-12);self.assertFalse(p['constraint_active']);self.assertIsNone(s.fit(np.ones((70,6)),np.ones(70),np.arange(70)*s.WEEK,np.ones(6))['mu'])
 def test_positive_asymmetry_increment_and_controls(self):
  p=models();self.assertEqual(s.decision('UV_INFO',p,-.5)[:2],(1.,True));self.assertEqual(s.decision('UV_INV',p,-.5)[:2],(-1.,True));p['UV_INFO']['beta'][-1]=0;self.assertEqual(s.decision('UV_INFO',p,-.5)[:2],(-.5,False));p=models();p['UV_COUNT']['mu']=.04;self.assertFalse(s.decision('UV_INFO',p,-.5)[1]);self.assertTrue(s.decision('UV_COUNT',p,-.5)[1]);p['UV_COUNT']['beta'][-1]=-.1;self.assertFalse(s.decision('UV_COUNT',p,-.5)[1]);self.assertTrue(s.decision('UV_SEMI',p,-.5)[1]);p['UV_SEMI']['beta'][-1]=-.1;self.assertFalse(s.decision('UV_SEMI',p,-.5)[1])
 def test_symmetric_strict_cost_se_and_signed_fallback(self):
  self.assertEqual(s.threshold(s.GATE,0),0);self.assertEqual(s.threshold(-s.GATE,0),0);self.assertEqual(s.threshold(.03,.04),0);p=models();p['UV_INFO']['mu']=None;self.assertTrue(s.decision('UV_SEMI',p,-.5)[1]);self.assertTrue(s.decision('UV_PRICE',p,-.5)[1]);self.assertEqual(s.decision('UV_INFO',p,-.5)[:2],(-.5,False));self.assertEqual(s.decision('UV_TREND',p,-.5)[:2],(-.5,False))
 def test_perp_both_directions_week_and_risk_hold(self):
  pp=[{'source':T,'models':models(),'training_n':80,'training_label_end':T-s.WEEK}];ff=[self.feature()];a=s.schedule(self.m,ff,pp,'UV_INFO',T+2*D,T+6*D);self.assertTrue(all(e['weights']=={'BS':0.,'BP':.5} for e in a));b=s.schedule(self.m,ff,pp,'UV_INV',T,T+D,.1);self.assertEqual(b[0]['weights'],{'BS':0.,'BP':-.25});self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'UV_INFO',T,T+D)[0]['weights'])
 def test_hac_calendar_gap_not_observation_gap(self):
  rng=np.random.default_rng(13);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];A=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:A+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(hac(Z,res,dates),10/6*B@A@B,rtol=1e-10,atol=1e-12)
 def test_long_short_funding_and_final_exit(self):
  x=s.ledger.simulate(market(),'UV_INFO',0,3*D,plan([(0,.5),(D,-.5)]));fund=[e for e in x['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertLess(fund[0]['cashflow'],0);self.assertGreater(fund[1]['cashflow'],0);self.assertEqual(fund[0]['observed_time'],D+47);self.assertTrue(all(e['instrument']=='BP' for e in x['events']));self.assertEqual(x['events'][-1]['reason'],'end_of_experiment');self.assertAlmostEqual(x['metrics']['initial']+x['metrics']['gross_pnl']+x['metrics']['funding']-x['metrics']['fees']-x['metrics']['impact'],x['metrics']['equity'])
 def test_frozen_delay_and_quantity_minimum(self):
  x=s.ledger.simulate(market(),'UV_INFO',0,3*D,plan([(0,.5)]),delay=1);self.assertEqual(x['events'][0]['time'],2*H);self.assertEqual(x['events'][0]['source_time'],0);self.assertAlmostEqual(x['events'][0]['position']/.001,round(x['events'][0]['position']/.001));z=s.ledger.simulate(market(),'UV_INFO',0,3*D,plan([(0,.01)]));self.assertEqual(z['metrics']['fills'],0)
 def test_missing_execution_does_not_invent_fill(self):
  m=market();m.rowmaps['BP'].pop(H);x=s.ledger.simulate(m,'UV_INFO',0,3*D,plan([(0,.5)]));self.assertEqual(x['metrics']['fills'],0);self.assertEqual(x['skips'][0]['reason'],'missing_execution_bar')
 def test_margin_uses_long_low_and_short_high(self):
  a=s.ledger.simulate(market(),'UV_INFO',0,3*D,plan([(0,.5)]));b=s.ledger.simulate(market(),'UV_INFO',0,3*D,plan([(0,-.5)]));self.assertIsNotNone(a['metrics']['min_adverse_margin_ratio']);self.assertIsNotNone(b['metrics']['min_adverse_margin_ratio']);self.assertNotEqual(a['metrics']['min_adverse_margin_ratio'],b['metrics']['min_adverse_margin_ratio'])
if __name__=='__main__':unittest.main()
