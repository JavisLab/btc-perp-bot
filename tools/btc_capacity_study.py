"""Frozen BTC prior capacity proxy x completed flow; no network or live clients."""
import argparse,csv,gzip,io,json,math,zipfile
from pathlib import Path
import numpy as np
from btc_session_study import Market,simulate,write,read,bootstrap,PERIODS,SCENARIOS,ROOT,DAY,HOUR,sha,canonical,ms
BLOCK=8*HOUR;WINDOW=1095;MIN_PAIRS=900;GATE=math.log1p(.0013)
IDS=('CP_INT','CP_ADD','CP_FLOW','CP_PRICE','CP_GAP','CP_INV');MODELS=IDS[:-1];COLS={'CP_INT':[0,1,2,3,4],'CP_ADD':[0,1,2,3],'CP_FLOW':[0,1,2],'CP_PRICE':[0,1],'CP_GAP':[0,1,2,5,6]}
PREMIUM=ROOT/'data/btc-premium-20261002';PREMIUM_SHA='2da88be7e88ba42f540c3132aaf6ba79778ba2a24d57e27ac1c61ff82c6e76b2'

def inputs():
 b=gzip.decompress((PREMIUM/'rows-repaired.json.gz').read_bytes());assert sha(b)==PREMIUM_SHA;prem={r[0]:r for r in json.loads(b)};spot={}
 for p in sorted((ROOT/'data/archive-1448/spot').glob('????-??.zip'))+sorted((ROOT/'data/archive-1458/BTCUSDT/spot').glob('????-??.zip')):
  assert sha(p.read_bytes())==p.with_suffix('.CHECKSUM').read_text().split()[0]
  with zipfile.ZipFile(p) as z:
   for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
    if not r[0].isdigit():continue
    t=int(r[0]);end=int(r[6]);div=1000 if t>10**14 else 1;t//=div;end//=div;spot[t]=(float(r[4]),end,float(r[5]))
 return prem,spot

def features(m,prem,spot):
 first=min(m.hourly)//BLOCK*BLOCK+BLOCK;end=(max(m.hourly)//BLOCK+1)*BLOCK;rows=[];vols={};bad={ms(e['time']) for e in m.resolution['unresolved'] if any(abs(v)>1e-3 for v in e['volume_errors'])};funds=sorted((v[2],v[0]) for v in m.funds.values());ft=np.array([x[0] for x in funds])
 for t in range(first,end+1,BLOCK):
  hh=[m.hourly.get(t-j*HOUR) for j in range(8,0,-1)];a,b=m.close(t-BLOCK),m.close(t);ok=a is not None and b is not None and all(r is not None and r[5]>0 and r[7]>0 and 0<=r[10]<=r[7] and r[6]==r[0]+HOUR-1 and r[0] not in bad for r in hh)
  r=math.log(b/a) if ok else None;f=2*math.fsum(x[10] for x in hh)/math.fsum(x[7] for x in hh)-1 if ok else None
  ps=[];gs=[]
  for h in range(t-2*BLOCK,t-BLOCK,HOUR):
   pr=prem.get(h);sp=spot.get(h);pe=m.hourly.get(h)
   if pr is not None and pr[5]==h+HOUR-1 and pr[6]>0:ps.append(pr[4])
   if sp is not None and sp[1]==h+HOUR-1 and sp[0]>0 and sp[2]>0 and pe is not None and pe[6]==h+HOUR-1 and pe[4]>0 and pe[5]>0:gs.append((pe[4]-sp[0])/pe[4])
  A=abs(math.fsum(ps)/8) if len(ps)==8 else None;gap=abs(math.fsum(gs)/8) if len(gs)==8 else None;day=t//DAY*DAY
  if day not in vols:
   c=[m.close(day-j*DAY) for j in range(20,-1,-1)];vols[day]=float(np.std(np.diff(np.log(c)),ddof=1)*math.sqrt(365)) if all(x is not None for x in c) else None
  j=int(np.searchsorted(ft,t-HOUR,side='left'))-1;known=funds[j] if j>=0 and t-funds[j][0]<=16*HOUR else None
  rows.append({'source':t,'flow_start':t-BLOCK,'state_start':t-2*BLOCK,'state_end':t-BLOCK,'r':r,'f':f,'A':A,'gap':gap,'price_valid':bool(ok),'feature_valid':bool(ok and A is not None and gap is not None),'risk_end':day,'annual_vol':vols[day],'funding_time':known[0] if known else None,'funding_rate':known[1] if known else None})
 return rows

def fit(x,y,current):
 k=x.shape[1];mean=x.mean(axis=0);mean[0]=0.;scale=x.std(axis=0);scale[scale<1e-12]=1.;z=(x-mean)/scale;now=(current-mean)/scale
 if np.linalg.matrix_rank(z)<k:return {'mu':None,'se':None,'reason':'rank'}
 beta=np.linalg.lstsq(z,y,rcond=None)[0];res=y-z@beta;s2=float(res@res)/(len(y)-k);mu=float(now@beta);se=math.sqrt(max(0.,s2*float(now@np.linalg.solve(z.T@z,now))));raw=beta/scale;raw[0]-=float((beta*mean/scale).sum())
 return {'mu':mu,'se':se,'beta':raw.tolist(),'residual_variance':s2}

