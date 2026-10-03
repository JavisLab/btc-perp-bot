"""Synthetic external-clock/incremental-information and BTC ledger boundaries."""
import copy,datetime as dt,math,unittest
import numpy as np
import btc_riskoff_study as s
from collect_btc_riskoff_data import normalize
class FakeMarket:
 def observation(self,t,risk):return .5,min(1,risk/.4),.4

def sample(t):
 daily={d:{'day':d,'end':d+s.DAY,'valid':True,'rv':.00003*(1+i%11),'close':100*math.exp(.01*math.sin(i/3)+i/500)} for i,d in enumerate(range(t-100*s.DAY,t+20*s.DAY,s.DAY))}
 vix={d:{'day':d,'valid':True,'base_assumed_available':d+2*s.DAY,'value':15+i/20} for i,d in enumerate(range(t-100*s.DAY,t+20*s.DAY,s.DAY)) if dt.datetime.fromtimestamp(d/1000,dt.timezone.utc).weekday()<5}
 return daily,vix
def pred(mu,se=0.,beta=-.5):return {'mu':mu,'se':se,'beta':[0.,beta]}
def models(info=.03,risk=.01,level=-.02,price=0.,beta=-.5):return dict(zip(s.MODELS,[pred(info,beta=beta),pred(risk),pred(level,beta=beta),pred(price)]))
class Tests(unittest.TestCase):
 def setUp(self):self.t=s.ms('2024-01-08');self.m=FakeMarket();self.d,self.v=sample(self.t)
 def feature(self,d=None,v=None,lag=0):return s.features(self.m,self.d if d is None else d,self.v if v is None else v,set(),lag,self.t,self.t+s.WEEK)[0]
 def test_Dplus2_and_lag7_completed_btc29_days(self):
  a=self.feature();b=self.feature(lag=7);self.assertTrue(a['valid']);self.assertEqual(a['last_market_close'],self.t);self.assertEqual(a['input_days'],list(range(self.t-29*s.DAY,self.t,s.DAY)));self.assertEqual(a['vix_last_day'],self.t-3*s.DAY);self.assertEqual(a['vix_age_days'],3);self.assertEqual(a['vix_last_assumed_available'],self.t-s.DAY);self.assertEqual(b['vix_last_day'],self.t-10*s.DAY);self.assertEqual(b['last_observation_day'],self.t-8*s.DAY);self.assertEqual(b['vix_last_assumed_available'],self.t-s.DAY)
 def test_six_observations_five_intervals_not_six_days(self):
  a=self.feature();obs=a['vix_input_days'];self.assertEqual(len(obs),6);self.assertEqual(obs[-1]-obs[0],7*s.DAY);self.assertAlmostEqual(a['shock'],math.log(self.v[obs[-1]]['value']/self.v[obs[0]]['value']),15);self.assertAlmostEqual(a['level'],math.log(self.v[obs[-1]]['value']),15)
 def test_holiday_absence_not_forward_filled(self):
  v=copy.deepcopy(self.v);del v[self.t-3*s.DAY];e=self.feature(v=v);self.assertTrue(e['valid']);self.assertEqual(e['vix_age_days'],4);self.assertNotIn(self.t-3*s.DAY,e['vix_input_days']);self.assertEqual(len(e['vix_input_days']),6)
 def test_invalid_row_not_skipped_to_older_valid(self):
  before=self.feature();v=copy.deepcopy(self.v);bad=before['vix_input_days'][2];v[bad]['valid']=False;e=self.feature(v=v);self.assertFalse(e['valid']);self.assertEqual(e['vix_input_days'],before['vix_input_days']);self.assertEqual(e['vix_bad_days'],[bad])
 def test_stale_and_short_and_long_span_invalidate_all(self):
  stale={t:v for t,v in self.v.items() if t<=self.t-8*s.DAY};self.assertFalse(self.feature(v=stale)['valid']);obs=self.feature()['vix_input_days'];self.assertFalse(self.feature(v={t:self.v[t] for t in obs[-5:]})['valid']);wide={t:self.v[t] for t in (self.t-3*s.DAY-i*7*s.DAY for i in range(6))};self.assertFalse(self.feature(v=wide)['valid'])
 def test_bad_clock_nonpositive_and_weekend_observations(self):
  for kind in ('clock','zero','negative','nan'):
   v=copy.deepcopy(self.v);r=v[self.t-3*s.DAY]
   if kind=='clock':r['base_assumed_available']+=s.DAY
   else:r['value']={'zero':0.,'negative':-1.,'nan':float('nan')}[kind]
   self.assertFalse(self.feature(v=v)['valid'],kind)
  v=copy.deepcopy(self.v);u=self.t-2*s.DAY;v[u]={'day':u,'base_assumed_available':u+2*s.DAY,'valid':True,'value':15.};self.assertFalse(self.feature(v=v)['valid'])
 def test_vix_units_and_future_independence(self):
  a=self.feature();v=copy.deepcopy(self.v)
  for r in v.values():r['value']*=100
  b=self.feature(v=v);self.assertAlmostEqual(a['shock'],b['shock'],14);self.assertAlmostEqual(b['level']-a['level'],math.log(100),14)
  for u,r in self.v.items():
   if u+2*s.DAY>self.t:r.update(value=1e9,valid=False)
  for u,r in self.d.items():
   if u>=self.t:r.update(close=1e20,rv=100,valid=False)
  self.assertEqual(a,self.feature())
 def test_btc_returns_arithmetic_mean_rv_and_price_units(self):
  a=self.feature();x=a['daily_inputs'];self.assertAlmostEqual(a['r7'],math.log(x['close'][-1]/x['close'][-8]),14);self.assertAlmostEqual(a['r28'],math.log(x['close'][-1]/x['close'][-29]),14)
  for n in (1,7,28):self.assertAlmostEqual(a['v'+str(n)],math.log(sum(x['rv'][-n:])/n),14)
  for r in self.d.values():r['close']*=100000
  b=self.feature()
  for k in s.MARKET_COLS:self.assertAlmostEqual(a[k],b[k],13)
 def test_btc_missing_clock_quality_zero_log_no_epsilon(self):
  for kind in ('missing','quality','end','negative','current_zero'):
   d=copy.deepcopy(self.d);u=self.t-29*s.DAY
   if kind=='missing':del d[u]
   elif kind=='quality':d[u]['valid']=False
   elif kind=='end':d[u]['end']+=1
   elif kind=='negative':d[u]['rv']=-1
   else:d[self.t-s.DAY]['rv']=0
   self.assertFalse(self.feature(d=d)['valid'],kind)
  d=copy.deepcopy(self.d);d[self.t-7*s.DAY]['rv']=0;self.assertTrue(self.feature(d=d)['valid'])
 def test_csv_crossfeed_missing_duplicate_and_holiday(self):
  cb='DATE,OPEN,HIGH,LOW,CLOSE\n01/04/2024,15,16,14,15\n01/05/2024,16,17,15,16\n';fr='observation_date,VIXCLS\n2024-01-01,\n2024-01-04,15\n2024-01-05,16\n';rows,blanks,_=normalize(cb,fr);self.assertEqual(len(rows),2);self.assertTrue(all(r['valid'] for r in rows));self.assertEqual(blanks,['2024-01-01'])
  for cc,ff in ((cb+'01/05/2024,16,17,15,16\n',fr),(cb,fr.replace('2024-01-05,16','2024-01-05,17')),(cb,fr.replace('2024-01-05,16','2024-01-05,'))):self.assertFalse(normalize(cc,ff)[0][-1]['valid'])
 def test_all_unconstrained_slopes_training_common_purge(self):
  rng=np.random.default_rng(8);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;ff.append(dict(source=t,valid=i!=100,**dict(zip(s.MARKET_COLS+('shock','level'),rng.normal(size=7)))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);want=[f['source'] for f in ff[44:148] if f['valid']];self.assertEqual(a['training_weeks'],want);self.assertTrue(all(p['training_n']==len(want) for p in a['models'].values()));self.assertEqual(a['training_label_end'],ff[148]['source']);yy[ff[148]['source']]['value']=100;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()))
  x=rng.normal(size=(100,6));beta=np.array([.01,-.02,.005,.009,-.03,.04]);p=s.fit(x,.004+x@beta,np.arange(100)*s.WEEK,x[0]);np.testing.assert_allclose(p['beta'],np.r_[.004,beta],atol=1e-12);self.assertFalse(p['constraint_active'])
 def test_level_constant_shift_prediction_invariance(self):
  rng=np.random.default_rng(71);x=rng.normal(size=(104,6));y=rng.normal(size=104)*.03;dates=np.arange(104)*s.WEEK;a=s.fit(x,y,dates,x[0]);x[:,-1]+=math.log(100);b=s.fit(x,y,dates,x[0]);self.assertAlmostEqual(a['mu'],b['mu'],13);self.assertAlmostEqual(a['se'],b['se'],13)
 def test_negative_riskoff_beta_and_same_inverse_events(self):
  for name in ('RF_INFO','RF_LEVEL'):
   self.assertTrue(s.decision(name,models(level=.03),.5)[1])
   for beta in (0.,.5):self.assertEqual(s.decision(name,models(beta=beta,level=.03),.5)[:2],(.5,False))
  self.assertEqual(s.decision('RF_INV',models(),.5)[:2],(-1.,True));self.assertEqual(s.decision('RF_INV',models(beta=1),.5)[:2],(.5,False));self.assertEqual(s.decision('RF_INFO',models(info=-.03,risk=-.01),.5)[:2],(-1.,True))
 def test_cost_uncertainty_increment_sign(self):
  self.assertEqual(s.decision('RF_INFO',models(info=.03,risk=.04),.5)[:2],(.5,False));self.assertEqual(s.decision('RF_LEVEL',models(level=.03,risk=.04),.5)[:2],(.5,False));self.assertEqual(s.threshold(.001,0),0);self.assertEqual(s.threshold(.03,.04),0);self.assertEqual(s.threshold(-.001,0),0);self.assertEqual(s.decision('RF_RISK',models(risk=-.03,beta=1),.5)[:2],(-1.,True))
 def test_rank_deficient_invalid_common_features(self):
  x=np.ones((70,8));self.assertIsNone(s.fit(x,np.arange(70),np.arange(70)*s.WEEK,x[0])['mu']);ff=[dict(source=self.t,valid=False)];yy={self.t:{'end':self.t+s.WEEK,'value':.1}};p=s.forecast_one(ff,yy,0);self.assertTrue(all(v['mu'] is None for v in p['models'].values()))
 def test_calendar_hac_not_compressed_gaps(self):
  rng=np.random.default_rng(12);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];M=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:M+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,dates),10/6*B@M@B,rtol=1e-10,atol=1e-12)
 def test_partial_week_same_direction_daily_risk(self):
  ff=[dict(source=self.t,valid=True)];pp=[dict(source=self.t,models=models(),training_n=70,training_label_end=self.t-s.WEEK)];a=s.schedule(self.m,ff,pp,'RF_INFO',self.t+2*s.DAY,self.t+6*s.DAY);self.assertTrue(all(e['detail']['week_source']==self.t and e['weights']=={'BS':.5,'BP':0.} for e in a));b=s.schedule(self.m,ff,pp,'RF_INFO',self.t+2*s.DAY,self.t+6*s.DAY,.1);self.assertTrue(all(e['weights']['BS']==.25 for e in b))
 def test_invalid_data_core_missing_risk_hold(self):
  mm={k:pred(None,None) for k in s.MODELS};self.assertEqual(s.decision('RF_INFO',mm,.5)[:2],(.5,False));ff=[dict(source=self.t,valid=False)];pp=[dict(source=self.t,models=mm,training_n=0,training_label_end=None)];self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'RF_INFO',self.t,self.t+s.DAY)[0]['weights'])
 def test_constant_prices_fees_funding_delay(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'RF_INFO',start,end,plan);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'RF_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);self.assertEqual(first['source_time'],start);c=s.ledger.simulate(m,'RF_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
