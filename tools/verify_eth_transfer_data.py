"""Independent Decimal/raw-CSV proof for ETH source evidence, without collector imports."""
import csv
import gzip
import hashlib
import io
import json
import socket
import zipfile
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/eth-transfer-20261002'
HOUR,STEP=3_600_000,300_000


def deny(*args,**kwargs):
    raise RuntimeError('Network disabled during independent verification')


def stamp(t):
    return datetime.fromtimestamp(t/1000,timezone.utc).isoformat().replace('+00:00','Z')


def rawrows(path):
    with zipfile.ZipFile(path) as z:
        assert len(z.namelist())==1
        data=z.read(z.namelist()[0])
    return [r for r in csv.reader(io.StringIO(data.decode())) if r and r[0].isdigit()]


def drow(r):
    return [int(r[0]),*map(Decimal,r[1:6]),int(r[6]),Decimal(r[7]),int(r[8]),Decimal(r[9]),Decimal(r[10])]


def agg(rows):
    return [rows[0][0],rows[0][1],max(r[2] for r in rows),min(r[3] for r in rows),rows[-1][4],
            sum(r[5] for r in rows),rows[-1][6],sum(r[7] for r in rows),sum(r[8] for r in rows),
            sum(r[9] for r in rows),sum(r[10] for r in rows)]


def different(a,b):
    return [j for j in (1,2,3,4,5,7,8,9,10) if abs(a[j]-b[j])>(Decimal('.00001') if j in (5,7,9,10) else 0)]


def native(row):
    return [float(v) if isinstance(v,Decimal) else v for v in row]


