"""Synthetic causal maturity selection, actual funding clocks and perp-only boundaries."""
import copy,math,unittest
from types import SimpleNamespace
import numpy as np
import btc_term_study as s
from btc_continuity_study import hac
from collect_btc_term_data import valid
D=s.DAY;H=s.HOUR;T=s.ms('2024-01-08')
def raw(t,price=100.,volume='5'):
 return [str(t),str(price),str(price),str(price),str(price),volume,str(t+H-1),'0.05','2','2','0.02','0']
def fixture():
 m=SimpleNamespace(rowmaps={'BP':{u-H:[u-H,100.,102.,99.,100*math.exp(.001*i+.01*math.sin(i)),u-1] for i,u in enumerate(range(T-120*D,T+30*D,D))}},funds={'BP':{u:[u,8,.0001,u+47] for u in range(T-120*D,T+30*D,8*H)}},observation=lambda t,risk:(-2/3,min(1,risk/.4),.4))
 contracts=[]
 for sym,expiry,price in [('BTCUSD_240329',s.ms('2024-03-29'),100),('BTCUSD_240628',s.ms('2024-06-28'),103),('BTCUSD_240927',s.ms('2024-09-27'),110)]:
  rr=[{'raw':raw(c-H,price),'valid':True} for c in (T-7*D,T,T+7*D)];contracts.append({'symbol':sym,'expiry_date_proxy':expiry,'first_valid_open':T-60*D,'rows':rr})
 return m,contracts

def pred(mu=.03,beta=-.4,se=0):return {'mu':mu,'se':se,'beta':[0,beta]}
def models():return {'TS_INFO':pred(),'TS_FUND':pred(.01),'TS_TERM':pred(-.02),'TS_PRICE':pred(.02,.5)}
def market():
 rows={};marks={}
 for k in ('BS','BP'):
  rows[k]={t:[t,100000.,110000.,90000.,100000.,t+H-1] for t in range(0,3*D,H)};marks[k]={t:r.copy() for t,r in rows[k].items()}
 return SimpleNamespace(rowmaps=rows,markmaps=marks,funds={'BP':{D:[D,8,.001,D+47],2*D:[2*D,8,.001,2*D+23]}})

def plan(weights):return [{'source_time':t,'weights':{'BS':0.,'BP':w},'hedge':False,'rebalance':True,'detail':{}} for t,w in weights]

