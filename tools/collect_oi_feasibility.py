"""Bounded official OI archive feasibility audit. No prices/returns/order APIs."""
import concurrent.futures
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data/oi-availability-20261002'
FIRST=Path('/home/ubuntu/.openclaw/workspace/tmp/eth-performance-20261002/oi-availability')
NS={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
DAYS=['2022-01-01','2022-06-23','2022-07-04','2023-11-14','2024-10-28','2025-01-29','2025-12-31','2026-01-01','2026-08-31']


def sha(body):return hashlib.sha256(body).hexdigest()


def get(url,path):
    if path.exists():return path.read_bytes()
    with urllib.request.urlopen(url,timeout=40) as r:
        if r.status!=200:raise ValueError(f'HTTP {r.status}: {url}')
        body=r.read()
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body);return body


def inventory(symbol):
    prefix=f'data/futures/um/daily/metrics/{symbol}/';marker=None;objects=[];pages=[]
    page=0
    while True:
        params={'delimiter':'/','prefix':prefix,'max-keys':1000}
        if marker:params['marker']=marker
        url='https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?'+urllib.parse.urlencode(params)
        path=OUT/'listing'/f'{symbol}-{page}.xml'
        if page==0 and not path.exists():
            original=FIRST/('btc-listing.xml' if symbol=='BTCUSDT' else 'eth-listing.xml')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(original.read_bytes())
        body=get(url,path);tree=ET.fromstring(body)
        entries=[]
        for obj in tree.findall('s:Contents',NS):
            entries.append({x.tag.split('}')[-1]:x.text for x in obj})
        objects+=entries;pages.append({'page':page,'url':url,'sha256':sha(body),'objects':len(entries)})
        if tree.findtext('s:IsTruncated',namespaces=NS)!='true':break
        next_marker=tree.findtext('s:NextMarker',namespaces=NS)
        assert next_marker and next_marker!=marker
        marker=next_marker;page+=1
    keys=[x['Key'] for x in objects];assert len(keys)==len(set(keys))
    zips={x['Key'][-14:-4]:x for x in objects if x['Key'].endswith('.zip')}
    for date in zips:dt.date.fromisoformat(date)
    start=dt.date(2022,1,1);end=dt.date(2026,9,1)
    expected=[(start+dt.timedelta(days=i)).isoformat() for i in range((end-start).days)]
    missing=[d for d in expected if d not in zips]
    missing_checksums=[d for d in expected if d in zips and zips[d]['Key']+'.CHECKSUM' not in keys]
    months={}
    for day in zips:months[day[:7]]=months.get(day[:7],0)+1
    sample_days=sorted(set(DAYS+[min(zips),max(zips)]))
    return {'symbol':symbol,'pages':pages,'listed_objects':len(objects),'zip_days':len(zips),'first_zip_day':min(zips),'last_zip_day':max(zips),
        'evaluation_expected_days':len(expected),'evaluation_present_zip_days':sum(d in zips for d in expected),
        'evaluation_missing_days':missing,'evaluation_missing_checksum_days':missing_checksums,'monthly_zip_counts':months,
        'sample_days':sample_days,'objects':objects}


def sample(symbol,date):
    filename=f'{symbol}-metrics-{date}.zip';url=f'https://data.binance.vision/data/futures/um/daily/metrics/{symbol}/{filename}'
    rec={'symbol':symbol,'day':date,'url':url}
    try:
        p=OUT/'samples'/filename;body=get(url,p);checksum=get(url+'.CHECKSUM',p.with_suffix('.zip.CHECKSUM'))
        assert sha(body)==checksum.decode().split()[0]
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            assert len(z.namelist())==1
            text=z.read(z.namelist()[0]).decode();reader=csv.DictReader(io.StringIO(text));rows=list(reader);columns=reader.fieldnames
        times=[];negative={};nonfinite={};zeros={};symbols=set();minimum={};maximum={}
        for r in rows:
            stamp=dt.datetime.fromisoformat(r['create_time']).replace(tzinfo=dt.timezone.utc);times.append(int(stamp.timestamp()))
            symbols.add(r['symbol'])
            for key,value in r.items():
                if key in ('create_time','symbol'):continue
                try:number=float(value)
                except ValueError:nonfinite[key]=nonfinite.get(key,0)+1;continue
                if not math.isfinite(number):nonfinite[key]=nonfinite.get(key,0)+1;continue
                if number<0:negative[key]=negative.get(key,0)+1
                if number==0:zeros[key]=zeros.get(key,0)+1
                minimum[key]=min(minimum.get(key,number),number);maximum[key]=max(maximum.get(key,number),number)
        midnight=int(dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone.utc).timestamp());expected=list(range(midnight,midnight+86400,300))
        rec.update(sha256=sha(body),checksum_sha256=sha(checksum),columns=columns,rows=len(rows),symbols=sorted(symbols),
            first_time=rows[0]['create_time'] if rows else None,last_time=rows[-1]['create_time'] if rows else None,
            missing_5m_times=[dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat() for t in sorted(set(expected)-set(times))],
            unexpected_times=[t for t in times if t not in expected],duplicate_times=len(times)-len(set(times)),strictly_ordered=times==sorted(set(times)),
            negative_values=negative,nonfinite_values=nonfinite,zero_values=zeros,minimum=minimum,maximum=maximum,checksum_verified=True)
    except Exception as e:rec['error']=str(e)
    return rec


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:inventories=list(pool.map(inventory,['BTCUSDT','ETHUSDT']))
    tasks=[(x['symbol'],d) for x in inventories for d in x['sample_days']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:samples=list(pool.map(lambda x:sample(*x),tasks))
    source_manifest=json.loads((FIRST/'sources.json').read_bytes())
    report={'scope':'Archive existence and preregistered small quality sample only; no strategy/returns',
        'evaluation':'[2022-01-01,2026-09-01) UTC','plan_commit':'fdf9efb','inventories':inventories,'samples':samples,
        'sources':source_manifest,'interpretation':[
            'ZIP/CHECKSUM object presence is not full intraday coverage; only listed sample days were opened.',
            'LastModified is current object metadata, not first publication or causal real-time availability.',
            'Official public-data README says next-day daily availability and permits archive revisions.',
            'OI value is an outstanding-position snapshot, not a trade flow; taker ratio is not volume.',
            '202 empty developer-document responses are failed document retrieval, not validated semantics.',
            'Known 1h taker buy and historical funding are already cached; no synthetic replacement or re-collection.']}
    target=OUT/'feasibility.json';target.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
    brief={'inventory':[{k:x[k] for k in ['symbol','listed_objects','zip_days','first_zip_day','last_zip_day','evaluation_expected_days','evaluation_present_zip_days','evaluation_missing_days','evaluation_missing_checksum_days']} for x in inventories],
        'sample_archives':len(samples),'verified_samples':sum(x.get('checksum_verified',False) for x in samples),
        'sample_missing_rows':sum(len(x.get('missing_5m_times',[])) for x in samples),'sample_errors':[x for x in samples if 'error' in x],
        'sample_nonfinite':[{'symbol':x['symbol'],'day':x['day'],'values':x.get('nonfinite_values')} for x in samples if x.get('nonfinite_values')]}
    (OUT/'summary.json').write_text(json.dumps(brief,ensure_ascii=False,sort_keys=True,indent=2)+'\n');print(json.dumps(brief,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
