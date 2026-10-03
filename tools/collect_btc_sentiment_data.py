"""Normalize already downloaded public Alternative.me BTC index; no network or performance."""
import json,datetime as dt
from pathlib import Path
from btc_perp_bot.research.archive import DAY,ms,canonical,sha
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/btc-sentiment-20261003';RAW_SHA='67b25d3d98f5a46c90868cdc9f3119dc24d264989fa8347d35d9cbdaf174f4ff'
def run():
 web=ROOT/'data/btc-web-20261003';raw=(web/'q131-fng-history.json').read_bytes();assert sha(raw)==RAW_SHA;j=json.loads(raw);assert j['metadata']['error'] is None;indexed={}
 for r in j['data']:
  t=int(r['timestamp'])*1000;v=int(r['value']);assert str(v)==r['value'] and 0<=v<=100 and t%DAY==0 and t not in indexed;indexed[t]=r
 days=[]
 for t in range(ms('2020-01-01'),ms('2026-09-01'),DAY):
  r=indexed.get(t);days.append({'day':t,'date':dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date().isoformat(),'value':int(r['value']) if r else None,'classification':r['value_classification'] if r else None,'raw_timestamp_seconds':int(r['timestamp']) if r else None,'valid':r is not None,'base_assumed_available':t+2*DAY})
 data={'provider':'Alternative.me','source_url':'https://api.alternative.me/fng/?limit=0&format=json','definition_url':'https://alternative.me/crypto/fear-and-greed-index/','retrieved_utc':'2026-10-03T09:02:43Z','raw_sha256':RAW_SHA,'scope':'BTC-only composite, not pure sentiment or first-vintage observations; provider values unchanged, daily masks/availability are our transformations','days':days};OUT.mkdir(exist_ok=True);(OUT/'daily.json').write_bytes(canonical(data));(OUT/'raw-fng-history.json').write_bytes(raw)
 for a,b in [('q130-fng-api-sample.json','raw-fng-latest10.json'),('q131-fetch-meta.json','history-fetch-meta.json'),('q130-fetch-meta.json','sample-and-definition-fetch-meta.json'),('q130-fng-official.txt','provider-definition.txt'),('q131-fng-quality.json','prestudy-quality.json')]: (OUT/b).write_bytes((web/a).read_bytes())
 report={'rows':len(days),'valid_rows':sum(r['valid'] for r in days),'missing_dates':[r['date'] for r in days if not r['valid']],'raw_rows':len(indexed),'normalized_sha256':sha((OUT/'daily.json').read_bytes()),'no_prices_models_or_pnl_computed':True};(OUT/'prepare-audit.json').write_bytes(canonical(report));print(json.dumps(report))
if __name__=='__main__':run()
