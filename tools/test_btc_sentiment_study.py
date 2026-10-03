"""Synthetic clocks, contamination controls and accounting for FGI; no historical model or PNL."""
import copy,math,unittest
import numpy as np
import btc_sentiment_study as s
class FakeMarket:
 def __init__(self):
  self.rowmaps={'BS':{}}
  for i,d in enumerate(range(s.ms('2018-01-01'),s.ms('2028-01-01'),s.DAY)):
   c=100*math.exp(.08*math.sin(i/17)+.03*math.cos(i/3)+i/5000);t=d+23*s.HOUR;self.rowmaps['BS'][t]=[t,c,c,c,c,d+s.DAY-1]
 def observation(self,t,risk):return .5,min(1,risk/.4),.4

def sample(t):
 fng={};volume={}
 for i,d in enumerate(range(t-150*s.DAY,t+40*s.DAY,s.DAY)):
  fng[d]={'value':i%101,'valid':True,'base_assumed_available':d+2*s.DAY};volume[d]={'quote':str(100000+i*290+(i%13)*870),'valid':True}
 return fng,volume

def pred(mu,se=0.):return {'mu':mu,'se':se}
def models(info=.03,mkt=.01,sent=-.02,price=0):return dict(zip(s.MODELS,[pred(info),pred(mkt),pred(sent),pred(price)]))
class Tests(unittest.TestCase):
 def setUp(self):self.t=s.ms('2024-01-08');self.m=FakeMarket();self.f,self.v=sample(self.t)
 def feature(self,f=None,v=None,lag=0):return s.features(self.m,self.f if f is None else f,self.v if v is None else v,set(),lag,self.t,self.t+s.WEEK)[0]
 def test_Dplus2_lag7_and_consecutive_windows(self):
  e=self.feature();b=self.feature(lag=7);self.assertEqual(e['last_observation_day'],self.t-2*s.DAY);self.assertEqual(e['last_market_close'],self.t-s.DAY);self.assertEqual(b['last_observation_day'],self.t-9*s.DAY);self.assertEqual(b['last_assumed_available'],self.t);self.assertEqual(e['price_days'],list(range(self.t-92*s.DAY,self.t-s.DAY,s.DAY)));self.assertEqual(e['quote_days'],e['price_days'][1:]);self.assertEqual(e['fng_days'],list(range(self.t-8*s.DAY,self.t-s.DAY,s.DAY)))
 def test_exact_30_90_return_std_and_quote_means(self):
  e=self.feature();p=e['prices'];r=np.array([math.log(b/a) for a,b in zip(p,p[1:])]);self.assertAlmostEqual(e['r30'],math.log(p[-1]/p[-31]),14);self.assertAlmostEqual(e['r90'],math.log(p[-1]/p[0]),14);self.assertAlmostEqual(e['lv30'],math.log(np.std(r[-30:],ddof=1)),12);self.assertAlmostEqual(e['lv90'],math.log(np.std(r,ddof=1)),12);self.assertAlmostEqual(e['qratio'],math.log(sum(e['quotes'][-30:])/30/(sum(e['quotes'])/90)),14)
 def test_price_quote_units_invariant(self):
  a=self.feature()
  for r in self.m.rowmaps['BS'].values():r[4]*=1000000
  v=copy.deepcopy(self.v)
  for r in v.values():r['quote']=str(float(r['quote'])*100000000)
  b=self.feature(v=v)
  for k in s.MARKET_COLS:self.assertAlmostEqual(a[k],b[k],11)
 def test_fng_zero100_and_midpoint_no_log_or_threshold(self):
  for score,want in ((0,-1),(50,0),(100,1)):
   f=copy.deepcopy(self.f)
   for r in f.values():r['value']=score
   e=self.feature(f=f);self.assertTrue(e['valid']);self.assertEqual(e['g'],want)
 def test_fng_missing_outside_range_noninteger_late(self):
  for k in ('missing','negative','large','noninteger','late'):
   f=copy.deepcopy(self.f);d=self.t-2*s.DAY
   if k=='missing':del f[d]
   elif k=='negative':f[d]['value']=-1
   elif k=='large':f[d]['value']=101
   elif k=='noninteger':f[d]['value']=50.1
   else:f[d]['base_assumed_available']=self.t+1
   e=self.feature(f=f);self.assertFalse(e['valid']);self.assertIn(d,e['bad_fng_days'])
 def test_missing_quote_not_filled_and_common_invalid(self):
  for ago in (91,31,2):
   for kind in ('missing','zero','bad','nan'):
    v=copy.deepcopy(self.v);d=self.t-ago*s.DAY
    if kind=='missing':del v[d]
    elif kind=='zero':v[d]['quote']='0'
    elif kind=='bad':v[d]['valid']=False
    else:v[d]['quote']='nan'
    self.assertFalse(self.feature(v=v)['valid'],(ago,kind))
 def test_future_all_inputs_and_target_dont_change_current_feature(self):
  a=self.feature();f,v=copy.deepcopy(self.f),copy.deepcopy(self.v)
  for d,r in f.items():
   if d>self.t-2*s.DAY:r['value']=0
  for d,r in v.items():
   if d>self.t-2*s.DAY:r['quote']='99999999999999'
  for r in self.m.rowmaps['BS'].values():
   if r[5]>=self.t-s.DAY:r[4]*=100
  self.assertEqual(a,self.feature(f=f,v=v))
 def test_completed_clock_price_mask_and_log_vol_zero(self):
  d=self.t-2*s.DAY;row=self.m.rowmaps['BS'][d+23*s.HOUR];row[5]+=1;self.assertFalse(self.feature()['valid']);row[5]-=1
  for r in self.m.rowmaps['BS'].values():r[4]=100.
  e=self.feature();self.assertFalse(e['valid']);self.assertIsNone(e['lv30']);self.assertIsNone(e['lv90'])
 def test_max_drawdown_includes_recovered_trough(self):
  d=self.t-2*s.DAY
  for row in self.m.rowmaps['BS'].values():row[4]=100.
  for lag,c in [(2,140),(1,70),(0,140)]:self.m.rowmaps['BS'][d-lag*s.DAY+23*s.HOUR][4]=c
  e=self.feature();self.assertEqual(e['dd30'],.5);self.assertEqual(e['dd90'],.5);self.assertEqual(1-e['prices'][-1]/max(e['prices']),0)
 def test_cohort_shift_not_current_one_day_fng(self):
  a=self.feature();f=copy.deepcopy(self.f);f[self.t-s.DAY]['value']=100;self.assertEqual(a,self.feature(f=f));f[self.t-2*s.DAY]['value']+=1;b=self.feature(f=f);self.assertAlmostEqual(b['g']-a['g'],1/350,14)
 def test_positive_negative_sentiment_slopes_unconstrained(self):
  rng=np.random.default_rng(304);x=rng.normal(size=(100,8));dates=np.arange(100)*s.WEEK;beta=np.array([.01,-.02,.005,.009,-.03,.02,.003,.04])
  for last in (-.04,.04):
   beta[-1]=last;y=.004+x@beta;p=s.fit(x,y,dates,x[0]);np.testing.assert_allclose(p['beta'],np.r_[.004,beta],atol=1e-12);self.assertFalse(p['constraint_active'])
 def test_common_104_week_mask_min52_purge_future_label(self):
  rng=np.random.default_rng(10);ff=[];yy={}
  for i in range(150):
   t=s.FIRST+i*s.WEEK;ff.append(dict(source=t,valid=i!=100,**dict(zip(s.MARKET_COLS+('g',),rng.normal(size=8)))));yy[t]={'end':t+s.WEEK,'value':float(rng.normal()*.02)}
  a=s.forecast_one(ff,yy,149);want=[f['source'] for f in ff[44:148] if f['valid']];self.assertEqual(a['training_weeks'],want);self.assertTrue(all(p['training_n']==len(want) for p in a['models'].values()));self.assertEqual(a['training_label_end'],ff[148]['source']);yy[ff[148]['source']]['value']=10;yy[ff[149]['source']]['value']=10;self.assertEqual(a,s.forecast_one(ff,yy,149));self.assertTrue(all(p['mu'] is None for p in s.forecast_one(ff,yy,52)['models'].values()));self.assertTrue(all(p['mu'] is not None for p in s.forecast_one(ff,yy,53)['models'].values()))
 def test_rank_deficient_and_invalid_common_features(self):
  x=np.ones((70,8));self.assertIsNone(s.fit(x,np.arange(70),np.arange(70)*s.WEEK,x[0])['mu']);ff=[dict(source=self.t,valid=False)];yy={self.t:{'end':self.t+s.WEEK,'value':.1}};p=s.forecast_one(ff,yy,0);self.assertTrue(all(v['mu'] is None for v in p['models'].values()))
 def test_calendar_hac_not_compressed_gaps(self):
  rng=np.random.default_rng(12);Z=np.c_[np.ones(10),rng.normal(size=(10,3))];res=rng.normal(size=10);dates=np.array([0,1,2,4,5,6,8,9,10,11])*s.WEEK;v=Z*res[:,None];M=v.T@v
  for i,t in enumerate(dates):
   for j,u in enumerate(dates):
    if t-u==s.WEEK:M+=.5*(np.outer(v[i],v[j])+np.outer(v[j],v[i]))
  B=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,dates),10/6*B@M@B,rtol=1e-10,atol=1e-12)
 def test_cost_and_incremental_gate_inverse_same_events(self):
  self.assertEqual(s.decision('FG_INFO',models(),.5)[:2],(1.,True));self.assertEqual(s.decision('FG_INV',models(),.5)[:2],(-1.,True));self.assertEqual(s.decision('FG_INFO',models(info=.03,mkt=.04),.5)[:2],(.5,False));self.assertEqual(s.decision('FG_INFO',models(info=-.03,mkt=-.01),.5)[:2],(-1.,True));self.assertEqual(s.threshold(.001,0),0);self.assertEqual(s.decision('FG_SENT',models(),.5)[:2],(-1.,True))
 def test_same_week_direction_partial_week_and_daily_risk(self):
  ff=[dict(source=self.t,valid=True)];pp=[dict(source=self.t,models=models(),training_n=70,training_label_end=self.t-s.WEEK)];a=s.schedule(self.m,ff,pp,'FG_INFO',self.t+2*s.DAY,self.t+6*s.DAY);self.assertTrue(all(e['detail']['week_source']==self.t and e['weights']=={'BS':.5,'BP':0.} for e in a));b=s.schedule(self.m,ff,pp,'FG_INFO',self.t+2*s.DAY,self.t+6*s.DAY,.1);self.assertTrue(all(e['weights']['BS']==.25 for e in b))
 def test_invalid_data_core_but_missing_risk_hold(self):
  models_none={k:pred(None,None) for k in s.MODELS};self.assertEqual(s.decision('FG_INFO',models_none,.5)[:2],(.5,False));ff=[dict(source=self.t,valid=False)];pp=[dict(source=self.t,models=models_none,training_n=0,training_label_end=None)];self.m.observation=lambda t,risk:None;self.assertIsNone(s.schedule(self.m,ff,pp,'FG_INFO',self.t,self.t+s.DAY)[0]['weights'])
 def test_constant_prices_fees_funding_delay(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'FG_INFO',start,end,plan);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'FG_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);self.assertEqual(first['source_time'],start);c=s.ledger.simulate(m,'FG_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
