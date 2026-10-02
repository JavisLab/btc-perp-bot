"""Chronology, thresholds, scaling and inverse control; no performance tuning."""
import copy,math
from btc_volume_interaction_study import Market,raw_features,predict,schedule,signal,COST_GATE,PERIODS,MODELS,ms

def run():
 m=Market();raw=raw_features(m);before=predict(raw);cut=ms('2024-01-01')
 for t,r in m.hourly.items():
  if t>=cut:r[1:5]=[v*1.35 for v in r[1:5]];r[7]*=3
 after=predict(raw_features(m));assert [e['models'] for e in before if e['source']<=cut]==[e['models'] for e in after if e['source']<=cut]
 for e in before:
  for n in MODELS:
   z=e['models'][n]
   if z['mu'] is not None:assert z['training_label_end']<=e['source'] and z['training_feature_end']<=e['day'] and z['se']>=0
 assert signal(COST_GATE+.001,.001)==0 and signal(COST_GATE+.0011,.001)==1 and signal(-COST_GATE-.0011,.001)==-1
 a=schedule(before,'VI_INT',*PERIODS['main']);b=schedule(before,'VI_NEG',*PERIODS['main']);assert all(x['weight'] is None if y['weight'] is None else x['weight']==-y['weight'] for x,y in zip(a,b))
 altered=copy.deepcopy(raw)
 for e in altered:
  if e['r'] is not None:e['r']*=2
 after=predict(altered)
 for x,y in zip(before,after):
  for n in MODELS:
   if x['models'][n]['mu'] is not None:assert abs(y['models'][n]['mu']-2*x['models'][n]['mu'])<1e-10 and abs(y['models'][n]['se']-2*x['models'][n]['se'])<1e-10
 print({'passed':5,'checks':['future_price_volume_perturbation','training_label_clock','cost_plus_mean_SE_cash_gate','exact_inverse_signal','return_and_SE_units']},flush=True)
if __name__=='__main__':run()