class TermTests(unittest.TestCase):
 def setUp(self):self.m,self.c=fixture()
 def feature(self,lag=0):return s.features(self.m,self.c,lag,T,T+s.WEEK)[0]
 def test_completed_pair_no_far_cherry_pick(self):
  a=self.feature();self.assertTrue(a['valid']);self.assertEqual(a['selected_symbols'],['BTCUSD_240329','BTCUSD_240628']);self.assertEqual(a['derivative_cutoff'],T);self.assertEqual(len(a['funding_rows']),21);self.assertTrue(all(r[3]<T for r in a['funding_rows']));self.c[0]['rows'][1]['valid']=False;b=self.feature();self.assertFalse(b['valid']);self.assertEqual(b['selected_symbols'],a['selected_symbols'])
 def test_nominal_expiry_exclusion_and_future_listing(self):
  self.c[0]['expiry_date_proxy']=T;self.assertEqual(self.feature()['selected_symbols'],['BTCUSD_240628','BTCUSD_240927']);self.c[1]['first_valid_open']=T;self.assertFalse(self.feature()['curve_valid']);self.assertEqual(self.feature()['selected_symbols'],['BTCUSD_240927'])
 def test_exact_current_bar_not_last_good_quote(self):
  self.c[0]['rows'].pop(1);a=self.feature();self.assertFalse(a['valid']);self.assertEqual(a['selected_closes'][0],None)
 def test_curve_units_and_sign_not_spot_ratio(self):
  a=self.feature();expected=365*D/(s.ms('2024-06-28')-s.ms('2024-03-29'))*math.log(1.03);self.assertAlmostEqual(a['carry'],expected)
  for c in self.c:
   for row in c['rows']:
    for j in (1,2,3,4):row['raw'][j]=str(float(row['raw'][j])*1000)
  b=self.feature();self.assertAlmostEqual(a['carry'],b['carry']);self.assertEqual(a['r7'],b['r7']);x=self.c[0]['rows'][1]['raw'][4];self.c[0]['rows'][1]['raw'][4]=self.c[1]['rows'][1]['raw'][4];self.c[1]['rows'][1]['raw'][4]=x;self.assertAlmostEqual(self.feature()['carry'],-a['carry'])
 def test_lag_moves_derivatives_not_current_price(self):
  a=self.feature();b=self.feature(7);self.assertEqual(a['price_times'],b['price_times']);self.assertEqual(a['r7'],b['r7']);self.assertEqual(b['derivative_cutoff'],T-7*D);self.assertEqual(b['funding_buckets'],[u-7*D for u in a['funding_buckets']]);self.assertAlmostEqual(b['tau']-a['tau'],7/365)
 def test_actual_clock_not_rounded_archive_clock(self):
  a=self.feature();self.m.funds['BP'][T-8*H][3]=T+1;b=self.feature();self.assertFalse(b['funding_valid']);self.assertEqual(len(a['funding_rows']),21);self.assertNotIn(self.m.funds['BP'][T],a['funding_rows'])
 def test_duplicate_and_missing_funding_invalidate(self):
  u=T-16*H;self.m.funds['BP'][u+1]=[u+1,8,.01,u+1];self.assertFalse(self.feature()['valid']);self.m.funds['BP'].pop(u+1);self.m.funds['BP'].pop(u);self.assertFalse(self.feature()['funding_valid'])
 def test_future_price_curve_funding_cannot_change_features(self):
  a=self.feature()
  for u,r in self.m.rowmaps['BP'].items():
   if u>=T:r[4]=1e20
  for c in self.c:
   for row in c['rows']:
    if int(row['raw'][0])>=T:row['raw'][4]='1e20'
  for u,r in self.m.funds['BP'].items():
   if r[3]>=T:r[2]=10.
  self.assertEqual(a,self.feature())
 def test_invalid_daily_boundary_no_fill(self):
  u=T-10*D-H;self.m.rowmaps['BP'][u][5]+=1;self.assertFalse(self.feature()['valid']);self.m.rowmaps['BP'][u][5]-=1;self.m.rowmaps['BP'].pop(u);self.assertFalse(self.feature()['valid'])
 def test_header_semantics_positive_trades_and_taker_bounds(self):
  r=raw(T-H);self.assertTrue(valid(r));r[5]='0';self.assertFalse(valid(r));r=raw(T-H);r[8]='0';self.assertFalse(valid(r));r=raw(T-H);r[10]='10';self.assertFalse(valid(r));r=raw(T-H);r[6]=str(T);self.assertFalse(valid(r))
 def test_purge_common_training_and_future_labels(self):
  rng=np.random.default_rng(901);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;vals=rng.normal(size=5);ff.append(dict(source=t,valid=i!=100,**dict(zip(s.FEATURE_COLS,vals))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);self.assertEqual(a['training_weeks'],[f['source'] for f in ff[44:148] if f['valid']]);self.assertTrue(all(p['training_n']==103 for p in a['models'].values()));yy[ff[148]['source']]['value']=1e20;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()))
 def test_no_beta_constraint_and_common_rank_failure(self):
  rng=np.random.default_rng(51);x=rng.normal(size=(104,5));b=np.array([1,2,-.3,.4,.7]);p=s.fit(x,.001+x@b,np.arange(104)*s.WEEK,x[0]);np.testing.assert_allclose(p['beta'],np.r_[.001,b],atol=1e-12);self.assertFalse(p['constraint_active']);self.assertIsNone(s.fit(np.ones((70,5)),np.ones(70),np.arange(70)*s.WEEK,np.ones(5))['mu'])
 def test_negative_slope_increment_and_inverse(self):
  p=models();self.assertEqual(s.decision('TS_INFO',p,-.5)[:2],(1.,True));self.assertEqual(s.decision('TS_INV',p,-.5)[:2],(-1.,True));p['TS_INFO']['beta'][-1]=0;self.assertEqual(s.decision('TS_INFO',p,-.5)[:2],(-.5,False));p=models();p['TS_FUND']['mu']=.04;self.assertFalse(s.decision('TS_INFO',p,-.5)[1]);self.assertTrue(s.decision('TS_FUND',p,-.5)[1])
 def test_symmetric_cost_se_controls_and_signed_fallback(self):
  self.assertEqual(s.threshold(.001,0),0);self.assertEqual(s.threshold(-.001,0),0);self.assertEqual(s.threshold(.03,.04),0);p=models();p['TS_INFO']['mu']=None;self.assertTrue(s.decision('TS_TERM',p,-.5)[1]);self.assertTrue(s.decision('TS_PRICE',p,-.5)[1]);self.assertEqual(s.decision('TS_INFO',p,-.5)[:2],(-.5,False));self.assertEqual(s.decision('TS_TREND',p,-.5)[:2],(-.5,False))
 def test_perp_both_directions_week_and_risk_hold(self):
  pp=[{'source':T,'models':models(),'training_n':80,'training_label_end':T-s.WEEK}];ff=[self.feature()];a=s.schedule(self.m,ff,pp,'TS_INFO',T+2*D,T+6*D);self.assertTrue(all(e['weights']=={'BS':0.,'BP':.5} for e in a));b=s.schedule(self.m,ff,pp,'TS_INV',T,T+D,.1);self.assertEqual(b[0]['weights'],{'BS':0.,'BP':-.25});self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'TS_INFO',T,T+D)[0]['weights'])
 def test_hac_calendar_gap_not_observation_gap(self):
  rng=np.random.default_rng(13);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];M=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:M+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(hac(Z,res,dates),10/6*B@M@B,rtol=1e-10,atol=1e-12)
 def test_long_short_funding_and_final_exit(self):
  x=s.ledger.simulate(market(),'TS_INFO',0,3*D,plan([(0,.5),(D,-.5)]));fund=[e for e in x['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertLess(fund[0]['cashflow'],0);self.assertGreater(fund[1]['cashflow'],0);self.assertEqual(fund[0]['observed_time'],D+47);self.assertTrue(all(e['instrument']=='BP' for e in x['events']));self.assertEqual(x['events'][-1]['reason'],'end_of_experiment');self.assertAlmostEqual(x['metrics']['initial']+x['metrics']['gross_pnl']+x['metrics']['funding']-x['metrics']['fees']-x['metrics']['impact'],x['metrics']['equity'])
 def test_frozen_delay_and_quantity_minimum(self):
  x=s.ledger.simulate(market(),'TS_INFO',0,3*D,plan([(0,.5)]),delay=1);self.assertEqual(x['events'][0]['time'],2*H);self.assertEqual(x['events'][0]['source_time'],0);self.assertAlmostEqual(x['events'][0]['position']/.001,round(x['events'][0]['position']/.001));z=s.ledger.simulate(market(),'TS_INFO',0,3*D,plan([(0,.01)]));self.assertEqual(z['metrics']['fills'],0)
 def test_missing_execution_does_not_invent_fill(self):
  m=market();m.rowmaps['BP'].pop(H);x=s.ledger.simulate(m,'TS_INFO',0,3*D,plan([(0,.5)]));self.assertEqual(x['metrics']['fills'],0);self.assertEqual(x['skips'][0]['reason'],'missing_execution_bar')
 def test_margin_uses_long_low_and_short_high(self):
  a=s.ledger.simulate(market(),'TS_INFO',0,3*D,plan([(0,.5)]));b=s.ledger.simulate(market(),'TS_INFO',0,3*D,plan([(0,-.5)]));self.assertIsNotNone(a['metrics']['min_adverse_margin_ratio']);self.assertIsNotNone(b['metrics']['min_adverse_margin_ratio']);self.assertNotEqual(a['metrics']['min_adverse_margin_ratio'],b['metrics']['min_adverse_margin_ratio'])
if __name__=='__main__':unittest.main()
