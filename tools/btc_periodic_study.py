"""Preregistered BTC calendar-risk information; unchanged long-only trend direction."""
import argparse,datetime as dt,gzip,json,math
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS,SCENARIOS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('PS_CAL','PS_HAR','PS_DAY','PS_MEAN','PS_INV','PS_TREND');FITS=IDS[:4];ledger.LABELS.update({n:n for n in IDS});FLOOR=1e-8
RV_SHA='2da197d43eb2275681050988c888093975eb8f34368f05570b146a6cc46a6c47'
GZIP_SHA='61b3b68aa4ac96116f30986e76303a8cb394837edff6a22242dbb226f20ef1ee'
AUDIT_SHA='0e9531e91d532305902625df2e9d8a49414c954ece2e6a693c80c2150d1dc725';PROOF_SHA='f70aceabfe3016dc26a15404478e4b8bd314e1b974885226aaae3b9ed4bd640e'
COLS={'PS_CAL':tuple(range(9)),'PS_HAR':(0,1,2),'PS_DAY':tuple(range(3,9)),'PS_MEAN':()}
def inputs():
 p=ROOT/'data/btc-rv-20261002';assert sha((p/'daily-rv.json.gz').read_bytes())==GZIP_SHA and sha((p/'audit.json').read_bytes())==AUDIT_SHA and sha((p/'verification.json').read_bytes())==PROOF_SHA;rows=read(p/'daily-rv.json.gz');assert sha(canonical(rows))==RV_SHA
 assert [r['day'] for r in rows]==list(range(ms('2020-01-01'),ms('2026-09-01'),DAY)) and all(r['end']==r['day']+DAY for r in rows)
 return rows

def weekday(t):return dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).weekday()
def calendar(t):
 d=weekday(t);return [int(d==k)-int(d==6) for k in range(6)]
def valid_rv(r):return r is not None and r['end']==r['day']+DAY and r['valid'] and r['rv'] is not None and math.isfinite(r['rv']) and r['rv']>0

def features(rows):
 byday={r['day']:r for r in rows};out=[]
 for r in rows:
  t=r['end'];d=r['day'];wanted=list(range(d-21*DAY,d+DAY,DAY));vv=[byday.get(u) for u in wanted];good=all(valid_rv(x) for x in vv);rv=[v['rv'] for v in vv] if good else None;y=byday.get(t);truth=y['rv'] if valid_rv(y) else None
  z=[math.log(rv[-1]),math.log(math.fsum(rv[-5:])/5),math.log(math.fsum(rv)/22)] if good else [None]*3
  out.append({'source':t,'observed_day':d,'input_days':wanted,'input_rv':rv,'valid':good,'log_rv_features':z,'weekday':weekday(t),'calendar':calendar(t),'features':z+calendar(t),'truth':truth,'truth_end':t+DAY if y is not None else None})
 return out

def restore(logpoint,logsmear):
 logv=logpoint+logsmear
 if not math.isfinite(logv):return {'prediction':None,'floor':False,'reason':'nonfinite_log_prediction'}
 try:raw=math.exp(logv)
 except OverflowError:return {'prediction':None,'floor':False,'reason':'exp_overflow','log_variance':logv}
 if not math.isfinite(raw):return {'prediction':None,'floor':False,'reason':'nonfinite_prediction','log_variance':logv}
 return {'prediction':max(raw,FLOOR),'unclipped':raw,'floor':raw<FLOOR,'log_variance':logv}

def fit(x,y,current):
 n,p=x.shape
 if not n or not all(np.all(np.isfinite(v)) for v in (x,y,current)):return {'prediction':None,'floor':False,'reason':'nonfinite_input','n':n,'rank':None}
 means=x.mean(axis=0);scale=x.std(axis=0);scale[scale<1e-12]=1.;Z=np.column_stack([np.ones(n),(x-means)/scale]);rank=int(np.linalg.matrix_rank(Z));out={'prediction':None,'floor':False,'rank':rank,'n':n}
 if rank!=p+1 or not np.all(np.isfinite(Z)) or not np.all(np.isfinite(y)):out['reason']='rank_or_nonfinite';return out
 coef=np.linalg.lstsq(Z,y,rcond=None)[0];beta=np.r_[coef[0]-np.dot(coef[1:]/scale,means),coef[1:]/scale];res=y-Z@coef;top=float(np.max(res));logsmear=top+math.log(float(np.mean(np.exp(res-top))));mu=float(np.r_[1.,current]@beta)
 out.update(restore(mu,logsmear));out.update(beta=beta.tolist(),feature_mean=means.tolist(),feature_scale=scale.tolist(),residuals=res.tolist(),log_smearing=logsmear,smearing=math.exp(logsmear),log_point=mu,residual_ss=float(res@res))
 return out

