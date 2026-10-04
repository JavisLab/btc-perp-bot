"""Frozen external cash-funding pressure for BTC information; BTCUSDT perp-only accounts."""
import argparse,datetime as dt,gzip,math
from pathlib import Path
import numpy as np
from btc_continuity_study import fit
from btc_session_study import ROOT,DAY,HOUR,ms,sha,canonical,read,write,bootstrap
from btc_persistence_study import Market,PERIODS
import btc_target_ledger as ledger
WEEK=7*DAY;FIRST=ms('2020-01-06');END=ms('2026-09-01');ZERO_HOUR=1730145600000
IDS=('DF_INFO','DF_BANK','DF_GAP','DF_PRICE','DF_INV','DF_TREND');MODELS=IDS[:4];CONTROLS=('DF_BANK','DF_GAP','DF_PRICE','DF_TREND');COLS={'DF_INFO':('r7','r28','funding','bank','gap'),'DF_BANK':('r7','r28','funding','bank'),'DF_GAP':('r7','r28','funding','gap'),'DF_PRICE':('r7','r28','funding')};FEATURE_COLS=('r7','r28','funding','bank','gap');SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'data_delay7':{'macro_lag':7}};GATE=math.log1p(.0013);ledger.LABELS.update({n:n for n in IDS})
DATA_SHA='e5070c9d570d7af17c093b5a4dbbc075e07b90cbb816c4ad44baf3243d3e2a33';GZIP_SHA='5ab1df19eddd1f92480b4cd629c487c375851a6a3e65f4b1989a4d25f59617d4'
def inputs():
 p=ROOT/'data/btc-dollar-funding-20261004';b=(p/'rates.json.gz').read_bytes();assert sha(b)==GZIP_SHA and sha(gzip.decompress(b))==DATA_SHA;a=read(p/'independent-audit.json');assert a['canonical_sha256']==DATA_SHA and a['raw_rows_exact'] and a['probe_overlap_exact'];return read(p/'rates.json.gz')['series']
def close(m,t):
 r=m.rowmaps['BP'].get(t-HOUR);return r[4] if r is not None and t-HOUR!=ZERO_HOUR and r[5]==t-1 and math.isfinite(r[4]) and r[4]>0 else None

