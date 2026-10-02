"""Chronology, missing-data, quantity and directional cash-flow boundaries."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import numpy as np
import btc_oi_study as s

def test_exact_oi_window_and_latency():
 a=np.arange(1.,201.);t=100*s.STEP
 z=s.oi_change(0,a,t,60)
 assert z['oi_end_qty']==89 and z['oi_start_qty']==41
 assert z['oi_observation_end']+s.HOUR==t
 assert s.oi_change(0,a,t+1,60) is None
 assert s.oi_change(0,a,10*s.STEP,60) is None

def test_hole_zero_interior_and_endpoints():
 for j in (40,60,88):
  for v in (np.nan,0.,-1.):
   a=np.ones(200);a[j]=v
   assert s.oi_change(0,a,100*s.STEP,60) is None

def test_future_perturbation():
 bars=[]
 for i in range(240):
  c=100+i%9*3
  bars.append({'t':i*4*s.HOUR,'o':c-1,'c':c,'h':c+2,'l':c-2})
 oi=np.linspace(100,500,12000);cut=120*4*s.HOUR
 a=s.plans(bars,0,oi)[0]
 future=[dict(b) for b in bars]
 for b in future:
  if b['t']>=cut:
   for k in ('o','h','l','c'):b[k]*=5
 modified=oi.copy();modified[cut//s.STEP+1:]*=17
 b=s.plans(future,0,modified)[0]
 for name in s.IDS:assert [x for x in a[name] if x['source']<=cut]==[x for x in b[name] if x['source']<=cut]

def tiny(side,delay=0,zero=False):
 rows=[[i*s.STEP,1000,1001,999,1000,0 if zero else 100] for i in range(6)]
 e={'source':0,'side':side,'stop':1000-side*20,'atr':10,'target':None,'regime':'range','er':0,'flow':None,'origin':None}
 f={4*s.STEP:{'rate':.001,'reference':1000,'raw_time':4*s.STEP}}
 return s.engine.simulate(rows,[e],{10:{},6:{}},f,'O_FLUSH',0,6*s.STEP,delay=delay)

def test_long_short_fees_funding_and_terminal():
 for side in (1,-1):
  x=tiny(side);t=x['trades'][0]
  assert t['entry']==s.STEP and t['exit']==6*s.STEP
  assert abs(t['funding']+side*t['qty'])<1e-9
  assert t['fees']>0 and t['impact']>0
  assert abs(t['net']-(t['funding']-t['fees']-t['impact']))<1e-9
  assert abs(t['net']-x['summary']['net'])<1e-9

def test_delayed_signal_is_frozen():
 x=tiny(1,delay=2*s.STEP);t=x['trades'][0]
 assert t['entry']==3*s.STEP and t['source']==0 and t['initial_stop']==980

def test_minimum_and_no_zero_volume_fill():
 assert s.engine.sized(20,1000,980,1,.0005,.00015,.005)==0
 assert not tiny(1,zero=True)['trades']
 q=s.engine.sized(1000,1000,980,1,.0005,.00015,.005)
 assert q*1000>=50 and abs(q/.001-round(q/.001))<1e-8
