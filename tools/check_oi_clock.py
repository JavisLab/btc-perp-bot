"""Preregistered second-date OI clock check, not a profitability holdout."""
import concurrent.futures as cf
import csv
import datetime as dt
from decimal import Decimal as D
import hashlib
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/oi-availability-20261002/clock-confirmation'
DATES=('2026-09-10','2026-09-20')


def get(url,path):
    if not path.exists():
        with urllib.request.urlopen(url,timeout=30) as r:
            assert r.status==200;body=r.read()
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
    return path.read_bytes()


def check(task):
    s,date=task;filename=f'{s}-metrics-{date}.zip';url=f'https://data.binance.vision/data/futures/um/daily/metrics/{s}/{filename}'
    body=get(url,OUT/filename);ck=get(url+'.CHECKSUM',OUT/(filename+'.CHECKSUM'));digest=hashlib.sha256(body).hexdigest();assert digest==ck.decode().split()[0]
    with zipfile.ZipFile(io.BytesIO(body)) as z:rows=list(csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode())))
    start=int(dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc).timestamp()*1000)
    params={'symbol':s,'period':'5m','startTime':start+300000,'endTime':start+86400000,'limit':500}
    apiurl='https://fapi.binance.com/futures/data/openInterestHist?'+urllib.parse.urlencode(params)
    api_body=get(apiurl,OUT/(s+'-'+date+'-api.json'));api={r['timestamp']:r for r in json.loads(api_body)}
    comparison=[];missing=[]
    for row in rows:
        t=int(dt.datetime.fromisoformat(row['create_time']).replace(tzinfo=dt.timezone.utc).timestamp()*1000);r=api.get(t+300000)
        if r is None:missing.append(t);continue
        comparison.append((D(row['sum_open_interest'])==D(r['sumOpenInterest']),D(row['sum_open_interest_value'])==D(r['sumOpenInterestValue'])))
    return {'symbol':s,'date':date,'archive_rows':len(rows),'api_rows':len(api),'compared':len(comparison),
        'exact_quantity':sum(x[0] for x in comparison),'exact_value':sum(x[1] for x in comparison),'missing_api_times':missing,
        'shift_ms':300000,'archive_url':url,'archive_sha256':digest,'api_url':apiurl,'api_sha256':hashlib.sha256(api_body).hexdigest()}


def main():
    with cf.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,[(s,d) for s in ('BTCUSDT','ETHUSDT') for d in DATES]))
    result={'checks':results,'all_four_dates_match_288_quantity_and_value':all(r['compared']==r['exact_quantity']==r['exact_value']==288 and not r['missing_api_times'] for r in results),
        'preregistered_shift_ms':300000,'not_proven':'Historical live publication time, historical-vintage corrections, field semantics of other columns, new OOS performance'}
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
