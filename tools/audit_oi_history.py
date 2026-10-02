"""Resumable official OI daily-archive integrity/coverage audit; no returns."""
import argparse
from collections import Counter
import concurrent.futures as cf
import csv
import datetime as dt
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'data/oi-availability-20261002';OUT=ROOT/'data/oi-history-20261002'
COLS=['create_time','symbol','sum_open_interest','sum_open_interest_value','count_toptrader_long_short_ratio','sum_toptrader_long_short_ratio','count_long_short_ratio','sum_taker_long_short_vol_ratio']
START=dt.date(2022,1,1);END=dt.date(2026,9,1)


def encoded(value):return (json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
def sha(body):return hashlib.sha256(body).hexdigest()
def atomic(path,body):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_name(path.name+'.tmp');tmp.write_bytes(body);os.replace(tmp,path)


def get(url,path):
    if path.exists():return path.read_bytes()
    cached=BASE/'samples'/path.name
    if cached.exists():body=cached.read_bytes()
    else:
        with urllib.request.urlopen(url,timeout=25) as r:
            if r.status!=200:raise ValueError('HTTP '+str(r.status))
            body=r.read()
    atomic(path,body);return body


def parse_csv(body,symbol,date):
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        if len(z.namelist())!=1:raise ValueError('Unexpected ZIP members')
        reader=csv.DictReader(io.StringIO(z.read(z.namelist()[0]).decode()));rows=list(reader)
        if reader.fieldnames!=COLS:raise ValueError('Schema '+str(reader.fieldnames))
    day=int(dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc).timestamp())
    expected=set(range(day,day+86400,300));times=[];normalized=[];null=Counter();zero=Counter();negative=Counter();bad_symbol=0
    for r in rows:
        stamp=dt.datetime.fromisoformat(r['create_time'])
        if stamp.tzinfo is not None:raise ValueError('Unexpected timezone-bearing schema')
        t=int(stamp.replace(tzinfo=dt.timezone.utc).timestamp());times.append(t);values=[]
        bad_symbol+=int(r['symbol']!=symbol)
        for key in COLS[2:]:
            try:v=Decimal(r[key])
            except InvalidOperation:v=Decimal('NaN')
            if not v.is_finite():values.append(None);null[key]+=1
            else:
                values.append(str(v));zero[key]+=int(v==0);negative[key]+=int(v<0)
        normalized.append([t*1000,*values])
    return {'rows':len(rows),'missing_times_ms':[t*1000 for t in sorted(expected-set(times))],
        'unexpected_times_ms':[t*1000 for t in times if t not in expected],'duplicates':len(times)-len(set(times)),
        'strictly_ordered':times==sorted(set(times)),'wrong_symbol_rows':bad_symbol,
        'null_counts':dict(null),'zero_counts':dict(zero),'negative_counts':dict(negative)},normalized


def audit_one(task):
    symbol,date=task;dest=OUT/'days'/symbol/(date+'.json')
    if dest.exists():return json.loads(dest.read_bytes())
    filename=f'{symbol}-metrics-{date}.zip';url=f'https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{filename}'
    record={'symbol':symbol,'date':date,'url':url}
    try:
        raw=OUT/'raw'/symbol/filename;body=get(url,raw);ck=get(url+'.CHECKSUM',raw.with_suffix('.zip.CHECKSUM'))
        if sha(body)!=ck.decode().split()[0]:raise ValueError('SHA256 checksum mismatch')
        stats,rows=parse_csv(body,symbol,date);normal=encoded({'columns':['time_ms',*COLS[2:]],'rows':rows})
        packed=gzip.compress(normal,mtime=0);atomic(OUT/'normalized'/symbol/(date+'.json.gz'),packed)
        record.update(stats,zip_sha256=sha(body),checksum_sha256=sha(ck),normalized_sha256=sha(normal),normalized_gzip_sha256=sha(packed),verified=True)
        atomic(dest,encoded(record))
    except Exception as e:
        record.update(verified=False,error=type(e).__name__+': '+str(e));atomic(OUT/'errors'/symbol/(date+'.json'),encoded(record))
    return record


def summarize(records,tasks,elapsed):
    records=sorted(records,key=lambda r:(r['symbol'],r['date']));summary={}
    for symbol in ['BTCUSDT','ETHUSDT']:
        part=[r for r in records if r['symbol']==symbol and r['verified']];null=Counter();zero=Counter();negative=Counter()
        for r in part:null.update(r['null_counts']);zero.update(r['zero_counts']);negative.update(r['negative_counts'])
        summary[symbol]={'verified_days':len(part),'rows':sum(r['rows'] for r in part),
            'missing_rows':sum(len(r['missing_times_ms']) for r in part),'days_with_gaps':sum(bool(r['missing_times_ms']) for r in part),
            'unexpected_times':sum(len(r['unexpected_times_ms']) for r in part),'duplicates':sum(r['duplicates'] for r in part),
            'unordered_days':sum(not r['strictly_ordered'] for r in part),'wrong_symbol_rows':sum(r['wrong_symbol_rows'] for r in part),
            'null_counts':dict(null),'zero_counts':dict(zero),'negative_counts':dict(negative)}
    done={(r['symbol'],r['date']) for r in records if r['verified']};remaining=[list(t) for t in tasks if t not in done]
    result={'scope':'OI data audit only; no signal/returns; no interpolation','expected_daily_archives':len(tasks),
        'complete':not remaining,'verified_days':len(done),'remaining_days':remaining,'summary':summary,'records':records,
        'window_elapsed_seconds':round(elapsed,3),'timestamp_assumption':'naive create_time interpreted as UTC/file day; publication availability unproven'}
    atomic(OUT/'audit.json',encoded(result));return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=480);a=p.parse_args();started=time.monotonic()
    tasks=[(symbol,(START+dt.timedelta(days=i)).isoformat()) for i in range((END-START).days) for symbol in ['BTCUSDT','ETHUSDT']]
    cached=[];todo=[]
    for t in tasks:
        p=OUT/'days'/t[0]/(t[1]+'.json')
        if p.exists():cached.append(json.loads(p.read_bytes()))
        else:todo.append(t)
    records=cached[:];iterator=iter(todo)
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        active={pool.submit(audit_one,t):t for t in [next(iterator,None) for _ in range(4)] if t is not None}
        while active:
            finished,_=cf.wait(active,return_when=cf.FIRST_COMPLETED)
            for future in finished:
                active.pop(future);records.append(future.result())
                if len(records)%100==0:
                    summarize(records,tasks,time.monotonic()-started)
                    print(json.dumps({'processed':len(records),'remaining':len(tasks)-len(records),'seconds':round(time.monotonic()-started,1)}),flush=True)
                if time.monotonic()-started<a.seconds:
                    t=next(iterator,None)
                    if t is not None:active[pool.submit(audit_one,t)]=t
    result=summarize(records,tasks,time.monotonic()-started)
    print(json.dumps({k:v for k,v in result.items() if k not in ('records','remaining_days')},indent=2),flush=True)


if __name__=='__main__':main()
