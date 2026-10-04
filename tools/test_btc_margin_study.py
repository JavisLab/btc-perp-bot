"""Synthetic causal publication, exact margin inventory snapshots, conditioning and perp-only checks."""
import copy,json,math,unittest
from types import SimpleNamespace
import numpy as np
import btc_margin_study as s
from btc_continuity_study import hac
from collect_btc_margin_data import normalize
from verify_btc_margin_study import independent_fit
D=s.DAY;H=s.HOUR;M=s.MINUTE;T=s.ms('2024-01-08')
def fixture():
 m=SimpleNamespace(rowmaps={'BP':{u-H:[u-H,100.,102.,99.,100*math.exp(.001*i+.01*math.sin(i)),u-1] for i,u in enumerate(range(T-120*D,T+30*D,D))}},funds={'BP':{u:[u,8,.0001,u+47] for u in range(T-120*D,T+30*D,8*H)}},observation=lambda t,risk:(-2/3,min(1,risk/.4),.4));snap=[]
 for i,c in enumerate(range(T-22*D,T+14*D,7*D)):
  for side,qty in [('long',100+12*i),('short',30+3*i)]:
   rows=[[u,qty] for u in range(c-H,c,M)];snap.append(normalize(json.dumps(rows).encode(),c,side))
 return m,snap

def pred(mu=.03,beta=-.4,se=0):return {'mu':mu,'se':se,'beta':[0,beta]}
def models():return {'MI_INFO':pred(),'MI_LONG':pred(.01,.4),'MI_SHORT':pred(-.02),'MI_PRICE':pred(.02,.5)}
def market():
 rows={};marks={}
 for k in ('BS','BP'):
  rows[k]={t:[t,100000.,110000.,90000.,100000.,t+H-1] for t in range(0,3*D,H)};marks[k]={t:r.copy() for t,r in rows[k].items()}
 return SimpleNamespace(rowmaps=rows,markmaps=marks,funds={'BP':{D:[D,8,.001,D+47],2*D:[2*D,8,.001,2*D+23]}})
def plan(weights):return [{'source_time':t,'weights':{'BS':0.,'BP':w},'hedge':False,'rebalance':True,'detail':{}} for t,w in weights]