def main():
    socket.socket=deny;socket.create_connection=deny
    audit=json.loads((SOURCE/'audit.json').read_bytes())
    for name,hashes in audit['artifacts'].items():
        raw=(SOURCE/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==hashes['gzip_sha256']
        assert hashlib.sha256(gzip.decompress(raw)).hexdigest()==hashes['uncompressed_sha256']
    normalized=json.loads(gzip.decompress((SOURCE/'hourly-ohlcv.json.gz').read_bytes()))['rows']
    price={r[0]:r for r in normalized};del normalized
    mf=json.loads(gzip.decompress((SOURCE/'mark-funding.json.gz').read_bytes()))
    mark={r[0]:r for r in mf['mark']};fund={r[0]:r for r in mf['funding']};del mf
    fine=json.loads(gzip.decompress((SOURCE/'bars-monthly.json.gz').read_bytes()))['rows']
    assert fine==json.loads(gzip.decompress((SOURCE/'bars-repaired.json.gz').read_bytes()))['rows']
    counts=Counter();hourly={};conflicts=[];minutetofive=[];daily={};fine_cursor=0
    for rec in audit['source_files']:
        path=ROOT/rec['path'];body=path.read_bytes()
        assert hashlib.sha256(body).hexdigest()==rec['sha256']
        check=path.with_suffix('.CHECKSUM').read_bytes()
        assert hashlib.sha256(check).hexdigest()==rec['checksum_sha256']
        assert check.decode().split()[0]==rec['sha256']
        raw=rawrows(path);assert len(raw)==rec['rows'];counts['verified_archives']+=1
        if rec['kind']=='funding':
            for r in raw:
                t=int(r[0]);row=[t//HOUR*HOUR,int(r[1]),float(Decimal(r[2])),t]
                assert row==fund[row[0]];assert row[0] in mark
                counts['funding_raw_rows_compared']+=1
            continue
        rows=[drow(r) for r in raw]
        ts=[r[0] for r in rows]
        assert ts==sorted(set(ts))
        for row in rows:
            assert row[6]==row[0]+rec['step_ms']-1
            assert 0<row[3]<=min(row[1],row[4])<=max(row[1],row[4])<=row[2]
            if rec['kind']=='perp':
                assert 0<=row[9]<=row[5] and 0<=row[10]<=row[7]
                for qty,quote in [(row[5],row[7]),(row[9],row[10])]:
                    assert row[3]*qty-Decimal('.00001')<=quote<=row[2]*qty+Decimal('.00001')
                assert (row[5]==0)==(row[7]==0)==(row[8]==0)
        if rec['step_ms']==HOUR:
            for row in rows:
                assert native(row)==(price if rec['kind']=='perp' else mark)[row[0]]
                if rec['kind']=='perp':hourly[row[0]]=row
                counts[rec['kind']+'_raw_rows_compared']+=1
        elif '/monthly/' in rec['url']:
            for row in rows:
                assert native(row)==fine[fine_cursor]
                assert row[0]==fine[0][0]+fine_cursor*STEP
                fine_cursor+=1;counts['fine_raw_rows_compared']+=1
            for i in range(0,len(rows),12):
                p=rows[i:i+12];a=agg(p);b=hourly[a[0]];fields=different(a,b)
                counts['decimal_hourly_aggregates_compared']+=1
                if fields:
                    nz=[r for r in p if r[5]>0]
                    explains=bool(nz and agg(nz)[1:5]==b[1:5] and a[1:5]!=b[1:5])
                    conflicts.append({'time':stamp(a[0]),'field_indices':fields,
                        'empty_bar_price_explains':explains,
                        'zero_bars_in_hour':sum(r[5]==0 for r in p),
                        'base_volume_difference':str(a[5]-b[5]),'trade_count_difference':a[8]-b[8],
                        'aggregate_ohlc':[str(x) for x in a[1:5]],'hourly_ohlc':[str(x) for x in b[1:5]],
                        'traded_bar_ohlc':[str(x) for x in agg(nz)[1:5]] if nz else None})
        else:
            daily[rec['first'][:10],rec['step_ms']]=rows
            counts['supplemental_raw_rows_checked']+=len(rows)
    assert fine_cursor==len(fine)==517248
    assert fine[-1][0]+STEP==int(datetime(2026,9,1,tzinfo=timezone.utc).timestamp()*1000)
    assert [c['time'] for c in conflicts]==[c['time'] for c in audit['initial_conflicts']]
    for day in sorted({d for d,s in daily}):
        mins,fives=daily[day,60000],daily[day,STEP]
        assert len(mins)==1440 and len(fives)==288
        for i,b in enumerate(fives):
            a=agg(mins[i*5:i*5+5]);assert a[0]==b[0]
            fields=different(a,b);counts['daily_1m_to_5m_compared']+=1
            if fields:minutetofive.append({'time':stamp(a[0]),'field_indices':fields,
                'aggregate_1m':native(a),'official_5m':native(b)})
    assert sum(r[5]==0 for r in fine)==audit['counts']['zero_volume_5m_bars']
    report={'type':'independent_raw_decimal_source_audit_not_account_verification','network_disabled':True,
        'counts':dict(counts),'hashes_verified':audit['artifacts'],'source_audit_sha256':hashlib.sha256((SOURCE/'audit.json').read_bytes()).hexdigest(),
        'normalized_legacy_rows_equal':True,'normalized_fine_rows_equal':True,'decimal_conflicts':conflicts,
        'daily_1m_5m_conflicts':minutetofive,'daily_1m_5m_conflict_count':len(minutetofive),
        'no_price_repair_supported_by_frozen_rule':True,'performance_computed':False,
        'note':'One hourly open AND low discrepancy vanishes when zero-volume rows are excluded from the diagnostic aggregation. Original bars remain unchanged and unfillable. Five other hours have unresolved volume/count differences.'}
    body=json.dumps(report,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    target=ROOT/'runs/eth-transfer-20261002/independent-verification.json';target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert target.read_bytes()==body
    else:target.write_bytes(body)
    print(json.dumps({'counts':dict(counts),'hourly_conflicts':len(conflicts),
                     'empty_bar_price_explained':sum(c['empty_bar_price_explains'] for c in conflicts),
                     'daily_1m_5m_conflicts':len(minutetofive),'sha256':hashlib.sha256(body).hexdigest()},ensure_ascii=False))


if __name__=='__main__':main()
