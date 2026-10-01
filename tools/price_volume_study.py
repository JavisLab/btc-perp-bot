"""Offline, preregistered OHLCV event diagnostics; NOT an account backtest."""
import argparse
import csv
import gzip
import io
import json
import math
import zipfile
from decimal import Decimal
from pathlib import Path

import numpy as np

from btc_perp_bot.research.archive import HOUR, DAY, canonical, ms, sha, utc

ROOT = Path(__file__).resolve().parents[1]
DIGEST = '9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4'
FAMILIES = ('B', 'F', 'P')
PERIODS = {'main': (ms('2022-01-01'), ms('2026-01-01')),
           'recent': (ms('2026-01-01'), ms('2026-09-01'))}
SCENARIOS = {'base': (1, 0), 'cost_x2': (2, 0), 'delay1': (1, HOUR)}
COLUMNS = ('time', 'open', 'high', 'low', 'close', 'volume', 'close_time',
           'quote_volume', 'trades', 'taker_buy_volume', 'taker_buy_quote_volume')


def write_fixed(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError('Refusing to replace different experiment output: ' + str(path))
    path.write_bytes(data)


def load_audited():
    raw = gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes())
    if sha(raw) != DIGEST:
        raise ValueError('Unexpected market dataset')
    market = json.loads(raw)
    original = {r[0]: r for r in market['series']['BTCUSDT']['perp']}
    paths = sorted((ROOT/'data/archive-1448/perp').glob('????-??.zip'))
    paths += sorted((ROOT/'data/archive-1458/BTCUSDT/perp').glob('????-??.zip'))
    rows, files, zero = [], [], []
    for path in paths:
        body = path.read_bytes()
        digest = path.with_suffix('.CHECKSUM').read_text().split()[0]
        if sha(body) != digest:
            raise ValueError('ZIP checksum failed')
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            if len(z.namelist()) != 1:
                raise ValueError('Archive layout')
            records = csv.reader(io.StringIO(z.read(z.namelist()[0]).decode()))
            n = 0
            for r in records:
                if r[0] == 'open_time':
                    continue
                if len(r) != 12:
                    raise ValueError('Kline schema')
                t, close = int(r[0]), int(r[6])
                d = [Decimal(x) for x in r[1:6]]
                o, h, l, c, v = d
                q, buy, bq = map(Decimal, (r[7], r[9], r[10]))
                trades = int(r[8])
                if not all(x.is_finite() for x in d+[q,buy,bq]):
                    raise ValueError('Non-finite value')
                if not (0 < l <= min(o,c) <= max(o,c) <= h and 0 <= buy <= v and 0 <= bq <= q and trades >= 0):
                    raise ValueError('Invalid OHLCV')
                eps = Decimal('0.00001')
                if not (l*v-eps <= q <= h*v+eps and l*buy-eps <= bq <= h*buy+eps):
                    raise ValueError('Volume/quote price outside OHLC')
                if (v == 0) != (q == 0) or (v == 0) != (trades == 0):
                    raise ValueError('Zero-volume/trade inconsistency')
                if t % HOUR or close != t+HOUR-1:
                    raise ValueError('Nonstandard perpetual bar')
                row = [t,float(o),float(h),float(l),float(c),float(v),close,
                       float(q),trades,float(buy),float(bq)]
                if [row[j] for j in (0,1,2,3,4,6)] != original.get(t):
                    raise ValueError('Price differs from previous dataset')
                if v == 0: zero.append(utc(t))
                rows.append(row); n += 1
        files.append({'path':str(path.relative_to(ROOT)), 'sha256':digest,'rows':n,
                      'url':'https://data.binance.vision/data/futures/um/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-'+path.stem+'.zip'})
    rows.sort(key=lambda x:x[0])
    expected = list(range(ms('2020-01-01'),ms('2026-09-01'),HOUR))
    if [r[0] for r in rows] != expected or len(rows) != len(original):
        raise ValueError('Duplicate/missing/unexpected timestamp')
    audit = {'market_sha256':DIGEST, 'ohlcv_sha256':sha(canonical(rows)),
             'columns':COLUMNS, 'files':files, 'rows':len(rows), 'first':utc(rows[0][0]),
             'end_exclusive':utc(rows[-1][0]+HOUR), 'zero_volume_hours':zero,
             'price_rows_equal':len(rows), 'interpolated_rows':0, 'missing_hours':0}
    return rows, market, audit


