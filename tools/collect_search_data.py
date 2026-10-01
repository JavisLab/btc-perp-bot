"""Extend public BTC archives and collect ETH; no account APIs or interpolation."""
import gzip
import io
import json
import sys
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from btc_perp_bot.research.archive import (
    DAY, HOUR, archive_url, canonical, fetch, months_until, ms, parse_csv, sha, utc, validate_series,
)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'data/archive-1458'
OUT = ROOT / 'data/search-1458'


def one(task):
    symbol, kind, date = task
    url = archive_url(kind, date).replace('BTCUSDT', symbol)
    directory = CACHE / symbol / kind
    directory.mkdir(parents=True, exist_ok=True)
    p, cp = directory / (date + '.zip'), directory / (date + '.CHECKSUM')
    try:
        if not cp.exists(): cp.write_bytes(fetch(url + '.CHECKSUM'))
        if not p.exists(): p.write_bytes(fetch(url))
        body = p.read_bytes()
        expected = cp.read_text().split()[0]
        if sha(body) != expected: raise ValueError('Checksum mismatch: ' + url)
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            if len(z.namelist()) != 1: raise ValueError('Unexpected archive layout')
            rejected = []
            rows = parse_csv(z.read(z.namelist()[0]), kind, rejected)
        return {'symbol':symbol,'kind':kind,'date':date,'url':url,'sha256':expected,
                'checksum_verified':True,'rows':len(rows),'rejected':rejected}, rows
    except urllib.error.HTTPError as e:
        return {'symbol':symbol,'kind':kind,'date':date,'url':url,'error':str(e.code)}, []


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original = ROOT / 'data/longitudinal-1448-repaired'
    old_manifest = json.loads((original/'manifest.json').read_text())
    raw = gzip.decompress((original/'binance-hourly.json.gz').read_bytes())
    assert sha(raw) == old_manifest['dataset_sha256']
    btc = json.loads(raw)['series']
    series = {'BTCUSDT':btc, 'ETHUSDT':{'perp':[], 'mark':[], 'funding':[]}}
    tasks = [('BTCUSDT',k,m) for m in months_until('2026-09') if m>'2026-05' for k in btc]
    tasks += [('ETHUSDT',k,m) for m in months_until('2026-09') if m>='2020-02' for k in series['ETHUSDT']]
    records=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,(record,rows) in enumerate(pool.map(one,tasks)):
            records.append(record); series[record['symbol']][record['kind']].extend(rows)
            if (i+1)%30==0 or 'error' in record:
                print(json.dumps({'done':i+1,'total':len(tasks),'symbol':record['symbol'],'date':record['date'],'error':record.get('error')}),flush=True)
    # End only at a jointly complete month: availability, never strategy results.
    ends=[]
    for sym in series:
        for kind in ('perp','mark','funding'):
            candidates=[r['date'] for r in records if r['symbol']==sym and r['kind']==kind and 'error' not in r]
            latest=max(candidates)
            y,m=map(int,latest.split('-'))
            ends.append(ms(f'{y+int(m==12)}-{m%12+1:02}-01'))
    end=min(ends)
    restored={}; validations={}
    for sym, kinds in series.items():
        start=ms('2020-01-01' if sym=='BTCUSDT' else '2020-02-01')
        for kind,rows in kinds.items():
            rows=[r for r in rows if start<=r[0]<end]
            validation=validate_series(rows,kind,start,end)
            if kind in ('perp','mark','spot'):
                # BTC historical remaining spot holes already unsuccessfully audited.
                days=sorted({t[:10] for t in validation['missing'] if sym!='BTCUSDT' or kind!='spot' or t>='2026-06'})
                ix={r[0]:r for r in rows}; n=0
                for day in days:
                    record,extra=one((sym,kind,day)); record['supplemental_daily']=True
                    for r in extra:
                        if start<=r[0]<end and r[0] not in ix: ix[r[0]]=r;n+=1
                        elif r[0] in ix and ix[r[0]]!=r: record.setdefault('conflicts',[]).append(utc(r[0]))
                    records.append(record)
                rows=[ix[t] for t in sorted(ix)];restored[sym+'_'+kind]=n
            kinds[kind]=rows
            validations[sym+'_'+kind]=validate_series(rows,kind,start,end)
    payload={'end':end,'series':series}
    raw=canonical(payload); p=OUT/'market.json.gz'
    if p.exists() and gzip.decompress(p.read_bytes())!=raw: raise ValueError('Refuse dataset overwrite')
    p.write_bytes(gzip.compress(raw,mtime=0))
    manifest={'dataset_sha256':sha(raw),'end':utc(end),'original_btc_manifest':old_manifest,
              'new_files':records,'validation':validations,'restored':restored,'interpolated_rows':0}
    (OUT/'manifest.json').write_bytes(canonical(manifest))
    print(json.dumps({'end':utc(end),'sha256':sha(raw),'verified_new_files':sum('error' not in r for r in records),
                      'validation':{k:{'rows':v['rows'],'missing':v['missing_count'],'short':len(v['short_bars'])} for k,v in validations.items()},
                      'restored':restored}),flush=True)


if __name__=='__main__': main()
