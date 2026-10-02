"""Frozen BTC return x volume-shock information model; no live/network access."""
import argparse,math,json
from pathlib import Path
import numpy as np
from btc_session_study import Market,simulate,write,read,bootstrap,PERIODS,SCENARIOS,ROOT,DAY,HOUR,sha,canonical,ms
IDS=('VI_INT','VI_ADD','VI_AR','VI_NEG');MODELS=IDS[:3];COST_GATE=math.log1p(.0013)
def raw_features(m):
 first=min(m.hourly)//DAY*DAY;end=max(m.hourly)//DAY*DAY+DAY;bad={ms(x['time'])//DAY*DAY for x in m.resolution['unresolved'] if any(abs(v)>1e-3 for v in x['volume_errors'])};rows=[]
 for day in range(first,end,DAY):
  rr=[m.hourly.get(day+j*HOUR) for j in range(24)];a,b=m.close(day),m.close(day+DAY);q=math.fsum(r[7] for r in rr) if all(r is not None for r in rr) else None;valid=day not in bad and a is not None and b is not None and q is not None and q>0 and all(r is not None and r[5]>0 and r[6]==r[0]+HOUR-1 for r in rr);cl=[m.close(day+DAY-j*DAY) for j in range(20,-1,-1)];vol=float(np.std(np.diff(np.log(cl)),ddof=1)*math.sqrt(365)) if all(c is not None for c in cl) else None
  rows.append({'day':day,'source':day+DAY,'quote':q,'valid':bool(valid),'conflict_day':day in bad,'r':math.log(b/a) if valid else None,'annual_vol':vol,'v':None})
 for i,e in enumerate(rows):
  h=rows[i-30:i]
  if i>=30 and e['valid'] and all(x['valid'] for x in h):e['v']=math.log(e['quote']/(math.fsum(x['quote'] for x in h)/30))
 return rows

def predict(rows):
 n=len(rows);X=np.full((n,4),np.nan);r=np.array([e['r'] if e['r'] is not None else np.nan for e in rows]);valid=np.array([e['r'] is not None and e['v'] is not None for e in rows]);X[valid]=np.array([[1,e['r'],e['v'],e['r']*e['v']] for e in rows if e['r'] is not None and e['v'] is not None]);out=[]
 for i,row in enumerate(rows):
  e=dict(row,models={},truth=rows[i+1]['r'] if i+1<n else None,truth_end=rows[i+1]['source'] if i+1<n else None);keep=np.arange(max(0,i-365),i);keep=keep[valid[keep]&np.isfinite(r[keep+1])]
  for name,k in [('VI_INT',4),('VI_ADD',3),('VI_AR',2)]:
   if i<365 or len(keep)<300 or not valid[i]:e['models'][name]={'mu':None,'se':None};continue
   x=X[keep,:k];y=r[keep+1];scale=x.std(axis=0);scale[scale<1e-12]=1.;scaled=x/scale
   if np.linalg.matrix_rank(scaled)<k:e['models'][name]={'mu':None,'se':None,'reason':'rank'};continue
   beta=np.linalg.lstsq(scaled,y,rcond=None)[0];res=y-scaled@beta;s2=float(res@res)/(len(keep)-k);current=X[i,:k]/scale;mu=float(current@beta);se=math.sqrt(max(0.,s2*float(current@np.linalg.solve(scaled.T@scaled,current))))
   e['models'][name]={'mu':mu,'se':se,'beta':(beta/scale).tolist(),'training_n':len(keep),'training_first':rows[int(keep[0])]['day'],'training_feature_end':rows[int(keep[-1])]['source'],'training_label_end':rows[int(keep[-1])+1]['source'],'residual_variance':s2}
  out.append(e)
 return out

def signal(mu,se):return (1 if mu>0 else -1) if abs(mu)>COST_GATE+se else 0

