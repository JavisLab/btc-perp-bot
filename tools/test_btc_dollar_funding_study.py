"""New macro date, publication-buffer, unit and missingness causality tests; pure BTC perp only."""
import copy,json,math,unittest,datetime as dt
from types import SimpleNamespace
import numpy as np
import btc_dollar_funding_study as s
from btc_continuity_study import hac
from collect_btc_dollar_funding_data import normalize
from verify_btc_dollar_funding_study import independent_fit
D=s.DAY;H=s.HOUR;T=s.ms('2024-01-08')
def fixture():
 m=SimpleNamespace(rowmaps={'BP':{u-H:[u-H,100.,102.,99.,100*math.exp(.001*i+.01*math.sin(i)),u-1] for i,u in enumerate(range(T-120*D,T+30*D,D))}},funds={'BP':{u:[u,8,.0001,u+47] for u in range(T-120*D,T+30*D,8*H)}},observation=lambda t,risk:(-2/3,min(1,risk/.4),.4));rates={}
 for kind in ('SOFR','EFFR'):
  rr=[]
  for i,t in enumerate(range(T-60*D,T+30*D,D)):
   date=dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date()
   if date.weekday()<5:rr.append({'effectiveDate':date.isoformat(),'type':kind,'percentRate':3+.002*i if kind=='EFFR' else 3.02+.003*i,'revisionIndicator':''})
  rates[kind]=normalize(json.dumps({'refRates':rr[::-1]}).encode(),kind,rr[0]['effectiveDate'],rr[-1]['effectiveDate']) if len(rr)<=23 else [r for offset in range(0,len(rr),20) for r in normalize(json.dumps({'refRates':rr[offset:offset+20][::-1]}).encode(),kind,rr[offset]['effectiveDate'],rr[min(offset+19,len(rr)-1)]['effectiveDate'])]
 return m,rates

def pred(mu=.03,beta=-.4,se=0):return {'mu':mu,'se':se,'beta':[0,beta]}
def models():return {'DF_INFO':pred(),'DF_BANK':pred(.01,-.4),'DF_GAP':pred(-.02),'DF_PRICE':pred(.02,.5)}
def market():
 rows={};marks={}
 for k in ('BS','BP'):
  rows[k]={t:[t,100000.,110000.,90000.,100000.,t+H-1] for t in range(0,3*D,H)};marks[k]={t:r.copy() for t,r in rows[k].items()}
 return SimpleNamespace(rowmaps=rows,markmaps=marks,funds={'BP':{D:[D,8,.001,D+47],2*D:[2*D,8,.001,2*D+23]}})
def plan(weights):return [{'source_time':t,'weights':{'BS':0.,'BP':w},'hedge':False,'rebalance':True,'detail':{}} for t,w in weights]

