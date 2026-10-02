"""Independent raw premium/price clocks and uncentered normal-equation forecasts. No strategy imports."""
import csv,gzip,io,json,math,zipfile,bisect
from decimal import Decimal
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,sha,ms
ROOT=Path(__file__).resolve().parents[1];D=lambda x:Decimal(str(x));BLOCK=8*HOUR

def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def records(p):
 with zipfile.ZipFile(p) as z:
  for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
   if r[0].isdigit():yield r

def premium_audit():
 base=ROOT/'data/btc-premium-20261002';audit=read(base/'audit.json');repair=read(base/'repair-audit.json');data={};files=0
 for info in audit['source_files']:
  p=base/info['file'];assert sha(p.read_bytes())==info['sha256']==p.with_suffix('.zip.CHECKSUM').read_text().split()[0];files+=1
  for r in records(p):
   t=int(r[0]);assert t not in data;data[t]=[t,*map(float,r[1:5]),int(r[6]),int(r[8])]
 raw=json.dumps([data[t] for t in sorted(data)],separators=(',',':')).encode();assert sha(raw)==audit['raw_rows_sha256'];fixed=0;other=0
 for info in repair['daily_sources']:
  assert info['status']==200;p=base/'daily'/info['file'];assert sha(p.read_bytes())==info['sha256']==p.with_suffix('.zip.CHECKSUM').read_text().split()[0];files+=1
  for r in records(p):
   t=int(r[0]);v=[t,*map(float,r[1:5]),int(r[6]),int(r[8])]
   if (t not in data or data[t][6]==0) and v[6]>0:data[t]=v;fixed+=1
   elif t in data and data[t]!=v:other+=1
 raw=json.dumps([data[t] for t in sorted(data)],separators=(',',':')).encode();assert sha(raw)==repair['raw_rows_sha256']=='2da88be7e88ba42f540c3132aaf6ba79778ba2a24d57e27ac1c61ff82c6e76b2';assert raw==gzip.decompress((base/'rows-repaired.json.gz').read_bytes());missing=[t for t in range(audit['start'],audit['end_close']+1,HOUR) if t not in data];zero=[t for t in sorted(data) if data[t][6]==0];assert missing==repair['remaining_missing'] and zero==repair['remaining_zero'] and fixed==len(repair['patched']) and other==len(repair['other_conflicts'])
 for t,r in data.items():assert r[5]==t+HOUR-1 and r[3]<=min(r[1],r[4])<=max(r[1],r[4])<=r[2]
 return data,{'raw_zip_files':files,'rows':len(data),'daily_repairs':fixed,'missing_hours':len(missing),'zero_count_hours':len(zero),'other_conflicts':other,'sha256':sha(raw)}

