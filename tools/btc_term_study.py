"""Frozen same-currency BTC dated-forward information; BTCUSDT perp-only accounts."""
import argparse,datetime as dt,gzip,math
from pathlib import Path
import numpy as np
from btc_continuity_study import fit
from btc_session_study import ROOT,DAY,HOUR,ms,sha,canonical,read,write,bootstrap
from btc_persistence_study import Market,PERIODS
import btc_target_ledger as ledger
WEEK=7*DAY;FIRST=ms('2020-01-06');END=ms('2026-09-01');ZERO_HOUR=1730145600000
IDS=('TS_INFO','TS_FUND','TS_TERM','TS_PRICE','TS_INV','TS_TREND');MODELS=IDS[:4];CONTROLS=('TS_FUND','TS_TERM','TS_PRICE','TS_TREND');COLS={'TS_INFO':('r7','r28','tau','funding','carry'),'TS_FUND':('r7','r28','tau','funding'),'TS_TERM':('r7','r28','tau','carry'),'TS_PRICE':('r7','r28','tau')};FEATURE_COLS=('r7','r28','tau','funding','carry');SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1},'data_delay7':{'derivative_lag':7}};GATE=math.log1p(.0013);ledger.LABELS.update({n:n for n in IDS})
DATA_SHA='5a398450cb7522e2ae8d6ead313ccfb6195f152f8e732eef08d6f61999da30c1';GZIP_SHA='73447f59f4be8119cf1efe42021ed3340bddd09eed5fb7a76a50df4d9bd536c8'
def inputs():
 p=ROOT/'data/btc-term-20261004';b=(p/'contracts.json.gz').read_bytes();assert sha(b)==GZIP_SHA and sha(gzip.decompress(b))==DATA_SHA;a=read(p/'independent-audit.json');assert a['canonical_sha256']==DATA_SHA and a['raw_rows_exact'];return read(p/'contracts.json.gz')['contracts']
def close(m,t):
 r=m.rowmaps['BP'].get(t-HOUR);return r[4] if r is not None and t-HOUR!=ZERO_HOUR and r[5]==t-1 and math.isfinite(r[4]) and r[4]>0 else None
