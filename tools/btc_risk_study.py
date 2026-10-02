"""BTC semivariance risk forecasts on an unchanged long-only trend signal."""
import argparse,gzip,json,math
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,ms,canonical,sha
from btc_persistence_study import Market,PERIODS,SCENARIOS
from btc_session_study import write,bootstrap
import btc_target_ledger as ledger
ROOT=Path(__file__).resolve().parents[1];IDS=('V_SRV','V_HAR','V_RV20');ledger.LABELS.update({k:k for k in IDS})
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def predict(rows):
 rv=np.array([r['rv'] if r['rv'] is not None else np.nan for r in rows]);up=np.array([r['up'] if r['up'] is not None else np.nan for r in rows]);down=np.array([r['down'] if r['down'] is not None else np.nan for r in rows]);X={k:np.full((len(rows),5 if k=='V_SRV' else 4),np.nan) for k in IDS[:2]}
 for i in range(21,len(rows)):
  h=rv[i-21:i+1]
  if np.all(np.isfinite(h)):
   X['V_HAR'][i]=[1,rv[i],np.mean(rv[i-4:i+1]),np.mean(h)];X['V_SRV'][i]=[1,up[i],down[i],np.mean(rv[i-4:i+1]),np.mean(h)]
 out=[]
 for i,row in enumerate(rows):
  e={'source':row['end'],'observed_day':row['day'],'truth':rows[i+1]['rv'] if i+1<len(rows) else None,'truth_end':rows[i+1]['end'] if i+1<len(rows) else None,'models':{}}
  for name in IDS:
   if name=='V_RV20':
    val=float(np.mean(rv[i-19:i+1])) if i>=19 and np.all(np.isfinite(rv[i-19:i+1])) else None;e['models'][name]={'prediction':val,'floor':False};continue
   j=np.arange(max(0,i-365),i);j=j[np.all(np.isfinite(X[name][j]),axis=1)&np.isfinite(rv[j+1])]
   if len(j)<300 or not np.all(np.isfinite(X[name][i])):e['models'][name]={'prediction':None,'floor':False};continue
   xx=X[name][j];yy=rv[j+1];scale=np.std(xx,axis=0);scale[scale<1e-12]=1.;beta=np.linalg.lstsq(xx/scale,yy,rcond=None)[0]/scale;raw=float(X[name][i]@beta);val=max(raw,1e-8)
   e['models'][name]={'prediction':val,'unclipped':raw,'floor':raw<1e-8,'beta':beta.tolist(),'training_first':rows[int(j[0])]['day'],'training_feature_end':rows[int(j[-1])]['end'],'training_label_end':rows[int(j[-1])+1]['end'],'training_n':len(j),'features':X[name][i].tolist()}
  out.append(e)
 return out

def schedule(m,pred,name,start,end,risk=.2):
 out=[]
 for e in pred:
  t=e['source']
  if not start<=t<end:continue
  obs=m.observation(t,risk);v=e['models'][name]['prediction']
  if obs is None or v is None:out.append({'source_time':t,'weights':None,'detail':{'missing':True,'forecast':v}});continue
  score,_,oldvol=obs;vol=math.sqrt(365*v);w=max(score,0)*min(1,risk/vol)
  out.append({'source_time':t,'weights':{'BS':w,'BP':0.},'hedge':False,'rebalance':True,'detail':{'score':score,'signal':max(score,0),'risk':min(1,risk/vol),'vol':vol,'old_vol':oldvol,'forecast':v,'floor':e['models'][name]['floor']}})
 return out

def run(out):
 out=Path(out);data=ROOT/'data/btc-rv-20261002';a=read(data/'audit.json');v=read(data/'verification.json');assert v['max_rv_error']<1e-12;daily=read(data/'daily-rv.json.gz');assert sha(canonical(daily))==a['daily_sha256'];pred=predict(daily);write(out/'predictions.json.gz',pred);m=Market();results={};summary={};unc={};forecast={}
 for period,(start,end) in PERIODS.items():
  paired=[e for e in pred if start<=e['source']<end and e['truth'] is not None and e['truth']>0 and e['truth_end']<=end and all(e['models'][k]['prediction'] is not None for k in IDS)]
  fm={};losses={}
  for name in IDS:
   y=np.array([e['truth'] for e in paired]);p=np.array([e['models'][name]['prediction'] for e in paired]);ratio=y/p;se=(y-p)**2;q=ratio-np.log(ratio)-1;fm[name]={'n':len(y),'mse':float(se.mean()),'qlike':float(q.mean()),'floor_fraction':sum(e['models'][name]['floor'] for e in paired)/len(paired)};losses[name]=(se,q)
  forecast[period]={'models':fm,'SRV_vs_HAR':{'mse_improvement':[bootstrap(losses['V_HAR'][0]-losses['V_SRV'][0],n) for n in (7,14,28)],'qlike_improvement':[bootstrap(losses['V_HAR'][1]-losses['V_SRV'][1],n) for n in (7,14,28)]},'bootstrap_units':'bootstrap generic mean_daily_pct/CI divides by100 to recover loss units'}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    conf=dict(c);risk=conf.pop('risk_target',.2);plan=schedule(m,pred,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**conf);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),rv_input_sha256=a['daily_sha256']);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);b=np.array(results[period,'V_HAR','base']['daily_returns']);o=np.array(old['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)],'vs_E_SPOT':[bootstrap(r-o,n) for n in (7,14,28)],'vs_V_HAR':[bootstrap(r-b,n) for n in (7,14,28)]}
 a=results['main','V_SRV','base']['metrics'];b=results['recent','V_SRV','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','V_SRV','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'V_SRV',c]['metrics']['net_pnl']>0 for p in PERIODS)
 for p in PERIODS:
  a,b=forecast[p]['models']['V_SRV'],forecast[p]['models']['V_HAR'];g[p+'_prediction']=a['qlike']<b['qlike'] and a['mse']<=b['mse'] and a['floor_fraction']<=.01
 write(out/'summary.json',summary);write(out/'uncertainty.json',unc);write(out/'forecast-summary.json',forecast);write(out/'selection.json',{'primary':'V_SRV','passed':all(g.values()),'checks':g,'scope':'risk allocation, not new directional alpha; development data'});print(json.dumps({'gates':g,'forecast':{p:v['models'] for p,v in forecast.items()}}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
