"""Frozen BTC persistence/asymmetry research, no ETH calculations."""
import argparse,gzip,json,math
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,sha,utc
from btc_target_ledger import simulate
from btc_oi_study import write
ROOT=Path(__file__).resolve().parents[1];IDS=('E_MIX','B_MIX','E_STRICT','H_MIX','H_STRICT')
PERIODS={'main':(ms('2022-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1}}
def ema(values,span):
 out=np.full(len(values),np.nan);last=np.nan
 for i,x in enumerate(values):
  if not np.isfinite(x):last=np.nan;continue
  last=x if not np.isfinite(last) else 2/(span+1)*x+(1-2/(span+1))*last;out[i]=last
 return out
class Market:
 def __init__(self):
  raw=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes());assert sha(raw)=='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4'
  payload=json.loads(raw);btc=payload['series']['BTCUSDT'];self.end=payload['end']
  self.rows={'BS':btc['spot'],'BP':btc['perp']};self.marks={'BS':btc['spot'],'BP':btc['mark']}
  self.rowmaps={k:{r[0]:r for r in v} for k,v in self.rows.items()};self.markmaps={k:{r[0]:r for r in v} for k,v in self.marks.items()};self.funds={'BP':{r[0]:r for r in btc['funding']}}
  self.days=np.arange(ms('2020-02-01'),self.end,DAY,dtype=np.int64);self.index={int(t):i for i,t in enumerate(self.days)}
  close=[]
  for t in self.days:
   r=self.rowmaps['BS'].get(int(t+23*HOUR));close.append(r[4] if r is not None and r[5]==t+DAY-1 else np.nan)
  self.close=np.array(close);self.ema={s:ema(self.close,s) for s in (8,16,32,64,128)}
 def observation(self,t,target=.2):
  idx=self.index.get(t-DAY,-1)
  if idx<128:return None
  c=self.close[idx];hist=self.close[idx-20:idx+1]
  if not np.all(np.isfinite(hist)):return None
  vol=float(np.std(np.diff(np.log(hist)),ddof=1)*math.sqrt(365));risk=min(1.,target/vol) if vol>1e-12 else 0
  signs=[float(np.sign(c-self.close[idx-n])) for n in (20,60,120)]+[float(np.sign(self.ema[a][idx]-self.ema[b][idx])) for a,b in ((8,32),(16,64),(32,128))]
  score=sum(signs)/6
  if not math.isfinite(score):return None
  return score,risk,vol

def schedule(m,name,start,end,risk_target=.2):
 state=0;out=[]
 for t in range(start,end,DAY):
  obs=m.observation(t,risk_target)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':{'missing_warmup':True}});continue
  score,risk,vol=obs
  if name=='E_SPOT':signal=max(0,score)
  elif name=='E_MIX':signal=score
  elif name=='B_MIX':signal=float(np.sign(score))
  elif name=='E_STRICT':signal=score if score>0 or score==-1 else 0
  else:
   if state==1 and score<=0:state=0
   elif state==-1 and score>=0:state=0
   if not state:
    if score>=2/3:state=1
    elif score<=(-1 if name=='H_STRICT' else -2/3):state=-1
   signal=state
  weights={'BS':max(0,signal)*risk,'BP':min(0,signal)*risk}
  out.append({'source_time':t,'weights':weights,'rebalance':True,'hedge':False,'detail':{'score':score,'signal':signal,'risk':risk,'vol':vol}})
 return out

def bootstrap(x,other=None,length=14):
 a=np.array(x['daily_returns'])
 if other is not None:a=a-np.array(other['daily_returns'])
 rng=np.random.default_rng(1487+length);idx=(rng.integers(0,len(a),(2000,math.ceil(len(a)/length),1))+np.arange(length))%len(a);v=a[idx.reshape(2000,-1)[:,:len(a)]].mean(axis=1)*100
 return {'block_days':length,'mean_daily_pct':float(a.mean()*100),'ci95':np.quantile(v,[.025,.975]).tolist(),'ci_bonferroni3':np.quantile(v,[.05/6,1-.05/6]).tolist(),'replicates':2000}

def run(out):
 out=Path(out);m=Market();results={};summary={};uncertainty={};gates={}
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
