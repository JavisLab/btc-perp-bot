"""ETH-only public archive audit. No strategy returns, account or order interfaces.

Run: python3 tools/collect_eth_transfer.py [--offline] [--output PATH]
Cached ZIP/checksums are immutable. All source conflicts are retained.
"""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/eth-transfer-20261002'
BASE = 'https://data.binance.vision/data/futures/um/'
HOUR, STEP, DAY = 3_600_000, 300_000, 86_400_000
MARKET_HASH = '9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4'
COLUMNS = ['time','open','high','low','close','volume','close_time',
           'quote_volume','trades','taker_buy_volume','taker_buy_quote_volume']


def ms(s):
    return int(datetime.fromisoformat(s.replace('Z','+00:00')).replace(tzinfo=timezone.utc).timestamp()*1000)


def utc(t):
    return datetime.fromtimestamp(t/1000,timezone.utc).isoformat().replace('+00:00','Z')


def canonical(x):
    return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def fixed(path, body):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=body:
        raise ValueError('Refuse to overwrite different evidence: '+str(path))
    if not path.exists():
        temp=path.with_name(path.name+'.partial')
        temp.write_bytes(body);temp.replace(path)


def fetch(url):
    if not url.startswith(BASE):
        raise ValueError('Public official archive allowlist')
    with urllib.request.urlopen(url,timeout=30) as r:
        return r.read()


def parse_klines(body, step, *, volume=True):
    """Validate before float conversion; futures timestamps must be milliseconds."""
    rows=[]
    for r in csv.reader(io.StringIO(body.decode())):
        if r and r[0]=='open_time':
            continue
        if len(r)!=12:
            raise ValueError('Kline schema')
        t,end,trades=int(r[0]),int(r[6]),int(r[8])
        if not ms('2019-01-01')<=t<ms('2030-01-01') or t%step or end!=t+step-1 or trades<0:
            raise ValueError('Timestamp unit/alignment/end/count')
        o,h,l,c,v,q,b,bq=map(Decimal,[*r[1:6],r[7],r[9],r[10]])
        if not all(x.is_finite() for x in (o,h,l,c,v,q,b,bq)):
            raise ValueError('Nonfinite kline')
        if not 0<l<=min(o,c)<=max(o,c)<=h:
            raise ValueError('OHLC')
        if volume:
            if not (0<=b<=v and 0<=bq<=q):
                raise ValueError('Volume/taker bounds')
            eps=Decimal('.00001')
            if not (l*v-eps<=q<=h*v+eps and l*b-eps<=bq<=h*b+eps):
                raise ValueError('Quote value outside OHLC')
            if (v==0)!=(q==0) or (v==0)!=(trades==0):
                raise ValueError('Zero-volume consistency')
        rows.append([t,float(o),float(h),float(l),float(c),float(v),end,float(q),trades,float(b),float(bq)])
    if not rows or [r[0] for r in rows]!=sorted({r[0] for r in rows}):
        raise ValueError('Empty/duplicate/reversed file')
    return rows