def forecast_one(ff,i):
 e=ff[i];t=e['source'];keep=[j for j in range(max(0,i-365),i) if t-365*DAY<=ff[j]['source']<=t-DAY and ff[j]['valid'] and ff[j]['truth'] is not None and ff[j]['truth_end']<=t];sources=[ff[j]['source'] for j in keep];counts=[sum(ff[j]['weekday']==d for j in keep) for d in range(7)];valid=e['valid'] and len(keep)>=300 and min(counts)>=40
 out={'source':t,'training_days':sources,'training_n':len(keep),'training_weekday_counts':counts,'training_label_end':max((ff[j]['truth_end'] for j in keep),default=None),'models':{}}
 for name,cols in COLS.items():
  if not valid:out['models'][name]={'prediction':None,'floor':False,'reason':'feature_or_common_warmup'};continue
  x=np.array([[ff[j]['features'][c] for c in cols] for j in keep]).reshape(len(keep),len(cols));y=np.log([ff[j]['truth'] for j in keep]);current=np.array([e['features'][c] for c in cols]);out['models'][name]=fit(x,y,current)
 a,b=out['models']['PS_CAL']['prediction'],out['models']['PS_HAR']['prediction']
 out['models']['PS_INV']=restore(2*math.log(b)-math.log(a),0.) if a is not None and b is not None else {'prediction':None,'floor':False,'reason':'base_model_missing'}
 return out

def predict(ff,m):
 out=[]
 for i,e in enumerate(ff):
  p=forecast_one(ff,i);obs=m.observation(e['source']);v=(obs[2]**2/365) if obs is not None else None;p['models']['PS_TREND']={'prediction':v,'floor':False};out.append(p)
 return out

def schedule(m,ff,pp,name,start,end,risk=.2):
 out=[];fm={e['source']:e for e in ff}
 for p in pp:
  t=p['source']
  if not start<=t<end:continue
  obs=m.observation(t,risk);model=p['models'][name];v=model['prediction'];detail={'forecast':v,'floor':model['floor'],'weekday':fm[t]['weekday'],'training_n':p['training_n'],'training_label_end':p['training_label_end'],'input_valid':fm[t]['valid']}
  if obs is None or v is None:out.append({'source_time':t,'weights':None,'detail':dict(detail,missing=True)});continue
  score,oldrisk,oldvol=obs;vol=oldvol if name=='PS_TREND' else math.sqrt(365*v);weight=oldrisk if name=='PS_TREND' else min(1,risk/vol);signal=max(0,score);detail.update(score=score,signal=signal,risk=weight,vol=vol,old_vol=oldvol,missing=False)
  out.append({'source_time':t,'weights':{'BS':signal*weight,'BP':0.},'hedge':False,'rebalance':True,'detail':detail})
 return out

