import unittest,copy,datetime as dt
from btc_macro_vintage_study import schedule,event_features,DAY,HOUR,ms
from collect_btc_macro_data import parse_csv
class Fake:
 def __init__(self):
  self.rowmaps={'BS':{}};d=ms('2022-03-16');self.event=d
  for t,c in ((d+DAY,100),(d+3*DAY,110)):self.rowmaps['BS'][t-HOUR]=[t-HOUR,c,c,c,c,t-1]
 def observation(self,t,target=.2):return (1/3,target/.4,.4)
def event():
 d=ms('2022-03-16');return {'event':'2022-03-16','vintage_date':'2022-03-17','source_time':d+3*DAY,'valid':True,'delta_percentage_points':.05}
class Tests(unittest.TestCase):
 def test_vintage_missing_and_units(self):
  b=b'observation_date,DGS2_20220317\n2022-03-15,1.85\n2022-03-16,1.90\n';z=parse_csv(b,'2022-03-17',dt.date(2022,3,16));self.assertAlmostEqual(z['delta_percentage_points']*100,5)
  self.assertIsNone(parse_csv(b'observation_date,DGS2_20220316\n2022-03-15,1.85\n','2022-03-16',dt.date(2022,3,16)))
  with self.assertRaises(AssertionError):parse_csv(b,'2022-03-16',dt.date(2022,3,16))
 def test_no_future_observation(self):
  with self.assertRaises(AssertionError):parse_csv(b'observation_date,DGS2_20220317\n2022-03-17,1.85\n','2022-03-17',dt.date(2022,3,16))
 def test_window_and_opposite_and_cash(self):
  m=Fake();e=event_features(m,[event()]);t=e[0]['source_time']
  for name,s in [('MB_RATE',-1),('MB_INV',1),('MB_PRICE',1),('MB_CASH',0)]:
   p=schedule(m,e,name,t-DAY,t+6*DAY);self.assertEqual(p[0]['detail']['signal'],1/3);self.assertEqual([x['detail']['signal'] for x in p[1:6]],[s]*5);self.assertEqual(p[-1]['detail']['signal'],1/3)
 def test_missing_zero_and_risk(self):
  m=Fake();e=event();e['delta_percentage_points']=0;f=event_features(m,[e]);t=e['source_time'];self.assertEqual(schedule(m,f,'MB_RATE',t,t+DAY)[0]['weights'],{'BS':0,'BP':0})
  e['valid']=False;f=event_features(m,[e]);self.assertTrue(all(schedule(m,f,n,t,t+DAY)[0]['detail']['signal']==0 for n in ('MB_RATE','MB_INV','MB_PRICE')))
  e=event();f=event_features(m,[e]);self.assertEqual(schedule(m,f,'MB_RATE',t,t+DAY,.1)[0]['weights']['BP'],-.25)
 def test_future_event_and_price_do_not_change_past(self):
  m=Fake();e=event();f=event_features(m,[e]);t=e['source_time'];before=schedule(m,f,'MB_RATE',t-2*DAY,t);e['delta_percentage_points']=-1;m.rowmaps['BS'][t-HOUR][4]=1e9;after=schedule(m,event_features(m,[e]),'MB_RATE',t-2*DAY,t);self.assertEqual(before,after)
 def test_price_is_fixed_at_event_entry(self):
  m=Fake();f=event_features(m,[event()]);t=f[0]['source_time'];m.rowmaps['BS'][t+DAY-HOUR]=[t+DAY-HOUR,1,1,1,1,t+DAY-1];p=schedule(m,f,'MB_PRICE',t,t+5*DAY);self.assertTrue(all(x['detail']['signal']==1 for x in p))
class Holiday(unittest.TestCase):
 def test_first_available_holiday_delay(self):
  from collect_btc_macro_vintage_data import first_available
  asked=[]
  def get(v):
   asked.append(v); text='observation_date,DGS2_'+v.replace('-','')+'\n2025-06-17,3.94\n'
   if v=='2025-06-20':text+='2025-06-18,3.95\n'
   return text.encode(),{}
  e=first_available(dt.date(2025,6,18),get)
  self.assertEqual(asked,['2025-06-19','2025-06-20']);self.assertEqual(e['source_time'],ms('2025-06-22'));self.assertFalse(e['attempts'][0]['valid']);self.assertAlmostEqual(e['delta_percentage_points'],.01)
if __name__=='__main__':unittest.main()
