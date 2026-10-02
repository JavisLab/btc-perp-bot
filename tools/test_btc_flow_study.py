"""Frozen-information test; actual inputs only for chronology, not optimization."""
from btc_flow_study import Market,features,schedule,DAY,PERIODS
from btc_perp_bot.research.archive import ms

def run():
 m=Market();before=features(m);cut=ms('2024-01-01');known=[e for e in before if e['source']<=cut]
 for t,r in m.hourly.items():
  if t>=cut:
   r[1:5]=[x*1.25 for x in r[1:5]];r[10]=r[7]*.9
 after=features(m);assert known==[e for e in after if e['source']<=cut]
 valid=[e for e in before if not e['missing']];assert valid and all(e['training_end']<=e['signal_day']<e['source'] for e in valid)
 a=schedule(before,'OF_RES',*PERIODS['main']);b=schedule(before,'OF_NEG',*PERIODS['main']);assert all(x['weight'] is None if y['weight'] is None else x['weight']==-y['weight'] for x,y in zip(a,b))
 for e in a:
  if e['weight'] is not None:assert bool(e['weight'])==(abs(e['detail']['z_res'])>=1)
 print({'passed':4,'checks':['future_price_flow_perturbation','strict_past_OLS_training','negative_control_exact_sign','one_sigma_cash_gate']})
if __name__=='__main__':run()
