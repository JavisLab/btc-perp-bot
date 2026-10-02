"""Observed public API/archive clock comparison; not a causal availability claim."""
import concurrent.futures as cf
import csv
import datetime as dt
from decimal import Decimal as D
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1];SOURCE=Path('/home/ubuntu/.openclaw/workspace/tmp/eth-performance-20261002/oi-availability')
OUT=ROOT/'data/oi-availability-20261002';DAY='2026-09-30'


def readzip(path):
    with zipfile.ZipFile(path) as z:return list(csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())))


def fetch(symbol):
    name=f'{symbol}-5m-{DAY}.zip';url=f'https://data.binance.vision/data/futures/um/daily/klines/{symbol}/5m/{name}'
    for suffix in ['', '.CHECKSUM']:
        p=OUT/'clock-probes'/(name+suffix);p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists():
            with urllib.request.urlopen(url+suffix,timeout=30) as r:
                assert r.status==200;p.write_bytes(r.read())
    path=OUT/'clock-probes'/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==path.with_suffix('.zip.CHECKSUM').read_text().split()[0]
    return symbol,{int(r[0]):r for r in readzip(path) if r[0].isdigit()}


def main():
    with cf.ThreadPoolExecutor(max_workers=2) as pool:klines=dict(pool.map(fetch,['BTCUSDT','ETHUSDT']))
    results=[]
    for symbol in ['BTCUSDT','ETHUSDT']:
        zipped=readzip(OUT/'samples'/f'{symbol}-metrics-{DAY}.zip');names=zipped[0]
        archive={int(dt.datetime.fromisoformat(r[0]).replace(tzinfo=dt.timezone.utc).timestamp()*1000):dict(zip(names,r)) for r in zipped[1:]}
        for endpoint,pairs in [('openInterestHist',[('sumOpenInterest','sum_open_interest'),('sumOpenInterestValue','sum_open_interest_value')]),('takerlongshortRatio',[('buySellRatio','sum_taker_long_short_vol_ratio')])]:
            api=json.loads((SOURCE/(symbol+'-'+endpoint+'.json')).read_bytes())
            for key,col in pairs:
                for shift in ([0,300000] if endpoint=='takerlongshortRatio' else [0]):
                    matched=[r for r in api if r['timestamp']+shift in archive]
                    diff=[abs(D(r[key])-D(archive[r['timestamp']+shift][col])) for r in matched]
                    results.append({'symbol':symbol,'endpoint':endpoint,'field':key,'archive_column':col,
                        'api_timestamp_to_archive_shift_ms':shift,'matched_rows':len(matched),'exact_matches':sum(x==0 for x in diff),
                        'matches_within_0_00005_ratio_rounding':sum(x<=D('.00005') for x in diff) if endpoint=='takerlongshortRatio' else None,
                        'max_abs_difference':str(max(diff)),'first_api_timestamp':api[0]['timestamp'],'last_api_timestamp':api[-1]['timestamp']})
            if endpoint=='takerlongshortRatio':
                matched=[r for r in api if r['timestamp'] in klines[symbol]];buys=[];sells=[]
                for r in matched:
                    bar=klines[symbol][r['timestamp']]
                    assert int(bar[6])==int(bar[0])+300000-1
                    buys.append(abs(D(r['buyVol'])-D(bar[9])));sells.append(abs(D(r['sellVol'])-(D(bar[5])-D(bar[9]))))
                results.append({'symbol':symbol,'comparison':'API taker volumes vs official 5m kline at SAME opening timestamp',
                    'matched_rows':len(matched),'exact_buy_matches':sum(x==0 for x in buys),'exact_sell_matches':sum(x==0 for x in sells),
                    'max_buy_difference':str(max(buys)),'max_sell_difference':str(max(sells))})
    report={'day':DAY,'results':results,'interpretation':[
        'The API range returned taker opening timestamps one 5m step earlier than OI snapshots; direct timestamp-set equality failed and is not assumed.',
        'Shift comparison is a data-clock diagnostic only; raw timestamps retained and no account performance calculated.',
        'Single-day agreement is not proof every historical day has identical semantics or real-time publication availability.',
        'Deprecated official connector notes 30-day history; actual public API response was checked, not assumed from old documentation.']}
    (OUT/'api-clock-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
