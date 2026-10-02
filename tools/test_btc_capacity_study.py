"""Chronology, stale funding, nonlinear state identity and missing-data tests before performance."""
import copy,math
import numpy as np
from btc_capacity_study import Market,inputs,features,predict,fit,schedule,signal,PERIODS,MODELS,GATE,BLOCK,HOUR,ms

def run():
 m=Market();prem,spot=inputs();raw=features(m,prem,spot);cut=ms('2022-01-01');before=predict([r for r in raw if r['source']<=cut+2*BLOCK])
 for t,r in m.hourly.items():
  if t>=cut:r[1:5]=[x*1.27 for x in r[1:5]];r[7]*=3;r[10]*=2
 for t,r in prem.items():
  if t>=cut:r[1:5]=[x+.3 for x in r[1:5]]
 for t,r in list(spot.items()):
  if t>=cut:spot[t]=(r[0]*1.15,r[1],r[2])
 after=predict([r for r in features(m,prem,spot) if r['source']<=cut+2*BLOCK]);assert [e['models'] for e in before if e['source']<=cut]==[e['models'] for e in after if e['source']<=cut]
 for e in before:
  for z in e['models'].values():
   if z['mu'] is not None:assert z['training_label_end']<=e['source']-BLOCK and z['training_first']>=e['source']-365*24*HOUR and z['se']>=0
 # State is known at flow START, not the contemporaneous end-state.
 m=Market();prem,spot=inputs();base=features(m,prem,spot);T=ms('2023-01-01')
 for h in range(T-BLOCK,T,HOUR):prem[h][4]+=1
 later=features(m,prem,spot);i=next(i for i,e in enumerate(base) if e['source']==T);assert base[i]['A']==later[i]['A'] and base[i+1]['A']!=later[i+1]['A']
 assert signal(GATE+.002+.001,.001,.002)==0 and signal(GATE+.002+.001+1e-8,.001,.002)==1
 assert signal(-GATE-.002-.001-1e-8,.001,-.002)==-1 and signal(-GATE-.001-1e-8,.001,.002)==-1
 # The settlement at T is never in the input; exact old raw-time boundary is strict.
 for e in base:
  if e['funding_time'] is not None:assert e['funding_time']<e['source']-HOUR and e['source']-e['funding_time']<=16*HOUR
 f=predict([r for r in base if r['source']<=cut+2*BLOCK]);a=schedule(f,'CP_INT',cut,cut+BLOCK*3);b=schedule(f,'CP_INV',cut,cut+BLOCK*3);assert all(x['weight']==-y['weight'] for x,y in zip(a,b))
 broken=copy.deepcopy(f[-1]);broken['models']['CP_INT']['mu']=None;assert schedule([broken],'CP_INT',0,10**20)[0]['weight']==0
 x=np.column_stack((np.ones(30),np.zeros((30,4))));assert fit(x,np.arange(30),x[0])['mu'] is None
 # Genuine zero premium is valid; absent sampling count must not masquerade as zero.
 p,s=inputs()
 for h in range(T-2*BLOCK,T-BLOCK,HOUR):p[h][4]=0
 z=features(m,p,s);assert z[i]['feature_valid'] and z[i]['A']==0
 p[T-2*BLOCK][6]=0;z=features(m,p,s);assert not z[i]['feature_valid'] and z[i]['A'] is None
 rng=np.random.default_rng(1490);r=rng.normal(0,.01,1000);flow=rng.normal(0,.1,1000);A=rng.uniform(0,.002,1000);x=np.column_stack((np.ones(1000),r,flow,A,A*flow));y=.2*r+.01*flow+3*A*flow+rng.normal(0,.005,1000);a=fit(x,y,x[-1]);x[:,1]*=2;b=fit(x,y*2,x[-1]);assert abs(b['mu']-2*a['mu'])<1e-11 and abs(b['se']-2*a['se'])<1e-11
 print({'passed':9,'checks':['future_price_flow_index_spot_perturbation','8h_label_purge_and_train_window','pre_flow_state_only','cost_funding_SE_and_strict_threshold','raw_funding_cutoff_age','exact_inverse','missing_or_rank_cash','zero_index_not_zero_sample_count','return_and_SE_units']},flush=True)
if __name__=='__main__':run()
