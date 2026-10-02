"""Preregistered BTC option-equivalent position information; no network or live trading."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_cot_study import close,risk_observation
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT
import btc_target_ledger as ledger
IDS=('OP_INC','OP_FUT','OP_PRICE','OP_INV');MODELS=IDS[:3];ledger.LABELS.update({x:x for x in IDS})
VARIANTS={'base':0,'rounding_plus':1,'rounding_minus':-1}
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'rounding_plus':{},'rounding_minus':{}}
LONG_GATE=math.log1p(.0023);SHORT_GATE=math.log1p(.0013)
def positions():
 data=ROOT/'data/btc-cot-20261002';rr=read(data/'reports.json');out=[]
 for file,expected in [('btc-futures-only.json','707932e8df4ebd9d2035591a5c9b017b485f71d98d7aaefdba0aeb5349b6b34b'),('btc-combined.json','78400a9a963b3e0ba14957842cfbd2157512b68fd940410f0fdade15a8dd655f')]:assert sha((data/file).read_bytes())==expected
 fut=read(data/'btc-futures-only.json');combo=read(data/'btc-combined.json');assert len(fut)==len(combo)==len(rr)==352
 for e,f,c in zip(rr,fut,combo):
  assert e['report_date']==f['report_date_as_yyyy_mm_dd'][:10]==c['report_date_as_yyyy_mm_dd'][:10]
  F=int(f['asset_mgr_positions_long'])-int(f['asset_mgr_positions_short']);O=int(c['asset_mgr_positions_long'])-int(c['asset_mgr_positions_short'])-F;out.append(dict(e,futures_net=F,options_net=O))
 return out

def raw_features(m,rows,variant='base'):
 phase=VARIANTS[variant];out=[]
 for j,row in enumerate(rows):
  O=row['options_net']+phase*(-1)**j;e=dict(row,options_adjusted=O,input_variant=variant,valid=False,r=None,f=None,o=None,truth=None,truth_end=row['source']+7*DAY)
  a,b=close(m,row['source']),close(m,e['truth_end'])
  if a is not None and b is not None:e['truth']=math.log(b/a)
  if j:
   prev=rows[j-1];a,b=close(m,prev['report_time']+DAY),close(m,row['report_time']+DAY)
   valid=prev['source']<=row['source'] and row['report_time']+DAY<=row['source'] and prev['oi']>0 and a is not None and b is not None;e.update(valid=valid,previous_report=prev['report_date'])
   if valid:e.update(r=math.log(b/a),f=(row['futures_net']-prev['futures_net'])/prev['oi'],o=(O-(prev['options_net']+phase*(-1)**(j-1)))/prev['oi'])
  out.append(e)
 return out

def predict(rows):
 X=np.array([[1,e['r'] if e['valid'] else np.nan,e['f'] if e['valid'] else np.nan,e['o'] if e['valid'] else np.nan] for e in rows]);out=[]
 for i,row in enumerate(rows):
  e=dict(row,models={});keep=[j for j in range(max(0,i-104),i) if rows[j]['valid'] and rows[j]['truth'] is not None and rows[j]['truth_end']<=row['source']]
  for name,k in [('OP_INC',4),('OP_FUT',3),('OP_PRICE',2)]:
   missing={'mu':None,'se':None,'training_n':len(keep)}
   if not row['valid'] or len(keep)<78:e['models'][name]=missing;continue
   x=X[keep,:k];y=np.array([rows[j]['truth'] for j in keep]);scale=x.std(axis=0);scale[scale<1e-12]=1.;scaled=x/scale
   if np.linalg.matrix_rank(scaled)<k:e['models'][name]=dict(missing,reason='rank');continue
   beta=np.linalg.lstsq(scaled,y,rcond=None)[0];res=y-scaled@beta;s2=float(res@res)/(len(keep)-k);current=X[i,:k]/scale;mu=float(current@beta);se=math.sqrt(max(0.,s2*float(current@np.linalg.solve(scaled.T@scaled,current))))
   e['models'][name]={'mu':mu,'se':se,'beta':(beta/scale).tolist(),'training_n':len(keep),'training_indices':keep,'training_label_end':max(rows[j]['truth_end'] for j in keep),'residual_variance':s2}
  out.append(e)
 return out

def signal(mu,se):return 1 if mu>LONG_GATE+se else -1 if mu<-SHORT_GATE-se else 0

def schedule(m,feats,name,start,end,risk=.2):
 out=[]
 for t in range(start,end,DAY):
  obs=risk_observation(m,t,risk)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':{'risk_missing':True}});continue
  w,vol=obs;available=[e for e in feats if e['source']<=t];e=max(available,key=lambda e:e['report_time']) if available else None;valid=e is not None and e['valid'] and t<e['expiry'];pred=e['models']['OP_INC' if name=='OP_INV' else name] if e else {'mu':None,'se':None};s=signal(pred['mu'],pred['se'])*(-1 if name=='OP_INV' else 1) if valid and pred['mu'] is not None else 0
  detail={'signal':s,'risk':w,'vol':vol,'report_date':e['report_date'] if e else None,'information_time':e['source'] if e else None,'age_days':(t-e['report_time'])//DAY if e else None,'expiry':e['expiry'] if e else None,'common_valid':valid,'model':pred}
  out.append({'source_time':t,'weights':{'BS':max(s,0)*w,'BP':min(s,0)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def forecast_summary(feats,start,end):
 paired=[e for e in feats if start<=e['source']<end and e['truth'] is not None and e['truth_end']<=end and all(e['models'][k]['mu'] is not None for k in MODELS)];out={}
 for name in MODELS:
  y=np.array([e['truth'] for e in paired]);mu=np.array([e['models'][name]['mu'] for e in paired]);beta=np.array([e['models'][name]['beta'] for e in paired]);se=np.array([e['models'][name]['se'] for e in paired]);tn=np.array([e['models'][name]['training_n'] for e in paired]);out[name]={'n':len(y),'mse':float(np.mean((y-mu)**2)) if len(y) else None,'sign_accuracy':float(np.mean(np.sign(y)==np.sign(mu))) if len(y) else None,'cash_gate_fraction':float(np.mean([signal(a,b)==0 for a,b in zip(mu,se)])) if len(y) else None,'coefficient_median':np.median(beta,axis=0).tolist() if len(y) else [],'coefficient_positive_fraction':np.mean(beta>0,axis=0).tolist() if len(y) else [],'coefficient_q10_q90':np.quantile(beta,[.1,.9],axis=0).tolist() if len(y) else [],'training_n_min_max':[int(tn.min()),int(tn.max())] if len(y) else [],'paired_report_dates':[e['report_date'] for e in paired]}
 return out

def run(out):
 out=Path(out);rr=positions();m=Market();feats={v:predict(raw_features(m,rr,v)) for v in VARIANTS}
 for v,f in feats.items():write(out/f'features-{v}.json.gz',f)
 results={};summary={};unc={};ages={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={v:forecast_summary(f,start,end) for v,f in feats.items()}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);variant=scenario if scenario in VARIANTS else 'base';plan=schedule(m,feats[variant],name,start,end,risk);write(out/f'{period}-{name}-plan-{variant}-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,input_variant=variant,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),position_input_sha256=sha(canonical(rr)));write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
    if name=='OP_INC' and scenario=='base':ages[period]={'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_days':sum(not e['detail'].get('common_valid',False) for e in plan),'model_missing_days':sum(e['detail'].get('model',{}).get('mu') is None for e in plan),'used_reports':len({e['detail'].get('report_date') for e in plan if e['detail'].get('common_valid')}),'age_day_counts':{str(k):sum(e['detail'].get('age_days')==k and e['detail'].get('common_valid',False) for e in plan) for k in range(21)}}
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,other in [('E_SPOT',old),('OP_FUT',results[period,'OP_FUT','base']),('OP_PRICE',results[period,'OP_PRICE','base'])]:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(other['daily_returns']),n) for n in (7,14,28)]
 a=results['main','OP_INC','base']['metrics'];b=results['recent','OP_INC','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','OP_INC','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','rounding_plus','rounding_minus'):g[c]=all(results[p,'OP_INC',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={'net_beats_futures_both':all(results[p,'OP_INC','base']['metrics']['net_pnl']>results[p,'OP_FUT','base']['metrics']['net_pnl'] for p in PERIODS),'mse_no_worse_both':all(forecast[p]['base']['OP_INC']['mse'] is not None and forecast[p]['base']['OP_INC']['mse']<=forecast[p]['base']['OP_FUT']['mse'] for p in PERIODS)}
 for n,v in [('summary',summary),('uncertainty',unc),('information-age',ages),('forecast-summary',forecast),('selection',{'primary':'OP_INC','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; delta-equivalent holdings, not new order flow; historical publication/PIT limitations; controls not promotable'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'information':ages}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