def features(m,rates,lag=0,start=FIRST,end=END):
 assert lag in (0,7)
 for kind,rr in rates.items():assert len({r['time'] for r in rr})==len(rr)
 fund={}
 for row in m.funds['BP'].values():fund.setdefault(row[3]//(8*HOUR)*(8*HOUR),[]).append(row)
 out=[]
 for t in range(start,end,WEEK):
  cutoff=t-(7+lag)*DAY;selected={k:sorted([r for r in rates[k] if cutoff-WEEK<=r['time']<cutoff],key=lambda r:r['time']) for k in ('SOFR','EFFR')};dates={k:[r['date'] for r in rr] for k,rr in selected.items()};macrook=dates['SOFR']==dates['EFFR'] and 3<=len(dates['SOFR'])<=5 and all(r['valid'] and math.isfinite(float(r['rate'])) for rr in selected.values() for r in rr)
  times=list(range(t-28*DAY,t+DAY,DAY));prices=[close(m,u) for u in times];priceok=all(x is not None for x in prices);buckets=list(range(t-WEEK,t,8*HOUR));settled=[r for u in buckets for r in fund.get(u,[]) if r[3]<t];fundok=all(len([r for r in fund.get(u,[]) if r[3]<t])==1 for u in buckets) and all(math.isfinite(r[2]) for r in settled)
  e={'source':t,'macro_lag':lag,'macro_cutoff':cutoff,'macro_window_start':cutoff-WEEK,'selected_rows':selected,'selected_dates':dates,'macro_valid':macrook,'price_times':times,'price_closes':prices,'price_valid':priceok,'funding_buckets':buckets,'funding_rows':settled,'funding_valid':fundok,'valid':macrook and priceok and fundok};e.update({k:None for k in FEATURE_COLS})
  if macrook:
   n=len(selected['EFFR']);e['bank']=math.fsum(float(r['rate']) for r in selected['EFFR'])/n;e['gap']=100*math.fsum(float(a['rate'])-float(b['rate']) for a,b in zip(selected['SOFR'],selected['EFFR']))/n
  if priceok:e['r7']=math.log(prices[-1]/prices[-8]);e['r28']=math.log(prices[-1]/prices[0])
  if fundok:e['funding']=365/7*math.fsum(r[2] for r in settled)
  assert cutoff+WEEK<=t and (not e['valid'] or all(math.isfinite(e[k]) for k in FEATURE_COLS));out.append(e)
 return out

def labels(m,start=FIRST,end=END):
 out={}
 for t in range(start,end,WEEK):
  a,b=close(m,t),close(m,t+WEEK);out[t]={'end':t+WEEK,'value':math.log(b/a) if a is not None and b is not None else None}
 return out

def forecast_one(rows,yy,i):
 row=rows[i];t=row['source'];keep=[j for j in range(max(0,i-105),i) if t-105*WEEK<=rows[j]['source']<=t-2*WEEK and rows[j]['valid'] and yy[rows[j]['source']]['value'] is not None and yy[rows[j]['source']]['end']<=t-DAY];weeks=[rows[j]['source'] for j in keep];e={'source':t,'training_weeks':weeks,'training_n':len(weeks),'training_label_end':max((yy[u]['end'] for u in weeks),default=None),'models':{}}
 for name,cols in COLS.items():
  if not row['valid'] or len(keep)<52:e['models'][name]={'mu':None,'se':None,'training_n':len(weeks),'reason':'feature_or_warmup'};continue
  a=np.array([[rows[j][c] for c in cols] for j in keep]);y=np.array([yy[u]['value'] for u in weeks]);cur=np.array([row[c] for c in cols]);e['models'][name]=fit(a,y,weeks,cur,constrain=False)
 return e

def threshold(mu,se):return (1 if mu>0 else -1) if abs(mu)>GATE+se else 0

def decision(name,models,score):
 info,base=models['DF_INFO'],models['DF_BANK'];side=0;delta=None
 if info['mu'] is not None and base['mu'] is not None:
  delta=info['mu']-base['mu'];gate=threshold(info['mu'],info['se'])
  if info['beta'][-1]<0 and gate and abs(delta)>1e-12 and delta*info['mu']>0:side=gate
 if name in ('DF_INFO','DF_INV'):over=side*(-1 if name=='DF_INV' else 1)
 elif name=='DF_TREND':over=0
 else:
  pred=models[name];over=threshold(pred['mu'],pred['se']) if pred['mu'] is not None and (name=='DF_PRICE' or (name=='DF_BANK' and pred['beta'][-1]<0) or (name=='DF_GAP' and pred['beta'][-1]<0)) else 0
 return float(over) if over else score,bool(over),delta

def schedule(m,ff,pp,name,start,end,risk=.2):
 ft={f['source']:f for f in ff};pt={p['source']:p for p in pp};out=[]
 for t in range(start,end,DAY):
  week=t-dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).weekday()*DAY;f=ft[week];p=pt[week];obs=m.observation(t,risk);detail={'week_source':week,'feature':f,'models':p['models'],'training_n':p['training_n'],'training_label_end':p['training_label_end']}
  if obs is None:out.append({'source_time':t,'weights':None,'detail':dict(detail,risk_missing=True)});continue
  score,w,vol=obs;signal,over,delta=decision(name,p['models'],score);detail.update(score=score,risk=w,vol=vol,signal=signal,override=over,core_fallback=not over,increment=delta);out.append({'source_time':t,'weights':{'BS':0.,'BP':signal*w},'rebalance':True,'hedge':False,'detail':detail})
 return out

def forecast_summary(pp,yy,start,end):
 eligible=[p for p in pp if start<=p['source']<end and yy[p['source']]['end']<=end and yy[p['source']]['value'] is not None];paired=[p for p in eligible if all(p['models'][k]['mu'] is not None for k in MODELS)];out={'n':len(paired),'eligible_label_weeks':len(eligible),'coverage':len(paired)/len(eligible) if eligible else 0,'common_weeks':[p['source'] for p in paired],'models':{}}
 for name in MODELS:
  mu=np.array([p['models'][name]['mu'] for p in paired]);y=np.array([yy[p['source']]['value'] for p in paired]);betas=[p['models'][name]['beta'][-1] for p in paired];out['models'][name]={'n':len(y),'mse':float(np.mean((mu-y)**2)) if len(y) else None,'sign_accuracy':float(np.mean(np.sign(mu)==np.sign(y))) if len(y) else None,'negative_last_beta_weeks':sum(b<0 for b in betas),'median_last_beta':float(np.median(betas)) if betas else None}
 return out

