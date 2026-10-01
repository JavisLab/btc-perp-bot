"""Economic invariants, chronology, real data parsing boundaries and immutable inputs."""
import copy
import math
import statistics

import pytest

from btc_perp_bot.research.archive import DAY, HOUR, ms, parse_csv, validate_series
from btc_perp_bot.research.longitudinal import (
    Costs, bootstrap, desired_quantity, periods, schedules, signal, simulate,
)

BASE=ms('2020-01-01')


def market(days=130, flat=False, rate=0):
    rows=[]
    previous=100.0
    for h in range(days*24):
        c=100.0 if flat else 100*math.exp(.001*h/24+.06*math.sin(h/24/9))
        t=BASE+h*HOUR
        rows.append([t,previous,max(previous,c)*1.001,min(previous,c)*.999,c,t+HOUR-1])
        previous=c
    return {'series':{'perp':rows,'mark':copy.deepcopy(rows),'spot':copy.deepcopy(rows),
            'funding':[[BASE+h*HOUR,8,rate,BASE+h*HOUR+7] for h in range(0,days*24,8)]}}


def test_signal_uses_sample_variance_and_exact_63_day_return():
    h=[100*math.exp(.01*i+.1*math.sin(i)) for i in range(85)]
    vol=statistics.stdev([math.log(h[i]/h[i-1]) for i in range(65,85)])*math.sqrt(365)
    assert signal(h,'T1')==pytest.approx(min(.5,.1/vol))
    assert signal([1]*85,'T1')==0
    assert signal(h[:84],'T1') is None
    down=list(reversed(h))
    assert signal(down,'T1')==0
    assert signal(down,'T5')<0


@pytest.mark.parametrize('old,weight',[(0,.5),(.002,.2),(-.005,-.4),(.04,.1)])
def test_target_includes_cost_and_rounds_down(old,weight):
    equity=1000;mark=70000;opening=70010;fee=5;impact=1.5;step=.001
    q=desired_quantity(equity,old,weight,mark,opening,fee,impact,step)
    d=q-old;fill=opening*(1+(impact/10000 if d>0 else -impact/10000))
    after=equity+d*(mark-fill)-abs(d)*fill*fee/10000
    assert abs(q)*mark<=abs(weight)*after+1e-7
    assert abs(q/step-round(q/step))<1e-7


def test_two_fill_roundtrip_cost_is_independently_known():
    data=market(flat=True)
    result=simulate(data,'perp_hold',BASE+85*DAY,BASE+87*DAY)
    fills=[x for x in result['events'] if x['kind']=='fill']
    q=fills[0]['delta']
    assert len(fills)==2
    # Constant price, symmetric 1.5bp impact and 5bp fee on both sides.
    assert result['metrics']['net_pnl']==pytest.approx(-q*100*2*6.5/10000,abs=1e-8)
    assert result['metrics']['remaining_position']==0


def test_funding_before_entry_then_only_held_intervals():
    data=market(flat=True,rate=.01)
    r=simulate(data,'perp_hold',BASE+85*DAY,BASE+87*DAY,Costs(fee=0,impact=0))
    f=[e for e in r['events'] if e['kind']=='funding']
    assert len(f)==5
    assert min(e['time'] for e in f)==BASE+85*DAY+8*HOUR
    assert r['metrics']['funding']==pytest.approx(-25)
    assert r['metrics']['equity']==pytest.approx(975)


def test_future_data_cannot_change_prior_fills_or_equity():
    data=market();changed=copy.deepcopy(data);boundary=BASE+110*DAY
    for kind in ('perp','mark','spot'):
        for row in changed['series'][kind]:
            if row[0]>=boundary:
                for i in range(1,5):row[i]*=3
    a=simulate(data,'T1',BASE+85*DAY,BASE+130*DAY)
    b=simulate(changed,'T1',BASE+85*DAY,BASE+130*DAY)
    assert [e for e in a['events'] if e['time']<boundary]==[e for e in b['events'] if e['time']<boundary]
    assert [e for e in a['daily'] if e['time']<=boundary]==[e for e in b['daily'] if e['time']<=boundary]