class MarginTests(unittest.TestCase):
 def setUp(self):self.m,self.c=fixture()
 def feature(self,lag=0):return s.features(self.m,self.c,lag,T,T+s.WEEK)[0]
 def current(self,side='short'):return next(e for e in self.c if e['side']==side and e['cutoff']==T-D)
 def test_exact_snapshot_and_publication_buffer(self):
  a=self.feature();self.assertTrue(a['valid']);self.assertEqual(a['margin_cutoff'],T-D);self.assertEqual(a['snapshot_cutoffs'],[T-8*D,T-D]);self.assertEqual(a['selected_rows']['short'][1][0],T-D-M);self.assertEqual(len(a['funding_rows']),21);self.assertTrue(all(r[3]<T for r in a['funding_rows']))
 def test_exact_minute_not_previous_or_next(self):
  e=self.current();e['selected'][0]-=M;self.assertFalse(self.feature()['valid']);e['selected'][0]+=2*M;self.assertFalse(self.feature()['valid']);e['selected']=None;self.assertFalse(self.feature()['valid'])
 def test_one_side_or_previous_snapshot_missing_invalidates_all(self):
  e=self.current();self.c.remove(e);a=self.feature();self.assertFalse(a['margin_valid']);self.assertTrue(a['price_valid']);self.assertTrue(a['funding_valid']);self.m,self.c=fixture();self.c=[e for e in self.c if not(e['side']=='long' and e['cutoff']==T-8*D)];self.assertFalse(self.feature()['valid'])
 def test_units_separate_sides_not_currency_basis(self):
  a=self.feature()
  for e in self.c:e['selected'][1]=str(float(e['selected'][1])*(1e6 if e['side']=='long' else .001))
  b=self.feature();self.assertAlmostEqual(a['long_growth'],b['long_growth']);self.assertAlmostEqual(a['short_growth'],b['short_growth']);self.assertEqual(a['r7'],b['r7']);self.assertEqual(a['funding'],b['funding'])
 def test_log_change_not_level_and_zero_not_clipped(self):
  a=self.feature();older,current=a['selected_rows']['short'];self.assertAlmostEqual(a['short_growth'],math.log(float(current[1])/float(older[1])));self.current()['selected'][1]='0';self.assertFalse(self.feature()['valid']);self.current()['selected'][1]='-1';self.assertFalse(self.feature()['valid'])
 def test_lag_moves_margin_only_not_price_or_funding(self):
  a=self.feature();b=self.feature(7);self.assertEqual(a['price_times'],b['price_times']);self.assertEqual(a['r7'],b['r7']);self.assertEqual(a['funding_rows'],b['funding_rows']);self.assertEqual(a['funding'],b['funding']);self.assertEqual(b['margin_cutoff'],T-8*D);self.assertEqual(b['snapshot_cutoffs'],[u-7*D for u in a['snapshot_cutoffs']])
 def test_future_including_publication_buffer_cannot_change_features(self):
  a=copy.deepcopy(self.feature())
  for e in self.c:
   if e['cutoff']>T-D:e['selected'][1]='1e20'
  for u,r in self.m.rowmaps['BP'].items():
   if u>=T:r[4]=1e20
  for r in self.m.funds['BP'].values():
   if r[3]>=T:r[2]=10.
  self.assertEqual(a,self.feature());extra=copy.deepcopy(self.current());extra['cutoff']=T;extra['selected']=[T-M,'1e25'];self.c.append(extra);self.assertEqual(a,self.feature())
 def test_duplicate_snapshot_fails_not_last_wins(self):
  self.c.append(copy.deepcopy(self.current()))
  with self.assertRaises(AssertionError):self.feature()
 def test_normalization_missing_last_vs_missing_internal_minute(self):
  c=T-D;rows=[[u,5.125] for u in range(c-H,c,M)];r=normalize(json.dumps(rows[:-1]).encode(),c,'long');self.assertFalse(r['valid']);self.assertIsNone(r['selected']);r=normalize(json.dumps(rows[1:]).encode(),c,'long');self.assertTrue(r['valid']);self.assertEqual(r['missing_minutes'],[c-H]);self.assertEqual(r['selected'],[c-M,'5.125'])
 def test_raw_duplicate_bad_clock_and_zero(self):
  c=T-D
  with self.assertRaises(AssertionError):normalize(json.dumps([[c-M,1],[c-M,2]]).encode(),c,'long')
  with self.assertRaises(AssertionError):normalize(json.dumps([[c,1]]).encode(),c,'long')
  with self.assertRaises(AssertionError):normalize(json.dumps([[c-M+1,1]]).encode(),c,'long')
  r=normalize(json.dumps([[c-M,0]]).encode(),c,'long');self.assertFalse(r['valid']);self.assertEqual(r['invalid_minutes'],[c-M])
 def test_decimal_raw_precision_preserved(self):
  c=T-D;r=normalize(('[['+str(c-M)+',0.0000000000000000001234567890123456789]]').encode(),c,'short');self.assertEqual(r['selected'][1],'1.234567890123456789E-19');self.assertTrue(r['valid'])
 def test_actual_funding_clock_not_rounded_archive_clock(self):
  a=self.feature();self.m.funds['BP'][T-8*H][3]=T+1;self.assertFalse(self.feature()['funding_valid']);self.assertNotIn(self.m.funds['BP'][T],a['funding_rows'])
 def test_duplicate_and_missing_funding_invalidate(self):
  u=T-16*H;self.m.funds['BP'][u+1]=[u+1,8,.01,u+1];self.assertFalse(self.feature()['valid']);self.m.funds['BP'].pop(u+1);self.m.funds['BP'].pop(u);self.assertFalse(self.feature()['funding_valid'])
 def test_invalid_daily_boundary_no_fill(self):
  u=T-10*D-H;self.m.rowmaps['BP'][u][5]+=1;self.assertFalse(self.feature()['valid']);self.m.rowmaps['BP'][u][5]-=1;self.m.rowmaps['BP'].pop(u);self.assertFalse(self.feature()['valid'])
 def test_purge_common_training_and_future_labels(self):
  rng=np.random.default_rng(901);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;vals=rng.normal(size=5);ff.append(dict(source=t,valid=i!=100,**dict(zip(s.FEATURE_COLS,vals))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);self.assertEqual(a['training_weeks'],[f['source'] for f in ff[44:148] if f['valid']]);self.assertTrue(all(p['training_n']==103 for p in a['models'].values()));yy[ff[148]['source']]['value']=1e20;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()));ff[149]['valid']=False;self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,149)['models'].values()))
 def test_unrestricted_and_independent_fit_not_beta_clipping(self):
  rng=np.random.default_rng(51);x=rng.normal(size=(104,5));b=np.array([1,2,-.3,.4,.7]);dates=np.arange(104)*s.WEEK;y=.001+x@b+rng.normal(size=104)*.01;p=s.fit(x,y,dates,x[0]);q=independent_fit(np.c_[np.ones(104),x],y,dates,np.r_[1,x[0]],False);self.assertGreater(p['beta'][-1],0);np.testing.assert_allclose(p['beta'],q['beta'],atol=1e-12);np.testing.assert_allclose(p['covariance'],q['covariance'],atol=1e-12);self.assertFalse(p['constraint_active']);self.assertIsNone(s.fit(np.ones((70,5)),np.ones(70),np.arange(70)*s.WEEK,np.ones(5))['mu'])
 def test_short_negative_increment_and_inverse_not_long_sign(self):
  p=models();self.assertEqual(s.decision('MI_INFO',p,-.5)[:2],(1.,True));self.assertEqual(s.decision('MI_INV',p,-.5)[:2],(-1.,True));p['MI_INFO']['beta'][-1]=0;self.assertEqual(s.decision('MI_INFO',p,-.5)[:2],(-.5,False));p=models();p['MI_LONG']['mu']=.04;self.assertFalse(s.decision('MI_INFO',p,-.5)[1]);self.assertTrue(s.decision('MI_LONG',p,-.5)[1]);p['MI_LONG']['beta'][-1]=-.1;self.assertFalse(s.decision('MI_LONG',p,-.5)[1]);self.assertTrue(s.decision('MI_SHORT',p,-.5)[1]);p['MI_SHORT']['beta'][-1]=.1;self.assertFalse(s.decision('MI_SHORT',p,-.5)[1])
 def test_symmetric_strict_cost_se_and_signed_fallback(self):
  self.assertEqual(s.threshold(s.GATE,0),0);self.assertEqual(s.threshold(-s.GATE,0),0);self.assertEqual(s.threshold(.03,.04),0);p=models();p['MI_INFO']['mu']=None;self.assertTrue(s.decision('MI_SHORT',p,-.5)[1]);self.assertTrue(s.decision('MI_PRICE',p,-.5)[1]);self.assertEqual(s.decision('MI_INFO',p,-.5)[:2],(-.5,False));self.assertEqual(s.decision('MI_TREND',p,-.5)[:2],(-.5,False))
 def test_perp_both_directions_week_and_risk_hold(self):
  pp=[{'source':T,'models':models(),'training_n':80,'training_label_end':T-s.WEEK}];ff=[self.feature()];a=s.schedule(self.m,ff,pp,'MI_INFO',T+2*D,T+6*D);self.assertTrue(all(e['weights']=={'BS':0.,'BP':.5} for e in a));b=s.schedule(self.m,ff,pp,'MI_INV',T,T+D,.1);self.assertEqual(b[0]['weights'],{'BS':0.,'BP':-.25});self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'MI_INFO',T,T+D)[0]['weights'])
 def test_hac_calendar_gap_not_observation_gap(self):
  rng=np.random.default_rng(13);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];A=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:A+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(hac(Z,res,dates),10/6*B@A@B,rtol=1e-10,atol=1e-12)
 def test_long_short_funding_and_final_exit(self):
  x=s.ledger.simulate(market(),'MI_INFO',0,3*D,plan([(0,.5),(D,-.5)]));fund=[e for e in x['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertLess(fund[0]['cashflow'],0);self.assertGreater(fund[1]['cashflow'],0);self.assertEqual(fund[0]['observed_time'],D+47);self.assertTrue(all(e['instrument']=='BP' for e in x['events']));self.assertEqual(x['events'][-1]['reason'],'end_of_experiment');self.assertAlmostEqual(x['metrics']['initial']+x['metrics']['gross_pnl']+x['metrics']['funding']-x['metrics']['fees']-x['metrics']['impact'],x['metrics']['equity'])
 def test_frozen_delay_and_quantity_minimum(self):
  x=s.ledger.simulate(market(),'MI_INFO',0,3*D,plan([(0,.5)]),delay=1);self.assertEqual(x['events'][0]['time'],2*H);self.assertEqual(x['events'][0]['source_time'],0);self.assertAlmostEqual(x['events'][0]['position']/.001,round(x['events'][0]['position']/.001));z=s.ledger.simulate(market(),'MI_INFO',0,3*D,plan([(0,.01)]));self.assertEqual(z['metrics']['fills'],0)
 def test_missing_execution_does_not_invent_fill(self):
  m=market();m.rowmaps['BP'].pop(H);x=s.ledger.simulate(m,'MI_INFO',0,3*D,plan([(0,.5)]));self.assertEqual(x['metrics']['fills'],0);self.assertEqual(x['skips'][0]['reason'],'missing_execution_bar')
 def test_margin_uses_long_low_and_short_high(self):
  a=s.ledger.simulate(market(),'MI_INFO',0,3*D,plan([(0,.5)]));b=s.ledger.simulate(market(),'MI_INFO',0,3*D,plan([(0,-.5)]));self.assertIsNotNone(a['metrics']['min_adverse_margin_ratio']);self.assertIsNotNone(b['metrics']['min_adverse_margin_ratio']);self.assertNotEqual(a['metrics']['min_adverse_margin_ratio'],b['metrics']['min_adverse_margin_ratio'])
if __name__=='__main__':unittest.main()
