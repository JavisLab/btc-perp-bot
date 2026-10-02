import unittest,copy,math,datetime as dt
import numpy as np
import btc_etfshort_study as s
class PriceMap:
 def get(self,t):
  price=20000+((t//s.HOUR)%1000)
  return [t,price,price,price,price,t+s.HOUR-1]
class Fixed:
 rowmaps={'BS':PriceMap()}
 def observation(self,t,risk=.2):return .5,min(1,risk/.5),.5

def rawrows(n=40):
 return [{'date':(dt.date(2024,1,1)+dt.timedelta(days=i)).strftime('%Y%m%d'),'values':{z:{'short':'10.25','exempt':'1.125','total':'100.5','markets':'B,Q,N'} for z in s.SYMS}} for i in range(n)]
def models(mu=.1,delta=.02,active=False):
 return {'EF_INFO':{'mu':mu,'se':.001,'constraint_active':active},'EF_PRICE':{'mu':mu-delta,'se':.001},'EF_RAW':{'mu':mu,'se':.001}}
class Tests(unittest.TestCase):
 def test_frozen_source_hash_precision_exempt(self):
  self.assertEqual(len(s.inputs()),661);r=rawrows();r[20]['values']['IBIT']['short']='20.75';p=s.reports(Fixed(),r)[20];self.assertAlmostEqual(p['x'],(20.75/100.5-10.25/100.5)/3);self.assertEqual(p['a'],0);self.assertEqual(len(p['previous20']),20);self.assertNotIn(r[20]['date'],p['previous20'])
 def test_twenty_previous_not_current(self):
  r=rawrows();self.assertIsNone(s.reports(Fixed(),r)[19]['x']);r[20]['values']['IBIT']['total']='201';p=s.reports(Fixed(),r)[20];self.assertAlmostEqual(p['a'],math.log(2)/3)
 def test_dst_publication_and_extra_elapsed_days(self):
  self.assertEqual(s.ny_time('20240112',18),s.ms('2024-01-12')+23*s.HOUR);self.assertEqual(s.ny_time('20240712',18),s.ms('2024-07-12')+22*s.HOUR);r=rawrows();a=s.reports(Fixed(),r);b=s.reports(Fixed(),r,7);self.assertTrue(all(y['available']-x['available']==7*s.DAY for x,y in zip(a,b)));self.assertEqual(s.ny_time('20240311',18)-s.ny_time('20240308',18),3*s.DAY-s.HOUR)
 def test_unavailable_and_stale_inclusive_boundary(self):
  a=s.ms('2024-03-01');r=[dict(date='20240228',available=a,price_time=a-2*s.HOUR,previous20=[],x=.1,a=0.,r_report=.01)];f=s.features(Fixed(),r,start=a-s.DAY,end=a+9*s.DAY);self.assertIsNone(f[0]['report']);self.assertTrue(f[1]['valid']);self.assertTrue(f[8]['valid']);self.assertFalse(f[9]['valid'])
 def test_future_reports_cannot_change_past_features(self):
  r=rawrows();base=s.reports(Fixed(),r);t=s.ms('2024-01-26');f=s.features(Fixed(),base,start=t,end=t+s.DAY);bad=copy.deepcopy(r)
  for a in bad[26:]:
   for v in a['values'].values():v.update(short='999',total='1000')
  self.assertEqual(f,s.features(Fixed(),s.reports(Fixed(),bad),start=t,end=t+s.DAY))
 def test_completed_close_not_open_label(self):
  class M:pass
  m=M();t=s.ms('2024-01-01');m.rowmaps={'BS':{t-s.HOUR:[t-s.HOUR,1,1,1,42,t-2]}};self.assertIsNone(s.close(m,t));m.rowmaps['BS'][t-s.HOUR][-1]=t-1;self.assertEqual(s.close(m,t),42);self.assertIsNone(s.close(m,t+s.HOUR))
 def test_calendar_hac_missing_days_not_row_lag(self):
  days=np.array([0,1,2,5,6,9,10,11,17,18])*s.DAY;x=np.arange(10);Z=np.column_stack([np.ones(10),x]);res=np.array([.2,-.3,.5,.7,-.1,.8,-.2,.4,-.6,.1]);meat=np.zeros((2,2))
  for i in range(10):
   for j in range(10):
    l=abs(int(days[i]-days[j]))//s.DAY
    if l<=7:meat+=(1-l/8)*np.outer(Z[i]*res[i],Z[j]*res[j])
  inv=np.linalg.inv(Z.T@Z);expected=10/8*inv@meat@inv;np.testing.assert_allclose(s.hac(Z,res,days),expected,rtol=1e-10,atol=1e-12);self.assertGreater(np.max(np.abs(s.hac(Z,res,days)-s.hac(Z,res,np.arange(10)*s.DAY))),1e-4)
 def test_positive_slope_nested_constraint(self):
  rng=np.random.default_rng(20);a=rng.normal(size=(200,4));y=.1+a@np.array([.2,-.1,.3,.8])+rng.normal(size=200)*.01;days=np.arange(200)*s.DAY;cur=a[-1];info=s.fit(a,y,days,cur,True);price=s.fit(a[:,:3],y,days,cur[:3]);self.assertTrue(info['constraint_active']);self.assertEqual(info['beta'][-1],0);self.assertEqual(info['mu'],price['mu']);self.assertEqual(info['se'],price['se']);np.testing.assert_array_equal(np.array(info['covariance'])[:4,:4],price['covariance']);self.assertTrue(np.all(np.array(info['covariance'])[-1]==0));raw=s.fit(a[:,3:],a[:,3]*.5+.03,days,cur[3:],True);self.assertTrue(raw['constraint_active']);self.assertAlmostEqual(raw['mu'],float(np.mean(a[:,3]*.5+.03)))
 def test_negative_slope_and_rank_failure(self):
  rng=np.random.default_rng(7);a=rng.normal(size=(200,4));y=a@np.array([.1,.2,-.1,-.9]);f=s.fit(a,y,np.arange(200)*s.DAY,a[0],True);self.assertFalse(f['constraint_active']);self.assertLess(f['beta'][-1],0);self.assertIsNone(s.fit(np.ones((200,4)),y,np.arange(200)*s.DAY,a[0],True)['mu']);a[0,0]=np.nan;self.assertIsNone(s.fit(a,y,np.arange(200)*s.DAY,np.zeros(4),True)['mu'])
 def test_training_calendar_window_seven_day_label_purge_future_invariance(self):
  rng=np.random.default_rng(40);z=rng.normal(size=(500,4));t0=s.ms('2022-01-01');rows=[dict(source=t0+i*s.DAY,valid=True,**dict(zip(('r_now','r_report','a','x'),z[i]))) for i in range(500)];yy={r['source']:{'value':float(z[i]@np.array([.1,.2,.3,-.4])),'end':r['source']+7*s.DAY} for i,r in enumerate(rows)};p=s.forecast_one(rows,yy,450);self.assertEqual(p['training_n'],365);self.assertEqual(p['training_days'][0],rows[78]['source']);self.assertEqual(p['training_days'][-1],rows[442]['source']);self.assertEqual(p['training_label_end'],rows[449]['source']);changed=copy.deepcopy(yy)
  for r in rows[443:]:changed[r['source']]['value']=1e6
  self.assertEqual(p,s.forecast_one(rows,changed,450));rows[442]['valid']=False;self.assertEqual(s.forecast_one(rows,yy,450)['training_n'],364)
 def test_warmup_and_missing_hold_core(self):
  t=s.ms('2022-01-01');r=[dict(source=t,valid=False,r_now=None,r_report=None,a=None,x=None)];p=s.forecast_one(r,{t:{'value':None,'end':t+7*s.DAY}},0);self.assertTrue(all(v['mu'] is None for v in p['models'].values()));self.assertEqual(s.decision('EF_INFO',p['models'],-.5)[:2],(0,False));self.assertEqual(s.decision('EF_INFO',p['models'],.5)[:2],(.5,False))
 def test_information_increment_inverse_and_exact_zero(self):
  p=models();self.assertEqual(s.decision('EF_INFO',p,.5)[:2],(1.,True));self.assertEqual(s.decision('EF_INV',p,.5)[:2],(-1.,True));self.assertEqual(s.decision('EF_TREND',p,.5)[:2],(.5,False));self.assertEqual(s.decision('EF_INFO',models(delta=-.02),.5)[:2],(.5,False));self.assertEqual(s.decision('EF_INFO',models(active=True),.5),(.5,False,0.));self.assertEqual(s.decision('EF_INFO',models(mu=-.1,delta=-.02),.5)[:2],(-1.,True));self.assertEqual(s.threshold(s.LONG_GATE+.001,.001),0)
 def test_schedule_risk_fallback_and_missing_hold(self):
  t=s.ms('2022-01-01');f=[dict(source=t,report=None,available=None,age_hours=None,valid=False)];p=[dict(source=t,models={n:{'mu':None,'se':None} for n in s.MODELS},training_n=0,training_label_end=None)];m=Fixed();a=s.schedule(m,f,p,'EF_INFO',t,t+s.DAY,.1)[0];self.assertEqual(a['weights'],{'BS':.1,'BP':0.});m.observation=lambda *x:None;self.assertIsNone(s.schedule(m,f,p,'EF_INFO',t,t+s.DAY)[0]['weights'])
 def test_costs_funding_signs_and_delayed_first_fill(self):
  class M:pass
  m=M();start=s.ms('2022-01-01');end=start+2*s.DAY;rr={t:[t,20000.,20000.,20000.,20000.,t+s.HOUR-1] for t in range(start,end,s.HOUR)};m.rowmaps={'BS':rr,'BP':rr};m.markmaps=m.rowmaps;m.funds={'BP':{start+8*s.HOUR:[start+8*s.HOUR,8,.001,start+8*s.HOUR],start+16*s.HOUR:[start+16*s.HOUR,8,-.001,start+16*s.HOUR]}}
  for direction in (1,-1):
   plan=[{'source_time':start,'weights':{'BS':.3 if direction>0 else 0.,'BP':-.3 if direction<0 else 0.}}];a=s.ledger.simulate(m,'EF_INFO',start,end,plan);self.assertLess(a['metrics']['net_pnl'],0);self.assertAlmostEqual(a['metrics']['gross_pnl'],0);self.assertAlmostEqual(a['metrics']['net_pnl'],-a['metrics']['fees']-a['metrics']['impact']+a['metrics']['funding']);fund=[e['cashflow'] for e in a['events'] if e['kind']=='funding']
   if direction<0:self.assertGreater(fund[0],0);self.assertLess(fund[1],0)
   else:self.assertEqual(fund,[])
   b=s.ledger.simulate(m,'EF_INFO',start,end,plan,delay=24);first=next(e for e in b['events'] if e['kind']=='fill');self.assertEqual(first['time'],start+25*s.HOUR);c=s.ledger.simulate(m,'EF_INFO',start,end,plan,multiplier=2);self.assertGreater(c['metrics']['fees']+c['metrics']['impact'],a['metrics']['fees']+a['metrics']['impact'])
if __name__=='__main__':unittest.main()
