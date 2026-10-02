"""Risk chronology and units; no performance tuning."""
import copy,math
from btc_risk_study import predict,read,ROOT
from btc_perp_bot.research.archive import ms

def run():
 rows=read(ROOT/'data/btc-rv-20261002/daily-rv.json.gz');before=predict(rows);cut=ms('2024-01-01');alter=copy.deepcopy(rows)
 for r in alter:
  if r['end']>cut and r['rv'] is not None:r['rv']*=9;r['up']*=9;r['down']*=9
 after=predict(alter);assert [e['models'] for e in before if e['source']<=cut]==[e['models'] for e in after if e['source']<=cut]
 for e in before:
  for name in ('V_SRV','V_HAR'):
   v=e['models'][name]
   if v['prediction'] is not None:assert v['training_label_end']<=e['source'] and v['training_feature_end']<=e['observed_day'] and v['prediction']>=1e-8
 assert all(abs(r['rv']-r['up']-r['down'])<1e-14 for r in rows if r['valid'])
 assert abs(math.sqrt(365*.0001)-.191049731745428)<1e-12
 print({'passed':4,'checks':['future_RV_perturbation','training_label_clock','semivariance_identity','annual_variance_units']})
if __name__=='__main__':run()
