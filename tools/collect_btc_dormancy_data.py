"""Freeze only already downloaded public BTC daily aggregates; no network or wallet queries."""
import csv,datetime as dt,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'data/btc-web-20261003';RAW=SRC/'q118-aggregate-probes';OUT=ROOT/'data/btc-dormancy-20261003';DAY=86400000
SERIES={'cdd':('obm_cdd_btcxdays_daily','BTC-days','276b4d34599c9c44bba10a79bab4f22c97d09eeee036414e1e3e4828c6ba28af'),'spent':('obm_spent_value_btc_daily','BTC','81c812d6778d5d857c77c6bca7504f6a840aebf93621853ca4474dbfd6afc0c3'),'dormancy':('obm_dormancy_days_daily','days','fca7fc078523d6c9d886e2dc6aed414aeb1b1cf00529562f8aeda6b892f45e98'),'blocks':('obm_block_count_daily','blocks','9abcc302799fede71c6b41ae070e32f8cf46294176774c65549fea5551329350'),'transactions':('obm_tx_count_daily','transactions','93de2c8a8b2f64484d53d7dae018b8808974295db9fe2fe1c0143049806e9ae7')}
def sha(b):return hashlib.sha256(b).hexdigest()
def ms(s):return int(dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def main():
 series={};manifest={'asset':'BTC','source_commit':'ab99e2609a257dfc0e1e4c7ec21708930909ec19','source_commit_time':'2026-10-03T02:52:31Z','license':'CC BY 4.0; Diego R. Llanos, Open Bitcoin Metrics','series':{},'no_new_network_fetch':True}
 for key,(sid,unit,digest) in SERIES.items():
  p=RAW/(sid+'.csv');b=p.read_bytes();assert sha(b)==digest;rows=list(csv.DictReader(b.decode().splitlines()));d={}
  for r in rows:
   assert set(r)=={'date','series_id','value','unit','frequency','release_version'} and r['series_id']==sid and r['unit']==unit and r['frequency']=='daily' and r['release_version']=='OBM v0.1.0';t=ms(r['date']);assert t not in d;d[t]=r['value']
  assert sorted(d)==list(range(min(d),max(d)+DAY,DAY));series[key]=d
  manifest['series'][key]={'path':str(p.relative_to(ROOT)),'sha256':digest,'unit':unit,'rows':len(rows),'first':rows[0]['date'],'last':rows[-1]['date']}
 p=ROOT/'data/btc-mining-20261002/n-transactions.json';b=p.read_bytes();assert sha(b)=='50756100c7848fe2a7715d39705d7de55338ffc4a9aa4db18a1e990ef7b93adb';x=json.loads(b);assert x['status']=='ok' and x['period']=='day' and x['unit']=='Transactions';tx={}
 for r in x['values']:
  t=r['x']*1000;assert t%DAY==0 and t not in tx and math.isfinite(r['y']) and r['y']>=0 and r['y']==int(r['y']);tx[t]=r['y']
 manifest['independent_transaction_counts']={'path':str(p.relative_to(ROOT)),'sha256':sha(b),'refetch':False,'observations':len(tx)}
 manifest['archive']={'path':str((RAW/'open_bitcoin_metrics-v0.1.0.tar.gz').relative_to(ROOT)),'sha256':'d5caa010dd0dfc08b6a428fe733b15265b5a159ebfe8a38c24ad6c799641a26c','md5':'99f21fe7ad4c0865949b49ecab4b4ca9','source':'https://doi.org/10.5281/zenodo.21156871'}
 start,end=ms('2020-01-01'),ms('2026-09-01');days=[]
 for t in range(start,end,DAY):
  r={'day':t,'date':dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat(),**{k:v.get(t) for k,v in series.items()},'independent_transaction_count':None if t not in tx else str(int(tx[t]))};why=[]
  if any(r[k] is None for k in SERIES):why.append('missing_obm')
  else:
   v={k:float(r[k]) for k in SERIES}
   if not all(math.isfinite(z) and z>=0 for z in v.values()):why.append('nonfinite_or_negative')
   elif not all(v[k]>0 for k in ('spent','blocks','transactions')):why.append('zero_denominator_or_activity')
   elif v['blocks']!=int(v['blocks']) or v['transactions']!=int(v['transactions']):why.append('noninteger_count')
   elif not(0<=v['dormancy']<=(t-ms('2009-01-03'))/DAY+1) or abs(v['cdd']/v['spent']-v['dormancy'])>2e-12:why.append('age_ratio_or_bound')
  if t not in tx:why.append('independent_count_missing')
  elif r['transactions'] is None or float(r['transactions'])!=tx[t]:why.append('independent_count_mismatch')
  r.update(valid=not why,invalid_reasons=why,base_assumed_available=t+6*DAY);days.append(r)
 normalized={'asset':'BTC','start':start,'end_exclusive':end,'base_assumed_lag_days':6,'first_publication':'2026-07-03','scope':'Current-vintage public daily aggregates, pre-publication historical reconstruction, not original release backtest or chain revalidation; no individual address/transaction data. Raw spent cohort, not entity-adjusted selling.','days':days}
 write(OUT/'daily.json',normalized);manifest['normalized_sha256']=sha((OUT/'daily.json').read_bytes());manifest['valid_days']=sum(r['valid'] for r in days);manifest['invalid_days']=[{'date':r['date'],'reasons':r['invalid_reasons']} for r in days if not r['valid']];write(OUT/'archive-manifest.json',manifest);print(json.dumps({'sha256':manifest['normalized_sha256'],'days':len(days),'valid':manifest['valid_days'],'invalid':manifest['invalid_days']},indent=2))
if __name__=='__main__':main()
