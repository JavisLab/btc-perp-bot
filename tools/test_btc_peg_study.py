"""Causal UTC clocks, USD numeraire, sign restriction, cash events and accounting boundaries."""
import copy,math,unittest
import numpy as np
import btc_peg_study as s
T=s.ms('2024-01-01')
class Fixed:
 def observation(self,t,risk=.2):return .5,min(1,risk/.5),.5

def fixtures():
 series={n:{t:[t,str(p),str(p),str(p),str(p),'1'] for t in range(T-9*s.DAY,T+3*s.DAY,s.HOUR)} for n,p in [('coinbase-btcusd',100.),('coinbase-usdtusd',1.001)]}
 return Fixed(),series,{n:set() for n in series},set()
def models(mu=-.1,delta=-.02,active=False):return {'PG_INFO':{'mu':mu,'se':.001,'constraint_active':active},'PG_PRICE':{'mu':mu-delta,'se':.001}}
class Tests(unittest.TestCase):
 def test_frozen_inputs_without_refetch(self):
  ss,mask,z=s.inputs();self.assertEqual(len(ss['coinbase-btcusd']),46763);self.assertEqual(len(ss['coinbase-usdtusd']),46688);self.assertEqual(len(z),3)
 def test_log_level_not_log_return_or_nominal_usdt_units(self):
  m,ss,mask,z=fixtures();f=s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0];self.assertTrue(f['valid']);self.assertAlmostEqual(f['premium'],math.log(1.001));self.assertEqual(f['fx'],0);self.assertEqual(f['window_first_close'],T-24*s.HOUR);self.assertEqual(f['window_last_close'],T-s.HOUR);self.assertEqual(f['last_available'],T)
 def test_actual_one_hour_and_extra_24h_buffer(self):
  m,ss,mask,z=fixtures();ss['coinbase-usdtusd'][T-2*s.HOUR][1:5]=['1.002']*4;a=s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0];b=s.features(m,ss,mask,z,24,start=T,end=T+s.DAY)[0];self.assertGreater(a['premium'],b['premium']);self.assertEqual(a['window_last_close']-b['window_last_close'],s.DAY);self.assertEqual(b['last_available'],T)
 def test_future_prices_do_not_enter_features(self):
  m,ss,mask,z=fixtures();a=s.features(m,ss,mask,z,start=T,end=T+s.DAY)
  for n in ss:
   for t,r in ss[n].items():
    if t>=T-s.HOUR:r[1:5]=['99999']*4
  self.assertEqual(a,s.features(m,ss,mask,z,start=T,end=T+s.DAY))
 def test_missing_fx_hour_and_price_endpoint_do_not_fill(self):
  m,ss,mask,z=fixtures();del ss['coinbase-usdtusd'][T-5*s.HOUR];f=s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0];self.assertFalse(f['valid']);self.assertEqual(f['missing_window_ends'],[T-4*s.HOUR]);self.assertIsNone(f['premium']);m,ss,mask,z=fixtures();del ss['coinbase-btcusd'][T-2*s.HOUR-7*s.DAY];self.assertFalse(s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0]['valid'])
 def test_zero_volume_bad_ohlc_and_explicit_mask(self):
  m,ss,mask,z=fixtures();ss['coinbase-usdtusd'][T-4*s.HOUR][-1]='0';self.assertFalse(s.features(m,ss,mask,z,start=T,end=T+s.DAY)[0]['valid']);ss['coinbase-btcusd'][T-2*s.HOUR][4]='101';self.assertIsNone(s.external_close(ss,mask,'coinbase-btcusd',T-s.HOUR));mask['coinbase-usdtusd'].add(T-2*s.HOUR);self.assertIsNone(s.external_close(ss,mask,'coinbase-usdtusd',T-s.HOUR))
 def test_usd_target_not_fx_induced_native_change(self):
  m,ss,mask,z=fixtures();y=s.labels(ss,mask,start=T,end=T+s.DAY)[T];ss['coinbase-usdtusd'][T+s.DAY-s.HOUR][1:5]=['.5']*4;self.assertEqual(y,s.labels(ss,mask,start=T,end=T+s.DAY)[T]);self.assertEqual(y['value'],0);self.assertEqual(y['base_available'],T+s.DAY+s.HOUR);ss['coinbase-btcusd'][T+s.DAY-s.HOUR][1:5]=['110']*4;self.assertAlmostEqual(s.labels(ss,mask,start=T,end=T+s.DAY)[T]['value'],math.log(1.1))
 def test_positive_premium_slope_nests_control_exactly(self):
  rng=np.random.default_rng(20);a=rng.normal(size=(200,4));y=.1+a@np.array([.2,-.1,.3,.8])+rng.normal(size=200)*.01;days=np.arange(200)*s.DAY;i=s.fit(a,y,days,a[-1],True);p=s.fit(a[:,:3],y,days,a[-1,:3]);self.assertTrue(i['constraint_active']);self.assertEqual(i['beta'][-1],0);self.assertEqual(i['mu'],p['mu']);self.assertEqual(i['se'],p['se']);np.testing.assert_array_equal(np.array(i['covariance'])[:4,:4],p['covariance']);self.assertTrue(np.all(np.array(i['covariance'])[-1]==0))
 def test_negative_premium_slope_and_rank_rejection(self):
  rng=np.random.default_rng(7);a=rng.normal(size=(200,4));y=a@np.array([.1,.2,-.1,-.9]);f=s.fit(a,y,np.arange(200)*s.DAY,a[0],True);self.assertFalse(f['constraint_active']);self.assertLess(f['beta'][-1],0);self.assertIsNone(s.fit(np.ones((200,4)),y,np.arange(200)*s.DAY,a[0],True)['mu'])
 def test_calendar_hac_does_not_compress_gaps(self):
  days=np.array([0,1,3,4,8,10,11,15,18,19])*s.DAY;Z=np.column_stack([np.ones(10),np.arange(10)]);res=np.array([.2,-.3,.5,.7,-.1,.8,-.2,.4,-.6,.1]);meat=np.zeros((2,2))
  for i in range(10):
   for j in range(10):
    gap=abs(days[i]-days[j])/s.DAY
    if gap<=1:meat+=(1-gap/2)*np.outer(Z[i]*res[i],Z[j]*res[j])
  bread=np.linalg.inv(Z.T@Z);np.testing.assert_allclose(s.hac(Z,res,days),10/8*bread@meat@bread,atol=1e-12);self.assertGreater(np.max(np.abs(s.hac(Z,res,days)-s.hac(Z,res,np.arange(10)*s.DAY))),1e-5)
 def test_training_purge_delays_target_as_well_as_features(self):
  rng=np.random.default_rng(40);z=rng.normal(size=(500,4));rows=[dict(source=T+i*s.DAY,valid=True,availability_delay_hours=0,**dict(zip(('r1','r7','fx','premium'),z[i]))) for i in range(500)];yy={r['source']:{'value':float(z[i]@np.array([.1,.2,.3,-.4])),'end':r['source']+s.DAY,'base_available':r['source']+s.DAY+s.HOUR} for i,r in enumerate(rows)};p=s.forecast_one(rows,yy,450);self.assertEqual(p['training_n'],365);self.assertEqual(p['training_days'][0],rows[84]['source']);self.assertEqual(p['training_days'][-1],rows[448]['source']);changed=copy.deepcopy(yy)
  for r in rows[449:]:changed[r['source']]['value']=1e6
  self.assertEqual(p,s.forecast_one(rows,changed,450));rows[450]['availability_delay_hours']=24;q=s.forecast_one(rows,yy,450);self.assertEqual(q['training_n'],364);self.assertEqual(q['training_days'][-1],rows[447]['source']);self.assertLessEqual(q['training_label_available'],rows[450]['source'])
 def test_cash_zero_is_a_real_event_not_core_fallback(self):
  f={'premium':.001};p=models();self.assertEqual(s.decision('PG_INFO',p,f,.5)[:2],(0.,True));self.assertEqual(s.decision('PG_PRICE',p,f,.5)[:2],(0.,True));self.assertEqual(s.decision('PG_SHORT',p,f,.5)[:2],(-1.,True));self.assertEqual(s.decision('PG_INV',p,f,.5)[:2],(1.,True));self.assertEqual(s.decision('PG_TREND',p,f,.5)[:2],(.5,False));self.assertEqual(s.decision('PG_INFO',p,f,0.)[:2],(0.,True))
 def test_discount_opposite_increment_and_gate_boundary_reject(self):
  self.assertEqual(s.decision('PG_INFO',models(),{'premium':-.001},.5)[:2],(.5,False));self.assertEqual(s.decision('PG_INFO',models(delta=.02),{'premium':.001},.5)[:2],(.5,False));self.assertEqual(s.decision('PG_INFO',models(active=True),{'premium':.001},.5)[2],0.);self.assertFalse(s.defensive_event(models(mu=-s.LONG_GATE-.001),{'premium':.001})[0])
 def test_missing_models_risk_and_cash_schedule(self):
  m,ss,mask,z=fixtures();ff=s.features(m,ss,mask,z,start=T,end=T+s.DAY);p=s.forecast_one(ff,s.labels(ss,mask,start=T,end=T+s.DAY),0);a=s.schedule(m,ff,[p],'PG_INFO',T,T+s.DAY,.1)[0];self.assertEqual(a['weights'],{'BS':.1,'BP':0.});p['models']=models();a=s.schedule(m,ff,[p],'PG_INFO',T,T+s.DAY)[0];self.assertEqual(a['weights'],{'BS':0.,'BP':0.});self.assertTrue(a['detail']['override']);self.assertFalse(a['detail']['core_fallback']);m.observation=lambda *x:None;self.assertIsNone(s.schedule(m,ff,[p],'PG_INFO',T,T+s.DAY)[0]['weights'])
 def test_costs_funding_signs_and_delayed_first_fill(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'PG_INFO',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'PG_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'PG_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
