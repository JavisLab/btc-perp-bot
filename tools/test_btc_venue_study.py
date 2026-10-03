"""Meaningful causal-clock, numeraire, missingness, constraint and accounting boundary checks."""
import copy,math,unittest
import numpy as np
import btc_venue_study as s
T=s.ms('2024-01-01')
class Fixed:
 def __init__(self):self.rowmaps={'BS':{t:[t,100.,100.,100.,100.,t+s.HOUR-1] for t in range(T-9*s.DAY,T+3*s.DAY,s.HOUR)}}
 def observation(self,t,risk=.2):return .5,min(1,risk/.5),.5

def fixtures():
 series={n:{t:[t,str(p),str(p),str(p),str(p),'1'] for t in range(T-9*s.DAY,T+3*s.DAY,s.HOUR)} for n,p in [('coinbase-btcusd',90.),('bitstamp-btcusd',90.),('coinbase-usdtusd',.9)]};return Fixed(),series,{n:set() for n in series},set()
def model(mu=.1,delta=.02,active=False):return {'VX_INFO':{'mu':mu,'se':.001,'constraint_active':active},'VX_PRICE':{'mu':mu-delta,'se':.001},'VX_RAW':{'mu':mu,'se':.001,'constraint_active':active}}
class Tests(unittest.TestCase):
 def test_frozen_inputs_and_explicit_masks(self):
  series,masks,excluded=s.inputs();self.assertEqual(sum(len(v) for v in series.values()),140227);self.assertEqual(len(masks['bitstamp-btcusd']),6);self.assertEqual(len(excluded),3)
 def test_fx_units_and_completed_window(self):
  m,ss,mask,z=fixtures();f=s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0];self.assertTrue(f['valid']);self.assertEqual(f['x'],0);self.assertAlmostEqual(f['x_raw'],math.log(.9));self.assertEqual(f['window_first_close'],T-24*s.HOUR);self.assertEqual(f['window_last_close'],T-s.HOUR);self.assertEqual(f['last_available'],T)
 def test_one_hour_buffer_and_additional_day_are_real_elapsed(self):
  m,ss,mask,z=fixtures();ss['coinbase-btcusd'][T-2*s.HOUR][4]='91';ss['coinbase-btcusd'][T-2*s.HOUR][2]='91';a=s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0];b=s.features(m,ss,mask,z,24,start=T,end=T+s.DAY)[0];self.assertGreater(a['x'],0);self.assertEqual(b['x'],0);self.assertEqual(a['window_last_close']-b['window_last_close'],s.DAY)
 def test_future_external_or_target_prices_do_not_change_features(self):
  m,ss,mask,z=fixtures();a=s.features(m,ss,mask,z,start=T,end=T+s.DAY)
  for n in ss:
   for t,r in ss[n].items():
    if t>=T-s.HOUR:r[1:5]=['99999']*4
  for t,r in m.rowmaps['BS'].items():
   if t>=T:r[1:5]=[99999.]*4
  self.assertEqual(a,s.features(m,ss,mask,z,start=T,end=T+s.DAY))
 def test_any_missing_hour_no_forward_fill(self):
  m,ss,mask,z=fixtures();del ss['coinbase-btcusd'][T-5*s.HOUR];f=s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0];self.assertFalse(f['valid']);self.assertEqual(f['missing_window_ends'],[T-4*s.HOUR]);self.assertIsNone(f['x'])
 def test_zero_volume_mask_and_clock_reject(self):
  m,ss,mask,z=fixtures();ss['bitstamp-btcusd'][T-4*s.HOUR][-1]='0';self.assertFalse(s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0]['valid']);self.assertIsNone(s.close(m,T,{T-s.HOUR}));m.rowmaps['BS'][T-s.HOUR][-1]=T-2;self.assertIsNone(s.close(m,T));mask['coinbase-usdtusd'].add(T-2*s.HOUR);self.assertIsNone(s.external_close(ss,mask,'coinbase-usdtusd',T-s.HOUR))
 def test_nonpositive_gap_slope_nests_price_exactly(self):
  rng=np.random.default_rng(20);a=rng.normal(size=(200,4));y=.1+a@np.array([.2,-.1,.3,-.8])+rng.normal(size=200)*.01;days=np.arange(200)*s.DAY;info=s.fit(a,y,days,a[-1],True);price=s.fit(a[:,:3],y,days,a[-1,:3]);self.assertTrue(info['constraint_active']);self.assertEqual(info['beta'][-1],0);self.assertEqual(info['mu'],price['mu']);self.assertEqual(info['se'],price['se']);np.testing.assert_array_equal(np.array(info['covariance'])[:4,:4],price['covariance']);self.assertTrue(np.all(np.array(info['covariance'])[-1]==0))
 def test_positive_gap_slope_and_rank_failure(self):
  rng=np.random.default_rng(7);a=rng.normal(size=(200,4));y=a@np.array([.1,.2,-.1,.9]);f=s.fit(a,y,np.arange(200)*s.DAY,a[0],True);self.assertFalse(f['constraint_active']);self.assertGreater(f['beta'][-1],0);self.assertIsNone(s.fit(np.ones((200,4)),y,np.arange(200)*s.DAY,a[0],True)['mu'])
 def test_hac_calendar_gaps_not_compressed_rows(self):
  days=np.array([0,1,3,4,8,10,11,15,18,19])*s.DAY;Z=np.column_stack([np.ones(10),np.arange(10)]);res=np.array([.2,-.3,.5,.7,-.1,.8,-.2,.4,-.6,.1]);meat=np.zeros((2,2))
  for i in range(10):
   for j in range(10):
    lag=abs(days[i]-days[j])/s.DAY
    if lag<=1:meat+=(1-lag/2)*np.outer(Z[i]*res[i],Z[j]*res[j])
  bread=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,days),10/8*bread@meat@bread,atol=1e-12);self.assertGreater(np.max(np.abs(s.hac(Z,res,days)-s.hac(Z,res,np.arange(10)*s.DAY))),1e-5)
 def test_training_purge_and_future_label_invariance(self):
  rng=np.random.default_rng(40);z=rng.normal(size=(500,5));rows=[dict(source=T+i*s.DAY,valid=True,**dict(zip(('r1','r7','fx','x','x_raw'),z[i]))) for i in range(500)];yy={r['source']:{'value':float(z[i]@np.array([.1,.2,.3,.4,.1])),'end':r['source']+s.DAY} for i,r in enumerate(rows)};p=s.forecast_one(rows,yy,450);self.assertEqual(p['training_n'],365);self.assertEqual(p['training_days'][0],rows[84]['source']);self.assertEqual(p['training_days'][-1],rows[448]['source']);self.assertEqual(p['training_label_end'],rows[449]['source']);changed=copy.deepcopy(yy)
  for r in rows[449:]:changed[r['source']]['value']=1e6
  self.assertEqual(p,s.forecast_one(rows,changed,450));rows[448]['valid']=False;self.assertEqual(s.forecast_one(rows,yy,450)['training_n'],364)
 def test_consensus_information_not_just_prediction_sign(self):
  f=dict(xC=.01,xS=.02,rawC=.01,rawS=.02);self.assertEqual(s.decision('VX_INFO',model(),f,.5)[:2],(1.,True));self.assertEqual(s.decision('VX_INV',model(),f,.5)[:2],(-1.,True));self.assertEqual(s.decision('VX_TREND',model(),f,.5)[:2],(.5,False));f['xS']=-.01;self.assertEqual(s.decision('VX_INFO',model(),f,.5)[:2],(.5,False));self.assertEqual(s.decision('VX_RAW',model(),f,.5)[:2],(1.,True));f['xS']=.01;self.assertEqual(s.decision('VX_INFO',model(delta=-.02),f,.5)[:2],(.5,False));self.assertEqual(s.decision('VX_INFO',model(active=True),f,.5)[2],0);self.assertEqual(s.threshold(s.LONG_GATE+.001,.001),0)
 def test_missing_models_core_and_no_silent_reversal(self):
  m,ss,mask,z=fixtures();f=s.features(m,ss,mask,z,start=T,end=T+s.DAY);p=s.forecast_one(f,{T:{'value':None,'end':T+s.DAY}},0);self.assertTrue(all(v['mu'] is None for v in p['models'].values()));a=s.schedule(m,f,[p],'VX_INFO',T,T+s.DAY,.1)[0];self.assertEqual(a['weights'],{'BS':.1,'BP':0.});m.observation=lambda *x:None;self.assertIsNone(s.schedule(m,f,[p],'VX_INFO',T,T+s.DAY)[0]['weights'])
 def test_negative_consensus_and_numeraire_wrong_control(self):
  f=dict(xC=-.01,xS=-.02,rawC=.01,rawS=.02);self.assertEqual(s.decision('VX_INFO',model(mu=-.1,delta=-.02),f,.5)[:2],(-1.,True));self.assertEqual(s.decision('VX_RAW',model(mu=-.1,delta=-.02),f,.5)[:2],(.5,False));self.assertEqual(s.decision('VX_PRICE',model(mu=-.1,delta=-.02),f,.5)[:2],(-1.,True))
 def test_costs_funding_signs_and_delayed_first_fill(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'VX_INFO',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'VX_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'VX_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
