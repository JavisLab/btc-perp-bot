"""Chronological OI inputs with explicit completion assumption and validity mask."""
import argparse
from decimal import Decimal
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];SOURCE=ROOT/'data/oi-history-20261002'
STEP=300000
sha=lambda b:hashlib.sha256(b).hexdigest()
canon=lambda x:(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def transform(row):
    t,q,v,*ratios=row
    usable=q is not None and v is not None and Decimal(q)>0 and Decimal(v)>0
    return {'source_time_ms':t,'observation_complete_assumed_ms':t+STEP,'oi_qty':q,'oi_value':v,'oi_usable':usable,'ratios':ratios}


def build(out):
    out.mkdir(parents=True,exist_ok=True);a=json.loads((SOURCE/'audit.json').read_bytes())
    clock=json.loads((ROOT/'data/oi-availability-20261002/clock-confirmation/verification.json').read_bytes())
    assert a['complete'] and clock['all_four_dates_match_288_quantity_and_value']
    manifest={'source_audit_sha256':sha((SOURCE/'audit.json').read_bytes()),'clock_confirmation_sha256':sha((ROOT/'data/oi-availability-20261002/clock-confirmation/verification.json').read_bytes()),
        'policy':'No interpolation, forward fill or timestamp overwrite. Explicit chronological order; zero/nonpositive OI quantity OR value makes oi_usable false. Observed completion +5m is an assumption beyond the checked dates; it is NOT publication availability.',
        'files':{}}
    for symbol in ['BTCUSDT','ETHUSDT']:
        target=out/(symbol+'.jsonl.gz');digest=hashlib.sha256();count=bad=0;last=None
        with target.open('wb') as f,gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0,compresslevel=6) as gz:
            for r in sorted([x for x in a['records'] if x['symbol']==symbol],key=lambda x:x['date']):
                raw=(SOURCE/'normalized'/symbol/(r['date']+'.json.gz')).read_bytes();decoded=gzip.decompress(raw)
                assert sha(raw)==r['normalized_gzip_sha256'] and sha(decoded)==r['normalized_sha256']
                for row in sorted(json.loads(decoded)['rows'],key=lambda r:r[0]):
                    assert last is None or row[0]>last
                    last=row[0];record=transform(row);body=canon(record);digest.update(body);gz.write(body);count+=1;bad+=int(not record['oi_usable'])
        assert count==a['summary'][symbol]['rows']
        manifest['files'][target.name]={'rows':count,'unusable_oi_rows':bad,'missing_timestamps_not_filled':a['summary'][symbol]['missing_rows'],
            'sha256':sha(target.read_bytes()),'uncompressed_sha256':digest.hexdigest()}
    (out/'manifest.json').write_bytes(canon(manifest));print(json.dumps(manifest,indent=2));return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'data/oi-inputs-20261002');a=p.parse_args();build(a.out)