def aggregate(rows):
    if len(rows) % 4:
        raise ValueError('Incomplete four-hour block')
    bars = []
    for i in range(0,len(rows),4):
        part = rows[i:i+4]; t = part[0][0]
        if t%(4*HOUR) or [r[0] for r in part] != [t+j*HOUR for j in range(4)]:
            raise ValueError('Incomplete/alignment')
        bars.append({'t':t, 'o':part[0][1], 'h':max(r[2] for r in part),
                     'l':min(r[3] for r in part), 'c':part[-1][4],
                     'v':math.fsum(r[5] for r in part),
                     'buy':math.fsum(r[9] for r in part), 'rvol':None})
    for i in range(120,len(bars)):
        denom = float(np.median([bars[i-j*6]['v'] for j in range(1,21)]))
        if denom > 0: bars[i]['rvol'] = bars[i]['v']/denom
    return bars


def detect(bars):
    events = []
    for i in range(123,len(bars)):
        b = bars[i]
        if b['h'] == b['l'] or any(x['rvol'] is None for x in bars[i-2:i+1]):
            continue
        recent, previous = bars[i-20:i], bars[i-40:i-20]
        upper, lower = max(x['h'] for x in recent), min(x['l'] for x in recent)
        old_upper, old_lower = max(x['h'] for x in previous), min(x['l'] for x in previous)
        clv = (b['c']-b['l'])/(b['h']-b['l'])
        for side in (1,-1):
            location = clv >= .75 if side == 1 else clv <= .25
            if not location: continue
            breakout = b['c'] > upper if side == 1 else b['c'] < lower
            failure = (b['l'] < lower < b['c']) if side == 1 else (b['h'] > upper > b['c'])
            failure = failure and not (b['l'] < lower and b['h'] > upper)
            a, p, q = bars[i-3:i]
            pullback = ((upper > old_upper and lower > old_lower and a['c'] > p['c'] > q['c']
                         and b['c'] > q['h'] and b['c'] > b['o']) if side == 1 else
                        (upper < old_upper and lower < old_lower and a['c'] < p['c'] < q['c']
                         and b['c'] < q['l'] and b['c'] < b['o']))
            pullvol = (p['rvol']+q['rvol'])/2
            for family, match, passed in (
                ('B',breakout,b['rvol']>=1.5), ('F',failure,b['rvol']<=1.),
                ('P',pullback,pullvol<1 and b['rvol']>pullvol)):
                if match:
                    events.append({'family':family,'source':b['t']+4*HOUR,'side':side,
                                   'rvol':b['rvol'],'volume_pass':bool(passed)})
    return events


def payoff(event, prices, marks, funding, multiplier=1, extra_delay=0):
    entry = event['source']+HOUR+extra_delay; end = entry+DAY
    p, q = prices[entry][1], prices[end][1]; side = event['side']
    impact, fee = .00015*multiplier, .0005*multiplier
    filled_in, filled_out = p*(1+side*impact), q*(1-side*impact)
    gross = side*(q-p)
    impact_paid = gross-side*(filled_out-filled_in)
    fees = fee*(filled_in+filled_out)
    flow = -side*math.fsum(funding[t][2]*marks[t][1]
                         for t in range(entry+HOUR,end+HOUR,HOUR) if t in funding)
    scale = 10000/p
    return dict(event,entry=entry,exit=end,reference_entry=p,reference_exit=q,
                filled_entry=filled_in,filled_exit=filled_out,
                gross_bp=gross*scale,impact_bp=impact_paid*scale,fees_bp=fees*scale,
                funding_bp=flow*scale,net_bp=(gross-impact_paid-fees+flow)*scale)


def stats(events):
    if not events: return {'n':0,'mean_net_bp':None,'median_net_bp':None,'positive_pct':None}
    values = np.array([e['net_bp'] for e in events])
    return {'n':len(events),'mean_net_bp':float(values.mean()),'median_net_bp':float(np.median(values)),
            'positive_pct':float((values>0).mean()*100), 'min_net_bp':float(values.min()),
            **{f'mean_{key}':float(np.mean([e[key] for e in events]))
               for key in ('gross_bp','impact_bp','fees_bp','funding_bp')}}


def uncertainty(events, start, end, block_days):
    # Keep all overlapping events in their original calendar cluster. No iid trade bootstrap.
    width = block_days*DAY; blocks = math.ceil((end-start)/width)
    sums = np.zeros((blocks,3)); counts = np.zeros((blocks,3))
    for e in events:
        k = (e['entry']-start)//width; group = 1 if e['volume_pass'] else 2
        for g in (0,group): sums[k,g]+=e['net_bp']; counts[k,g]+=1
    rng = np.random.default_rng(1462+block_days)
    idx = rng.integers(0,blocks,size=(2000,blocks))
    ss, nn = sums[idx].sum(axis=1), counts[idx].sum(axis=1)
    means = np.divide(ss,nn,out=np.full(ss.shape,np.nan),where=nn>0)
    def ci(x):
        x = x[np.isfinite(x)]
        if len(x)<1900: return {'valid_replicates':len(x),'ci95':None,'ci_bonferroni6':None}
        return {'valid_replicates':len(x),'ci95':np.quantile(x,[.025,.975]).tolist(),
                'ci_bonferroni6':np.quantile(x,[.05/12,1-.05/12]).tolist()}
    return {'block_days':block_days,'blocks':blocks,'replicates':2000,
            'all':ci(means[:,0]),'volume_pass':ci(means[:,1]),
            'pass_minus_fail':ci(means[:,1]-means[:,2])}


