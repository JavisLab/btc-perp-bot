"""Independent raw-archive signal enumeration and Decimal cash-flow verification."""
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
import zipfile
from decimal import Decimal as D
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
H=3600000


def main():
    out=ROOT/'runs/price-volume-1462'
    audit=json.loads((out/'data-audit.json').read_text())
    raw={}
    for rec in audit['files']:
        path=ROOT/rec['path'];body=path.read_bytes()
        assert hashlib.sha256(body).hexdigest()==rec['sha256']
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            for row in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
                if row[0]=='open_time':continue
                raw[int(row[0])]=row
    times=sorted(raw);bars=[]
    for j in range(0,len(times),4):
        rr=[raw[t] for t in times[j:j+4]]
        bars.append([times[j],float(rr[0][1]),max(float(r[2]) for r in rr),
                     min(float(r[3]) for r in rr),float(rr[-1][4]),math.fsum(float(r[5]) for r in rr)])
    ratios={}
    for i in range(120,len(bars)):
        denom=statistics.median(bars[j][5] for j in range(i-120,i,6))
        if denom:ratios[i]=bars[i][5]/denom
    # Enumerate all matching raw OHLCV events, not merely the events the study elected to save.
    signals=set()
    for i in range(123,len(bars)):
        t,o,high,low,close,v=bars[i]
        if high==low or any(j not in ratios for j in (i-2,i-1,i)):continue
        hh=max(b[2] for b in bars[i-20:i]);ll=min(b[3] for b in bars[i-20:i])
        oldh=max(b[2] for b in bars[i-40:i-20]);oldl=min(b[3] for b in bars[i-40:i-20])
        location=(close-low)/(high-low); pull=(ratios[i-2]+ratios[i-1])/2
        side=1 if location>=.75 else -1 if location<=.25 else 0
        if not side:continue
        if (side>0 and close>hh) or (side<0 and close<ll):
            signals.add(('B',t+4*H,side,ratios[i]>=1.5))
        if not (high>hh and low<ll) and ((side>0 and low<ll<close) or (side<0 and high>hh>close)):
            signals.add(('F',t+4*H,side,ratios[i]<=1))
        c1,c2,c3=[bars[k][4] for k in (i-3,i-2,i-1)]
        if (side>0 and hh>oldh and ll>oldl and c1>c2>c3 and close>bars[i-1][2] and close>o) or (
            side<0 and hh<oldh and ll<oldl and c1<c2<c3 and close<bars[i-1][3] and close<o):
            signals.add(('P',t+4*H,side,pull<1 and ratios[i]>pull))
    data=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes())
    assert hashlib.sha256(data).hexdigest()==audit['market_sha256']
    market=json.loads(data)['series']['BTCUSDT'];marks={r[0]:D(str(r[1])) for r in market['mark']}
    funding={}
    for directory in ('data/archive-1448/funding','data/archive-1458/BTCUSDT/funding'):
        for path in sorted((ROOT/directory).glob('????-??.zip')):
            body=path.read_bytes()
            assert hashlib.sha256(body).hexdigest()==path.with_suffix('.CHECKSUM').read_text().split()[0]
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
                    if not r[0].isdigit():continue
                    t=int(r[0]);funding[t//H*H]=D(r[2])
    assert {t:float(v) for t,v in funding.items()}=={r[0]:r[2] for r in market['funding']}
    events=json.loads(gzip.decompress((out/'events.json.gz').read_bytes()))
    windows={'main':(1640995200000,1767225600000),'recent':(1767225600000,1788220800000)}
    max_error=0.
    for period,(start,end) in windows.items():
        expected={s for s in signals if start<=s[1] and s[1]+26*H<end}
        for scenario in ('base','cost_x2','delay1'):
            saved=[e for e in events if e['period']==period and e['scenario']==scenario]
            assert {(e['family'],e['source'],e['side'],e['volume_pass']) for e in saved}==expected
            assert len(saved)==len(expected)
    for e in events:
        sign=D(e['side']);entry=e['source']+(2 if e['scenario']=='delay1' else 1)*H;exit=entry+24*H
        assert e['entry']==entry and e['exit']==exit
        p,q=D(raw[entry][1]),D(raw[exit][1]); multiplier=2 if e['scenario']=='cost_x2' else 1
        slip=D('0.00015')*multiplier; fee=D('0.0005')*multiplier
        pin=p*(1+sign*slip);pout=q*(1-sign*slip)
        carry=sum((-sign*funding[t]*marks[t] for t in range(entry+H,exit+H,H) if t in funding),D(0))
        components={'gross_bp':sign*(q-p),'impact_bp':(p+q)*slip,
                    'fees_bp':(pin+pout)*fee,'funding_bp':carry,
                    'net_bp':sign*(pout-pin)-(pin+pout)*fee+carry}
        for key,value in components.items():
            error=abs(float(value/p*10000)-e[key]);max_error=max(max_error,error);assert error<1e-8
    report=json.loads((out/'results.json').read_text());checked=0
    for r in report['results']:
        ee=[e for e in events if (e['period'],e['scenario'],e['family'])==(r['period'],r['scenario'],r['family'])]
        for name,group in r['groups'].items():
            values=[e['net_bp'] for e in ee if name=='all' or e['volume_pass']==(name=='volume_pass')]
            assert len(values)==group['n']
            if values:assert abs(statistics.mean(values)-group['mean_net_bp'])<1e-10
            checked+=1
    proof={'independent_raw_signal_sets_equal':True,'rows':len(events),'summary_groups':checked,
           'raw_funding_rows_checked':len(funding),'max_component_error_bp':max_error,
           'raw_price_files_checked':len(audit['files']),'real_account_or_orders':False}
    (out/'verification.json').write_text(json.dumps(proof,sort_keys=True))
    print(json.dumps(proof))


if __name__=='__main__':main()
