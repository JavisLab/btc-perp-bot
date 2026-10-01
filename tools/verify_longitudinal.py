"""Independent event/cash-flow/day-end audit plus network-disabled reproducibility."""
import json
import math
import socket
from pathlib import Path

from btc_perp_bot.research.archive import DAY,HOUR,ms,canonical,sha
from btc_perp_bot.research.longitudinal import Costs,load_data,simulate

ROOT=Path(__file__).resolve().parents[1]
def deny(*args,**kwargs):raise AssertionError('Offline verification attempted network access')
socket.socket=deny
data,manifest=load_data(ROOT/'data/longitudinal-1448-repaired/binance-hourly.json.gz',ROOT/'data/longitudinal-1448-repaired/manifest.json')
legacy=json.loads((ROOT/'data/research-1428-btc-1h.json').read_text())
rows=[[b['t'],*[float(b[k]) for k in ('o','h','l','c')],b['t']+HOUR-1] for b in legacy['candles']]
bytime={r[0]:r for r in rows}
hl={'series':{'perp':rows,'mark':rows,'spot':[], 'funding':[
    [f['time'],1,float(f['rate']),f['observed_time'],bytime[f['time']-HOUR][4]] for f in legacy['funding'] if f['time']-HOUR in bytime]}}
audits=[]
for path in sorted((ROOT/'runs/longitudinal-1448').glob('*.json')):
    report=json.loads(path.read_text());source=hl if report['period']=='hl_regression' else data
    costs=Costs(fee=4.5,step=.00001,minimum=10,spot_fee=7,spot_minimum=10) if report['period'].startswith('hl_') else Costs()
    for label,run in list(report['results'].items())+list(report['stress'].items()):
        model=run['model'];start=ms(run['start'].replace('Z','+00:00'));end=ms(run['end'].replace('Z','+00:00'))
        rerun=simulate(source,run['strategy'],start,end,costs,delay=model['delay_hours'],
                       multiplier=2 if label=='cost_x2' else 1.0,funding_scale=model['funding_reference_scale'])
        if canonical(rerun)!=canonical(run):raise AssertionError(f'Non-reproducible {path.name}/{label}')
        spot=run['strategy']=='spot_hold';prices={r[0]:r for r in source['series']['spot' if spot else 'mark']}
        funds={r[0]:r for r in source['series']['funding']}
        q=0.0;cash=1000.0;event_index=0;residual=0.0
        for day in run['daily']:
            while event_index<len(run['events']):
                e=run['events'][event_index]
                if e['time']>day['time'] or (e['time']==day['time'] and day['time']!=end):break
                if e['kind']=='fill':
                    if e['source_time'] is not None and e['time']<e['source_time']+HOUR*(1+model['delay_hours']):raise AssertionError('Lookahead')
                    cash-=e['delta']*e['price']+e['fee'];q+=e['delta']
                    assert math.isclose(e['fee'],abs(e['delta'])*e['price']*model['fee_bps']/10000,abs_tol=1e-9)
                else:
                    f=funds[e['time']]
                    ref=(f[4] if len(f)>4 else prices[e['time']][1])*model['funding_reference_scale']
                    payment=-q*ref*f[2]
                    assert math.isclose(payment,e['cashflow'],abs_tol=1e-8)
                    cash+=payment
                event_index+=1
            independent=cash+q*prices[day['time']-HOUR][4]
            residual=max(residual,abs(independent-day['equity']))
            assert residual<1e-7
        assert event_index==len(run['events'])
        assert math.isclose(sum(v['pnl'] for v in run['periods']['quarterly'].values()),run['metrics']['net_pnl'],abs_tol=1e-8)
        audits.append({'period':report['period'],'run':label,'daily_points':len(run['daily']),
                       'events':len(run['events']),'maximum_independent_equity_residual':residual,'reproduction_identical':True})
out={'network_disabled':True,'runs':len(audits),'audits':audits,
     'code_sha256':sha((ROOT/'src/btc_perp_bot/research/longitudinal.py').read_bytes()),
     'max_residual':max(a['maximum_independent_equity_residual'] for a in audits)}
(ROOT/'runs/longitudinal-1448-audit.json').write_bytes(canonical(out))
print(json.dumps({k:v for k,v in out.items() if k!='audits'},indent=2))
