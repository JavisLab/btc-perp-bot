"""Frozen ETH-only offline adapter. No exchange, account, wallet or order API."""
import argparse
import gzip
import importlib.util
import json
import math
from pathlib import Path

from btc_perp_bot.research.archive import canonical, sha, ms

ROOT = Path(__file__).resolve().parents[1]
ENGINE_SHA = '8274d1ebdf8fd2a97448693847e761ba47ce5a2280b4dd8996a61cb6655b8451'
AGGREGATE_SHA = 'f03cdfcdf1ddfd380e921e90a52d91a8558a37f39aa976fa52a830ff5eea9f01'
AUDIT_SHA = 'a3b8cb29c3749b2684aa15562ca0143356b7a462925386d3ec07087be3741771'
for filename, digest in [('structural_study.py', ENGINE_SHA), ('price_volume_study.py', AGGREGATE_SHA)]:
    if sha((ROOT/'tools'/filename).read_bytes()) != digest:
        raise ValueError('Frozen inherited implementation changed: '+filename)
# Private module namespace: BTC module and its outputs are never modified.
_spec = importlib.util.spec_from_file_location('_eth_frozen_engine', ROOT/'tools/structural_study.py')
engine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(engine)
IDS, LABELS, SCENARIOS, PERIODS = engine.IDS, engine.LABELS, engine.SCENARIOS, engine.PERIODS
STEP, HOUR, DAY = engine.STEP, engine.HOUR, engine.DAY
signals, exit_at_bar, bootstrap = engine.signals, engine.exit_at_bar, engine.bootstrap
write_fixed = engine.write_fixed


def sizing(equity, reference, stop, side, fee, impact, risk, stop_extra=0, min_notional=20):
    fill = reference*(1+side*impact)
    stopped = stop*(1-side*(impact+stop_extra))
    perunit = side*(fill-stopped)+fee*(fill+stopped)
    raw = min(equity*risk/perunit, equity/fill) if perunit > 0 and equity > 0 else 0.
    capped = min(raw, 2000.)
    rounded = math.floor((capped+1e-12)/.001)*.001
    reason = 'invalid_risk' if raw <= 0 else 'minimum_qty' if rounded < .001 else 'minimum_notional' if rounded*fill < min_notional else None
    accepted = rounded if reason is None else 0.
    return {'equity':equity, 'reference':reference, 'stop':stop, 'side':side,
            'fee_rate':fee, 'impact_rate':impact, 'stop_extra':stop_extra, 'risk_fraction':risk,
            'risk_budget':equity*risk, 'fill':fill, 'stopped_fill':stopped, 'loss_per_unit':perunit,
            'raw_qty':raw, 'capped_qty':capped, 'rounded_qty':rounded, 'accepted_qty':accepted,
            'raw_notional':raw*fill, 'rounded_notional':rounded*fill,
            'raw_stop_risk':raw*perunit, 'rounded_stop_risk':rounded*perunit,
            'rounding_risk_loss':(capped-rounded)*perunit,
            'min_notional':min_notional, 'reject_reason':reason, 'max_qty_capped':raw>2000.}


def sized(*args, **kw):
    return sizing(*args, **kw)['accepted_qty']


def simulate(*args, min_notional=20, **kw):
    attempts = []
    def size_adapter(*a):
        d = sizing(*a, min_notional=min_notional)
        d['attempt_index'] = len(attempts)
        attempts.append(d)
        return d['accepted_qty']
    original = engine.sized
    engine.sized = size_adapter
    try:
        result = engine.simulate(*args, **kw)
    finally:
        engine.sized = original
    accepted = [a for a in attempts if a['accepted_qty']]
    entries = [e for e in result['events'] if e['kind']=='entry']
    assert len(accepted)==len(entries)
    for a, e in zip(accepted, entries):
        a.update(time=e['time'], source=e['source'])
    result.update(symbol='ETHUSDT', sizing=attempts)
    result['config'].update(min_notional=min_notional, qty_step=.001, min_qty=.001, max_market_qty=2000.)
    result['summary']['sizing'] = {'attempts':len(attempts), 'accepted':len(accepted),
        'minimum_notional_rejects':sum(a['reject_reason']=='minimum_notional' for a in attempts),
        'minimum_qty_rejects':sum(a['reject_reason']=='minimum_qty' for a in attempts),
        'maximum_qty_caps':sum(a['max_qty_capped'] for a in attempts),
        'accepted_rounding_risk_loss':math.fsum(a['rounding_risk_loss'] for a in accepted)}
    return result