def parse_funding(body):
    rows=[]
    for r in csv.reader(io.StringIO(body.decode())):
        if r and r[0]=='calc_time':
            continue
        if len(r)!=3:
            raise ValueError('Funding schema')
        t,interval,rate=int(r[0]),int(r[1]),Decimal(r[2])
        if not ms('2019-01-01')<=t<ms('2030-01-01') or t%HOUR>=60_000:
            raise ValueError('Funding timestamp')
        if interval not in (1,4,8) or not rate.is_finite() or abs(rate)>.05:
            raise ValueError('Funding rate/interval')
        rows.append([t//HOUR*HOUR,interval,float(rate),t])
    if not rows or [r[0] for r in rows]!=sorted({r[0] for r in rows}):
        raise ValueError('Funding duplicate/reversed')
    return rows


def archive(path, url, step=HOUR, *, kind='perp', offline=False):
    check=path.with_suffix('.CHECKSUM')
    if not check.exists():
        if offline: raise ValueError('Missing offline checksum '+str(check))
        fixed(check,fetch(url+'.CHECKSUM'))
    if not path.exists():
        if offline: raise ValueError('Missing offline archive '+str(path))
        fixed(path,fetch(url))
    raw=path.read_bytes();expected=check.read_text().split()[0]
    if len(expected)!=64 or sha(raw)!=expected:
        raise ValueError('Publisher checksum mismatch '+str(path))
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist())!=1 or z.getinfo(z.namelist()[0]).file_size>20_000_000:
            raise ValueError('ZIP layout/size')
        body=z.read(z.namelist()[0])
    rows=parse_funding(body) if kind=='funding' else parse_klines(body,step,volume=kind!='mark')
    record={'url':url,'sha256':expected,'checksum_sha256':sha(check.read_bytes()),
            'checksum_verified':True,'bytes':len(raw),'rows':len(rows),'kind':kind,
            'step_ms':None if kind=='funding' else step,'first':utc(rows[0][0]),'last':utc(rows[-1][0]),
            'path':str(path.relative_to(ROOT))}
    return rows,record


def complete(rows,start,end,step):
    if [r[0] for r in rows]!=list(range(start,end,step)):
        raise ValueError('Incomplete/duplicate/reversed period')


def hourly_aggregate(part):
    return [part[0][0],part[0][1],max(r[2] for r in part),min(r[3] for r in part),part[-1][4],
            math.fsum(r[5] for r in part),part[-1][6],math.fsum(r[7] for r in part),
            sum(r[8] for r in part),math.fsum(r[9] for r in part),math.fsum(r[10] for r in part)]


def differences(fine,hourly,step=STEP):
    conflicts=[];max_errors=[0.,0.,0.,0.];width=HOUR//step
    for i in range(0,len(fine),width):
        part=fine[i:i+width];a=hourly_aggregate(part);b=hourly[a[0]]
        errors=[a[j]-b[j] for j in (5,7,9,10)]
        max_errors=[max(v,abs(e)) for v,e in zip(max_errors,errors)]
        if a[1:5]!=b[1:5] or a[8]!=b[8] or any(abs(e)>1e-5 for e in errors):
            nonzero=next((r for r in part if r[5]>0),None)
            conflicts.append({'time':utc(a[0]),'aggregate':a,'hourly':b,'volume_signed_errors':errors,
                              'price_conflict':a[1:5]!=b[1:5],
                              'leading_empty_open_explains':bool(nonzero is not None and part[0][5]==0
                                  and a[2:5]==b[2:5] and nonzero[1]==b[1])})
    return conflicts,max_errors


def can_repair(conflict,proof):
    """Same predeclared BTC policy: two daily timeframes corroborate hour price/count."""
    b=conflict['hourly']
    return (conflict['price_conflict'] and set(proof)=={'1m','5m'}
            and all(p[1:5]==b[1:5] and p[8]==b[8] for p in proof.values()))


def existing_eth():
    market_raw=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes())
    if sha(market_raw)!=MARKET_HASH:
        raise ValueError('Original dataset hash')
    market=json.loads(market_raw)['series']['ETHUSDT']
    source=ROOT/'data/archive-1458/ETHUSDT';series={};files=[];restored=[];daily_conflicts=[]
    for kind in ('perp','mark','funding'):
        ix={}
        monthly=sorted((source/kind).glob('????-??.zip'))
        daily=sorted((source/kind).glob('????-??-??.zip'))
        for path in monthly+daily:
            date=path.stem;period='daily' if len(date)==10 else 'monthly'
            tail=(f'fundingRate/ETHUSDT/ETHUSDT-fundingRate-{date}.zip' if kind=='funding'
                  else f'{"markPriceKlines" if kind=="mark" else "klines"}/ETHUSDT/1h/ETHUSDT-1h-{date}.zip')
            part,record=archive(path,BASE+period+'/'+tail,kind=kind,offline=True)
            files.append(record)
            for r in part:
                if r[0] in ix:
                    if period=='monthly': raise ValueError('Monthly overlap')
                    if ix[r[0]]!=r: daily_conflicts.append({'kind':kind,'time':utc(r[0])})
                else:
                    ix[r[0]]=r
                    if period=='daily': restored.append({'kind':kind,'time':utc(r[0]),'source':record['url']})
        rows=[ix[t] for t in sorted(ix)]
        compare=rows if kind=='funding' else [[r[j] for j in (0,1,2,3,4,6)] for r in rows]
        if compare!=market[kind]: raise ValueError('Legacy market differs: '+kind)
        if kind!='funding':
            complete(rows,ms('2020-02-01'),ms('2026-09-01'),HOUR)
        else:
            if rows[0][0]!=ms('2020-02-01') or rows[-1][0]+rows[-1][1]*HOUR!=ms('2026-09-01'):
                raise ValueError('Funding boundary')
            if any(b[0]-a[0]!=b[1]*HOUR for a,b in zip(rows,rows[1:])):
                raise ValueError('Funding interval coverage')
        series[kind]=rows
    return series,files,restored,daily_conflicts


