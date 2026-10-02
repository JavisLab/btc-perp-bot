"""BTC regime-short hypotheses, separately fixed after attribution."""
import argparse,gzip,json,math
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,sha
from btc_persistence_study import Market,SCENARIOS,PERIODS
import btc_target_ledger as ledger
from btc_oi_study import write
ROOT=Path(__file__).resolve().parents[1];IDS=('RG_FLAT','RG_ENTRY')
ledger.LABELS.update({n:n for n in IDS});simulate=ledger.simulate

def schedule(m,name,start,end,risk_target=.2):
 allowed=False;out=[]
 for t in range(start,end,DAY):
  obs=m.observation(t,risk_target);i=m.index.get(t-DAY,-1);hist=m.close[i-19:i+1]
  if obs is None or len(hist)!=20 or not np.all(np.isfinite(hist)):
   out.append({'source_time':t,'weights':None,'detail':{'missing_warmup':True}});continue
  score,risk,vol=obs;delta=hist[-1]-hist[0];length=math.fsum(abs(b-a) for a,b in zip(hist,hist[1:]));er=abs(delta)/length if length else 0.;down=er>=.3 and delta<0
  if score>=0:allowed=False
  elif down:allowed=True
  signal=score if score>0 or (score<0 and (down if name=='RG_FLAT' else allowed)) else 0.
  out.append({'source_time':t,'weights':{'BS':max(0,signal)*risk,'BP':min(0,signal)*risk},'rebalance':True,'hedge':False,'detail':{'score':score,'signal':signal,'risk':risk,'vol':vol,'er':er,'efficient_down':bool(down),'short_intent_allowed':allowed}})
 return out

def bootstrap(x,other=None,length=14):
 a=np.array(x['daily_returns'])
 if other is not None:a=a-np.array(other['daily_returns'])
 rng=np.random.default_rng(1489+length);idx=(rng.integers(0,len(a),(2000,math.ceil(len(a)/length),1))+np.arange(length))%len(a);v=a[idx.reshape(2000,-1)[:,:len(a)]].mean(axis=1)*100
 return {'block_days':length,'mean_daily_pct':float(a.mean()*100),'ci95':np.quantile(v,[.025,.975]).tolist(),'ci_bonferroni2':np.quantile(v,[.0125,.9875]).tolist(),'replicates':2000}

def run(out):
 out=Path(out);m=Market();results={(p,'E_MIX',c):json.loads(gzip.decompress((ROOT/f'runs/btc-persistence-20261002/{p}-E_MIX-{c}.json.gz').read_bytes())) for p in PERIODS for c in SCENARIOS};summary={};uncertainty={};gates={}
 for period,(start,end) in PERIODS.items():
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    conf=dict(c);risk=conf.pop('risk_target',.2);plan=schedule(m,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan)
    x=simulate(m,name,start,end,plan,**conf);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()))
    write(out/f'{period}-{name}-{scenario}.json.gz',x);results[(period,name,scenario)]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**x['metrics']}),flush=True)
  for name in IDS:
   x=results[(period,name,'base')];u={'mean':[bootstrap(x,length=n) for n in (7,14,28)],'vs_E_MIX':[bootstrap(x,results[(period,'E_MIX','base')],n) for n in (7,14,28)]}
   if name.startswith('H_'):u['vs_B_MIX']=[bootstrap(x,results[(period,'B_MIX','base')],n) for n in (7,14,28)]
   uncertainty[f'{period}-{name}']=u
 for name in IDS:
  m=results[('main',name,'base')]['metrics'];r=results[('recent',name,'base')]['metrics'];annual=results[('main',name,'base')]['periods']['yearly']
  g={'main_return':m['return_pct']>52.8387132247115,'main_dd':m['max_drawdown_pct']<=13.561952026088653,'recent_return':r['return_pct']>4.62839056986033,'recent_dd':r['max_drawdown_pct']<=10.450945997063743,'years':sum(v['return_pct']>0 for v in annual.values())>=3,'sharpe':m['sharpe']>=.8,'main_risk':m['realized_vol_pct']<=13.34362053507505,'recent_risk':r['realized_vol_pct']<=16.520409487759576,'episodes':m['round_trips']>=20,'margin':m['margin_buffer_breach_hours']==r['margin_buffer_breach_hours']==0}
  for s in ('base','cost_x2','delay1','delay24'):g[s]=all(results[(p,name,s)]['metrics']['net_pnl']>0 for p in PERIODS)
  gates[name]={'passed':all(g.values()),'checks':g,'is_control':name in ('E_MIX','B_MIX')}
 write(out/'summary.json',summary);write(out/'uncertainty.json',uncertainty);write(out/'selection.json',gates);print(json.dumps(gates),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
