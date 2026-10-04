"""Independent Decimal reparse of the new BTC dated-futures raw archives only."""
import argparse,csv,datetime as dt,gzip,hashlib,io,json,xml.etree.ElementTree as ET,zipfile
from decimal import Decimal,getcontext
from pathlib import Path
getcontext().prec=60;ROOT=Path(__file__).resolve().parents[1];H=3600000;D=Decimal

def audit(out):
 out=Path(out);p=out/'contracts.json.gz';data=json.loads(gzip.decompress(p.read_bytes()));a=json.loads((out/'prepare-audit.json').read_text());raw={};invalid=[];count=0
 for s in a['sources']:
  path=ROOT/s['path'];b=path.read_bytes();assert hashlib.sha256(b).hexdigest()==s['sha256']==path.with_suffix('.CHECKSUM').read_text().split()[0]
  with zipfile.ZipFile(io.BytesIO(b)) as z:
   assert len(z.namelist())==1;rows=[r for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())) if r and r[0].isdigit()]
  assert s['rows']==len(rows);bad=0
  for r in rows:
   t=int(r[0]);key=s['symbol'],t;assert key not in raw;assert dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).strftime('%Y-%m')==s['month'];assert '2020-01'<=s['month']<='2026-08';o,h,l,c,v,base,n,bv,bb=[D(r[j]) for j in (1,2,3,4,5,7,8,9,10)];ok=len(r)==12 and t%H==0 and int(r[6])==t+H-1 and all(x.is_finite() for x in (o,h,l,c,v,base,n,bv,bb)) and 0<l<=o<=h and l<=c<=h and v>0 and base>0 and n>0 and n==int(n) and 0<=bv<=v and 0<=bb<=base;raw[key]={'raw':r,'valid':ok};bad+=not ok;count+=1
   if not ok:invalid.append([s['symbol'],t])
  assert s['invalid']==bad
 total=valid=0
 for contract,metadata in zip(data['contracts'],a['contracts']):
  sym=contract['symbol'];assert sym==metadata['symbol'];expiry=dt.datetime.strptime(sym[-6:],'%y%m%d').replace(tzinfo=dt.timezone.utc);assert expiry.weekday()==4 and int(expiry.timestamp()*1000)==contract['expiry_date_proxy']==metadata['expiry_date_proxy'];expected=[r for (s,t),r in sorted(raw.items()) if s==sym];assert expected==contract['rows'];first=min((int(r['raw'][0]) for r in expected if r['valid']),default=None);assert contract['first_valid_open']==first
  b=(ROOT/metadata['listing']).read_bytes();assert hashlib.sha256(b).hexdigest()==metadata['listing_sha256'];tree=ET.fromstring(b);assert tree.find('{*}IsTruncated').text=='false';expectedmonths=sorted(e.text[-11:-4] for e in tree.findall('{*}Contents/{*}Key') if e.text.endswith('.zip') and '2020-01'<=e.text[-11:-4]<=min('2026-08',expiry.strftime('%Y-%m')));actualmonths=sorted(s['month'] for s in a['sources'] if s['symbol']==sym);assert expectedmonths==actualmonths;total+=len(expected);valid+=sum(r['valid'] for r in expected)
 canonical=json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=hashlib.sha256(canonical).hexdigest();assert digest==a['canonical_sha256'] and total==count==a['hours'] and valid==a['valid_hours'] and len(a['sources'])==a['archives'];assert hashlib.sha256(p.read_bytes()).hexdigest()==a['gzip_sha256'];report={'canonical_sha256':digest,'archives':a['archives'],'contracts':len(data['contracts']),'hours':total,'valid_hours':valid,'invalid_hours':len(invalid),'raw_rows_exact':True,'listing_completeness_for_frozen_current_archive':True,'initial_publication_vintage_proven':False,'scope':'Independent Decimal raw reconstruction, exact clocks/positive-volume/maturity-month/current-list completeness, no account performance'};(out/'independent-audit.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':')));print(report,flush=True);return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);audit(p.parse_args().out)