def features(m,contracts,lag=0,start=FIRST,end=END):
 cm={c['symbol']:{int(e['raw'][0]):e for e in c['rows']} for c in contracts};fund={}
 for row in m.funds['BP'].values():fund.setdefault(row[3]//(8*HOUR)*(8*HOUR),[]).append(row)
 out=[]
 for t in range(start,end,WEEK):
  cutoff=t-lag*DAY;eligible=sorted([c for c in contracts if c['first_valid_open'] is not None and c['first_valid_open']+HOUR<=cutoff<c['expiry_date_proxy']],key=lambda c:c['expiry_date_proxy']);pair=eligible[:2];bars=[cm[c['symbol']].get(cutoff-HOUR) for c in pair];curveok=len(pair)==2 and all(b is not None and b['valid'] and int(b['raw'][6])==cutoff-1 for b in bars);times=list(range(t-28*DAY,t+DAY,DAY));prices=[close(m,u) for u in times];priceok=all(x is not None for x in prices);buckets=list(range(cutoff-WEEK,cutoff,8*HOUR));settled=[r for u in buckets for r in fund.get(u,[]) if r[3]<cutoff];fundok=all(len([r for r in fund.get(u,[]) if r[3]<cutoff])==1 for u in buckets) and all(math.isfinite(r[2]) for r in settled)
  e={'source':t,'derivative_lag':lag,'derivative_cutoff':cutoff,'eligible_symbols':[c['symbol'] for c in eligible],'selected_symbols':[c['symbol'] for c in pair],'selected_expiry_dates':[c['expiry_date_proxy'] for c in pair],'selected_closes':[float(b['raw'][4]) if b is not None else None for b in bars],'selected_valid':[b is not None and b['valid'] for b in bars],'curve_valid':curveok,'price_times':times,'price_closes':prices,'price_valid':priceok,'funding_buckets':buckets,'funding_rows':settled,'funding_valid':fundok,'valid':curveok and priceok and fundok};e.update({k:None for k in FEATURE_COLS})
  if curveok:
   near,far=pair;assert far['expiry_date_proxy']>near['expiry_date_proxy'];e['carry']=365*DAY/(far['expiry_date_proxy']-near['expiry_date_proxy'])*math.log(float(bars[1]['raw'][4])/float(bars[0]['raw'][4]));e['tau']=(near['expiry_date_proxy']-cutoff)/(365*DAY)
  if priceok:e['r7']=math.log(prices[-1]/prices[-8]);e['r28']=math.log(prices[-1]/prices[0])
  if fundok:e['funding']=365/7*math.fsum(r[2] for r in settled)
  assert not e['valid'] or all(math.isfinite(e[k]) for k in FEATURE_COLS);out.append(e)
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
 info,base=models['TS_INFO'],models['TS_FUND'];side=0;delta=None
 if info['mu'] is not None and base['mu'] is not None:
  delta=info['mu']-base['mu'];gate=threshold(info['mu'],info['se'])
  if info['beta'][-1]<0 and gate and abs(delta)>1e-12 and delta*info['mu']>0:side=gate
 if name in ('TS_INFO','TS_INV'):over=side*(-1 if name=='TS_INV' else 1)
 elif name=='TS_TREND':over=0
 else:
  pred=models[name];over=threshold(pred['mu'],pred['se']) if pred['mu'] is not None and (name=='TS_PRICE' or pred['beta'][-1]<0) else 0
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
 a=summary['main-TS_INFO-base']['metrics'];b=summary['recent-TS_INFO-base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in summary['main-TS_INFO-base']['annual'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24','data_delay7'):g[c]=all(summary[p+'-TS_INFO-'+c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for name in CONTROLS:extra['net_beats_'+name+'_both']=all(summary[p+'-TS_INFO-base']['metrics']['net_pnl']>summary[p+'-'+name+'-base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_FUND_both']=all(summary[p+'-TS_INFO-base']['metrics']['max_drawdown_pct']<=summary[p+'-TS_FUND-base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for ctrl in ('TS_FUND','TS_PRICE'):extra['mse_strictly_better_'+ctrl+'_both']=all(forecasts[p]['0']['models']['TS_INFO']['mse'] is not None and forecasts[p]['0']['models'][ctrl]['mse'] is not None and forecasts[p]['0']['models']['TS_INFO']['mse']<forecasts[p]['0']['models'][ctrl]['mse'] for p in PERIODS)
 for p in PERIODS:
  f=forecasts[p]['0'];beta=f['models']['TS_INFO']['median_last_beta'];extra[p+'_enough_forecasts']=f['n']>=(52 if p=='main' else 20);extra[p+'_coverage']=f['coverage']>=.8;extra[p+'_negative_carry_beta']=beta is not None and beta<0;extra[p+'_new_information_active']=activity[p]['TS_INFO-base']['override_weeks']>=(20 if p=='main' else 5)
 return {'primary':'TS_INFO','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'BTC-only repeated-history development; dated USD forward carry conditional on settled perpetual funding, USD(T) price and nominal maturity calendar. Perp-only executions; no real demand observation, exact settlement clock, original PIT archive vintage, unused OOS or control promotion.'}

def run(out):
 out=Path(out);m=Market();m.rowmaps['BP'].pop(ZERO_HOUR,None);contracts=inputs();yy=labels(m);write(out/'labels.json.gz',{str(k):v for k,v in yy.items()});ff={};pp={}
 for lag in (0,7):
  ff[lag]=features(m,contracts,lag);pp[lag]=[forecast_one(ff[lag],yy,i) for i in range(len(ff[lag]))];write(out/f'features-lag{lag}.json.gz',ff[lag]);write(out/f'forecasts-lag{lag}.json.gz',pp[lag])
 results={};summary={};unc={};identity={};activity={};forecast={}
 for period,(start,end) in PERIODS.items():
  forecast[period]={str(lag):forecast_summary(p,yy,start,end) for lag,p in pp.items()};activity[period]={}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);lag=cfg.pop('derivative_lag',0);plan=schedule(m,ff[lag],pp[lag],name,start,end,risk);pf=f'{period}-{name}-plan-risk{risk:.2f}-lag{lag}.json.gz';write(out/pf,plan);x=ledger.simulate(m,name,start,end,plan,**cfg);assert all(e.get('instrument')=='BP' for e in x['events']) and all(d['positions']['BS']==0 for d in x['daily']);x.update(period=period,scenario=scenario,risk_target=risk,derivative_lag=lag,schedule_file=pf,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),fit_helper_sha256=sha((ROOT/'tools/btc_continuity_study.py').read_bytes()),term_input_sha256=DATA_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']};activity[period][name+'-'+scenario]={'override_days':sum(e['detail'].get('override',False) for e in plan),'override_weeks':len({e['detail']['week_source'] for e in plan if e['detail'].get('override')}),'fallback_days':sum(e['detail'].get('core_fallback',False) for e in plan),'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'invalid_feature_days':sum(not e['detail']['feature']['valid'] for e in plan),'model_missing_days':sum(e['detail']['models']['TS_INFO']['mu'] is None for e in plan),'nonnegative_carry_beta_days':sum(e['detail']['models']['TS_INFO']['mu'] is not None and e['detail']['models']['TS_INFO']['beta'][-1]>=0 for e in plan)}
    if scenario=='base':print({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}},flush=True)
  old=read(ROOT/f'runs/btc-pressure-20261004/{period}-TP_TREND-base.json.gz');ctrl=results[period,'TS_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':f'runs/btc-pressure-20261004/{period}-TP_TREND-base.json.gz'}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in CONTROLS:unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 sel=selection(summary,forecast,activity)
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('forecast-summary',forecast),('selection',sel)]:write(out/f'{n}.json',v)
 print({'selection':sel,'forecast':{p:forecast[p]['0'] for p in PERIODS}},flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
