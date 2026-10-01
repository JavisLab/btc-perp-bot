"""Download only official public BTCUSDT 5m archives; no trading interfaces."""
import csv
import gzip
import io
import json
import math
import zipfile
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from btc_perp_bot.research.archive import HOUR, canonical, fetch, ms, sha, utc

ROOT = Path(__file__).resolve().parents[1]
STEP = 300_000
START, END = ms('2021-10-01'), ms('2026-09-01')


def one(month):
    cache = ROOT/'data/structure-1471/raw'; cache.mkdir(parents=True,exist_ok=True)
    url = 'https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/5m/BTCUSDT-5m-'+month+'.zip'
    path, check = cache/(month+'.zip'), cache/(month+'.CHECKSUM')
    if not check.exists(): check.write_bytes(fetch(url+'.CHECKSUM'))
    if not path.exists(): path.write_bytes(fetch(url))
    raw = path.read_bytes(); digest = check.read_text().split()[0]
    if sha(raw) != digest: raise ValueError('Checksum '+month)
    rows, zero = [], []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist()) != 1 or z.getinfo(z.namelist()[0]).file_size > 10_000_000:
            raise ValueError('Archive layout')
        for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
            if r[0] == 'open_time': continue
            if len(r) != 12: raise ValueError('Schema')
            t, end, trades = int(r[0]), int(r[6]), int(r[8])
            o,h,l,c,v,q,b,bq = map(Decimal,[*r[1:6],r[7],r[9],r[10]])
            if not all(x.is_finite() for x in (o,h,l,c,v,q,b,bq)): raise ValueError('Finite')
            if not (0 < l <= min(o,c) <= max(o,c) <= h and 0 <= b <= v and 0 <= bq <= q):
                raise ValueError('OHLCV')
            if t % STEP or end != t+STEP-1 or trades < 0: raise ValueError('Time/count')
            eps = Decimal('.00001')
            if not (l*v-eps <= q <= h*v+eps and l*b-eps <= bq <= h*b+eps):
                raise ValueError('Quote validation')
            if (v == 0) != (trades == 0) or (v == 0) != (q == 0): raise ValueError('Zero mismatch')
            if v == 0: zero.append(t)
            rows.append([t,float(o),float(h),float(l),float(c),float(v),end,float(q),trades,float(b),float(bq)])
    return rows, {'month':month,'url':url,'sha256':digest,'bytes':len(raw),'rows':len(rows),'zero_volume':zero}


