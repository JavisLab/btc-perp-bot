"""Future price/OI perturbation leaves completed historical features unchanged."""
import sys,gzip,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import btc_oi_information as s

def test_future_data_perturbation():
 baseline=s.features(60);first,oi=s.load_oi();changed=oi.copy();cut=s.ms('2024-01-01');changed[(cut-first)//s.STEP+1:]*=3
 p=s.ROOT/'data/search-1458/market.json.gz';blob=p.read_bytes();decode=gzip.decompress;payload=json.loads(decode(blob))
 for row in payload['series']['BTCUSDT']['perp']:
  if row[0]>=cut:
   for i in range(1,5):row[i]*=2
 replacement=json.dumps(payload).encode()
 with patch.object(s,'load_oi',return_value=(first,changed)),patch.object(s.gzip,'decompress',side_effect=lambda b:replacement if b==blob else decode(b)):
  perturbed=s.features(60)
 a={r['source']:r for r in baseline};b={r['source']:r for r in perturbed}
 for t,r in a.items():
  if t<=cut:assert b[t]['x']==r['x']
  if t+s.DAY<=cut:assert b[t]['y']==r['y']
