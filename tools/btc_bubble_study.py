"""Preregistered causal BTC log-periodic bubble-break overlay. Offline, no external model code."""
import argparse,json,math,itertools
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_cot_study import close
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('BB_SWITCH','BB_CASH','BB_QUAD','BB_TREND');ledger.LABELS.update({x:x for x in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1}}
N=672;GRID=tuple(itertools.product((.05,.1,.2,1/3),(.1,.3,.5,.7,.9),(4.,8.,12.,16.,20.,24.)))
U=np.linspace(0,1,N);BASES=[]
for d,m,w in GRID:
 z=1+d-U;f=z**m;BASES.append(np.column_stack([np.ones(N),f,f*np.cos(w*np.log(z)),f*np.sin(w*np.log(z))]))
BASES=np.array(BASES);PINVS=np.linalg.pinv(BASES);Q=np.column_stack([np.ones(N),U,U*U]);L=Q[:,:2];QP=np.linalg.pinv(Q);LP=np.linalg.pinv(L)
def bic(sse,k,search=1):return N*math.log(max(sse/N,1e-24))+k*math.log(N)+2*math.log(search)
def fit_curve(prices):
 y=np.log(np.asarray(prices,float)/prices[0]);coef=PINVS@y;fitted=np.einsum('gnk,gk->gn',BASES,coef);err=fitted-y;sse=np.einsum('gn,gn->g',err,err);j=int(np.argmin(sse));b=coef[j];d,m,w=GRID[j];linear=LP@y;quad=QP@y;ls=float(np.sum((L@linear-y)**2));qs=float(np.sum((Q@quad-y)**2));score=bic(float(sse[j]),7,len(GRID));cycles=w/(2*math.pi)*math.log((1+d)/d);amp=math.hypot(b[2],b[3]);damping=m*abs(float(b[1]))/(w*amp) if amp else None;maxerror=float(np.max(np.abs(np.expm1(err[j]))));direction=1 if b[1]<0 and y[-1]>0 else -1 if b[1]>0 and y[-1]<0 else 0
 checks={'linear_bic':bic(ls,2)-score>=10,'quadratic_bic':bic(qs,3)-score>=10,'horizon':d<=.2,'full_cycles':cycles>=2.5,'damping':damping is None or damping>=1,'relative_error':maxerror<=.15,'direction':direction!=0};bubble=direction if all(checks.values()) else 0;qdir=int(quad[2]>0)-int(quad[2]<0);qflag=qdir if qdir and qdir*float(y[-1])>0 and qdir*float(quad[1]+2*quad[2])>0 and bic(ls,2)-bic(qs,3)>=10 else 0
 return {'valid':True,'best_index':j,'parameters':list(GRID[j]),'beta':b.tolist(),'sse_all':sse.tolist(),'linear_beta':linear.tolist(),'quadratic_beta':quad.tolist(),'linear_sse':ls,'quadratic_sse':qs,'bic':score,'linear_bic':bic(ls,2),'quadratic_bic':bic(qs,3),'full_cycles':cycles,'damping':damping,'max_relative_error':maxerror,'checks':checks,'bubble':bubble,'quadratic':qflag,'window_log_return':float(y[-1])}
def features(m,start=ms('2020-01-01'),end=ms('2026-09-01')):
 out=[]
 for t in range(start,end,DAY):
  rows=[m.rowmaps['BS'].get(h) for h in range(t-N*HOUR,t,HOUR)];valid=all(r is not None and r[4]>0 and r[5]==r[0]+HOUR-1 and r[5]<t for r in rows);e={'source':t,'first_open':t-N*HOUR,'last_close':t-1,'valid':False,'bubble':0,'quadratic':0}
  if valid:e.update(fit_curve([r[4] for r in rows]))
  out.append(e)
 return out

def states(m,feats,name,start,end):
 table={e['source']:e for e in feats};expiry=start;direction=0;cause=None;out={};field='quadratic' if name=='BB_QUAD' else 'bubble'
 for t in range(start,end,DAY):
  triggered=False
  if t>=expiry:direction=0;cause=None
  a,b=close(m,t-DAY),close(m,t);rv=math.log(b/a) if a is not None and b is not None and a>0 and b>0 else None
  if name!='BB_TREND' and direction==0:
   known=[table[s] for s in range(t-7*DAY,t,DAY) if s in table and table[s]['valid'] and table[s][field]];e=known[-1] if known else None
   if e is not None and rv is not None and rv*e[field]<0:direction=-e[field];cause=e['source'];expiry=t+7*DAY;triggered=True
  out[t]={'direction':direction,'cause':cause,'expiry':expiry if direction else None,'triggered':triggered,'last_day_return':rv}
 return out

def schedule(m,feats,name,start,end,risk=.2):
 out=[];state=states(m,feats,name,start,end)
 for t in range(start,end,DAY):
  e=state[t];obs=m.observation(t,risk)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':dict(e,risk_missing=True)});continue
  score,w,vol=obs;s=(0 if name=='BB_CASH' else e['direction']) if e['direction'] else max(0,score)
  out.append({'source_time':t,'weights':{'BS':max(0,s)*w,'BP':min(0,s)*w},'rebalance':True,'hedge':False,'detail':dict(e,score=score,risk=w,vol=vol,signal=s)})
 return out

def run(out):
 out=Path(out);m=Market();feats=features(m);write(out/'features.json.gz',feats);results={};summary={};unc={};identity={};activity={}
 for period,(start,end) in PERIODS.items():
  ff=[e for e in feats if start<=e['source']<end];activity[period]={'feature_days':len(ff),'missing_windows':sum(not e['valid'] for e in ff),'bubble_positive':sum(e['bubble']==1 for e in ff),'bubble_negative':sum(e['bubble']==-1 for e in ff),'quadratic_positive':sum(e['quadratic']==1 for e in ff),'quadratic_negative':sum(e['quadratic']==-1 for e in ff),'failed_filters':{k:sum(e['valid'] and not e['checks'][k] for e in ff) for k in ('linear_bic','quadratic_bic','horizon','full_cycles','damping','relative_error','direction')},'strategies':{}}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan=schedule(m,feats,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()));write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':
     print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True);activity[period]['strategies'][name]={'overlay_days':sum(bool(e['detail']['direction']) for e in plan),'overlay_starts':sum(e['detail']['triggered'] for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'risk_missing_days':sum(e['weights'] is None for e in plan)}
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'BB_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7,(period,errors,daily);identity[period]={'metric_errors':errors,'daily_return_max_error':daily}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('BB_TREND','BB_QUAD'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','BB_SWITCH','base']['metrics'];b=results['recent','BB_SWITCH','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','BB_SWITCH','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'BB_SWITCH',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={'net_beats_trend_both':all(results[p,'BB_SWITCH','base']['metrics']['net_pnl']>results[p,'BB_TREND','base']['metrics']['net_pnl'] for p in PERIODS),'net_beats_quadratic_both':all(results[p,'BB_SWITCH','base']['metrics']['net_pnl']>results[p,'BB_QUAD','base']['metrics']['net_pnl'] for p in PERIODS),'dd_no_worse_trend_both':all(results[p,'BB_SWITCH','base']['metrics']['max_drawdown_pct']<=results[p,'BB_TREND','base']['metrics']['max_drawdown_pct'] for p in PERIODS)}
 for n,v in [('summary',summary),('uncertainty',unc),('trend-identity',identity),('activity',activity),('selection',{'primary':'BB_SWITCH','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; discrete log-periodic approximation, not paper replication or calibrated crash probability; controls not promotable'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'activity':activity}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
