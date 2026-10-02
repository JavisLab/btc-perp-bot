"""Preregistered BTC holder cost-basis information; offline only, no live trading."""
import argparse,json,math,datetime as dt
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_cot_study import close,risk_observation
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('VA_INC','VA_PRICE','VA_VALUE','VA_INV');MODELS=IDS[:3];ledger.LABELS.update({x:x for x in IDS})
VARIANTS={'base':2,'source_delay7':9}
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'source_delay7':{}}
LONG_GATE=math.log1p(.0023);SHORT_GATE=math.log1p(.0013)
INPUT_SHA='db696818880b69e8320e192c60eb5429a40db0ecf5845ece194a01b0524d4a61'
COLS={'VA_INC':(0,1,2),'VA_PRICE':(0,1),'VA_VALUE':(2,)}
def inputs():
 raw=(ROOT/'data/btc-valuation-20261002/coinmetrics.json').read_bytes();assert sha(raw)==INPUT_SHA
 data=json.loads(raw);assert not data.get('next_page_url');out={}
 for e in data['data']:
  t=ms(e['time'][:10]);v=float(e['CapMVRVCur']);assert e['asset']=='btc' and t not in out and v>0 and math.isfinite(v);out[t]=v
 assert len(out)==2435 and list(out)==list(range(min(out),max(out)+DAY,DAY));return out

def raw_features(m,data,lag,start=ms('2020-01-06'),end=ms('2026-09-01')):
 out=[]
 for t in range(start,end,7*DAY):
  d=t-lag*DAY;b=d+DAY;h=[close(m,b-j*DAY) for j in range(200)];v=data.get(d)
  e={'source':t,'observation':d,'price_end':b,'expiry':t+7*DAY,'source_lag_days':lag,'valid':False,'r7':None,'p200':None,'v':None,'mvrv':v,'truth':None,'truth_end':t+7*DAY}
  a,z=close(m,t),close(m,t+7*DAY)
  if a is not None and z is not None and a>0 and z>0:e['truth']=math.log(z/a)
  if v is not None and math.isfinite(v) and v>0 and all(z is not None and math.isfinite(z) and z>0 for z in h):e.update(valid=True,r7=math.log(h[0]/h[7]),p200=math.log(h[0]/(sum(h)/200)),v=math.log(v))
  out.append(e)
 return out

def predict(rows):
 out=[]
 for i,row in enumerate(rows):
  e=dict(row,models={});keep=[j for j in range(max(0,i-104),i) if rows[j]['valid'] and rows[j]['truth'] is not None and rows[j]['truth_end']<=row['source']-7*DAY]
  for name,cols in COLS.items():
   k=len(cols)+1;p={'mu':None,'se':None,'training_n':len(keep)};e['models'][name]=p
   if not row['valid'] or len(keep)<78:continue
   a=np.array([[rows[j][('r7','p200','v')[c]] for c in cols] for j in keep]);y=np.array([rows[j]['truth'] for j in keep]);center=a.mean(axis=0);sd=a.std(axis=0);sd[sd<1e-12]=1.;Z=np.column_stack([np.ones(len(a)),(a-center)/sd])
   if np.linalg.matrix_rank(Z)<k:p['reason']='rank';continue
   coef=np.linalg.lstsq(Z,y,rcond=None)[0];res=y-Z@coef;s2=float(res@res)/(len(keep)-k);current=np.r_[1.,(np.array([row[('r7','p200','v')[c]] for c in cols])-center)/sd];mu=float(current@coef);se=math.sqrt(max(0.,s2*float(current@np.linalg.solve(Z.T@Z,current))));beta=np.r_[coef[0]-sum(coef[1:]*center/sd),coef[1:]/sd]
   p.update(mu=mu,se=se,beta=beta.tolist(),training_indices=keep,training_label_end=max(rows[j]['truth_end'] for j in keep),residual_variance=s2)
  out.append(e)
 return out

def signal(mu,se):return 1 if mu>LONG_GATE+se else -1 if mu<-SHORT_GATE-se else 0

