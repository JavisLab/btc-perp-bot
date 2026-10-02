import unittest,math,copy
import numpy as np
import btc_path_study as s
class Fake:
 def __init__(self,n=470):
  self.first=s.ms('2020-01-01');self.rowmaps={'BS':{}};self.index={};self.close=[]
  for h in range(-1,n*24):
   t=self.first+h*s.HOUR;p=100*math.exp(.0001*h+.02*math.sin(h*.09)+.008*math.cos(h*.017));self.rowmaps['BS'][t]=[t,p,p,p,p,t+s.HOUR-1]
  for i in range(n):self.index[self.first+i*s.DAY]=i;self.close.append(self.rowmaps['BS'][self.first+(i*24+23)*s.HOUR][4])
  self.close=np.array(self.close)
def curves(n=460):
 out=[];h=np.arange(1,25)/24
 for i in range(n):
  r=.02*math.sin(i*.31)+.001*i/n;a=.04*math.sin(i*.23);b=.006*math.cos(i*.07);c=r*h+a*h*(1-h)+b*np.sin(h*2*math.pi);d=s.ms('2020-01-01')+i*s.DAY;out.append({'day':d,'available':d+s.DAY,'valid':True,'curve':c.tolist(),'r':float(c[-1]),'rv':float(sum(np.diff(np.r_[0.,c])**2)),'area':float(np.mean(c-h*c[-1]))})
 return out
