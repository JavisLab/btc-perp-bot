"""Frozen continuous OI forecast comparison; NOT a backtest or cash account."""
import argparse,bisect,gzip,json,math
from pathlib import Path
import numpy as np
from sklearn.linear_model import Ridge
from btc_perp_bot.research.archive import DAY,HOUR,ms,sha,utc,canonical
from btc_oi_study import load_oi,write,STEP
ROOT=Path(__file__).resolve().parents[1]
PERIODS={'main':(ms('2023-01-01'),ms('2026-01-01')),'recent':(ms('2026-01-01'),ms('2026-09-01'))}

def features(availability):
 payload=json.loads(gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes()))['series']['BTCUSDT'];rows=payload['perp'];arr=np.array(rows);times=arr[:,0].astype(np.int64)+HOUR;c=arr[:,4];logs=np.log(c);ret=np.r_[np.nan,np.diff(logs)];ema=[];last=c[0]
 for v in c:last=2/169*v+167/169*last;ema.append(last)
 fs=payload['funding'];ft=[r[0] for r in fs];first,oi=load_oi();bad=np.r_[0,np.cumsum(~np.isfinite(oi))];out=[]
 for i,t in enumerate(times):
  t=int(t)
  if t<ms('2022-01-01') or i<168 or t%(6*HOUR) or i+24>=len(c):continue
  assert times[i+24]==t+DAY
  endpoint=t-availability*60000;j=(endpoint-first)//STEP
  if endpoint<first or (endpoint-first)%STEP or j<2016 or j>=len(oi) or bad[j+1]!=bad[j-2016]:continue
  r=[float(logs[i]-logs[i-n]) for n in (4,24,168)];f=math.fsum(row[2] for row in fs[bisect.bisect_left(ft,t-DAY):bisect.bisect_left(ft,t)] if row[3]<t)
  x=r+[float(ret[i-23:i+1].std(ddof=1)),float(ret[i-167:i+1].std(ddof=1)),float(math.log(c[i]/ema[i])),f,float((arr[i-23:i+1,2].max()-arr[i-23:i+1,3].min())/c[i])]
  changes=[float(math.log(oi[j]/oi[j-n])) for n in (48,288,2016)];x+=changes+[a*b for a,b in zip(changes,r)]
  out.append({'source':t,'oi_end':endpoint,'oi_values':[float(oi[j-n]) for n in (0,48,288,2016)],'x':x,'y':float(logs[i+24]-logs[i]),'label_complete':t+DAY})
 return out

def uncertainty(records,length):
 byday={}
 for r in records:
  d=r['source']//DAY;byday.setdefault(d,[]).append((r['y']-r['P_RIDGE'])**2-(r['y']-r['OI_RIDGE'])**2)
 days=list(range(min(byday),max(byday)+1));sums=np.array([sum(byday.get(d,[])) for d in days]);counts=np.array([len(byday.get(d,[])) for d in days]);rng=np.random.default_rng(1488+length);idx=(rng.integers(0,len(days),(2000,math.ceil(len(days)/length),1))+np.arange(length))%len(days);idx=idx.reshape(2000,-1)[:,:len(days)];n=counts[idx].sum(axis=1);v=sums[idx].sum(axis=1)/np.maximum(n,1)
 return {'block_days':length,'mse_gain':float(sums.sum()/counts.sum()),'ci95':np.quantile(v,[.025,.975]).tolist(),'replicates':2000}

def run(out):
 out=Path(out);summary={};gates={}
 for availability in (60,0,240,1440):
  f=features(availability);write(out/f'features-a{availability}.json.gz',f);t=np.array([r['source'] for r in f]);x=np.array([r['x'] for r in f]);y=np.array([r['y'] for r in f]);trainings=[];pred=[];previous=None;models=None
  for i,record in enumerate(f):
   source=record['source']
   if source<PERIODS['main'][0]:continue
   date=utc(source);quarter=date[:4]+'Q'+str((int(date[5:7])-1)//3+1)
   if quarter!=previous:
    previous=quarter;mask=(t>=source-365*DAY)&(t<=source-26*HOUR);ix=np.flatnonzero(mask);models={};train={'fit':source,'quarter':quarter,'count':len(ix),'indices':ix.tolist(),'last_label':int(t[ix[-1]]+DAY) if len(ix) else None,'skipped':len(ix)<500,'models':{}}
    if len(ix)>=500:
     assert train['last_label']<=source-2*HOUR
     for name,n in [('P_RIDGE',8),('OI_RIDGE',14)]:
      xx=x[ix,:n];center=xx.mean(axis=0);scale=xx.std(axis=0);scale[scale==0]=1;z=(xx-center)/scale;model=Ridge(alpha=10,fit_intercept=True);model.fit(z,y[ix]);models[name]=(center,scale,model)
      train['models'][name]={'center':center.tolist(),'scale':scale.tolist(),'coef':model.coef_.tolist(),'intercept':float(model.intercept_)}
    trainings.append(train)
   if not models:continue
   if not any(a<=source<b-DAY for a,b in PERIODS.values()):continue
   pr={'source':source,'label_complete':record['label_complete'],'fit':trainings[-1]['fit'],'y':record['y']}
   for name,(center,scale,model) in models.items():pr[name]=float(np.clip(model.predict(((x[i,:len(center)]-center)/scale)[None,:])[0],-.1,.1))
   pred.append(pr)
  write(out/f'training-a{availability}.json.gz',trainings);write(out/f'predictions-a{availability}.json.gz',pred)
  for period,(start,end) in PERIODS.items():
   rr=[r for r in pred if start<=r['source']<end-DAY];yy=np.array([r['y'] for r in rr]);s={'count':len(rr),'availability_minutes':availability,'period':period,'models':{}}
   for name in ('P_RIDGE','OI_RIDGE'):
    pp=np.array([r[name] for r in rr]);s['models'][name]={'mse':float(np.mean((yy-pp)**2)),'correlation':float(np.corrcoef(yy,pp)[0,1]),'sign_accuracy_pct':float(np.mean(np.sign(pp)==np.sign(yy))*100)}
   s['uncertainty']=[uncertainty(rr,n) for n in (7,14,28)];summary[f'{period}-a{availability}']=s
   print(json.dumps(s),flush=True)
 for period in PERIODS:
  s=summary[period+'-a60'];stress=summary[period+'-a240'];g={'samples':s['count']>=500,'mse':s['models']['OI_RIDGE']['mse']<s['models']['P_RIDGE']['mse'],'correlation':s['models']['OI_RIDGE']['correlation']>0,'ci14':s['uncertainty'][1]['ci95'][0]>0,'delay240':stress['models']['OI_RIDGE']['mse']<stress['models']['P_RIDGE']['mse']};gates[period]={'checks':g,'passed':all(g.values())}
 write(out/'summary.json',summary);write(out/'selection.json',gates);print(json.dumps(gates),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
