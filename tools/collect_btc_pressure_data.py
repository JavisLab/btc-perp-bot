"""New pressure aggregates from already-frozen public BTC perp hourly candles only."""
import argparse,csv,io,math,zipfile
from pathlib import Path
from decimal import Decimal,getcontext
getcontext().prec=60
from btc_session_study import ROOT,DAY,HOUR,ms,sha,read,write
CF_SHA='30fc996715649844cb1dc224a88b60f07e6cf9e0e211722b44ec8579252190cf'
def aggregate(rr,old_valid):
 q=sum((Decimal(x['quote']) for x in rr),Decimal(0));b=sum((Decimal(x['buy_quote']) for x in rr),Decimal(0));signed=[2*Decimal(x['buy_quote'])-Decimal(x['quote']) for x in rr];net=sum(signed,Decimal(0));gross=sum((abs(s) for s in signed),Decimal(0))
 good=old_valid and len(rr)==24 and all(x['valid'] for x in rr) and q>0
 return {'valid':good,'quote':float(q),'buy_quote':float(b),'signed_quote':float(net),'absolute_quote':float(gross),'signed':float(net/q) if q>0 else None,'net':float(abs(net)/q) if q>0 else None,'gross':float(gross/q) if q>0 else None,'hours':rr}

def run(out):
 cp=ROOT/'data/btc-cashflow-20261003/daily.json';assert sha(cp.read_bytes())==CF_SHA;cf=read(cp);mask={r['day']:r['valid'] for r in cf['series']['perp']};hours={};sources=[];zero=[]
 for p in sorted((ROOT/'data/archive-1448/perp').glob('????-??.zip'))+sorted((ROOT/'data/archive-1458/BTCUSDT/perp').glob('????-??.zip')):
  b=p.read_bytes();h=sha(b);assert h==p.with_suffix('.CHECKSUM').read_text().split()[0];sources.append({'path':str(p.relative_to(ROOT)),'sha256':h})
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   assert len(z.namelist())==1
   for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
    if not r[0].isdigit():continue
    t=int(r[0]);end=int(r[6]);assert t<10**14 and t%HOUR==0 and t not in hours
    o,h,l,c,base,q,bb,bq,count=[float(r[j]) for j in (1,2,3,4,5,7,9,10,8)];good=all(math.isfinite(v) for v in (o,h,l,c,base,q,bb,bq,count)) and 0<l<=o<=h and l<=c<=h and base>0 and q>0 and 0<=bb<=base and 0<=bq<=q and count>=0 and count==int(count) and end==t+HOUR-1
    if base<=0:zero.append(t)
    hours[t]={'time':t,'end':end,'quote':r[7],'buy_quote':r[10],'base':r[5],'buy_base':r[9],'trades':r[8],'ohlc':r[1:5],'valid':good}
 rows=[]
 for d in range(ms('2020-01-01'),ms('2026-09-01'),DAY):
  wanted=list(range(d,d+DAY,HOUR));rr=[hours[t] for t in wanted if t in hours];e=aggregate(rr,mask[d]);e.update(day=d,end=d+DAY,prior_valid=mask[d],missing_hours=[t for t in wanted if t not in hours]);rows.append(e)
 payload={'rows':rows,'zero_execution_hours':zero,'scope':'BTCUSDT UM hourly taker quote aggregates; not VPIN; no performance'};write(Path(out)/'daily.json.gz',payload);report={'daily_sha256':sha(__import__('btc_session_study').canonical(payload)),'gzip_sha256':sha((Path(out)/'daily.json.gz').read_bytes()),'cf_sha256':CF_SHA,'sources':sources,'days':len(rows),'valid_days':sum(r['valid'] for r in rows),'invalid_days':[r['day'] for r in rows if not r['valid']],'hours':len(hours),'zero_execution_hours':zero};write(Path(out)/'prepare-audit.json',report);print({k:v for k,v in report.items() if k!='sources'},flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);run(p.parse_args().out)
