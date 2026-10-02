import unittest,math,copy,numpy as np
from btc_valuation_study import raw_features,predict,schedule,signal,DAY,HOUR,ms,LONG_GATE,SHORT_GATE
from btc_cot_study import risk_observation
class Fake:
 def __init__(self):
  start=ms('2020-01-01');self.index={start+i*DAY:i for i in range(1400)};self.close=np.array([100+i*.03+math.sin(i*.7) for i in range(1400)]);self.rowmaps={'BS':{}};self.data={}
  for i,c in enumerate(self.close):
   t=start+(i+1)*DAY;self.rowmaps['BS'][t-HOUR]=[t-HOUR,c,c,c,c,t-1];self.data[t-DAY]=1.5+.2*math.sin(i*.15)
def samples():
 t=ms('2020-01-06')
 return [dict(source=t+j*7*DAY,observation=t+(j*7-2)*DAY,price_end=t+(j*7-1)*DAY,expiry=t+(j+1)*7*DAY,valid=True,r7=math.sin(j*.7)*.1,p200=math.cos(j*.4)*.2,v=math.sin(j*.9)*.3,truth=math.cos(j*.2)*.05,truth_end=t+(j+1)*7*DAY) for j in range(140)]
class Tests(unittest.TestCase):
 def test_week_purge_exact_boundary(self):
  a=samples();i=110;p=predict(a)[i]['models']['VA_INC'];self.assertIn(i-2,p['training_indices']);self.assertNotIn(i-1,p['training_indices']);self.assertEqual(p['training_indices'][0],i-104);a[i-2]['truth_end']+=1;self.assertNotIn(i-2,predict(a)[i]['models']['VA_INC']['training_indices'])
 def test_future_and_current_labels(self):
  a=samples();p=predict(a);b=copy.deepcopy(a)
  for e in b[110:]:e['truth']=999;e['v']=-999;e['r7']=999
  q=predict(b)
  for i in range(110):self.assertEqual(p[i]['models'],q[i]['models'])
  b=copy.deepcopy(a);b[110]['truth']=999;b[109]['truth']=-999;self.assertEqual(predict(b)[110]['models'],p[110]['models'])
 def test_rank_minimum_uncertainty(self):
  p=predict(samples());self.assertIsNone(p[78]['models']['VA_INC']['mu']);self.assertIsNotNone(p[79]['models']['VA_INC']['mu']);self.assertGreater(p[110]['models']['VA_INC']['se'],0)
  a=samples()
  for e in a:e['v']=0
  self.assertIsNone(predict(a)[110]['models']['VA_INC']['mu']);self.assertIsNotNone(predict(a)[110]['models']['VA_PRICE']['mu'])
 def test_direction_cost_boundaries(self):
  se=.01;self.assertEqual(signal(LONG_GATE+se,se),0);self.assertEqual(signal(-SHORT_GATE-se,se),0);self.assertEqual(signal(LONG_GATE+se+1e-9,se),1);self.assertEqual(signal(-SHORT_GATE-se-1e-9,se),-1);self.assertEqual(signal(.002,0),0);self.assertEqual(signal(-.002,0),-1)
 def test_observation_lag_and_price_completion(self):
  m=Fake();t=ms('2021-01-04');a=raw_features(m,m.data,2,t,t+DAY)[0];b=raw_features(m,m.data,9,t,t+DAY)[0];self.assertEqual(a['observation'],t-2*DAY);self.assertEqual(a['price_end'],t-DAY);self.assertEqual(a['v'],math.log(m.data[t-2*DAY]));self.assertEqual(b['observation'],a['observation']-7*DAY)
  for key in m.data:
   if key>t-2*DAY:m.data[key]*=10
  for key,r in m.rowmaps['BS'].items():
   if key>=t-DAY:r[4]*=10
  c=raw_features(m,m.data,2,t,t+DAY)[0]
  for k in ('valid','r7','p200','v'):self.assertEqual(a[k],c[k])
 def test_complete_200_days_and_missing_source(self):
  m=Fake();t=ms('2021-01-04');e=raw_features(m,m.data,2,t,t+DAY)[0];b=e['price_end'];values=[m.rowmaps['BS'][b-i*DAY-HOUR][4] for i in range(200)];self.assertAlmostEqual(e['p200'],math.log(values[0]/(sum(values)/200)));self.assertAlmostEqual(e['r7'],math.log(values[0]/values[7]));del m.rowmaps['BS'][b-199*DAY-HOUR];self.assertFalse(raw_features(m,m.data,2,t,t+DAY)[0]['valid']);m=Fake();del m.data[t-2*DAY];self.assertFalse(raw_features(m,m.data,2,t,t+DAY)[0]['valid'])
 def test_inverse_expiry_latest_invalid_cash(self):
  m=Fake();rr=samples()
  for e in rr:e['models']={k:{'mu':-.03,'se':0} for k in ('VA_INC','VA_PRICE','VA_VALUE')}
  t=rr[110]['source'];self.assertEqual(schedule(m,rr,'VA_INC',t,t+DAY)[0]['detail']['signal'],-1);self.assertEqual(schedule(m,rr,'VA_INV',t,t+DAY)[0]['detail']['signal'],1);rr[110]['valid']=False
  for n in ('VA_INC','VA_PRICE','VA_VALUE','VA_INV'):self.assertEqual(schedule(m,rr,n,t,t+DAY)[0]['detail']['signal'],0)
  expiry=rr[109]['expiry'];self.assertEqual(schedule(m,rr[:110],'VA_INC',expiry,expiry+DAY)[0]['detail']['signal'],0)
 def test_risk_future_prices_irrelevant(self):
  m=Fake();t=ms('2021-01-04');a=risk_observation(m,t,.2);m.close[m.index[t]:]*=100;self.assertEqual(risk_observation(m,t,.2),a)
 def test_predicted_weeks_do_not_read_future_mvrv(self):
  m=Fake();cut=ms('2022-01-03');rr=raw_features(m,m.data,2,end=ms('2023-01-01'));before=predict(rr);data=copy.deepcopy(m.data)
  for d in data:
   if d>=cut-DAY:data[d]*=12
  after=predict(raw_features(m,data,2,end=ms('2023-01-01')))
  for a,b in zip(before,after):
   if a['source']<=cut:self.assertEqual(a['models'],b['models'])
if __name__=='__main__':unittest.main()