def independent(out,hourly,funds):
 out=Path(out);premium,audit=premium_audit();spot={};spot_files=0
 for p in sorted((ROOT/'data/archive-1448/spot').glob('????-??.zip'))+sorted((ROOT/'data/archive-1458/BTCUSDT/spot').glob('????-??.zip')):
  assert sha(p.read_bytes())==p.with_suffix('.CHECKSUM').read_text().split()[0];spot_files+=1
  for r in records(p):
   t=int(r[0]);div=1000 if t>10**14 else 1;spot[t//div]=(D(r[4]),int(r[6])//div,D(r[5]))
 bad={ms(e['time']) for e in read(ROOT/'data/structure-1471/resolution.json')['unresolved'] if any(abs(v)>1e-3 for v in e['volume_errors'])}
 def close(t):
  a=hourly.get(t-HOUR);return a[0] if a and a[1]==t-1 and a[2]>0 else None
 first=(min(hourly)//BLOCK+1)*BLOCK;end=(max(hourly)//BLOCK+1)*BLOCK;times=list(range(first,end+1,BLOCK));fundlist=sorted((raw,rate) for rate,raw in funds.values());fts=[x[0] for x in fundlist];volumes={};feature=[]
 for t in times:
  a,b=close(t-BLOCK),close(t);hh=[(h,hourly.get(h)) for h in range(t-BLOCK,t,HOUR)];ok=a is not None and b is not None and all(v and v[1]==h+HOUR-1 and v[2]>0 and v[3]>0 and 0<=v[4]<=v[3] and h not in bad for h,v in hh);ret=math.log(float(b/a)) if ok else None;flow=float(2*sum(v[4] for _,v in hh)/sum(v[3] for _,v in hh)-1) if ok else None;pa=[];gap=[]
  for h in range(t-2*BLOCK,t-BLOCK,HOUR):
   v=premium.get(h);s=spot.get(h);p=hourly.get(h)
   if v and v[5]==h+HOUR-1 and v[6]>0:pa.append(D(v[4]))
   if s and s[0]>0 and s[1]==h+HOUR-1 and s[2]>0 and p and p[1]==h+HOUR-1 and p[0]>0 and p[2]>0:gap.append((p[0]-s[0])/p[0])
  A=float(abs(sum(pa)/8)) if len(pa)==8 else None;G=float(abs(sum(gap)/8)) if len(gap)==8 else None;day=t//DAY*DAY
  if day not in volumes:
   c=[close(day-j*DAY) for j in range(20,-1,-1)]
   if any(v is None for v in c):volumes[day]=None
   else:
    rr=[math.log(float(y/x)) for x,y in zip(c,c[1:])];mean=math.fsum(rr)/20;volumes[day]=math.sqrt(math.fsum((v-mean)**2 for v in rr)*365/19)
  j=bisect.bisect_left(fts,t-HOUR)-1;fund=fundlist[j] if j>=0 and t-fundlist[j][0]<=16*HOUR else None
  feature.append({'source':t,'r':ret,'f':flow,'A':A,'gap':G,'valid':bool(ok and A is not None and G is not None),'price_valid':bool(ok),'annual_vol':volumes[day],'funding_rate':float(fund[1]) if fund else None,'funding_time':fund[0] if fund else None})
 saved=read(out/'features.json.gz');assert len(saved)==len(feature);pred={};nfit=0;err=0.;cols={'CP_INT':(0,1,2,3,4),'CP_ADD':(0,1,2,3),'CP_FLOW':(0,1,2),'CP_PRICE':(0,1),'CP_GAP':(0,1,2,5,6)}
 X=np.array([[1,e['r'],e['f'],e['A'],e['A']*e['f'],e['gap'],e['gap']*e['f']] if e['valid'] else [np.nan]*7 for e in feature]);Y=np.array([e['r'] if e['r'] is not None else np.nan for e in feature]);valid=np.array([e['valid'] for e in feature])
 for i,(a,b) in enumerate(zip(feature,saved)):
  t=a['source'];assert t==b['source'] and a['valid']==b['feature_valid'] and a['price_valid']==b['price_valid'];assert b['state_start']==t-2*BLOCK and b['state_end']==b['flow_start']==t-BLOCK and b['risk_end']==t//DAY*DAY
  for key in ('r','f','A','gap','annual_vol','funding_rate','funding_time'):
   if a[key] is None:assert b[key] is None,(t,key)
   else:assert b[key] is not None and abs(a[key]-b[key])<1e-10,(t,key,a[key],b[key])
  lo=bisect.bisect_left(times,t-365*DAY);hi=bisect.bisect_right(times,t-2*BLOCK);ix=np.array([j for j in range(lo,hi) if valid[j] and np.isfinite(Y[j+1])],dtype=int);current={}
  for name,col in cols.items():
   target=b['models'][name]
   if t-times[0]<365*DAY or len(ix)<900 or not a['valid']:
    assert target['mu'] is None;current[name]=(None,None);continue
   x=X[ix][:,col];now=X[i,list(col)];y=Y[ix+1];sc=np.std(x,axis=0);sc[sc<1e-12]=1.;z=x/sc;now=now/sc;k=len(col)
   if np.linalg.matrix_rank(z)<k:assert target['mu'] is None;current[name]=(None,None);continue
   beta=np.linalg.solve(z.T@z,z.T@y);res=y-z@beta;s2=float(res@res)/(len(y)-k);mu=float(now@beta);se=math.sqrt(max(0.,s2*float(now@np.linalg.solve(z.T@z,now))));current[name]=(mu,se);nfit+=1;err=max(err,abs(mu-target['mu']),abs(se-target['se']));assert abs(mu-target['mu'])<1e-9 and abs(se-target['se'])<1e-9,(t,name,mu,target['mu']);assert target['training_n']==len(ix) and target['training_first']==times[ix[0]] and target['training_feature_end']==times[ix[-1]] and target['training_label_end']==times[ix[-1]+1]
  pred[t]=(a,current)
 plans={};decisions=0
 for p in sorted(out.glob('*-plan-risk*.json.gz')):
  period,name,_,riskstr=p.name.split('-',3);risk=float(riskstr.removeprefix('risk').removesuffix('.json.gz'));plan=read(p);plans[(period,name,risk)]=plan
  for e in plan:
   a,pr=pred[e['source']];mu,se=pr['CP_INT' if name=='CP_INV' else name];F=a['funding_rate'];v=a['annual_vol'];ok=mu is not None and F is not None and v is not None and v>1e-12;s=0
   if ok:s=1 if mu>math.log1p(.0013)+max(F,0)+se else -1 if mu<-(math.log1p(.0013)+max(-F,0)+se) else 0
   if name=='CP_INV':s=-s
   w=s*min(1,risk/v) if ok else 0.;assert abs(w-e['weight'])<1e-10 and e['detail']['sign']==s and bool(ok)==e['detail']['valid'];decisions+=1
 return plans,decisions,len(feature),{'premium':audit,'spot_zip_files':spot_files,'normal_equation_predictions':nfit,'prediction_maximum_error':err}
