"""Causal dated vintages, weekly label purge/HAC, held weekly direction and daily quantity/risk boundaries."""
import copy,math,unittest
import numpy as np
import btc_uncertainty_study as s
T=s.ms('2024-01-01')
class Fixed:
 def __init__(self):self.rowmaps={'BS':{t:[t,100.,100.,100.,100.,t+s.HOUR-1] for t in range(T-40*s.DAY,T+15*s.DAY,s.HOUR)}}
 def observation(self,t,risk=.2):return .5,min(1,risk/.5),.5

def fixtures():
 m=Fixed();v={}
 for monday in (T-s.WEEK,T,T+s.WEEK):
  vintage=monday-3*s.DAY;values={s.date(d):'10' for d in range(vintage-35*s.DAY,vintage,s.DAY)}
  for d in range(vintage-7*s.DAY,vintage,s.DAY):values[s.date(d)]='20'
  v[s.date(vintage)]={'values':values}
 return m,v

def model(mu=.1,delta=.02,active=False):return {'UP_INFO':{'mu':mu,'se':.001,'constraint_active':active},'UP_PRICE':{'mu':mu-delta,'se':.001},'UP_RAW':{'mu':mu,'se':.001,'constraint_active':active}}
def forecast(t,models):return {'source':t,'models':models,'training_n':90,'training_label_end':t-s.WEEK}