def forecast(mu=None):return {'mu':list(mu if mu is not None else np.arange(1,25)*.002),'covariance_upper':[0.]*300,'leverage':1.,'training_n':365}
class Tests(unittest.TestCase):
 def test_equal_endpoint_different_path_area(self):
  m=Fake();d=m.first+100*s.DAY;p0=m.rowmaps['BS'][d-s.HOUR][4]
  for h in range(1,25):m.rowmaps['BS'][d+(h-1)*s.HOUR][4]=p0*math.exp(.03*h/24)
  a=s.raw_curves(m,d,d+s.DAY)[0];self.assertAlmostEqual(a['area'],0)
  for h in range(1,24):m.rowmaps['BS'][d+(h-1)*s.HOUR][4]*=math.exp(.01)
  b=s.raw_curves(m,d,d+s.DAY)[0];self.assertEqual(a['r'],b['r']);self.assertAlmostEqual(b['area'],.01*23/24)
 def test_complete_boundary_missing_and_clock(self):
  m=Fake();d=m.first+100*s.DAY;self.assertTrue(s.raw_curves(m,d,d+s.DAY)[0]['valid']);m.rowmaps['BS'][d-s.HOUR][5]=d;self.assertFalse(s.raw_curves(m,d,d+s.DAY)[0]['valid']);m=Fake();del m.rowmaps['BS'][d+5*s.HOUR];self.assertFalse(s.raw_curves(m,d,d+s.DAY)[0]['valid'])
 def test_extra_day_label_purge_and_window(self):
  rr=curves();t=rr[410]['day'];a=s.predict(rr,t,t+s.DAY)[0];self.assertEqual(a['training_days'][0],t-366*s.DAY);self.assertEqual(a['training_days'][-1],t-2*s.DAY);self.assertEqual(a['training_label_end'],t-s.DAY);rr[409]['curve']=[999.]*24;self.assertEqual(s.predict(rr,t,t+s.DAY)[0]['models'],a['models'])
 def test_future_raw_prices_do_not_change_forecast(self):
  m=Fake();t=m.first+410*s.DAY;a=s.predict(s.raw_curves(m,end=t+2*s.DAY),t,t+s.DAY)[0]
  for k,r in m.rowmaps['BS'].items():
   if k>=t:r[4]*=50
  b=s.predict(s.raw_curves(m,end=t+2*s.DAY),t,t+s.DAY)[0];self.assertEqual(a,b)
 def test_minimum_pairs_rank_and_missing_does_not_bridge(self):
  rr=curves();a=s.predict(rr,rr[301]['day'],rr[303]['day']);self.assertIsNone(a[0]['models']['IC_PATH']['mu']);self.assertEqual(a[1]['models']['IC_PATH']['training_n'],300);self.assertIsNotNone(a[1]['models']['IC_PATH']['mu']);t=rr[410]['day'];rr[300]['valid']=False;b=s.predict(rr,t,t+s.DAY)[0];self.assertNotIn(rr[300]['day'],b['training_days']);self.assertNotIn(rr[301]['day'],b['training_days'])
  for e in rr:e['area']=0.
  b=s.predict(rr,t,t+s.DAY)[0];self.assertIsNone(b['models']['IC_PATH']['mu']);self.assertIsNotNone(b['models']['IC_PRICE']['mu'])
 def test_clock_extrema_direction_and_strict_cost_gate(self):
  a=s.choose(forecast());self.assertTrue(a['trade']);self.assertEqual((a['best']['entry_hour'],a['best']['exit_hour'],a['best']['direction']),(1,24,1));b=s.choose(forecast(-np.arange(1,25)*.002));self.assertEqual(b['best']['direction'],-1);mu=[0.]*24;mu[-1]=s.LONG;self.assertFalse(s.choose(forecast(mu))['trade']);mu[-1]+=1e-10;self.assertTrue(s.choose(forecast(mu))['trade']);self.assertFalse(s.choose(forecast([0.]*24))['trade'])
 def test_interval_ties_and_mean_uncertainty(self):
  mu=[0.]*22+[1.,1.];a=s.choose(forecast(mu));self.assertEqual((a['best']['entry_hour'],a['best']['exit_hour']),(1,23));p=forecast();cov=np.eye(24)*.0001;p['covariance_upper']=cov[s.UPPER].tolist();p['leverage']=.5;a=s.choose(p);self.assertAlmostEqual(a['best']['mean_se'],.01);self.assertTrue(np.array_equal(s.unpack(p['covariance_upper']),cov))
 def test_preannounced_release_inverse_same_times(self):
  m=Fake();t=m.first+410*s.DAY;f=[{'source':t,'input_day':t-s.DAY,'training_label_end':t-s.DAY,'models':{k:forecast() for k in s.MODELS}}];a,da=s.schedule(m,f,'IC_PATH',t,t+s.DAY);b,db=s.schedule(m,f,'IC_INV',t,t+s.DAY);self.assertEqual([e['source_time'] for e in a],[t,t+23*s.HOUR]);self.assertEqual([e['source_time'] for e in a],[e['source_time'] for e in b]);self.assertEqual(da[0]['signal'],-db[0]['signal']);self.assertEqual(a[0]['decision_time'],t);self.assertEqual(a[-1]['weights'],{'BS':0.,'BP':0.});self.assertGreaterEqual(a[0]['source_time']+s.HOUR,t+s.HOUR)
 def test_risk_fixed_to_decision_and_half_risk(self):
  m=Fake();t=m.first+410*s.DAY;f=[{'source':t,'input_day':t-s.DAY,'training_label_end':t-s.DAY,'models':{k:forecast() for k in s.MODELS}}];a,da=s.schedule(m,f,'IC_PATH',t,t+s.DAY);b,db=s.schedule(m,f,'IC_PATH',t,t+s.DAY,.1);self.assertAlmostEqual(a[0]['weights']['BS']/2,b[0]['weights']['BS']);m.close[m.index[t]:]*=30;self.assertEqual(s.schedule(m,f,'IC_PATH',t,t+s.DAY)[0],a)
 def test_forecast_mse_separate_from_decision(self):
  rr=curves();t=rr[410]['day'];f=s.predict(rr,t,t+s.DAY);before=s.choose(f[0]['models']['IC_PATH']);base=s.forecast_stats(f,rr,t,t+s.DAY);rr[410]['curve']=[999.]*24;after=s.forecast_stats(f,rr,t,t+s.DAY);self.assertEqual(before,s.choose(f[0]['models']['IC_PATH']));self.assertNotEqual(base['IC_PATH']['mse'],after['IC_PATH']['mse'])
 def test_independent_multivariate_normal_equation_and_clock(self):
  from verify_btc_path_study import independent_model,independent_choice
  rr=curves();t=rr[410]['day'];a=s.predict(rr,t,t+s.DAY)[0];b=independent_model({e['day']:e for e in rr},t);self.assertEqual(a['training_days'],b['training_days'])
  for name in s.MODELS:
   self.assertTrue(np.allclose(a['models'][name]['mu'],b['models'][name]['mu'],rtol=1e-9,atol=1e-10));x=s.choose(a['models'][name]);y=independent_choice(b['models'][name]);self.assertEqual(x['trade'],y['trade'])
   for k in ('entry_hour','exit_hour','direction'):self.assertEqual(x['best'][k],y['best'][k])
 def test_risk_missing_is_explicit_flat(self):
  m=Fake();t=m.first+410*s.DAY;f=[{'source':t,'input_day':t-s.DAY,'training_label_end':t-s.DAY,'models':{k:forecast() for k in s.MODELS}}];m.close[m.index[t-s.DAY]]=np.nan;plan,dec=s.schedule(m,f,'IC_PATH',t,t+s.DAY);self.assertEqual(len(plan),1);self.assertEqual(plan[0]['detail']['action'],'flat');self.assertTrue(dec[0]['risk_missing']);self.assertFalse(dec[0]['trade'])
if __name__=='__main__':unittest.main()