class DollarFundingTests(unittest.TestCase):
 def setUp(self):self.m,self.c=fixture()
 def feature(self,lag=0):return s.features(self.m,self.c,lag,T,T+s.WEEK)[0]
 def chosen(self,kind='SOFR'):return [r for r in self.c[kind] if T-14*D<=r['time']<T-7*D]
 def test_frozen_calendar_week_and_seven_day_buffer(self):
  a=self.feature();self.assertTrue(a['valid']);self.assertEqual(a['macro_cutoff'],T-7*D);self.assertEqual(a['macro_window_start'],T-14*D);self.assertEqual(len(a['selected_rows']['SOFR']),5);self.assertTrue(all(r['time']<T-7*D for r in a['selected_rows']['SOFR']))
 def test_percent_vs_basis_points_not_daily_or_fraction(self):
  for r in self.chosen('SOFR'):r['rate']='3.65'
  for r in self.chosen('EFFR'):r['rate']='3.60'
  a=self.feature();self.assertAlmostEqual(a['bank'],3.6);self.assertAlmostEqual(a['gap'],5.)
 def test_new_spread_not_same_bank_current_F_or_price(self):
  a=self.feature();self.chosen()[0]['rate']='4.0';b=self.feature();self.assertEqual(a['bank'],b['bank']);self.assertEqual(a['funding'],b['funding']);self.assertEqual(a['r7'],b['r7']);self.assertNotEqual(a['gap'],b['gap'])
 def test_buffer_future_cannot_change_current_feature(self):
  a=copy.deepcopy(self.feature())
  for rr in self.c.values():
   for r in rr:
    if r['time']>=T-7*D:r['rate']='100'
  for r in self.m.funds['BP'].values():
   if r[3]>=T:r[2]=100.
  for u,r in self.m.rowmaps['BP'].items():
   if u>=T:r[4]=1e20
  self.assertEqual(a,self.feature())
 def test_boundary_C_excluded_and_left_included(self):
  a=self.feature();left=next(r for r in self.c['SOFR'] if r['time']==T-14*D);left['rate']='4';self.assertNotEqual(a['gap'],self.feature()['gap']);a=copy.deepcopy(self.feature());next(r for r in self.c['SOFR'] if r['time']==T-7*D)['rate']='99';self.assertEqual(a,self.feature())
 def test_extra7_moves_both_macro_inputs_not_current_BTC(self):
  a,b=self.feature(),self.feature(7);self.assertEqual(a['funding_rows'],b['funding_rows']);self.assertEqual(a['price_times'],b['price_times']);self.assertEqual(b['macro_cutoff'],T-14*D);self.assertEqual(b['macro_window_start'],T-21*D);self.assertNotEqual(a['bank'],b['bank']);self.assertNotEqual(a['gap'],b['gap'])
 def test_one_sided_holiday_invalid_not_intersection(self):
  self.c['SOFR'].remove(self.chosen()[0]);a=self.feature();self.assertFalse(a['macro_valid']);self.assertEqual(len(a['selected_rows']['EFFR']),5);self.assertIsNone(a['gap'])
 def test_same_dates_three_and_four_valid_two_invalid(self):
  for kind in self.c:self.c[kind].remove(self.chosen(kind)[0])
  self.assertTrue(self.feature()['valid'])
  for kind in self.c:self.c[kind].remove(self.chosen(kind)[0])
  self.assertTrue(self.feature()['valid'])
  for kind in self.c:self.c[kind].remove(self.chosen(kind)[0])
  self.assertFalse(self.feature()['valid'])
 def test_wrong_flag_or_footnote_invalid_not_dropped(self):
  self.chosen()[0]['valid']=False;self.assertFalse(self.feature()['valid']);r={'effectiveDate':'2024-01-02','type':'SOFR','percentRate':3.5,'revisionIndicator':'Y'};a=normalize(json.dumps({'refRates':[r]}).encode(),'SOFR','2024-01-01','2024-01-31');self.assertTrue(a[0]['valid']);r['footnoteId']=1;a=normalize(json.dumps({'refRates':[r]}).encode(),'SOFR','2024-01-01','2024-01-31');self.assertFalse(a[0]['valid'])
 def test_duplicate_macro_timestamp_hardfailure(self):
  self.c['SOFR'].append(copy.deepcopy(self.c['SOFR'][-1]))
  with self.assertRaises(AssertionError):self.feature()
 def test_negative_zero_interest_valid(self):
  for kind in self.c:
   for r in self.chosen(kind):r['rate']='0' if kind=='EFFR' else '-.01'
  a=self.feature();self.assertTrue(a['valid']);self.assertEqual(a['bank'],0);self.assertAlmostEqual(a['gap'],-1)
 def test_raw_decimal_and_empty_period(self):
  b=b'{"refRates":[{"effectiveDate":"2024-01-02","type":"SOFR","percentRate":0.0000000000000123456789,"revisionIndicator":""}]}';a=normalize(b,'SOFR','2024-01-01','2024-01-31');self.assertEqual(a[0]['rate'],'1.23456789E-14');self.assertEqual(normalize(b'{"refRates":[]}','EFFR','2024-01-01','2024-01-31'),[])
 def test_raw_bad_clock_type_duplicates_and_order(self):
  r={'effectiveDate':'2024-01-02','type':'SOFR','percentRate':3.5,'revisionIndicator':''}
  for arr in ([r,r],[dict(r,effectiveDate='2024-01-06')],[dict(r,type='OTHER')],[dict(r,percentRate='NaN')],[r,dict(r,effectiveDate='2024-01-03')]):
   with self.assertRaises(AssertionError):normalize(json.dumps({'refRates':arr}).encode(),'SOFR','2024-01-01','2024-01-31')
 def test_current_funding_actual_timestamp_and_missing(self):
  a=self.feature();self.assertNotIn(self.m.funds['BP'][T],a['funding_rows']);self.m.funds['BP'][T-8*H][3]=T+1;self.assertFalse(self.feature()['funding_valid'])
 def test_invalid_daily_price_boundary(self):
  self.m.rowmaps['BP'][T-10*D-H][5]+=1;self.assertFalse(self.feature()['valid'])
 def test_purge_common_training_and_future_labels(self):
  rng=np.random.default_rng(901);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;vals=rng.normal(size=5);ff.append(dict(source=t,valid=i!=100,**dict(zip(s.FEATURE_COLS,vals))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);self.assertEqual(a['training_weeks'],[f['source'] for f in ff[44:148] if f['valid']]);self.assertTrue(all(p['training_n']==103 for p in a['models'].values()));yy[ff[148]['source']]['value']=1e20;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()));ff[149]['valid']=False;self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,149)['models'].values()))
 def test_unrestricted_and_independent_fit_not_beta_clipping(self):
  rng=np.random.default_rng(51);x=rng.normal(size=(104,5));b=np.array([1,2,-.3,.4,.7]);dates=np.arange(104)*s.WEEK;y=.001+x@b+rng.normal(size=104)*.01;p=s.fit(x,y,dates,x[0]);q=independent_fit(np.c_[np.ones(104),x],y,dates,np.r_[1,x[0]],False);self.assertGreater(p['beta'][-1],0);np.testing.assert_allclose(p['beta'],q['beta'],atol=1e-12);np.testing.assert_allclose(p['covariance'],q['covariance'],atol=1e-12);self.assertFalse(p['constraint_active']);self.assertIsNone(s.fit(np.ones((70,5)),np.ones(70),np.arange(70)*s.WEEK,np.ones(5))['mu'])
 def test_negative_gap_increment_and_inverse(self):
  p=models();self.assertEqual(s.decision('DF_INFO',p,-.5)[:2],(1.,True));self.assertEqual(s.decision('DF_INV',p,-.5)[:2],(-1.,True));p['DF_INFO']['beta'][-1]=0;self.assertEqual(s.decision('DF_INFO',p,-.5)[:2],(-.5,False));p=models();p['DF_BANK']['mu']=.04;self.assertFalse(s.decision('DF_INFO',p,-.5)[1]);self.assertTrue(s.decision('DF_BANK',p,-.5)[1]);p['DF_BANK']['beta'][-1]=.1;self.assertFalse(s.decision('DF_BANK',p,-.5)[1]);self.assertTrue(s.decision('DF_GAP',p,-.5)[1]);p['DF_GAP']['beta'][-1]=.1;self.assertFalse(s.decision('DF_GAP',p,-.5)[1])
 def test_symmetric_strict_cost_se_and_signed_fallback(self):
  self.assertEqual(s.threshold(s.GATE,0),0);self.assertEqual(s.threshold(-s.GATE,0),0);self.assertEqual(s.threshold(.03,.04),0);p=models();p['DF_INFO']['mu']=None;self.assertTrue(s.decision('DF_GAP',p,-.5)[1]);self.assertTrue(s.decision('DF_PRICE',p,-.5)[1]);self.assertEqual(s.decision('DF_INFO',p,-.5)[:2],(-.5,False));self.assertEqual(s.decision('DF_TREND',p,-.5)[:2],(-.5,False))
 def test_perp_both_directions_week_and_risk_hold(self):
  pp=[{'source':T,'models':models(),'training_n':80,'training_label_end':T-s.WEEK}];ff=[self.feature()];a=s.schedule(self.m,ff,pp,'DF_INFO',T+2*D,T+6*D);self.assertTrue(all(e['weights']=={'BS':0.,'BP':.5} for e in a));b=s.schedule(self.m,ff,pp,'DF_INV',T,T+D,.1);self.assertEqual(b[0]['weights'],{'BS':0.,'BP':-.25});self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'DF_INFO',T,T+D)[0]['weights'])
 def test_hac_calendar_gap_not_observation_gap(self):
  rng=np.random.default_rng(13);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];A=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:A+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(hac(Z,res,dates),10/6*B@A@B,rtol=1e-10,atol=1e-12)
 def test_long_short_funding_and_final_exit(self):
  x=s.ledger.simulate(market(),'DF_INFO',0,3*D,plan([(0,.5),(D,-.5)]));fund=[e for e in x['events'] if e['kind']=='funding'];self.assertEqual(len(fund),2);self.assertLess(fund[0]['cashflow'],0);self.assertGreater(fund[1]['cashflow'],0);self.assertEqual(fund[0]['observed_time'],D+47);self.assertTrue(all(e['instrument']=='BP' for e in x['events']));self.assertEqual(x['events'][-1]['reason'],'end_of_experiment');self.assertAlmostEqual(x['metrics']['initial']+x['metrics']['gross_pnl']+x['metrics']['funding']-x['metrics']['fees']-x['metrics']['impact'],x['metrics']['equity'])
 def test_frozen_delay_and_quantity_minimum(self):
  x=s.ledger.simulate(market(),'DF_INFO',0,3*D,plan([(0,.5)]),delay=1);self.assertEqual(x['events'][0]['time'],2*H);self.assertEqual(x['events'][0]['source_time'],0);self.assertAlmostEqual(x['events'][0]['position']/.001,round(x['events'][0]['position']/.001));z=s.ledger.simulate(market(),'DF_INFO',0,3*D,plan([(0,.01)]));self.assertEqual(z['metrics']['fills'],0)
 def test_missing_execution_does_not_invent_fill(self):
  m=market();m.rowmaps['BP'].pop(H);x=s.ledger.simulate(m,'DF_INFO',0,3*D,plan([(0,.5)]));self.assertEqual(x['metrics']['fills'],0);self.assertEqual(x['skips'][0]['reason'],'missing_execution_bar')
 def test_margin_uses_long_low_and_short_high(self):
  a=s.ledger.simulate(market(),'DF_INFO',0,3*D,plan([(0,.5)]));b=s.ledger.simulate(market(),'DF_INFO',0,3*D,plan([(0,-.5)]));self.assertIsNotNone(a['metrics']['min_adverse_margin_ratio']);self.assertIsNotNone(b['metrics']['min_adverse_margin_ratio']);self.assertNotEqual(a['metrics']['min_adverse_margin_ratio'],b['metrics']['min_adverse_margin_ratio'])
if __name__=='__main__':unittest.main()
