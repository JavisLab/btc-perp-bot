"""Raw BTC labels/features + independent normal-equation OI model verification."""
import argparse,csv,gzip,io,json,math,zipfile
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,sha
ROOT=Path(__file__).resolve().parents[1];STEP=300000

def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def run(out):
 out=Path(out);raw=[];funds=[]
 for name in ('perp','funding'):
  for p in sorted((ROOT/f'data/archive-1448/{name}').glob('????-??.zip'))+sorted((ROOT/f'data/archive-1458/BTCUSDT/{name}').glob('????-??.zip')):
   with zipfile.ZipFile(p) as z:
    for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
     if not r[0].isdigit():continue
     if name=='perp':raw.append([int(r[0]),*map(float,r[1:5])])
     else:funds.append((int(r[0])//HOUR*HOUR,int(r[0]),float(r[2])))
 arr=np.array(raw);price=arr[:,4];idx={int(r[0])+HOUR:i for i,r in enumerate(arr)};returns=np.diff(np.log(price));em=[];last=price[0]
 for v in price:last=(2*v+167*last)/169;em.append(last)
 oip=ROOT/'data/oi-inputs-20261002/BTCUSDT.jsonl.gz';assert sha(oip.read_bytes())=='76acc5bba07b27e50f2c780eb58e557e1c003c35a7cf2cacc69024c19c695b0f'
 oi=[json.loads(s) for s in gzip.decompress(oip.read_bytes()).splitlines()];oiidx={r['observation_complete_assumed_ms']:i for i,r in enumerate(oi)};bad=np.r_[0,np.cumsum([not r['oi_usable'] for r in oi])];feature_count=prediction_count=model_count=0;worst=0.
 for lag in (60,0,240,1440):
  f=read(out/f'features-a{lag}.json.gz');train=read(out/f'training-a{lag}.json.gz');pred=read(out/f'predictions-a{lag}.json.gz');tx=np.array([r['source'] for r in f]);xx=np.array([r['x'] for r in f]);yy=np.array([r['y'] for r in f]);fi={r['source']:i for i,r in enumerate(f)}
  for record in f:
   t=record['source'];i=idx[t];endpoint=t-lag*60000;j=oiidx[endpoint];k=oiidx[endpoint-7*DAY]
   assert j-k==2016 and bad[j+1]==bad[k] and record['oi_end']==endpoint
   oi_values=[float(oi[oiidx[endpoint-h*HOUR]]['oi_qty']) for h in (0,4,24,168)];assert oi_values==record['oi_values']
   r=[math.log(price[i]/price[i-n]) for n in (4,24,168)];f24=math.fsum(v for bucket,rt,v in funds if t-DAY<=bucket<t and rt<t)
   want=r+[float(returns[i-24:i].std(ddof=1)),float(returns[i-168:i].std(ddof=1)),math.log(price[i]/em[i]),f24,float((arr[i-23:i+1,2].max()-arr[i-23:i+1,3].min())/price[i])]
   ch=[math.log(oi_values[0]/q) for q in oi_values[1:]];want+=ch+[a*b for a,b in zip(ch,r)]
   delta=max(abs(a-b) for a,b in zip(record['x'],want));worst=max(worst,delta);assert delta<1e-10
   assert record['label_complete']==t+DAY and abs(record['y']-math.log(price[i+24]/price[i]))<1e-12
   feature_count+=1
  reconstructed={}
  for tr in train:
   ids=np.flatnonzero((tx>=tr['fit']-365*DAY)&(tx<=tr['fit']-26*HOUR));assert ids.tolist()==tr['indices'];assert (len(ids)<500)==tr['skipped']
   if tr['skipped']:continue
   assert max(f[i]['label_complete'] for i in ids)<=tr['fit']-2*HOUR
   for name,n in [('P_RIDGE',8),('OI_RIDGE',14)]:
    X=xx[ids,:n];center=X.mean(axis=0);scale=X.std(axis=0);scale[scale==0]=1;Z=(X-center)/scale;zmean=Z.mean(axis=0);zc=Z-zmean;yc=yy[ids]-yy[ids].mean();coef=np.linalg.solve(zc.T@zc+10*np.eye(n),zc.T@yc);intercept=float(yy[ids].mean()-zmean@coef)
    expected=tr['models'][name];delta=max(float(np.max(abs(coef-np.array(expected['coef'])))),abs(intercept-expected['intercept']));worst=max(worst,delta);assert delta<1e-10
    reconstructed[(tr['fit'],name)]=(coef,intercept,center,scale);model_count+=1
  for r in pred:
   i=fi[r['source']];assert r['y']==f[i]['y'] and r['label_complete']==r['source']+DAY
   for name in ('P_RIDGE','OI_RIDGE'):
    coef,inter,center,scale=reconstructed[(r['fit'],name)];y=float(np.clip((xx[i,:len(coef)]-center)/scale@coef+inter,-.1,.1));delta=abs(y-r[name]);worst=max(worst,delta);assert delta<1e-10
   prediction_count+=1
 result={'features':feature_count,'independent_normal_equation_models':model_count,'paired_predictions':prediction_count,'max_error':worst,'training_label_purge_checked':True,'raw_price_features_and_labels':True,'oi_verified_input_hash_and_exact_2017_row_windows':True,'scope':'forecast comparison only; no account PnL or execution claim'}
 (out/'verification.json').write_bytes(canonical(result));print(json.dumps(result),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