def run():
    months=[f'{y}-{m:02}' for y in range(2021,2027) for m in range(1,13)
            if '2021-10' <= f'{y}-{m:02}' <= '2026-08']
    rows, files = [], []
    with ThreadPoolExecutor(max_workers=4) as p:
        for i,(part,record) in enumerate(p.map(one,months)):
            rows.extend(part); files.append(record)
            if (i+1)%10 == 0: print(json.dumps({'files':i+1,'total':len(months)}),flush=True)
    times=[r[0] for r in rows]
    if times != list(range(START,END,STEP)): raise ValueError('Missing/reversed/duplicate timestamp')
    original=json.loads(gzip.decompress((ROOT/'runs/price-volume-1462/ohlcv.json.gz').read_bytes()))
    hourly={r[0]:r for r in original['rows']}
    conflicts=[]; max_volume_error=0.
    for i in range(0,len(rows),12):
        a=rows[i:i+12]; t=a[0][0]; b=hourly[t]
        ohlc=[a[0][1],max(x[2] for x in a),min(x[3] for x in a),a[-1][4]]
        volume=[math.fsum(x[j] for x in a) for j in (5,7,9,10)]
        errs=[abs(v-b[j]) for v,j in zip(volume,(5,7,9,10))]
        max_volume_error=max(max_volume_error,*errs)
        if ohlc != b[1:5] or sum(x[8] for x in a)!=b[8] or any(e>1e-5 for e in errs):
            conflicts.append({'time':utc(t),'five_minute_aggregate':ohlc,'hourly':b[1:5],
                              'volume_errors':errs,'trades_difference':sum(x[8] for x in a)-b[8]})
    audit={'files':files,'rows':len(rows),'hours_compared':len(rows)//12,'start':utc(START),
           'end_exclusive':utc(END),'missing':0,'interpolated':0,'hourly_conflicts':conflicts,
           'max_volume_rounding_error':max_volume_error,'rows_sha256':sha(canonical(rows))}
    out=ROOT/'data/structure-1471'; out.mkdir(exist_ok=True)
    for name,body in [('bars.json.gz',gzip.compress(canonical({'rows':rows}),mtime=0)),
                      ('audit.json',canonical(audit))]:
        dest=out/name
        if dest.exists() and dest.read_bytes()!=body: raise ValueError('Immutable dataset mismatch')
        dest.write_bytes(body)
    print(json.dumps({k:v for k,v in audit.items() if k!='files'},ensure_ascii=False),flush=True)
    # Preserve monthly dataset. Repair only a price conflict where BOTH official
    # daily 5m and 1m independently aggregate to the original hourly OHLC/count.
    fixed=[list(r) for r in rows]; repairs=[]; supplements=[]
    checks=ROOT/'data/structure-1471/supplemental/checks.json'
    if not checks.exists():
        if conflicts: raise ValueError('Inspect official daily evidence for conflicts first')
    else:
        supplements=json.loads(checks.read_text())
        for rec in supplements:
            p=ROOT/'data/structure-1471/supplemental'/rec['url'].split('/')[-1]
            if sha(p.read_bytes())!=rec['sha256']: raise ValueError('Supplemental checksum')
        for c in conflicts:
            if c['five_minute_aggregate']==c['hourly']: continue
            t=ms(c['time'].replace('Z','')); day=c['time'][:10]
            proof=[h for rec in supplements if rec['day']==day for h in rec['hours'] if h['time']==c['time']]
            if len(proof)!=2 or any(h['ohlc']!=c['hourly'] or h['trades']!=hourly[t][8] for h in proof): continue
            p=ROOT/'data/structure-1471/supplemental'/('BTCUSDT-5m-'+day+'.zip')
            with zipfile.ZipFile(p) as z:
                for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
                    if not r[0].isdigit() or not t<=int(r[0])<t+HOUR: continue
                    a=[int(r[0]),*map(float,r[1:6]),int(r[6]),float(r[7]),int(r[8]),float(r[9]),float(r[10])]
                    # Daily rows must satisfy the same basic bar bounds.
                    if a[6]!=a[0]+STEP-1 or not 0<a[3]<=min(a[1],a[4])<=max(a[1],a[4])<=a[2] or not 0<=a[9]<=a[5]:
                        raise ValueError('Invalid repair row')
                    fixed[(a[0]-START)//STEP]=a
            repairs.append({'hour':c['time'],'source':str(p.relative_to(ROOT)),
                            'reason':'daily_1m_and_5m_agree_with_hourly_price_and_trade_count'})
    resolution={**audit,'repairs':repairs,'supplemental':supplements,
                'unresolved':[c for c in conflicts if c['time'] not in {r['hour'] for r in repairs}],
                'repaired_rows_sha256':sha(canonical(fixed)),
                'zero_volume_bars':[utc(r[0]) for r in fixed if r[5]==0],
                'policy':'No simulated fills in zero-volume bars; 4 volume/count discrepancies retained; one hourly-open discrepancy is explained by leading empty bars.'}
    for name,body in [('bars-repaired.json.gz',gzip.compress(canonical({'rows':fixed}),mtime=0)),
                      ('resolution.json',canonical(resolution))]:
        dest=out/name
        if dest.exists() and dest.read_bytes()!=body: raise ValueError('Immutable repaired dataset mismatch')
        dest.write_bytes(body)
    print(json.dumps({'repaired_hours':len(repairs),'unresolved_hours':len(resolution['unresolved']),
                      'zero_volume_bars':len(resolution['zero_volume_bars']),
                      'sha256':resolution['repaired_rows_sha256']}),flush=True)


if __name__=='__main__': run()
