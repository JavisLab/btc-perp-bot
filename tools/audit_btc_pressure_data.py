"""Separate raw Decimal construction; imports no collector or strategy implementation."""
import argparse,csv,gzip,hashlib,io,json,zipfile
from decimal import Decimal,getcontext
from pathlib import Path
getcontext().prec=60
ROOT=Path(__file__).resolve().parents[1];DAY=86400000;H=3600000;D=Decimal

def audit(out):
 p=Path(out);payload=json.loads(gzip.decompress((p/'daily.json.gz').read_bytes()));a=json.loads((p/'prepare-audit.json').read_text());cfp=ROOT/'data/btc-cashflow-20261003/daily.json';assert hashlib.sha256(cfp.read_bytes()).hexdigest()==a['cf_sha256']=='30fc996715649844cb1dc224a88b60f07e6cf9e0e211722b44ec8579252190cf';cf=json.loads(cfp.read_text());prior={r['day']:r for r in cf['series']['perp']};raw={};archives=0;checks=0;worst=0.;zeros=[]
 for rec in a['sources']:
  q=ROOT/rec['path'];b=q.read_bytes();assert hashlib.sha256(b).hexdigest()==rec['sha256']==q.with_suffix('.CHECKSUM').read_text().split()[0];archives+=1
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   for row in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
    if not row[0].isdigit():continue
    t=int(row[0]);assert t not in raw;raw[t]=row
    if D(row[5])<=0:zeros.append(t)
 for e in payload['rows']:
  t=e['day'];wanted=list(range(t,t+DAY,H));rr=[raw[u] for u in wanted if u in raw];assert e['end']==t+DAY and e['missing_hours']==[u for u in wanted if u not in raw] and e['prior_valid']==prior[t]['valid'] and len(e['hours'])==len(rr);q=b=g=s=D(0);valid=[]
  for r,saved in zip(rr,e['hours']):
   start=int(r[0]);end=int(r[6]);o,high,low,c,base,quote,bbase,bquote,n=[D(r[j]) for j in (1,2,3,4,5,7,9,10,8)];good=all(x.is_finite() for x in (o,high,low,c,base,quote,bbase,bquote,n)) and 0<low<=o<=high and low<=c<=high and base>0 and quote>0 and 0<=bbase<=base and 0<=bquote<=quote and n>=0 and n==int(n) and end==start+H-1 and start%H==0;valid.append(good);assert saved=={'time':start,'end':end,'quote':r[7],'buy_quote':r[10],'base':r[5],'buy_base':r[9],'trades':r[8],'ohlc':r[1:5],'valid':good};q+=quote;b+=bquote;s+=2*bquote-quote;g+=abs(2*bquote-quote);checks+=1
  assert e['valid']==(len(rr)==24 and all(valid) and prior[t]['valid'] and q>0)
  assert q==D(prior[t]['quote']) and b==D(prior[t]['buy_quote'])
  expected={'quote':q,'buy_quote':b,'signed_quote':s,'absolute_quote':g,'signed':s/q if q>0 else None,'net':abs(s)/q if q>0 else None,'gross':g/q if q>0 else None}
  if q>0:assert 0<=abs(s)<=g<=q
  for k,v in expected.items():
   if v is None:assert e[k] is None;continue
   err=abs(float(v)-e[k])/max(1,abs(float(v)));worst=max(worst,err);assert err<3e-14,(t,k,err)
 assert len(payload['rows'])==a['days']==2435 and archives==80 and checks==58440 and sorted(zeros)==payload['zero_execution_hours'];assert a['valid_days']==sum(e['valid'] for e in payload['rows']);canonical=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode();assert hashlib.sha256(canonical).hexdigest()==a['daily_sha256'];report={'raw_archives':archives,'raw_hours':checks,'days':len(payload['rows']),'valid_days':a['valid_days'],'invalid_days':a['invalid_days'],'max_scaled_error':worst,'daily_sha256':a['daily_sha256'],'zero_execution_hours':zeros,'scope':'New G/N pressure fields rebuilt from raw Decimal; frozen CF masks retained; not account performance or unchanged full archive rerun'};(p/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')));print(report,flush=True);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);audit(p.parse_args().out)
