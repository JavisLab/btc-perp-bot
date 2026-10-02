import unittest,copy,math
from btc_options_study import raw_features,predict,schedule,signal,LONG_GATE,SHORT_GATE,DAY,HOUR
from test_btc_cot_study import Fake,rows

def samples():
 return [dict(report_date=str(j),report_time=j*7*DAY,source=(j*7+10)*DAY,expiry=(j*7+21)*DAY,valid=True,r=math.sin(j*.7)*.1,f=math.cos(j*.4)*.2,o=math.sin(j*.9)*.3,truth=math.cos(j*.2)*.05,truth_end=(j*7+17)*DAY) for j in range(140)]
class Tests(unittest.TestCase):
 def test_completed_label_boundary(self):
  a=samples();i=110;a[i-1]['truth_end']=a[i]['source']+1;p=predict(a)[i]['models']['OP_INC'];self.assertNotIn(i-1,p['training_indices']);a[i-1]['truth_end']-=1;p=predict(a)[i]['models']['OP_INC'];self.assertIn(i-1,p['training_indices']);self.assertNotIn(i,p['training_indices']);self.assertEqual(p['training_indices'][0],i-104)
 def test_future_positions_and_labels(self):
  a=samples();p=predict(a);b=copy.deepcopy(a)
  for e in b[110:]:e['truth']=999;e['o']=-999;e['r']=999
  q=predict(b)
  for i in range(110):self.assertEqual(p[i]['models'],q[i]['models'])
  b=copy.deepcopy(a);b[110]['truth']=999;self.assertEqual(predict(b)[110]['models'],p[110]['models'])
 def test_se_minimum_rank(self):
  p=predict(samples());self.assertIsNone(p[77]['models']['OP_INC']['mu']);self.assertIsNotNone(p[78]['models']['OP_INC']['mu']);self.assertGreater(p[110]['models']['OP_INC']['se'],0)
  a=samples()
  for e in a:e['o']=0
  self.assertIsNone(predict(a)[110]['models']['OP_INC']['mu']);self.assertIsNotNone(predict(a)[110]['models']['OP_FUT']['mu'])
 def test_directional_cost_and_exact_boundary(self):
  se=.01;self.assertEqual(signal(LONG_GATE+se,se),0);self.assertEqual(signal(-SHORT_GATE-se,se),0);self.assertEqual(signal(LONG_GATE+se+1e-9,se),1);self.assertEqual(signal(-SHORT_GATE-se-1e-9,se),-1);self.assertEqual(signal(.002,0),0);self.assertEqual(signal(-.002,0),-1)
 def test_rounding_and_price_completion(self):
  m=Fake();rr=rows()
  for i,e in enumerate(rr):e.update(futures_net=20+i*10,options_net=5+i*4)
  base=raw_features(m,rr);plus=raw_features(m,rr,'rounding_plus');minus=raw_features(m,rr,'rounding_minus');self.assertAlmostEqual(base[1]['o'],.004);self.assertAlmostEqual(plus[1]['o'],.002);self.assertAlmostEqual(minus[1]['o'],.006);self.assertEqual(base[1]['f'],.01)
  cutoff=rr[1]['source'];before=base[1].copy()
  for t,r in m.rowmaps['BS'].items():
   if t>=cutoff:r[4]*=10
  after=raw_features(m,rr)[1]
  for k in ('r','f','o','valid'):self.assertEqual(before[k],after[k])
 def test_latest_invalid_cash_expiry_inverse(self):
  m=Fake();rr=rows()
  for e in rr:e.update(valid=True,models={n:{'mu':-.02,'se':0} for n in ('OP_INC','OP_FUT','OP_PRICE')})
  t=rr[1]['source'];p=schedule(m,rr,'OP_INC',t,t+DAY);q=schedule(m,rr,'OP_INV',t,t+DAY);self.assertEqual(p[0]['detail']['signal'],-1);self.assertEqual(q[0]['detail']['signal'],1)
  rr[1]['models']['OP_INC']['mu']=None;self.assertEqual(schedule(m,rr,'OP_INC',t,t+DAY)[0]['detail']['signal'],0);rr[1]['models']['OP_INC']['mu']=-.02;t=rr[1]['expiry'];self.assertEqual(schedule(m,rr,'OP_INC',t,t+DAY)[0]['detail']['signal'],0)
 def test_unavailable_report_ignored(self):
  m=Fake();rr=rows()
  for e in rr:e.update(valid=True,models={n:{'mu':.1,'se':0} for n in ('OP_INC','OP_FUT','OP_PRICE')})
  t=rr[1]['source'];a=schedule(m,rr,'OP_INC',t-DAY,t);rr[1]['models']['OP_INC']['mu']=-10;self.assertEqual(a,schedule(m,rr,'OP_INC',t-DAY,t))
if __name__=='__main__':unittest.main()
