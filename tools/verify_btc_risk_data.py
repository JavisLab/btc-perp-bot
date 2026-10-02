"""Reconstruct RV from original BTC ZIP closes, independently of collector."""
import csv,gzip,io,json,math,zipfile
from pathlib import Path
from btc_perp_bot.research.archive import sha,canonical,DAY,HOUR,ms
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/btc-rv-20261002';STEP=300000

def rows(p):
 with zipfile.ZipFile(p) as z:
  for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
   if r[0].isdigit():yield r

def run():
 audit=json.loads((DATA/'audit.json').read_text());resolution=json.loads((ROOT/'data/structure-1471/resolution.json').read_text());price={};zero={}
 for rec in audit['new_files']+resolution['files']:
  base=DATA/'raw' if rec in audit['new_files'] else ROOT/'data/structure-1471/raw';p=base/(rec['month']+'.zip');assert sha(p.read_bytes())==rec['sha256']
  for r in rows(p):t=int(r[0]);assert t not in price;price[t]=float(r[4]);zero[t]=float(r[5])==0
 for fix in resolution['repairs']:
  t=ms(fix['hour'])
  for r in rows(ROOT/fix['source']):
   if t<=int(r[0])<t+HOUR:price[int(r[0])]=float(r[4]);zero[int(r[0])]=float(r[5])==0
 assert sorted(price)==list(range(ms('2020-01-01'),ms('2026-09-01'),STEP));daily=json.loads(gzip.decompress((DATA/'daily-rv.json.gz').read_bytes()));assert sha(canonical(daily))==audit['daily_sha256'];worst=0.
 for e in daily:
  t=e['day'];valid=t-STEP in price and t not in audit['invalid_close_days'];assert valid==e['valid'];assert sum(zero[x] for x in range(t,t+DAY,STEP))==e['zero_bars']
  if not valid:assert e['rv'] is None;continue
  changes=[math.log(price[x])-math.log(price[x-STEP]) for x in range(t,t+DAY,STEP)];up=sum(x*x for x in changes if x>0);down=sum(x*x for x in changes if x<0)
  for k,v in [('rv',up+down),('up',up),('down',down)]:err=abs(v-e[k]);worst=max(worst,err);assert err<1e-12,(e['day'],k,err)
 result={'new_zip_files':len(audit['new_files']),'raw_price_rows':len(price),'daily_rows':len(daily),'max_rv_error':worst,'old_archives_reused':len(resolution['files']),'interpolation':False};(DATA/'verification.json').write_bytes(canonical(result));print(json.dumps(result))
if __name__=='__main__':run()
