"""Frozen BTC miner-pressure participation gate; offline historical research only."""
import argparse,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT
import btc_target_ledger as ledger
IDS=('HG_REC','HG_STRESS','HG_HASH','HG_INV');ledger.LABELS.update({n:n for n in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'source_delay7':{'source_lag_days':9},'provider_cm':{'input_variant':'provider_cm'}}
def features(rows,variant='base'):
 key='hashrate' if variant=='base' else 'hashrate_provider_cm';byday={e['day']:e for e in rows};out={}
 for e in rows:
  h=[byday.get(e['day']-j*DAY,{}).get(key) for j in range(59,-1,-1)];valid=all(v is not None and math.isfinite(v) and v>0 for v in h);out[e['day']]={'day':e['day'],'source':e['source'],'h30':math.fsum(h[-30:])/30 if valid else None,'h60':math.fsum(h)/60 if valid else None,'valid':valid,'input_variant':variant}
 return out

def direction(name,P,G):
 if name=='HG_REC':return P*G
 if name=='HG_STRESS':return P*(1-G)
 if name=='HG_HASH':return float(G)
 if name=='HG_INV':return -P*G
 raise ValueError(name)

def schedule(m,feats,name,start,end,risk=.2,lag=2):
 out=[]
 for t in range(start,end,DAY):
  obs=m.observation(t,risk)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':{'price_risk_missing':True}});continue
  score,w,vol=obs;P=max(score,0);e=feats.get(t-lag*DAY);valid=e is not None and e['valid'] and e['source']<=t;G=int(e['h30']>=e['h60']) if valid else None;s=direction(name,P,G) if valid else 0
  detail={'signal':s,'score':score,'risk':w,'vol':vol,'gate':G,'common_valid':valid,'observed_day':e['day'] if e else None,'information_time':e['source'] if e else None,'usable_time':e['day']+lag*DAY if e else None,'h30':e['h30'] if e else None,'h60':e['h60'] if e else None,'age_days':lag}
  out.append({'source_time':t,'weights':{'BS':max(s,0)*w,'BP':min(s,0)*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def run(out):
 out=Path(out);data=ROOT/'data/btc-mining-20261002';audit=read(data/'prepare-audit.json');rr=read(data/'prepared.json');assert sha(canonical(rr))==audit['rows_sha256']=='1429ff3f1b56e977f0af6000b0956f62abdc1b9a5ac3f647e41b9e8b0a8f0d92'
 for n,h in audit['source_files'].items():assert sha((data/n).read_bytes())==h
 m=Market();feats={v:features(rr,v) for v in ('base','provider_cm')};write(out/'features.json.gz',{v:list(f.values()) for v,f in feats.items()});results={};summary={};unc={};ages={}
 for period,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);variant=cfg.pop('input_variant','base');lag=cfg.pop('source_lag_days',2);plan=schedule(m,feats[variant],name,start,end,risk,lag);write(out/f'{period}-{name}-plan-{variant}-lag{lag}-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,input_variant=variant,source_lag_days=lag,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),mining_input_sha256=audit['rows_sha256']);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
    if name=='HG_REC':ages[period+'-'+scenario]={'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_days':sum(not e['detail'].get('common_valid',False) for e in plan),'gate_on_days':sum(e['detail'].get('gate')==1 for e in plan),'source_lag_days':lag,'input_variant':variant}
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,other in [('E_SPOT',old),('HG_HASH',results[period,'HG_HASH','base']),('HG_STRESS',results[period,'HG_STRESS','base'])]:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(other['daily_returns']),n) for n in (7,14,28)]
 a=results['main','HG_REC','base']['metrics'];b=results['recent','HG_REC','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','HG_REC','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','source_delay7','provider_cm'):g[c]=all(results[p,'HG_REC',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra=all(results[p,'HG_REC','base']['metrics']['net_pnl']>results[p,'HG_HASH','base']['metrics']['net_pnl'] for p in PERIODS)
 for n,e in [('summary',summary),('uncertainty',unc),('information-age',ages),('selection',{'primary':'HG_REC','passed':all(g.values()),'checks':g,'price_information_increment_vs_hash_both':extra,'scope':'development only; delayed provider snapshots not full first-vintage proof; hashrate is an estimate, not miner selling; no hindsight peak exits/control promotion'})]:write(out/f'{n}.json',e)
 print(json.dumps({'gates':g,'price_information_increment':extra,'information':ages}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