def forecast_summary(ff,pp,start,end):
 truth={e['source']:e for e in ff};paired=[p for p in pp if start<=p['source']<end and truth[p['source']]['truth'] is not None and truth[p['source']]['truth_end']<=end and all(p['models'][n]['prediction'] is not None and math.isfinite(p['models'][n]['prediction']) and p['models'][n]['prediction']>0 for n in IDS)];out={'n':len(paired),'calendar_days':(end-start)//DAY,'coverage':len(paired)/((end-start)//DAY),'common_days':[p['source'] for p in paired],'models':{},'loss_differences':{},'ci_units':'Generic bootstrap mean_daily_pct/ci95 divide by100 for variance-squared or QLIKE units; paired rows compressed if missing, not independent OOS'};losses={};y=np.array([truth[p['source']]['truth'] for p in paired])
 for name in IDS:
  v=np.array([p['models'][name]['prediction'] for p in paired]);mse=(y-v)**2;ratio=y/v;q=ratio-np.log(ratio)-1;scheduled=[p for p in pp if start<=p['source']<end and p['models'][name]['prediction'] is not None];floors=sum(p['models'][name]['floor'] for p in scheduled);out['models'][name]={'n':len(y),'mse':float(np.mean(mse)) if len(y) else None,'qlike':float(np.mean(q)) if len(y) else None,'floor_fraction':floors/len(scheduled) if scheduled else None,'scheduled_predictions':len(scheduled),'floor_count':floors};losses[name]=(mse,q)
 for ctrl in ('PS_HAR','PS_MEAN'):
  out['loss_differences']['CAL_vs_'+ctrl]={k:[bootstrap(losses[ctrl][j]-losses['PS_CAL'][j],b) for b in (7,14,28)] if len(y) else [] for j,k in enumerate(('mse_improvement','qlike_improvement'))}
 return out

def run(out):
 out=Path(out);daily=inputs();ff=features(daily);m=Market();pp=predict(ff,m);write(out/'features.json.gz',ff);write(out/'predictions.json.gz',pp);results={};summary={};forecast={};unc={};activity={};identity={}
 for period,(start,end) in PERIODS.items():
  forecast[period]=forecast_summary(ff,pp,start,end);activity[period]={}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan=schedule(m,ff,pp,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),rv_input_sha256=RV_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']};activity[period][name+'-'+scenario]={'missing_days':sum(e['weights'] is None for e in plan),'floor_days':sum(e['detail']['floor'] for e in plan),'positive_direction_days':sum(e['detail'].get('signal',0)>0 for e in plan),'long_target_days':sum(e['weights'] is not None and e['weights']['BS']>0 for e in plan)}
    if scenario=='base':print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{period}-E_SPOT.json.gz');ctrl=results[period,'PS_TREND','base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};err=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and err<1e-9 and max(errors.values())<1e-7;identity[period]={'metric_errors':errors,'daily_return_max_error':err,'saved_control':f'runs/search-1458/{period}-E_SPOT.json.gz'}
  for name in IDS:
   rr=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(rr,b) for b in (7,14,28)]}
   for ctrl in ('PS_HAR','PS_DAY','PS_MEAN','PS_TREND'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(rr-np.array(results[period,ctrl,'base']['daily_returns']),b) for b in (7,14,28)]
 a=results['main','PS_CAL','base']['metrics'];b=results['recent','PS_CAL','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','PS_CAL','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'PS_CAL',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for ctrl in ('PS_HAR','PS_DAY','PS_MEAN','PS_TREND'):extra['net_beats_'+ctrl+'_both']=all(results[p,'PS_CAL','base']['metrics']['net_pnl']>results[p,ctrl,'base']['metrics']['net_pnl'] for p in PERIODS)
 extra['dd_no_worse_HAR_both']=all(results[p,'PS_CAL','base']['metrics']['max_drawdown_pct']<=results[p,'PS_HAR','base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 for period,fc in forecast.items():
  aa,bb,cc=map(fc['models'].get,('PS_CAL','PS_HAR','PS_MEAN'));extra[period+'_coverage']=fc['coverage']>=.90;extra[period+'_floor']=aa['floor_fraction'] is not None and aa['floor_fraction']<=.01;extra[period+'_prediction']=aa['qlike'] is not None and bb['qlike'] is not None and cc['qlike'] is not None and aa['qlike']<bb['qlike'] and aa['qlike']<cc['qlike'] and aa['mse']<=bb['mse']
 for n,v in [('summary',summary),('forecast-summary',forecast),('uncertainty',unc),('activity',activity),('control-identity',identity),('selection',{'primary':'PS_CAL','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'Known weekday in log-RV risk prediction only; unchanged BTC long-only direction, funding zero by instrument; development data, current-vintage archives, not OOS or original EGARCH replication, no control promotion'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'forecast':{p:{'n':fc['n'],'coverage':fc['coverage'],'models':fc['models']} for p,fc in forecast.items()}}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