def schedule(feats,name,start,end,risk=.2):
 out=[]
 for e in feats:
  t=e['source']
  if not start<=t<end:continue
  pred=e['models']['VI_INT' if name=='VI_NEG' else name];vol=e['annual_vol'];detail={'model':pred,'r':e['r'],'v':e['v'],'annual_vol':vol}
  if pred['mu'] is None or vol is None or vol<=1e-12:out.append({'source':t,'weight':None,'detail':detail|{'missing':True}});continue
  s=signal(pred['mu'],pred['se'])*(-1 if name=='VI_NEG' else 1);out.append({'source':t,'weight':s*min(1,risk/vol),'detail':detail|{'sign':s,'cost_gate':COST_GATE}})
 return out

def run(out):
 out=Path(out);m=Market();feat=predict(raw_features(m));write(out/'features.json.gz',feat);results={};summary={};uncertainty={};forecast={}
 for p,(start,end) in PERIODS.items():
  paired=[e for e in feat if start<=e['source']<end and e['truth'] is not None and e['truth_end']<=end and all(e['models'][k]['mu'] is not None for k in MODELS)]
  forecast[p]={}
  for name in MODELS:
   y=np.array([e['truth'] for e in paired]);muh=np.array([e['models'][name]['mu'] for e in paired]);se=np.array([e['models'][name]['se'] for e in paired]);bet=np.array([e['models'][name]['beta'] for e in paired]);forecast[p][name]={'n':len(y),'mse':float(np.mean((y-muh)**2)),'sign_accuracy':float(np.mean(np.sign(y)==np.sign(muh))),'cash_gate_fraction':float(np.mean(np.abs(muh)<=COST_GATE+se)),'coefficient_median':np.median(bet,axis=0).tolist(),'coefficient_positive_fraction':np.mean(bet>0,axis=0).tolist(),'r_v_coefficient_q10_q90':np.quantile(bet[:,-1],[.1,.9]).tolist() if name=='VI_INT' else None}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    risk=c.get('risk',.2);plan=schedule(feat,name,start,end,risk);write(out/f'{p}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=simulate(m,name,start,end,plan,**c);x.update(period=p,scenario=scenario,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_session_study.py').read_bytes()));write(out/f'{p}-{name}-{scenario}.json.gz',x);results[p,name,scenario]=x;summary[f'{p}-{name}-{scenario}']=x['metrics']
    if scenario=='base':print(json.dumps({'period':p,'name':name,**{k:x['metrics'][k] for k in ('return_pct','dd_pct','sharpe','realized_vol_pct','fees','funding','round_trips')}}),flush=True)
  for name in IDS:
   a=np.array(results[p,name,'base']['daily_returns']);u={'mean':[bootstrap(a,n) for n in (7,14,28)]}
   for ctrl in ('VI_ADD','VI_AR'):u['vs_'+ctrl]=[bootstrap(a-np.array(results[p,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
   uncertainty[p+'-'+name]=u
 a=results['main','VI_INT','base']['metrics'];b=results['recent','VI_INT','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['dd_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['dd_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v>0 for v in a['annual'].values())>=3,'trades':a['round_trips']>=100,'margin':a['margin_breach_bars']==b['margin_breach_bars']==0}
 for c in ('base','cost_x2','delay60','delay240'):g[c]=all(results[p,'VI_INT',c]['metrics']['net']>0 for p in PERIODS)
 write(out/'summary.json',summary);write(out/'uncertainty.json',uncertainty);write(out/'forecast-summary.json',forecast);write(out/'selection.json',{'primary':'VI_INT','passed':all(g.values()),'checks':g,'interaction_improves_both':all(results[p,'VI_INT','base']['metrics']['net']>results[p,'VI_ADD','base']['metrics']['net'] for p in PERIODS),'comparisons_not_eligible':list(IDS[1:]),'scope':'development only; conditional association is not causal or fresh OOS'});print(json.dumps(g),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