def selection(summary,forecasts,activity):
 a=summary['main-DF_INFO-base']['metrics'];b=summary['recent-DF_INFO-base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-DF_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):g[c]=all(summary[p+'-DF_INFO-'+c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in CONTROLS:extra['net_beats_'+name+'_both']=all(summary[p+'-DF_INFO-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_LONG_both']=all(summary[p+'-DF_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-DF_BANK-base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for ctrl in ('DF_BANK','DF_PRICE'):extra['mse_strictly_better_'+ctrl+'_both']=all(forecasts[p]['0']['models']['DF_INFO']['mse'] is not None and forecasts[p]['0']['models'][ctrl]['mse'] is not None and forecasts[p]['0']['models']['DF_INFO']['mse']<forecasts[p]['0']['models'][ctrl]['mse'] for p in PERIODS)
 for p in PERIODS:
  f=forecasts[p]['0'];beta=f['models']['DF_INFO']['median_last_beta'];extra[p+'_enough_forecasts']=f['n']>=(52 if p=='main' else 20);extra[p+'_coverage']=f['coverage']>=.8;extra[p+'_negative_gap_beta']=beta is not None and beta<0;extra[p+'_new_information_active']=activity[p]['DF_INFO-base']['override_weeks']>=(20 if p=='main' else 5)
 return {'primary':'DF_INFO','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'BTC-only repeated-history development. External SOFR-EFFR funding pressure conditional on EFFR level, current BTC settled funding and price; macro weekly observations delayed at least seven calendar days. No structural funding-flow identification, first-vintage or unused-OOS proof, other-asset trades, or control promotion.'}

def run(out):
 out=Path(out);m=Market();m.rowmaps['BP'].pop(ZERO_HOUR,None);snapshots=inputs();yy=labels(m);write(out/'labels.json.gz',{str(k):v for k,v in yy.items()});ff={};pp={}
 for lag in (0,7):
  ff[lag]=features(m,snapshots,lag);pp[lag]=[forecast_one(ff[lag],yy,i) for i in range(len(ff[lag]))];write(out/f'features-lag{lag}.json.gz',ff[lag]);write(out/f'forecasts-lag{lag}.json.gz',pp[lag])
 results={};summary={};unc={};identity={};activity={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={str(lag):forecast_summary(p,yy,start,end) for lag,p in pp.items()};activity[period]={}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);lag=cfg.pop('macro_lag',0);plan=schedule(m,ff[lag],pp[lag],name,start,end,risk);pf=f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz';write(out/pf,plan);x=ledger.simulate(m,name,start,end,plan,**cfg);assert all(e.get('instrument')=='BP' for e in x['events']) and all(d['positions']['BS']==0 for d in x['daily']);x.update(period=period,scenario=scenario,risk_target=risk,macro_lag=lag,schedule_file=pf,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),fit_helper_sha256=sha((ROOT/'tools/btc_continuity_study.py').read_bytes()),macro_input_sha256=DATA_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']};activity[period][name+'-'+scenario]={'override_days':sum(e['detail'].get('override',False) for e in plan),'override_weeks':len({e['detail']['week_source'] for e in plan if e['detail'].get('override')}),'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_feature_days':sum(not e['detail']['feature']['valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['DF_INFO']['mu'] is None for e in plan),'nonnegative_gap_beta_days':sum(e['detail']['models']['DF_INFO']['mu'] is not None and e['detail']['models']['DF_INFO']['beta'][-1]>=0 for e in plan)}
    if scenario=='base':print({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}},flush=True)
  old=read(ROOT/f'runs/btc-pressure-20261004/{period}-TP_TREND-base.json.gz');ctrl=results[period,'DF_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':f'runs/btc-pressure-20261004/{period}-TP_TREND-base.json.gz'}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in CONTROLS:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 sel=selection(summary,forecast,activity)
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('forecast-summary',forecast),('selection',sel)]:write(out/f'{n}.json',v)
 print({'selection':sel,'forecast':{p:forecast[p]['0'] for p in PERIODS}},flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
