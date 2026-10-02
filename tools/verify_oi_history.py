"""Independent archive-to-normalized OI verification; no collector import."""
import calendar
from collections import Counter
import csv
import datetime
from decimal import Decimal,InvalidOperation
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'data/oi-history-20261002'
sha=lambda b:hashlib.sha256(b).hexdigest()


def main():
    a=json.loads((BASE/'audit.json').read_bytes());assert a['complete'] and a['verified_days']==3408
    checked=rows_checked=missing=0;counts={};zero_oi=[];gap_days=[]
    for record in a['records']:
        symbol,date=record['symbol'],record['date'];raw=BASE/'raw'/symbol/f'{symbol}-metrics-{date}.zip'
        packed=raw.read_bytes();checksum=raw.with_suffix('.zip.CHECKSUM').read_bytes()
        assert sha(packed)==record['zip_sha256']==checksum.decode().split()[0]
        assert sha(checksum)==record['checksum_sha256']
        normalized=(BASE/'normalized'/symbol/(date+'.json.gz')).read_bytes();decoded=gzip.decompress(normalized)
        assert sha(normalized)==record['normalized_gzip_sha256'] and sha(decoded)==record['normalized_sha256']
        clean=json.loads(decoded);target=clean['rows']
        with zipfile.ZipFile(io.BytesIO(packed)) as z:
            reader=csv.reader(io.StringIO(z.read(z.namelist()[0]).decode()));columns=next(reader);source=list(reader)
        assert clean['columns']==['time_ms',*columns[2:]] and len(source)==len(target)==record['rows']
        null=Counter();zero=Counter();negative=Counter();times=[]
        for src,dst in zip(source,target):
            t=calendar.timegm(datetime.datetime.strptime(src[0],'%Y-%m-%d %H:%M:%S').timetuple())*1000
            assert src[1]==symbol and dst[0]==t
            times.append(t)
            for name,original,normalized in zip(columns[2:],src[2:],dst[1:]):
                try:v=Decimal(original)
                except InvalidOperation:v=Decimal('NaN')
                if not v.is_finite():assert normalized is None;null[name]+=1
                else:
                    assert normalized is not None and Decimal(normalized)==v
                    if v==0:zero[name]+=1
                    if v<0:negative[name]+=1
            if dst[1] is not None and Decimal(dst[1])==0:zero_oi.append({'symbol':symbol,'time_ms':t})
            rows_checked+=1
        start=calendar.timegm(datetime.datetime.strptime(date,'%Y-%m-%d').timetuple())*1000
        expected=set(range(start,start+86400000,300000));gaps=sorted(expected-set(times))
        assert gaps==record['missing_times_ms']
        assert len(times)-len(set(times))==record['duplicates']
        assert sorted(t for t in times if t not in expected)==sorted(record['unexpected_times_ms'])
        assert (times==sorted(set(times)))==record['strictly_ordered']
        for c,key in [(null,'null_counts'),(zero,'zero_counts'),(negative,'negative_counts')]:
            assert all(c[n]==record[key].get(n,0) for n in set(c)|set(record[key]))
        counts.setdefault(symbol,{'null':Counter(),'zero':Counter(),'negative':Counter()})
        counts[symbol]['null'].update(null);counts[symbol]['zero'].update(zero);counts[symbol]['negative'].update(negative)
        if gaps:gap_days.append({'symbol':symbol,'date':date,'missing_times_ms':gaps})
        missing+=len(gaps);checked+=1
    assert rows_checked+missing==3408*288
    for symbol,cs in counts.items():
        for key in ['null','zero','negative']:
            assert all(cs[key][n]==a['summary'][symbol][key+'_counts'].get(n,0) for n in set(cs[key])|set(a['summary'][symbol][key+'_counts']))
    result={'daily_archives':checked,'rows':rows_checked,'missing_rows':missing,'all_archive_checksum_and_normalized_hashes_match':True,
        'independent_decimal_rows_equal':True,'zero_oi_observations':zero_oi,'gap_days':gap_days,
        'not_verified':'Economic truth of zero OI, ratio-window semantics, first-published real-time timestamps, archive vintage/revisions, investment edge'}
    (BASE/'verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('zero_oi_observations','gap_days')},indent=2))


if __name__=='__main__':main()
