"""Independent raw-price/ledger audit, paired block bootstrap and offline replay.

This does not establish profitability. It checks numerical/chronological claims.
"""
import argparse
import gzip
import hashlib
import json
import math
import socket
from pathlib import Path

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
HOUR=3_600_000
DAY=24*HOUR
CANDIDATES=('E_SPOT','E_PERP','E_LS','B_SPOT','C_ALWAYS','C_FILTER','P_PAIR','M_GBDT','M_RIDGE')
KEYS=('BS','BP','EP')


def read(path):
    data=Path(path).read_bytes()
    return json.loads(gzip.decompress(data) if str(path).endswith('.gz') else data)


def save(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')))


def audit(directory):
    from datetime import datetime
    payload=read(ROOT/'data/search-1458/market.json.gz')
    raw=payload['series']
    rows={'BS':raw['BTCUSDT']['spot'],'BP':raw['BTCUSDT']['perp'],'EP':raw['ETHUSDT']['perp']}
    marks={'BS':rows['BS'],'BP':raw['BTCUSDT']['mark'],'EP':raw['ETHUSDT']['mark']}
    rows={k:{r[0]:r for r in v} for k,v in rows.items()}
    marks={k:{r[0]:r for r in v} for k,v in marks.items()}
    funds={k:{r[0]:r for r in raw[s]['funding']} for k,s in [('BP','BTCUSDT'),('EP','ETHUSDT')]}
    reports=[]
    for path in sorted(directory.glob('*.json.gz')):
        r=read(path);model=r['model'];q={k:0. for k in KEYS};cash=1000.;fees=funding=impact=0.
        peak=1000.;dd=0.;held_stale=0;minimum_margin=None;breaches=0
        start=int(datetime.fromisoformat(r['start'].replace('Z','+00:00')).timestamp()*1000)
        end=int(datetime.fromisoformat(r['end'].replace('Z','+00:00')).timestamp()*1000)
        bytime={};days={d['time']:d for d in r['daily']};latest={k:None for k in KEYS}
        errors={'equity':0.,'cash':0.,'position':0.,'fees':0.,'funding':0.,'impact':0.,'drawdown':0.}
        def close(actual,expected,kind):
            errors[kind]=max(errors[kind],abs(actual-expected))
            assert math.isclose(actual,expected,abs_tol=1e-7,rel_tol=1e-10),(path.name,kind,actual,expected)
        for e in r['events']:bytime.setdefault(e['time'],[]).append(e)
        def value(prices):return cash+sum(q[k]*prices[k] for k in KEYS)
        def observe(prices):
            nonlocal peak,dd
            eq=value(prices);peak=max(peak,eq);dd=max(dd,100*(1-eq/peak));return eq
        def fill(e):
            nonlocal cash,fees,impact
            k=e['instrument'];delta=e['delta'];t=e['time']
            ref=rows[k][end-HOUR][4] if t==end else rows[k][t][1]
            px=ref*(1+math.copysign(model['impact_bps']/10000,delta))
            fee=abs(delta)*px*model['fee_bps'][k]/10000
            slip=abs(delta)*ref*model['impact_bps']/10000
            close(e['reference'],ref,'equity');close(e['price'],px,'equity');close(e['fee'],fee,'fees');close(e['impact'],slip,'impact')
            if e['source_time'] is not None:
                assert e['time']==e['source_time']+HOUR*(1+model['extra_delay_hours'])
                step=.00001 if k=='BS' else .001
                assert abs(e['position']/step-round(e['position']/step))<1e-6
                reducing=q[k]*delta<0 and abs(e['position'])<abs(q[k])
                assert abs(delta)*px>=({'BS':5,'BP':50,'EP':20}[k])-1e-7 or (k!='BS' and reducing)
            q[k]+=delta
            if abs(q[k])<1e-12:q[k]=0.
            cash-=delta*px+fee;fees+=fee;impact+=slip
            close(q[k],e['position'],'position')
        for t in range(start,end,HOUR):
            op={};cl={}
            for k in KEYS:
                bar=marks[k].get(t)
                if bar is None:
                    assert k=='BS' and latest[k] is not None
                    op[k]=cl[k]=latest[k]
                    if q[k]:held_stale+=1
                else:op[k]=bar[1];cl[k]=bar[4];latest[k]=bar[4]
            event=bytime.get(t,[]);fe=[e for e in event if e['kind']=='funding']
            expected=[k for k in ('BP','EP') if q[k] and t in funds[k]]
            assert [e['instrument'] for e in fe]==expected
            for e in fe:
                k=e['instrument'];f=funds[k][t];amount=-q[k]*marks[k][t][1]*f[2]
                close(e['cashflow'],amount,'funding');close(e['position'],q[k],'position')
                assert e['rate']==f[2] and e['observed_time']==f[3]
                cash+=amount;funding+=amount
            observe(op)
            for e in event:
                if e['kind']=='fill':fill(e)
            observe(op);eq=observe(cl)
            if r['strategy'] in ('E_SPOT','B_SPOT','V_SPOT','H_SPOT'):assert cash>=-1e-7
            if r['strategy'] in ('C_ALWAYS','C_FILTER'):close(q['BS']+q['BP'],0.,'position')
            if q['BP'] or q['EP']:
                adverse={k:marks[k][t][3 if q[k]>0 else 2] for k in ('BP','EP')}
                collateral=cash+sum(q[k]*adverse[k] for k in ('BP','EP'))
                ratio=collateral/sum(abs(q[k])*adverse[k] for k in ('BP','EP'))
                minimum_margin=ratio if minimum_margin is None else min(minimum_margin,ratio)
                breaches+=int(ratio<.05)
            if t+HOUR in days:
                d=days[t+HOUR]
                if t+HOUR==end:
                    for e in bytime.get(end,[]):assert e['kind']=='fill';fill(e)
                    eq=observe({k:rows[k][end-HOUR][4] for k in KEYS})
                close(eq,d['equity'],'equity');close(cash,d['cash'],'cash')
                for k in KEYS:close(q[k],d['positions'][k],'position')
                for k,x in [('fees',fees),('funding',funding),('impact',impact)]:close(x,d[k],k)
                close(100*(1-eq/peak),d['drawdown_pct'],'drawdown')
        met=r['metrics']
        close(cash,met['equity'],'equity');close(dd,met['max_drawdown_pct'],'drawdown')
        assert breaches==met['margin_buffer_breach_hours'] and held_stale==met['stale_held_spot_hours']
        if minimum_margin is not None:close(minimum_margin,met['min_adverse_margin_ratio'],'equity')
        for train in r.get('training',[]):assert train['last_label_time']<=train['fit_time']-2*HOUR
        for group in r['periods'].values():close(sum(p['pnl'] for p in group.values()),met['net_pnl'],'equity')
        reports.append({'file':path.name,'daily_points':len(r['daily']),'events':len(r['events']),'max_absolute_errors':errors,'passed':True})
    out={'runs':len(reports),'total_daily_points':sum(x['daily_points'] for x in reports),'total_events':sum(x['events'] for x in reports),
         'maximum_error':max(max(x['max_absolute_errors'].values()) for x in reports),'audits':reports,
         'scope':'independent raw-price/funding cash ledger, hourly drawdown and collateral; not exchange fill or liquidation proof'}
    save(directory/'independent-audit.json',out)
    print('AUDIT',json.dumps({k:v for k,v in out.items() if k!='audits'}),flush=True)


def statistics(directory):
    out={'resamples':2000,'seed':1458,'candidate_count':9,'benchmark':'V_SPOT','method':'paired circular moving-block bootstrap, percentile intervals; zero risk-free rate',
         'limitations':['Historical exploratory comparison; no new blind holdout.','Bonferroni endpoints have only about 6 tail replicates at B=2000: approximate, not calibrated proof.','Correcting nine candidates does not remove researcher choice, prior experiments, regime change or unspecified trials.'], 'periods':{}}
    def sharpe(x):
        std=x.std(axis=-1,ddof=1);return np.divide(x.mean(axis=-1)*np.sqrt(365),std,out=np.zeros_like(std),where=std>1e-14)
    for stage in ('main','recent'):
        bench=np.asarray(read(directory/f'{stage}-V_SPOT.json.gz')['daily_returns'])
        ns=len(bench);result={n:[] for n in CANDIDATES}
        for length in (14,7,28):
            rng=np.random.default_rng(1458+length)
            starts=rng.integers(0,ns,size=(2000,math.ceil(ns/length)))
            indices=((starts[...,None]+np.arange(length))%ns).reshape(2000,-1)[:,:ns]
            bs=sharpe(bench[indices]);a=.05/(2*9)
            for n in CANDIDATES:
                values=np.asarray(read(directory/f'{stage}-{n}.json.gz')['daily_returns'])
                assert len(values)==ns
                sampled=values[indices];means=sampled.mean(axis=1)*100;diff=sharpe(sampled)-bs
                result[n].append({'block_days':length,'resamples':2000,'observed_mean_daily_pct':float(values.mean()*100),
                    'observed_sharpe_difference':float(sharpe(values)-sharpe(bench)),
                    'mean_daily_pct_ci95':np.quantile(means,[.025,.975]).tolist(),
                    'sharpe_difference_ci95':np.quantile(diff,[.025,.975]).tolist(),
                    'mean_daily_pct_bonferroni9':np.quantile(means,[a,1-a]).tolist(),
                    'sharpe_difference_bonferroni9':np.quantile(diff,[a,1-a]).tolist()})
        out['periods'][stage]=result
    save(directory/'uncertainty.json',out)
    print('UNCERTAINTY',json.dumps(out['periods']['main']['E_SPOT'][0]),flush=True)


def replay(directory, destination):
    # Load optional libraries first, then disallow all internet connection paths.
    import sklearn, xgboost  # noqa: F401
    from btc_perp_bot.research.strategy_search import run
    def deny(*args,**kwargs):raise AssertionError('Network attempt during offline replay')
    socket.create_connection=deny;socket.socket.connect=deny;socket.socket.connect_ex=deny;socket.socket.sendto=deny
    run('main',destination);run('recent',destination)
    files=sorted(directory.glob('*.json.gz'))+[directory/'main-summary.json',directory/'recent-summary.json',directory/'selection.json']
    for p in files:assert p.read_bytes()==(destination/p.name).read_bytes(),p.name
    result={'network_disabled':True,'files_byte_identical':len(files),'runs_byte_identical':len(list(directory.glob('*.json.gz'))),
            'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    save(directory/'reproduction.json',result);print('REPLAY',len(files),'byte-identical files',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',default='runs/search-1458');p.add_argument('--replay');args=p.parse_args()
    directory=Path(args.directory)
    audit(directory);statistics(directory)
    if args.replay:replay(directory,Path(args.replay))