class Tests(unittest.TestCase):
 def test_frozen_vintages_masks_and_anomalous_snapshot_warmup(self):
  v,z=s.inputs();self.assertEqual(len(v),349);self.assertEqual(len(z),3);self.assertEqual(set(v['2020-01-03']['values'].values()),{'10.92'});m=s.Market()
  for lag,t in ((0,s.ms('2020-01-06')),(7,s.ms('2020-01-13'))):
   f=s.features(m,v,z,lag,start=t,end=t+s.WEEK)[0];self.assertEqual(f['vintage_date'],'2020-01-03');self.assertIsNone(f['r28']);self.assertFalse(f['valid'])
 def test_friday_monday_clock_disjoint_7_28_windows(self):
  m,v=fixtures();f=s.features(m,v,set(),start=T,end=T+s.WEEK)[0];self.assertTrue(f['valid']);self.assertEqual(f['vintage_date'],'2023-12-29');self.assertEqual(f['u7'],20);self.assertEqual(f['u28'],10);self.assertAlmostEqual(f['x'],math.log(2));self.assertEqual(f['window_dates'][0],'2023-11-24');self.assertEqual(f['window_dates'][-1],'2023-12-28');self.assertEqual(f['vintage_assumed_available'],T)
 def test_seven_day_delay_moves_vintage_not_current_price(self):
  m,v=fixtures();v['2023-12-22']['values']={k:'5' for k in v['2023-12-22']['values']};a=s.features(m,v,set(),start=T,end=T+s.WEEK)[0];b=s.features(m,v,set(),7,start=T,end=T+s.WEEK)[0];self.assertEqual(b['vintage_date'],'2023-12-22');self.assertEqual(b['x'],0);self.assertGreater(a['x'],0);self.assertEqual((a['r7'],a['r28']),(b['r7'],b['r28']))
 def test_future_vintage_revision_or_target_prices_do_not_change_past_features(self):
  m,v=fixtures();a=s.features(m,v,set(),start=T,end=T+s.WEEK)
  v['2024-01-05']['values']={k:'999999' for k in v['2024-01-05']['values']}
  for t,r in m.rowmaps['BS'].items():
   if t>=T:r[1:5]=[99999.]*4
  self.assertEqual(a,s.features(m,v,set(),start=T,end=T+s.WEEK))
 def test_missing_dot_zero_mean_and_no_forward_fill(self):
  m,v=fixtures();values=v['2023-12-29']['values'];key='2023-12-23';values[key]=None;f=s.features(m,v,set(),start=T,end=T+s.WEEK)[0];self.assertFalse(f['valid']);self.assertEqual(f['missing_dates'],[key]);self.assertIsNone(f['x']);del values[key];self.assertEqual(f,s.features(m,v,set(),start=T,end=T+s.WEEK)[0]);values[key]='0';self.assertTrue(s.features(m,v,set(),start=T,end=T+s.WEEK)[0]['valid'])
  for k in values:values[k]='0'
  self.assertIsNone(s.features(m,v,set(),start=T,end=T+s.WEEK)[0]['x'])
 def test_completed_price_clock_and_no_trade_mask(self):
  m,v=fixtures();self.assertIsNone(s.close(m,T,{T-s.HOUR}));m.rowmaps['BS'][T-s.HOUR][-1]=T;self.assertIsNone(s.close(m,T));self.assertFalse(s.features(m,v,set(),start=T,end=T+s.WEEK)[0]['valid'])
 def test_negative_news_coefficient_nests_price_exactly_and_raw_intercept(self):
  rng=np.random.default_rng(20);a=rng.normal(size=(90,3));y=.1+a@np.array([.2,-.1,-.8])+rng.normal(size=90)*.01;weeks=np.arange(90)*s.WEEK;info=s.fit(a,y,weeks,a[-1],True);price=s.fit(a[:,:2],y,weeks,a[-1,:2]);self.assertTrue(info['constraint_active']);self.assertEqual(info['beta'][-1],0);self.assertEqual(info['mu'],price['mu']);self.assertEqual(info['se'],price['se']);np.testing.assert_array_equal(np.array(info['covariance'])[:3,:3],price['covariance']);self.assertTrue(np.all(np.array(info['covariance'])[-1]==0));raw=s.fit(a[:,2:],y,weeks,a[-1,2:],True);self.assertTrue(raw['constraint_active']);self.assertAlmostEqual(raw['mu'],np.mean(y));self.assertEqual(raw['beta'][1],0)
 def test_positive_coefficient_and_rank_rejection(self):
  rng=np.random.default_rng(7);a=rng.normal(size=(90,3));y=a@np.array([.1,.2,.9]);f=s.fit(a,y,np.arange(90)*s.WEEK,a[0],True);self.assertFalse(f['constraint_active']);self.assertGreater(f['beta'][-1],0);self.assertIsNone(s.fit(np.ones((90,3)),y,np.arange(90)*s.WEEK,a[0],True)['mu'])
 def test_calendar_week_hac_missing_weeks_not_compressed(self):
  weeks=np.array([0,1,3,4,8,10,11,15,18,19])*s.WEEK;Z=np.column_stack([np.ones(10),np.arange(10)]);res=np.array([.2,-.3,.5,.7,-.1,.8,-.2,.4,-.6,.1]);meat=np.zeros((2,2))
  for i in range(10):
   for j in range(10):
    lag=abs(weeks[i]-weeks[j])/s.WEEK
    if lag<=1:meat+=(1-lag/2)*np.outer(Z[i]*res[i],Z[j]*res[j])
  bread=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,weeks),10/8*bread@meat@bread,atol=1e-12);self.assertGreater(np.max(np.abs(s.hac(Z,res,weeks)-s.hac(Z,res,np.arange(10)*s.WEEK))),1e-5)
 def test_104_week_window_minimum_52_and_seven_day_label_purge(self):
  rng=np.random.default_rng(40);z=rng.normal(size=(150,3));rows=[dict(source=T+i*s.WEEK,valid=True,**dict(zip(('r7','r28','x'),z[i]))) for i in range(150)];yy={r['source']:{'value':float(z[i]@np.array([.1,.2,.4])),'end':r['source']+s.WEEK} for i,r in enumerate(rows)};p=s.forecast_one(rows,yy,140);self.assertEqual(p['training_n'],104);self.assertEqual(p['training_weeks'][0],rows[35]['source']);self.assertEqual(p['training_weeks'][-1],rows[138]['source']);self.assertEqual(p['training_label_end'],rows[139]['source']);changed=copy.deepcopy(yy)
  for r in rows[139:]:changed[r['source']]['value']=1e6
  self.assertEqual(p,s.forecast_one(rows,changed,140));self.assertIsNotNone(s.forecast_one(rows,yy,53)['models']['UP_INFO']['mu']);self.assertIsNone(s.forecast_one(rows,yy,52)['models']['UP_INFO']['mu']);rows[138]['valid']=False;self.assertEqual(s.forecast_one(rows,yy,140)['training_n'],103)
 def test_increment_constraint_inverse_and_cost_gate(self):
  self.assertEqual(s.decision('UP_INFO',model(),.5)[:2],(1.,True));self.assertEqual(s.decision('UP_INV',model(),.5)[:2],(-1.,True));self.assertEqual(s.decision('UP_TREND',model(),.5)[:2],(.5,False));self.assertEqual(s.decision('UP_INFO',model(delta=-.02),.5)[:2],(.5,False));self.assertEqual(s.decision('UP_INFO',model(active=True),.5)[2],0);self.assertEqual(s.threshold(s.LONG_GATE+.001,.001),0);self.assertEqual(s.decision('UP_INFO',model(mu=-.1,delta=-.02),.5)[:2],(-1.,True));self.assertEqual(s.decision('UP_RAW',model(mu=-.1,delta=.02),.5)[:2],(-1.,True))
 def test_weekly_direction_daily_risk_new_monday_and_period_start(self):
  m,v=fixtures();ff=s.features(m,v,set(),start=T,end=T+2*s.WEEK);pp=[forecast(T,model()),forecast(T+s.WEEK,model(mu=-.1,delta=-.02))];m.observation=lambda t,risk:(-.5,min(1,risk/(.5+(t-T)/s.DAY*.01)),.5+(t-T)/s.DAY*.01);p=s.schedule(m,ff,pp,'UP_INFO',T+3*s.DAY,T+9*s.DAY);self.assertEqual([r['detail']['signal'] for r in p],[1.,1.,1.,1.,-1.,-1.]);self.assertEqual(p[0]['detail']['week_source'],T);self.assertNotEqual(p[0]['weights']['BS'],p[1]['weights']['BS']);self.assertEqual(p[-1]['detail']['week_source'],T+s.WEEK);self.assertLess(p[-1]['weights']['BP'],0)
 def test_missing_week_reverts_core_no_indefinite_fill_and_missing_risk_hold(self):
  m,v=fixtures();ff=s.features(m,v,set(),start=T,end=T+2*s.WEEK);none={n:{'mu':None,'se':None} for n in s.MODELS};pp=[forecast(T,model()),forecast(T+s.WEEK,none)];p=s.schedule(m,ff,pp,'UP_INFO',T+6*s.DAY,T+8*s.DAY);self.assertTrue(p[0]['detail']['override']);self.assertFalse(p[1]['detail']['override']);self.assertEqual(p[1]['weights'],{'BS':.2,'BP':0.});m.observation=lambda *x:None;self.assertIsNone(s.schedule(m,ff,pp,'UP_INFO',T,T+s.DAY)[0]['weights'])
 def test_constant_prices_cost_funding_and_delayed_quantity(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'UP_INFO',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'UP_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'UP_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