def schedule(m,feats,name,start,end,risk=.2):
 out=[]
 for t in range(start,end,DAY):
  obs=risk_observation(m,t,risk)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':{'risk_missing':True}});continue
  w,vol=obs;available=[e for e in feats if e['source']<=t];e=available[-1] if available else None;valid=e is not None and e['valid'] and t<e['expiry'];pred=e['models']['VA_INC' if name=='VA_INV' else name] if e else {'mu':None,'se':None};s=signal(pred['mu'],pred['se'])*(-1 if name=='VA_INV' else 1) if valid and pred['mu'] is not None else 0
  detail={'signal':s,'risk':w,'vol':vol,'observed_day':e['observation'] if e else None,'information_time':e['source'] if e else None,'age_days':(t-e['observation'])//DAY if e else None,'expiry':e['expiry'] if e else None,'common_valid':valid,'model':pred}
  out.append({'source_time':t,'weights':{'BS':max(s,0)*w,'BP':min(s,0)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def forecast_summary(feats,start,end):
 paired=[e for e in feats if start<=e['source']<end and e['truth'] is not None and e['truth_end']<=end and all(e['models'][k]['mu'] is not None for k in MODELS)];out={}
 for name in MODELS:
  y=np.array([e['truth'] for e in paired]);mu=np.array([e['models'][name]['mu'] for e in paired]);beta=np.array([e['models'][name]['beta'] for e in paired]);se=np.array([e['models'][name]['se'] for e in paired]);tn=np.array([e['models'][name]['training_n'] for e in paired]);out[name]={'n':len(y),'mse':float(np.mean((y-mu)**2)) if len(y) else None,'sign_accuracy':float(np.mean(np.sign(y)==np.sign(mu))) if len(y) else None,'cash_gate_fraction':float(np.mean([signal(a,b)==0 for a,b in zip(mu,se)])) if len(y) else None,'coefficient_median':np.median(beta,axis=0).tolist() if len(y) else [],'coefficient_positive_fraction':np.mean(beta>0,axis=0).tolist() if len(y) else [],'coefficient_q10_q90':np.quantile(beta,[.1,.9],axis=0).tolist() if len(y) else [],'training_n_min_max':[int(tn.min()),int(tn.max())] if len(y) else [],'paired_source_times':[e['source'] for e in paired]}
 return out

def run(out):
 out=Path(out);rr=inputs();m=Market();feats={v:predict(raw_features(m,rr,lag)) for v,lag in VARIANTS.items()}
 for v,f in feats.items():write(out/f'features-{v}.json.gz',f)
 results={};summary={};unc={};ages={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={v:forecast_summary(f,start,end) for v,f in feats.items()}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);variant=scenario if scenario in VARIANTS else 'base';plan=schedule(m,feats[variant],name,start,end,risk);write(out/f'{period}-{name}-plan-{variant}-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,input_variant=variant,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),valuation_input_sha256=INPUT_SHA,source_lag_days=VARIANTS[variant]);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
    if name=='VA_INC' and scenario=='base':ages[period]={'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_days':sum(not e['detail'].get('common_valid',False) for e in plan),'model_missing_days':sum(e['detail'].get('model',{}).get('mu') is None for e in plan),'used_reports':len({e['detail'].get('information_time') for e in plan if e['detail'].get('common_valid')}),'age_day_counts':{str(k):sum(e['detail'].get('age_days')==k and e['detail'].get('common_valid',False) for e in plan) for k in range(16)}}
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,other in [('E_SPOT',old),('VA_PRICE',results[period,'VA_PRICE','base']),('VA_VALUE',results[period,'VA_VALUE','base'])]:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(other['daily_returns']),n) for n in (7,14,28)]
 a=results['main','VA_INC','base']['metrics'];b=results['recent','VA_INC','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','VA_INC','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','source_delay7'):g[c]=all(results[p,'VA_INC',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={'net_beats_price_both':all(results[p,'VA_INC','base']['metrics']['net_pnl']>results[p,'VA_PRICE','base']['metrics']['net_pnl'] for p in PERIODS),'mse_no_worse_both':all(forecast[p]['base']['VA_INC']['mse'] is not None and forecast[p]['base']['VA_INC']['mse']<=forecast[p]['base']['VA_PRICE']['mse'] for p in PERIODS)}
 for n,v in [('summary',summary),('uncertainty',unc),('information-age',ages),('forecast-summary',forecast),('selection',{'primary':'VA_INC','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; UTXO cost approximation, not actual purchased cost; historical publication/PIT assumptions; controls not promotable'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'information':ages}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
