import unittest,math,copy
from btc_attention_study import raw_features,predict,schedule,signal,DAY,HOUR,ms,LONG_GATE,SHORT_GATE
from btc_cot_study import risk_observation
from test_btc_valuation_study import Fake as PriceFake
class Fake(PriceFake):
 def __init__(self):
  super().__init__();self.data={t:int(10000+500*math.sin(i*.15)+50*(i%7)) for i,t in enumerate(self.data)}
def samples():
 t=ms('2020-01-01');out=[]
 for j in range(460):
  rv=math.sin(j*.7)*.1;out.append(dict(source=t+j*DAY,observation=t+(j-2)*DAY,price_end=t+(j-1)*DAY,expiry=t+(j+1)*DAY,valid=True,r_source=rv,abs_source=abs(rv),r_now=math.cos(j*.4)*.2,attention=math.sin(j*.9)*.3,truth=math.cos(j*.2)*.05,truth_end=t+(j+1)*DAY))
 return out
class Tests(unittest.TestCase):
 def test_day_purge_exact_boundary(self):
  a=samples();i=410;p=predict(a)[i]['models']['AT_INFO'];self.assertIn(i-2,p['training_indices']);self.assertNotIn(i-1,p['training_indices']);self.assertEqual(p['training_indices'][0],i-365);a[i-2]['truth_end']+=1;self.assertNotIn(i-2,predict(a)[i]['models']['AT_INFO']['training_indices'])
 def test_future_and_current_labels(self):
  a=samples();p=predict(a);b=copy.deepcopy(a)
  for e in b[410:]:e['truth']=999;e['attention']=-999;e['r_source']=999
  q=predict(b)
  for i in range(410):self.assertEqual(p[i]['models'],q[i]['models'])
  b=copy.deepcopy(a);b[410]['truth']=999;b[409]['truth']=-999;self.assertEqual(predict(b)[410]['models'],p[410]['models'])
 def test_rank_minimum_uncertainty(self):
  p=predict(samples());self.assertIsNone(p[300]['models']['AT_INFO']['mu']);self.assertIsNotNone(p[301]['models']['AT_INFO']['mu']);self.assertGreater(p[410]['models']['AT_INFO']['se'],0)
  a=samples()
  for e in a:e['attention']=0
  self.assertIsNone(predict(a)[410]['models']['AT_INFO']['mu']);self.assertIsNotNone(predict(a)[410]['models']['AT_PRICE']['mu'])
 def test_direction_cost_boundaries(self):
  se=.01;self.assertEqual(signal(LONG_GATE+se,se),0);self.assertEqual(signal(-SHORT_GATE-se,se),0);self.assertEqual(signal(LONG_GATE+se+1e-9,se),1);self.assertEqual(signal(-SHORT_GATE-se-1e-9,se),-1);self.assertEqual(signal(.002,0),0);self.assertEqual(signal(-.002,0),-1)
 def test_lag_and_price_completion(self):
  m=Fake();t=ms('2021-01-04');a=raw_features(m,m.data,2,t,t+DAY)[0];b=raw_features(m,m.data,9,t,t+DAY)[0];self.assertEqual(a['observation'],t-2*DAY);self.assertEqual(a['price_end'],t-DAY);self.assertEqual(b['observation'],a['observation']-7*DAY)
  for key in m.data:
   if key>t-2*DAY:m.data[key]*=10
  for key,r in m.rowmaps['BS'].items():
   if key>=t:r[4]*=10
  c=raw_features(m,m.data,2,t,t+DAY)[0]
  for k in ('valid','r_source','abs_source','r_now','attention'):self.assertEqual(a[k],c[k])
 def test_weekday_and_missing_or_zero(self):
  m=Fake();t=ms('2021-01-04');e=raw_features(m,m.data,2,t,t+DAY)[0];d=e['observation'];wanted=math.log(m.data[d])-sum(math.log(m.data[d-7*i*DAY]) for i in range(1,9))/8;self.assertAlmostEqual(e['attention'],wanted);self.assertEqual(e['abs_source'],abs(e['r_source']));m.data[d-8*7*DAY]=0;self.assertFalse(raw_features(m,m.data,2,t,t+DAY)[0]['valid']);m=Fake();del m.data[d];self.assertFalse(raw_features(m,m.data,2,t,t+DAY)[0]['valid'])
 def test_inverse_expiry_latest_invalid_cash(self):
  m=Fake();rr=samples()
  for e in rr:e['models']={k:{'mu':-.03,'se':0} for k in ('AT_INFO','AT_PRICE','AT_RAW')}
  t=rr[410]['source'];self.assertEqual(schedule(m,rr,'AT_INFO',t,t+DAY)[0]['detail']['signal'],-1);self.assertEqual(schedule(m,rr,'AT_INV',t,t+DAY)[0]['detail']['signal'],1);rr[410]['valid']=False
  for n in ('AT_INFO','AT_PRICE','AT_RAW','AT_INV'):self.assertEqual(schedule(m,rr,n,t,t+DAY)[0]['detail']['signal'],0)
  self.assertEqual(schedule(m,rr[:410],'AT_INFO',t,t+DAY)[0]['detail']['signal'],0)
 def test_risk_future_prices_irrelevant(self):
  m=Fake();t=ms('2021-01-04');a=risk_observation(m,t,.2);m.close[m.index[t]:]*=100;self.assertEqual(risk_observation(m,t,.2),a)
 def test_future_view_counts_irrelevant(self):
  m=Fake();cut=ms('2021-01-04');rr=raw_features(m,m.data,2,end=ms('2021-02-01'));before=predict(rr);data=copy.deepcopy(m.data)
  for d in data:
   if d>=cut-DAY:data[d]*=12
  after=predict(raw_features(m,data,2,end=ms('2021-02-01')))
  for a,b in zip(before,after):
   if a['source']<=cut:self.assertEqual(a['models'],b['models'])
if __name__=='__main__':unittest.main()