def load():
    source = ROOT/'data/eth-transfer-20261002'
    if sha((source/'audit.json').read_bytes()) != AUDIT_SHA:
        raise ValueError('Frozen ETH audit changed')
    audit = json.loads((source/'audit.json').read_bytes())
    def read(name):
        packed = (source/name).read_bytes(); raw = gzip.decompress(packed)
        expected = audit['artifacts'][name]
        if sha(packed)!=expected['gzip_sha256'] or sha(raw)!=expected['uncompressed_sha256']:
            raise ValueError('Frozen ETH dataset changed: '+name)
        return json.loads(raw)
    rows = read('bars-repaired.json.gz')['rows']
    hourly = read('hourly-ohlcv.json.gz')['rows']
    mf = read('mark-funding.json.gz'); mark = {r[0]:r[1] for r in mf['mark']}
    funding = {r[0]:{'rate':r[2], 'reference':mark[r[0]], 'raw_time':r[3]} for r in mf['funding']}
    return rows, engine.aggregate(hourly), funding, audit


def run(out, period):
    out = Path(out); rows, bars, funding, audit = load(); plans, trails = signals(bars)
    write_fixed(out/'signals.json.gz', gzip.compress(canonical({'signals':plans, 'trails':trails,
        'fine_sha256':audit['artifacts']['bars-repaired.json.gz']['uncompressed_sha256']}), mtime=0))
    start, end = PERIODS[period]; summaries = {}; uncertainty = {}
    conflicts = {ms(c['time'].replace('Z','')) for c in audit['unresolved_conflicts']}
    for name in IDS:
        summaries[name] = {}
        for scenario, config in {**SCENARIOS, 'min50':{'min_notional':50}}.items():
            result = simulate(rows, plans[name], trails, funding, name, start, end, conflict_hours=conflicts, **config)
            result.update(period=period, scenario=scenario)
            write_fixed(out/f'{period}-{name}-{scenario}.json.gz', gzip.compress(canonical(result), mtime=0))
            summaries[name][scenario] = result['summary']
            if scenario=='base':uncertainty[name]=[bootstrap(result['daily'], n) for n in (7,14,28)]
        print(json.dumps({'period':period,'family':name,'base':summaries[name]['base']},ensure_ascii=False),flush=True)
    result = {'period':period, 'summaries':summaries, 'uncertainty':uncertainty}
    if period=='main':
        gates = {}; selection = []
        for name, s in summaries.items():
            b, c = s['base'], s['cost_x2']
            gate = {'cagr':b['cagr_pct']>=10,'sharpe':b['sharpe']>=.8,'drawdown':b['dd_pct']<=25,
                    'years':b['positive_years']>=3,'cost_x2':c['net']>0,'ex_best_quarter':b['ex_best_quarter_pct']>0,
                    'margin':b['margin_breaches']==0,'trades':b['trades']>=100}
            gates[name]=gate
            if all(gate.values()):selection.append(name)
        # Spec tie breaker: lower turnover (sum of entry+exit notional).
        def rank(name):
            account=json.loads(gzip.decompress((out/f'main-{name}-base.json.gz').read_bytes()))
            turnover=math.fsum(t['qty']*(t['fill']+t['exit_fill']) for t in account['trades'])
            return (-min(summaries[name][s]['cagr_pct']/max(summaries[name][s]['dd_pct'],1e-9) for s in ('base','cost_x2')), turnover)
        selection.sort(key=rank)
        result.update(gates=gates, ranked_passes=selection)
        write_fixed(out/'selection.json', canonical({'ranked_passes':selection,'gates':gates,'recent_used':False}))
    write_fixed(out/f'{period}-summary.json', canonical(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--period',choices=PERIODS,required=True)
    a=p.parse_args();run(a.out,a.period)
