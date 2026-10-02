import sys,copy,gzip,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import btc_persistence_study as s
class Toy:
 def __init__(self,values):self.values=values
 def observation(self,t,target):return self.values[t//s.DAY],.5,.4

def test_hysteresis_and_strict_short():
 vals=[0,2/3,1/3,0,-2/3,-1,-1/3,0,1]
 h=s.schedule(Toy(vals),'H_MIX',0,len(vals)*s.DAY)
 hs=s.schedule(Toy(vals),'H_STRICT',0,len(vals)*s.DAY)
 assert [p['detail']['signal'] for p in h]==[0,1,1,0,-1,-1,-1,0,1]
 assert [p['detail']['signal'] for p in hs]==[0,1,1,0,0,-1,-1,0,1]
 for p in h+hs:assert not(p['weights']['BS'] and p['weights']['BP'])

def test_prefix_invariance():
 a=[0,2/3,1/3,0,-1];b=a+[1,-1,1]
 for name in s.IDS:
  assert s.schedule(Toy(a),name,0,len(a)*s.DAY)==s.schedule(Toy(b),name,0,len(b)*s.DAY)[:len(a)]

def test_existing_spot_regression():
 m=s.Market();start,end=s.PERIODS['recent'];plan=s.schedule(m,'E_SPOT',start,end)
 x=s.simulate(m,'E_SPOT',start,end,plan)
 y=json.loads(gzip.decompress((s.ROOT/'runs/search-1458/recent-E_SPOT.json.gz').read_bytes()))
 assert abs(x['metrics']['equity']-y['metrics']['equity'])<1e-8
 assert x['events']==y['events']

def test_reversal_and_minimum():
 m=s.Market();start,end=s.PERIODS['recent'];end=start+3*s.DAY
 plan=[{'source_time':start,'weights':{'BS':.2,'BP':0}}, {'source_time':start+s.DAY,'weights':{'BS':0,'BP':-.2}}, {'source_time':start+2*s.DAY,'weights':{'BS':0,'BP':0}}]
 x=s.simulate(m,'E_MIX',start,end,plan)
 q={'BS':0,'BP':0}
 for e in x['events']:
  if e['kind']=='fill':q[e['instrument']]=e['position'];assert abs(q['BS']*q['BP'])<1e-10
 assert x['metrics']['fees']>0 and x['metrics']['round_trips']==2
 tiny=[{'source_time':start,'weights':{'BS':0,'BP':-.001}}]
 z=s.simulate(m,'E_MIX',start,end,tiny)
 assert z['metrics']['fills']==0
