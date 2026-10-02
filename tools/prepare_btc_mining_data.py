"""Normalize public BTC mining data after separate count/header consistency checks."""
import csv,datetime as dt,hashlib,json,math
from decimal import Decimal
from pathlib import Path
from btc_perp_bot.research.archive import canonical,sha,DAY,ms
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/btc-mining-20261002'
def run():
 charts={name:{int(e['x'])*1000:float(e['y']) for e in json.loads((DATA/(name+'.json')).read_text())['values']} for name in ('hash-rate','difficulty','n-transactions','n-transactions-per-block')};sources=[DATA/(name+'.json') for name in charts];cm={ms(e['time']):e for e in csv.DictReader((DATA/'btc-community.csv').open())};sources.append(DATA/'btc-community.csv');patch={}
 for date in ('2025-11-13','2025-11-14','2025-11-15'):
  p=DATA/f'blocks-day-{date}.json';sources.append(p);r=json.loads(p.read_text());r.sort(key=lambda x:x['height']);day=ms(date);heights=[e['height'] for e in r];assert heights==list(range(min(heights),max(heights)+1)) and min(heights)//2016==max(heights)//2016;assert all(day<=e['time']*1000<day+DAY for e in r);targets=[]
  for e in (r[0],r[-1]):
   hp=DATA/f'header-{e["height"]}.txt';sources.append(hp);b=bytes.fromhex(hp.read_text().strip());assert len(b)==80 and hashlib.sha256(hashlib.sha256(b).digest()).digest()[::-1].hex()==e['hash'];assert int.from_bytes(b[68:72],'little')==e['time'];bits=int.from_bytes(b[72:76],'little');targets.append((bits & 0xffffff)*2**(8*((bits>>24)-3)))
  assert targets[0]==targets[1];difficulty=Decimal(0xffff*2**(8*(0x1d-3)))/Decimal(targets[0]);h=Decimal(len(r))*difficulty*2**32/Decimal(86400*10**12);assert int(cm[day]['BlkCnt'])==len(r) and abs(Decimal(cm[day]['HashRate'])/h-1)<Decimal('1e-7');patch[day]={'hashrate':float(h),'difficulty':float(difficulty),'blocks':len(r)}
 rows=[];formula_error=0.;normaldates=set(charts['hash-rate']);assert all(set(c)==normaldates for c in charts.values());first,last=min(normaldates),max(normaldates)
 for day in range(first,last+DAY,DAY):
  if day in normaldates:
   h=charts['hash-rate'][day];difficulty=charts['difficulty'][day];ratio=charts['n-transactions'][day]/charts['n-transactions-per-block'][day];n=round(ratio);assert abs(ratio-n)<1e-8 and n>0;derived=n*difficulty*2**32/(86400*10**12);err=abs(derived/h-1);assert err<1e-12;formula_error=max(formula_error,err);kind='blockchain-chart'
  else:
   assert day in patch;x=patch[day];h,difficulty,n=x['hashrate'],x['difficulty'],x['blocks'];kind='raw-block-header-gap-reconstruction'
  alt=float(cm[day]['HashRate']) if day in cm and cm[day]['HashRate'] else h;assert h>0 and alt>0
  rows.append({'day':day,'source':day+2*DAY,'hashrate':h,'hashrate_provider_cm':alt,'difficulty':difficulty,'blocks':n,'provenance':kind,'cm_present':day in cm and bool(cm[day]['HashRate'])})
 manifest={p.name:sha(p.read_bytes()) for p in sources};audit={'rows':len(rows),'start':dt.datetime.fromtimestamp(first/1000,dt.timezone.utc).isoformat(),'end':dt.datetime.fromtimestamp(last/1000,dt.timezone.utc).isoformat(),'patch_days':len(patch),'patch_blocks':sum(e['blocks'] for e in patch.values()),'hash_verified_headers':6,'formula_relative_error':formula_error,'rows_sha256':sha(canonical(rows)),'source_files':manifest,'timestamp_assumption':'d+2UTC day00 availability, not complete first-publication/vintage proof; additional7day sensitivity preregistered'}
 for n,e in [('prepared.json',rows),('prepare-audit.json',audit)]:
  p=DATA/n;b=canonical(e)
  if p.exists():assert p.read_bytes()==b
  else:p.write_bytes(b)
 print(json.dumps(audit))
if __name__=='__main__':run()
