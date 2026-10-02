import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import btc_funding_study as s

def test_raw_time_and_window_exclusion():
 f={t:{'rate':.0002,'raw_time':t} for t in range(0,48*s.HOUR,8*s.HOUR)}
 z=s.known(sorted(f),f,25*s.HOUR,60)
 assert z['funding_buckets']==[0,8*s.HOUR,16*s.HOUR]
 assert abs(z['known_funding']-.0006)<1e-12
 f[16*s.HOUR]['raw_time']=24*s.HOUR
 assert s.known(sorted(f),f,25*s.HOUR,60) is None

def test_no_missing_or_irregular_settlement():
 f={t:{'rate':.0002,'raw_time':t} for t in [0,8*s.HOUR,15*s.HOUR]}
 assert s.known(sorted(f),f,25*s.HOUR,60) is None
 del f[15*s.HOUR]
 assert s.known(sorted(f),f,25*s.HOUR,60) is None

def test_future_funding_perturbation():
 f={t:{'rate':.0002,'raw_time':t} for t in range(0,72*s.HOUR,8*s.HOUR)}
 a=s.known(sorted(f),f,25*s.HOUR,60)
 for t in f:
  if t>=24*s.HOUR:f[t]['rate']=10
 assert s.known(sorted(f),f,25*s.HOUR,60)==a