def predict(rows):
 n=len(rows);X=np.full((n,7),np.nan);ret=np.array([e['r'] if e['r'] is not None else np.nan for e in rows]);valid=np.array([e['feature_valid'] for e in rows])
 for i,e in enumerate(rows):
  if valid[i]:X[i]=[1,e['r'],e['f'],e['A'],e['A']*e['f'],e['gap'],e['gap']*e['f']]
 out=[]
 for i,row in enumerate(rows):
  e=dict(row,models={},truth=rows[i+1]['r'] if i+1<n else None,truth_end=rows[i+1]['source'] if i+1<n else None);ix=np.arange(max(0,i-WINDOW),max(0,i-1));ix=ix[valid[ix]&np.isfinite(ret[ix+1])]
  for name in MODELS:
   if i<WINDOW or len(ix)<MIN_PAIRS or not valid[i]:e['models'][name]={'mu':None,'se':None};continue
   col=COLS[name];z=fit(X[ix][:,col],ret[ix+1],X[i,col]);z.update(training_n=len(ix),training_first=rows[int(ix[0])]['source'],training_feature_end=rows[int(ix[-1])]['source'],training_label_end=rows[int(ix[-1])+1]['source']);e['models'][name]=z
  out.append(e)
 return out

def signal(mu,se,F):return 1 if mu>GATE+max(F,0)+se else -1 if mu<-(GATE+max(-F,0)+se) else 0

def schedule(feats,name,start,end,risk=.2):
 out=[]
 for e in feats:
  t=e['source']
  if not start<=t<end:continue
  model=e['models']['CP_INT' if name=='CP_INV' else name];vol=e['annual_vol'];F=e['funding_rate'];valid=model['mu'] is not None and vol is not None and vol>1e-12 and F is not None;s=signal(model['mu'],model['se'],F)*(-1 if name=='CP_INV' else 1) if valid else 0
  out.append({'source':t,'weight':s*min(1,risk/vol) if valid else 0.,'detail':{'model':model,'r':e['r'],'f':e['f'],'A':e['A'],'gap':e['gap'],'annual_vol':vol,'funding_rate':F,'funding_time':e['funding_time'],'valid':valid,'sign':s}})
 return out

def run(out):
 out=Path(out);m=Market();prem,spot=inputs();f=predict(features(m,prem,spot));write(out/'features.json.gz',f);results={};summary={};unc={};forecast={}
 for p,(start,end) in PERIODS.items():
  paired=[e for e in f if start<=e['source']<end and e['truth'] is not None and e['truth_end']<=end and all(e['models'][k]['mu'] is not None for k in MODELS)];forecast[p]={}
  for name in MODELS:
   y=np.array([e['truth'] for e in paired]);mu=np.array([e['models'][name]['mu'] for e in paired]);beta=np.array([e['models'][name]['beta'] for e in paired]);forecast[p][name]={'n':len(y),'mse':float(np.mean((y-mu)**2)),'sign_accuracy':float(np.mean(np.sign(y)==np.sign(mu))),'coefficient_median':np.median(beta,axis=0).tolist(),'coefficient_positive_fraction':np.mean(beta>0,axis=0).tolist()}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    risk=c.get('risk',.2);plan=schedule(f,name,start,end,risk);write(out/f'{p}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=simulate(m,name,start,end,plan,**c);x.update(period=p,scenario=scenario,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_session_study.py').read_bytes()),premium_sha256=PREMIUM_SHA);write(out/f'{p}-{name}-{scenario}.json.gz',x);results[p,name,scenario]=x;summary[f'{p}-{name}-{scenario}']=x['metrics']
    if scenario=='base':print(json.dumps({'period':p,'name':name,**{k:x['metrics'][k] for k in ('return_pct','dd_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True)
  old=read(ROOT/f'runs/search-1458/{p}-E_SPOT.json.gz')
  for name in IDS:
   r=np.array(results[p,name,'base']['daily_returns']);unc[p+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl,other in [('E_SPOT',old),('CP_ADD',results[p,'CP_ADD','base']),('CP_FLOW',results[p,'CP_FLOW','base'])]:unc[p+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(other['daily_returns']),n) for n in (7,14,28)]
 a=results['main','CP_INT','base']['metrics'];b=results['recent','CP_INT','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['dd_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['dd_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe']>=.8,'years':sum(v>0 for v in a['annual'].values())>=3,'trades':a['round_trips']>=100,'margin':a['margin_breach_bars']==b['margin_breach_bars']==0}
 for c in ('base','cost_x2','delay60','delay240'):g[c]=all(results[p,'CP_INT',c]['metrics']['net']>0 for p in PERIODS)
 for ctrl in ('CP_ADD','CP_FLOW'):
  g['mse_vs_'+ctrl]=all(forecast[p]['CP_INT']['mse']<forecast[p][ctrl]['mse'] for p in PERIODS);g['net_vs_'+ctrl]=all(results[p,'CP_INT','base']['metrics']['net']>results[p,ctrl,'base']['metrics']['net'] for p in PERIODS)
 info={p:{'decisions':len(z:=[e for e in f if start<=e['source']<end]),'invalid_features':sum(not e['feature_valid'] for e in z),'missing_funding':sum(e['funding_rate'] is None for e in z),'missing_risk':sum(e['annual_vol'] is None for e in z)} for p,(start,end) in PERIODS.items()}
 for n,v in [('summary',summary),('uncertainty',unc),('forecast-summary',forecast),('input-incidence',info),('selection',{'primary':'CP_INT','passed':all(g.values()),'checks':g,'comparisons_not_eligible':list(IDS[1:]),'scope':'BTC-only development; hypothesis about lagged information, not replication of pooled contemporaneous price impact; premium vintage/execution assumptions remain'})]:write(out/f'{n}.json',v)
 print(json.dumps(g),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
