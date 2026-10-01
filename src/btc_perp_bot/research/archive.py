"""Public Binance archives only. No wallet, account or exchange-order dependency."""
import argparse
import calendar
import csv
import gzip
import hashlib
import io
import json
import math
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

HOUR = 3_600_000
DAY = 24 * HOUR
ROOT = "https://data.binance.vision/data/"
KINDS = ("spot", "perp", "mark", "funding")


def ms(date):
    return int(datetime.fromisoformat(date).replace(tzinfo=timezone.utc).timestamp() * 1000)


def utc(t):
    return datetime.fromtimestamp(t / 1000, timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def archive_url(kind, month):
    if kind == "funding":
        suffix = f"futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-{month}.zip"
    else:
        folder = {"spot": "spot/monthly/klines", "perp": "futures/um/monthly/klines",
                  "mark": "futures/um/monthly/markPriceKlines"}[kind]
        suffix = f"{folder}/BTCUSDT/1h/BTCUSDT-1h-{month}.zip"
    if len(month)==10:
        suffix=suffix.replace('/monthly/','/daily/')
    return ROOT + suffix


def fetch(url):
    if not url.startswith(ROOT):
        raise ValueError("Only official public archives are allowed")
    with urllib.request.urlopen(url, timeout=25) as r:
        return r.read()


def timestamp(value):
    t = int(value)
    # Spot switched from milliseconds to microseconds in January 2025.
    if t > 100_000_000_000_000:
        t //= 1000
    if not ms("2019-01-01") <= t < ms("2030-01-01"):
        raise ValueError("Unexpected timestamp unit or range")
    return t


def parse_csv(raw, kind, rejected=None):
    rows = []
    for r in csv.reader(io.StringIO(raw.decode())):
        if not r or not r[0].isdigit():
            if r and r[0] not in ("open_time", "calc_time"):
                raise ValueError(f"Unexpected CSV header: {r[0]}")
            continue
        t = timestamp(r[0])
        if kind != "funding" and t % HOUR:
            raise ValueError("Non-hourly archive timestamp")
        if kind == "funding":
            interval, rate = int(r[1]), float(r[2])
            if interval not in (1, 4, 8) or not math.isfinite(rate) or abs(rate) > 0.05:
                raise ValueError("Invalid funding row")
            if t % HOUR >= 60_000:
                raise ValueError("Unexpected funding settlement offset")
            rows.append([t // HOUR * HOUR, interval, rate, t])
        else:
            o, h, l, c = map(float, r[1:5])
            if not all(math.isfinite(x) and x > 0 for x in (o,h,l,c)) or not l <= min(o,c) <= max(o,c) <= h:
                raise ValueError("Invalid OHLC")
            close_time = timestamp(r[6])
            if not t <= close_time <= t + HOUR - 1:
                if rejected is None:
                    raise ValueError("Unexpected bar end")
                rejected.append({"time":utc(t),"reason":"close_time_outside_bar","original_close_time":r[6]})
                continue
            rows.append([t, o, h, l, c, close_time])
    times = [r[0] for r in rows]
    if not times or times != sorted(set(times)):
        raise ValueError("Empty, duplicated or unsorted file")
    return rows


def download_one(task):
    kind, month, cache = task
    url = archive_url(kind, month)
    folder = Path(cache) / kind
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (month + ".zip")
    cp = folder / (month + ".CHECKSUM")
    try:
        if not cp.exists():
            cp.write_bytes(fetch(url + ".CHECKSUM"))
        expected = cp.read_text().split()[0]
        if not path.exists():
            path.write_bytes(fetch(url))
        body = path.read_bytes()
        if sha(body) != expected:
            raise ValueError("Archive checksum mismatch")
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            if len(z.namelist()) != 1 or z.getinfo(z.namelist()[0]).file_size > 5_000_000:
                raise ValueError("Unexpected archive layout/size")
            rejected = []
            rows = parse_csv(z.read(z.namelist()[0]), kind, rejected)
        return {"kind": kind, "month": month, "url": url, "sha256": expected,
                "bytes": len(body), "rows": len(rows), "first": utc(rows[0][0]),
                "last": utc(rows[-1][0]), "checksum_verified": True,"rejected_rows":rejected}, rows
    except urllib.error.HTTPError as e:
        return {"kind": kind, "month": month, "url": url, "error": f"HTTP {e.code}"}, []


def months_until(end):
    return [f"{y}-{m:02}" for y in range(2020, 2027) for m in range(1,13) if f"{y}-{m:02}" <= end]


def validate_series(rows, kind, start, end):
    times = [x[0] for x in rows]
    if times != sorted(set(times)):
        raise ValueError(f"Duplicate or reversed {kind} timestamp")
    existing = set(times)
    missing = []
    if kind == "funding":
        # Every interval is checked against the following record's published interval.
        for prev, nxt in zip(rows, rows[1:]):
            if nxt[0] - prev[0] != nxt[1] * HOUR:
                missing.append({"after": utc(prev[0]), "before": utc(nxt[0]), "expected_hours": nxt[1]})
        if not rows or rows[0][0] != start or rows[-1][0] + rows[-1][1] * HOUR != end:
            missing.append({"boundary_mismatch": True})
    else:
        missing = [utc(t) for t in range(start,end,HOUR) if t not in existing]
    return {"rows": len(rows), "missing_count": len(missing), "missing": missing,
            "short_bars": [utc(r[0]) for r in rows if kind != "funding" and r[5] != r[0]+HOUR-1],
            "first": utc(times[0]) if times else None, "last": utc(times[-1]) if times else None}


def collect(cache, out, end_month="2026-05", repair_daily=False):
    start = ms("2020-01-01")
    year, month = map(int,end_month.split("-"))
    end = ms(f"{year+int(month==12)}-{month%12+1:02}-01")
    tasks = [(kind, month, cache) for month in months_until(end_month) for kind in KINDS]
    records, series = [], {k: [] for k in KINDS}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,(record, rows) in enumerate(pool.map(download_one,tasks)):
            records.append(record)
            series[record['kind']].extend(rows)
            if (i+1) % 20 == 0 or "error" in record:
                print(json.dumps({"completed":i+1,"total":len(tasks),"last":record['month'],"error":record.get('error')}),flush=True)
    validation = {k:validate_series(v,k,start,end) for k,v in series.items()}
    monthly_validation = validation
    restored = {k:0 for k in KINDS}
    if repair_daily:
        for kind in ("spot","perp","mark"):
            days=sorted(set(t[:10] for t in validation[kind]['missing']))
            indexed={r[0]:r for r in series[kind]}
            for day in days:
                record,rows=download_one((kind,day,cache))
                record['supplemental_daily']=True
                records.append(record)
                for r in rows:
                    if r[0] not in indexed:
                        indexed[r[0]]=r;restored[kind]+=1
                    elif indexed[r[0]]!=r:
                        record.setdefault('overlap_conflicts',[]).append(utc(r[0]))
                print(json.dumps({'daily':day,'kind':kind,'restored_total':restored[kind],'error':record.get('error')}),flush=True)
            series[kind]=[indexed[t] for t in sorted(indexed)]
        validation={k:validate_series(v,k,start,end) for k,v in series.items()}
    # Never interpolate holes or overwrite a previous snapshot.
    out = Path(out)
    out.mkdir(parents=True,exist_ok=True)
    blob = canonical({"start":start,"end":end,"series":series})
    payload = out / "binance-hourly.json.gz"
    if payload.exists() and gzip.decompress(payload.read_bytes()) != blob:
        raise ValueError("Refusing to replace a different dataset")
    payload.write_bytes(gzip.compress(blob,mtime=0))
    manifest = {"schema":1,"downloaded_at":utc(int(datetime.now(timezone.utc).timestamp()*1000)),
                "symbol":"BTCUSDT","quote":"USDT","dataset_sha256":sha(blob),
                "files":records,"validation":validation,"monthly_validation":monthly_validation,
                "restored_from_daily":restored,"interpolated_rows":0,
                "archive_errors":sum('error' in x for x in records)}
    (out / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"validation":{k:{a:b for a,b in v.items() if a not in ('missing','short_bars')} for k,v in validation.items()},"restored_from_daily":restored,"archive_errors":manifest['archive_errors'],"sha256":sha(blob)},ensure_ascii=False),flush=True)


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--cache",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--end-month",default="2026-05")
    p.add_argument("--repair-daily",action="store_true")
    args=p.parse_args()
    collect(args.cache,args.out,args.end_month,args.repair_daily)