def test_delay_freezes_signal_at_original_decision_time():
    data=market();start=BASE+85*DAY;end=BASE+120*DAY
    a=schedules(data['series']['perp'],'T1',start,end)
    b=schedules(data['series']['perp'],'T1',start,end,24)
    assert all(x['target']==y['target'] and x['source_time']==y['source_time'] and y['time']-x['time']==DAY for x,y in zip(a,b))
    run=simulate(data,'T1',start,end,delay=24)
    assert all(e['source_time']+25*HOUR<=e['time'] for e in run['events'] if e['kind']=='fill' and e['source_time'] is not None)


def test_missing_execution_hour_uses_next_observation_not_phantom_price():
    data=market(flat=True);start=BASE+85*DAY
    data['series']['spot']=[r for r in data['series']['spot'] if r[0]!=start+HOUR]
    run=simulate(data,'spot_hold',start,start+2*DAY)
    assert run['events'][0]['time']==start+2*HOUR
    assert any(x['reason']=='unobserved_hours' for x in run['skips'])


def test_minimum_increase_is_skipped_not_rounded_up():
    data=market(flat=True)
    run=simulate(data,'perp_hold',BASE+85*DAY,BASE+87*DAY,Costs(minimum=600))
    assert not run['events']
    assert run['metrics']['equity']==1000
    assert run['metrics']['skipped']==2


def test_long_short_pnl_and_cash_replay_agree_with_basis():
    data=market(200,rate=.0001)
    for kind in ('perp','mark','spot'):
        for row in data['series'][kind]:
            scale=math.exp(-.01*max(0,(row[0]-BASE)/DAY-100))
            for i in range(1,5):row[i]*=scale
    for row in data['series']['mark']:
        for i in range(1,5):row[i]*=1.002
    run=simulate(data,'T5',BASE+85*DAY,BASE+200*DAY)
    assert run['metrics']['accounting_residual']==pytest.approx(0,abs=1e-7)
    assert sum(run['metrics']['directional_pnl'].values())==pytest.approx(run['metrics']['net_pnl'],abs=1e-7)
    assert any(e['position']<0 for e in run['events'] if e['kind']=='fill')


def test_quarter_reporting_does_not_reset_equity():
    ds=[{'time':ms('2022-04-01'),'equity':1100},{'time':ms('2022-07-01'),'equity':990}]
    q=periods(ds)['quarterly']
    assert q['2022-Q1']['return_pct']==pytest.approx(10)
    assert q['2022-Q2']['return_pct']==pytest.approx(-10)
    assert sum(v['pnl'] for v in q.values())==-10


def test_microseconds_funding_offsets_and_invalid_original_rows():
    t=ms('2025-01-01')
    raw=f'{t*1000},100,101,99,100,1,{(t+HOUR)*1000-1},0,1,0,0,0\n'.encode()
    assert parse_csv(raw,'spot')[0][0]==t
    assert parse_csv(f'{t+23},8,0.0001\n'.encode(),'funding')[0]==[t,8,.0001,t+23]
    bad=f'{t},100,101,99,100,0,{t-1},0,0,0,0,0\n'.encode()
    with pytest.raises(ValueError):parse_csv(bad,'spot')


def test_missing_funding_not_silently_zero():
    rows=[[BASE,8,.0001,BASE],[BASE+16*HOUR,8,.0001,BASE+16*HOUR]]
    assert validate_series(rows,'funding',BASE,BASE+DAY)['missing_count']==1


def test_paired_block_bootstrap_same_series_has_zero_sharpe_difference():
    x=[.002*math.sin(i/7)+.0002 for i in range(100)]
    a=bootstrap(x,x,resamples=100,blocks=(14,))
    assert a==bootstrap(x,x,resamples=100,blocks=(14,))
    assert a[0]['sharpe_difference_ci95']==[0,0]
