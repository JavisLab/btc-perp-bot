import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import btc_regime_study as s
class Market:
 def __init__(self):
  self.close=np.array(list(range(100,80,-1))+[100,101,99,98,97],dtype=float);self.index={i*s.DAY:i for i in range(len(self.close))}
 def observation(self,t,target):return (-1. if t<22*s.DAY else 0.),.4,.5

def test_regime_exit_vs_entry_gate():
 m=Market();a=s.schedule(m,'RG_FLAT',20*s.DAY,23*s.DAY);b=s.schedule(m,'RG_ENTRY',20*s.DAY,23*s.DAY)
 assert [p['weights']['BP'] for p in a]==[-.4,0.,0.]
 assert [p['weights']['BP'] for p in b]==[-.4,-.4,0.]

def test_future_regime_input():
 m=Market();a=s.schedule(m,'RG_ENTRY',20*s.DAY,23*s.DAY);m.close[22:]*=10;b=s.schedule(m,'RG_ENTRY',20*s.DAY,23*s.DAY)
 assert a==b

def test_missing_daily_regime():
 m=Market();m.close[5]=np.nan
 assert s.schedule(m,'RG_FLAT',20*s.DAY,21*s.DAY)[0]['weights'] is None