def run(output=OUT,offline=False):
    start,end=ms('2021-10-01'),ms('2026-09-01')
    series,legacy_files,restored,daily_conflicts=existing_eth()
    hourly={r[0]:r for r in series['perp']}
    months=[f'{y}-{m:02}' for y in range(2021,2027) for m in range(1,13)
            if '2021-10'<=f'{y}-{m:02}'<='2026-08']
    def one(month):
        url=BASE+f'monthly/klines/ETHUSDT/5m/ETHUSDT-5m-{month}.zip'
        return archive(OUT/'raw'/(month+'.zip'),url,STEP,offline=offline)
    fine=[];files=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,(part,rec) in enumerate(pool.map(one,months)):
            fine.extend(part);files.append(rec)
            if (i+1)%10==0: print(json.dumps({'verified_months':i+1,'total':len(months)}),flush=True)
    complete(fine,start,end,STEP)
    conflicts,max_errors=differences(fine,hourly)
    print(json.dumps({'rows_5m':len(fine),'hourly_conflicts':len(conflicts),
                      'conflict_times':[c['time'] for c in conflicts]}),flush=True)
    days=sorted({c['time'][:10] for c in conflicts});supplements=[];daily={}
    for day in days:
        for tf,step in [('1m',60_000),('5m',STEP)]:
            name=f'ETHUSDT-{tf}-{day}.zip';url=BASE+f'daily/klines/ETHUSDT/{tf}/'+name
            part,rec=archive(OUT/'supplemental'/name,url,step,offline=offline)
            complete(part,ms(day),ms(day)+DAY,step)
            daily[day,tf]=part;supplements.append(rec)
    repaired=[list(r) for r in fine];repairs=[];evidence=[]
    for c in conflicts:
        t=ms(c['time']);day=c['time'][:10]
        proof={tf:hourly_aggregate([r for r in daily[day,tf] if t<=r[0]<t+HOUR]) for tf in ('1m','5m')}
        evidence.append({'time':c['time'],'daily_1m':proof['1m'],'daily_5m':proof['5m'],
                         'monthly_5m':c['aggregate'],'monthly_1h':c['hourly']})
        if can_repair(c,proof):
            part=[r for r in daily[day,'5m'] if t<=r[0]<t+HOUR]
            i=(t-start)//STEP;repaired[i:i+12]=part
            repairs.append({'time':c['time'],'rows':12,'reason':'daily_1m_and_5m_agree_with_hourly_price_and_count',
                            'source':BASE+f'daily/klines/ETHUSDT/5m/ETHUSDT-5m-{day}.zip'})
    complete(repaired,start,end,STEP)
    unresolved,post_errors=differences(repaired,hourly)
    marks={r[0]:r for r in series['mark']}
    if any(r[0] not in marks for r in series['funding']): raise ValueError('Missing funding mark')
    counts={'monthly_5m_archives':len(files),'supplemental_daily_archives':len(supplements),
            'reverified_legacy_archives':len(legacy_files),'rows_5m':len(fine),
            'hours_compared':len(fine)//12,'hourly_ohlcv_rows':len(series['perp']),
            'mark_rows':len(series['mark']),'funding_events':len(series['funding']),
            'mark_hours_restored_from_existing_daily':len(restored),'initial_conflict_hours':len(conflicts),
            'repaired_hours':len(repairs),'remaining_conflict_hours':len(unresolved),
            'zero_volume_5m_bars':sum(r[5]==0 for r in repaired),'missing_5m_timestamps':0,
            'interpolated_rows':0,'funding_raw_timestamp_offsets':sum(r[0]!=r[3] for r in series['funding'])}
    payloads={'bars-monthly.json.gz':{'columns':COLUMNS,'rows':fine},
              'bars-repaired.json.gz':{'columns':COLUMNS,'rows':repaired},
              'hourly-ohlcv.json.gz':{'columns':COLUMNS,'rows':series['perp']},
              'mark-funding.json.gz':{'mark':series['mark'],'funding':series['funding']}}
    hashes={}
    for name,payload in payloads.items():
        raw=canonical(payload);body=gzip.compress(raw,mtime=0);fixed(output/name,body)
        hashes[name]={'uncompressed_sha256':sha(raw),'gzip_sha256':sha(body)}
    audit={'schema':'eth-transfer-source-audit-v1','spec':'docs/EXPERIMENT_ETH_TRANSFER_20261002.md',
           'preregistration_commit':'eaacfbd','original_market_sha256':MARKET_HASH,'symbol':'ETHUSDT',
           'scope':'source_audit_only_no_strategy_returns','counts':counts,'start':utc(start),'end_exclusive':utc(end),
           'source_files':legacy_files+files+supplements,'artifacts':hashes,'initial_conflicts':conflicts,
           'daily_comparisons':evidence,'repairs':repairs,'unresolved_conflicts':unresolved,
           'existing_daily_mark_restorations':restored,'legacy_daily_conflicts':daily_conflicts,
           'max_abs_volume_errors_before':max_errors,'max_abs_volume_errors_after':post_errors,
           'volume_absolute_tolerance':.00001,'zero_volume_times':[utc(r[0]) for r in repaired if r[5]==0],
           'funding_max_raw_offset_ms':max(r[3]-r[0] for r in series['funding']),
           'data_gate':'audited_with_disclosed_conflicts' if unresolved else 'audited_no_remaining_hourly_conflicts',
           'economic_completeness_proven':False,'performance_computed':False,
           'next_gate':'freeze ETH-only sizing adapter; independent signal/account replay; conflict exposure; offline reproduction',
           'policy':'Monthly retained unless both official daily 1m and 5m match hourly price/count for a price conflict. No zero-volume fills. No interpolation. No returns calculated.'}
    fixed(output/'audit.json',canonical(audit))
    print(json.dumps({'counts':counts,'audit_sha256':sha(canonical(audit)),
                      'remaining_conflicts':[{'time':c['time'],'price':c['price_conflict'],
                          'leading_empty':c['leading_empty_open_explains']} for c in unresolved]},ensure_ascii=False),flush=True)
    return audit


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--offline',action='store_true');p.add_argument('--output',type=Path,default=OUT)
    args=p.parse_args();run(args.output,args.offline)