def run(output, audit_only=False):
    rows, market, audit = load_audited(); bars = aggregate(rows)
    output = Path(output)
    audit['four_hour_bars'] = len(bars)
    write_fixed(output/'data-audit.json',canonical(audit))
    write_fixed(output/'ohlcv.json.gz',gzip.compress(canonical({'columns':COLUMNS,'rows':rows}),mtime=0))
    if audit_only:
        print(json.dumps({k:v for k,v in audit.items() if k not in ('files','columns')})); return
    events = detect(bars)
    original = market['series']['BTCUSDT']
    prices = {r[0]:r for r in original['perp']}; marks = {r[0]:r for r in original['mark']}
    funding = {r[0]:r for r in original['funding']}
    results = []; all_events = []
    for period,(start,end) in PERIODS.items():
        # Common events across all diagnostics: differing terminal inclusion cannot make a result win.
        selected = [e for e in events if start<=e['source'] and e['source']+2*HOUR+DAY<end]
        for scenario,(cost,delay) in SCENARIOS.items():
            rows = [dict(payoff(e,prices,marks,funding,cost,delay),period=period,scenario=scenario)
                    for e in selected]
            all_events.extend(rows)
            for family in FAMILIES:
                sample = [e for e in rows if e['family']==family]
                groups = {'all':sample,'volume_pass':[e for e in sample if e['volume_pass']],
                          'volume_fail':[e for e in sample if not e['volume_pass']]}
                result = {'period':period,'scenario':scenario,'family':family,
                          'groups':{k:stats(v) for k,v in groups.items()}}
                result['by_year_side'] = {k:{y:{s:stats([e for e in v if utc(e['entry'])[:4]==y and
                    (s=='both' or e['side']==(1 if s=='long' else -1))]) for s in ('both','long','short')}
                    for y in sorted({utc(e['entry'])[:4] for e in sample})} for k,v in groups.items()}
                if scenario=='base':
                    result['uncertainty'] = [uncertainty(sample,start,end,b) for b in (14,7,28)]
                results.append(result)
    priority = []
    for family in FAMILIES:
        gates = []
        for period,minimum in (('main',50),('recent',20)):
            base = next(r for r in results if (r['family'],r['period'],r['scenario'])==(family,period,'base'))
            stress = next(r for r in results if (r['family'],r['period'],r['scenario'])==(family,period,'cost_x2'))
            a,b = base['groups']['volume_pass'], stress['groups']['volume_pass']
            interval = base['uncertainty'][0]['pass_minus_fail']['ci_bonferroni6']
            gates.append({'period':period,'sufficient_events':a['n']>=minimum,
                          'net_positive':a['mean_net_bp'] is not None and a['mean_net_bp']>0,
                          'cost_x2_positive':b['mean_net_bp'] is not None and b['mean_net_bp']>0,
                          'adjusted_difference_positive':interval is not None and interval[0]>0})
        priority.append({'family':family,'gates':gates,
                         'eligible_for_next_study':all(v for g in gates for k,v in g.items() if k!='period')})
    report = {'type':'exploratory_event_study_not_account_backtest','spec':'docs/EXPERIMENT_1462.md',
              'market_sha256':DIGEST,'ohlcv_sha256':audit['ohlcv_sha256'],'results':results,
              'selection':priority,'real_trading':False}
    write_fixed(output/'results.json',canonical(report))
    write_fixed(output/'events.json.gz',gzip.compress(canonical(all_events),mtime=0))
    buf=io.StringIO(); writer=csv.DictWriter(buf,fieldnames=list(all_events[0]))
    writer.writeheader(); writer.writerows(all_events)
    write_fixed(output/'events.csv',buf.getvalue().encode())
    print(json.dumps({'summaries':len(results),'event_rows':len(all_events),'selection':priority,
        'base':[{'period':r['period'],'family':r['family'],'groups':r['groups']} for r in results if r['scenario']=='base']},ensure_ascii=False))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',default='runs/price-volume-1462');p.add_argument('--audit-only',action='store_true')
    args=p.parse_args();run(args.output,args.audit_only)
