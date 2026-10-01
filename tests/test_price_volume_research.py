"""Financial chronology and information-boundary tests for the event study."""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip('numpy')
spec = importlib.util.spec_from_file_location('pv',Path(__file__).parents[1]/'tools/price_volume_study.py')
pv = importlib.util.module_from_spec(spec);spec.loader.exec_module(pv)


def history():
    return [dict(t=i*4*pv.HOUR,o=100.,h=102.,l=98.,c=100.,v=100.,buy=50.,rvol=1.) for i in range(130)]


def test_aggregation_same_slot_and_current_bar_exclusion():
    rows=[]
    for i in range(4*127):
        volume=1.+(i//4)%6
        rows.append([i*pv.HOUR,100,102,98,101,volume,i*pv.HOUR+pv.HOUR-1,100*volume,1,volume/2,50*volume])
    before=pv.aggregate(rows)
    assert before[120]['rvol']==1
    assert before[125]['rvol']==1
    assert before[0]['v']==4 and before[0]['buy']==2
    rows[4*120][5]*=9
    after=pv.aggregate(rows)
    assert after[120]['rvol']==3  # (9+1+1+1)/4; denominator cannot contain current bar.
    assert after[121]['rvol']==1


def test_breakout_uses_prior_high_and_symmetric_short():
    bars=history();bars[-1].update(o=102,h=104,l=101,c=104,rvol=1.5)
    found=pv.detect(bars)
    event=[e for e in found if e['family']=='B'][-1]
    assert event['side']==1 and event['volume_pass'] and event['source']==130*4*pv.HOUR
    bars[-1].update(o=98,h=99,l=96,c=96)
    event=[e for e in pv.detect(bars) if e['family']=='B'][-1]
    assert event['side']==-1


def test_failed_breakout_requires_reclaim_and_rejects_both_sides():
    bars=history();bars[-1].update(o=98,h=101,l=97,c=100.5,rvol=.7)
    assert [(e['side'],e['volume_pass']) for e in pv.detect(bars) if e['family']=='F']==[(1,True)]
    bars[-1].update(h=103,c=102.5)
    assert not [e for e in pv.detect(bars) if e['family']=='F']


def test_pullback_reclaims_previous_high_not_just_green_bar():
    bars=history()
    for b in bars[-21:-1]:b.update(o=105,h=108,l=103,c=105)
    bars[-4]['c']=107;bars[-3].update(c=106,rvol=.6);bars[-2].update(c=105,h=106,rvol=.7)
    bars[-1].update(o=105,h=108,l=104,c=107.5,rvol=.8)
    assert [(e['side'],e['volume_pass']) for e in pv.detect(bars) if e['family']=='P']==[(1,True)]
    bars[-1].update(h=106,c=105.8)
    assert not [e for e in pv.detect(bars) if e['family']=='P']


def test_payoff_cash_flow_and_funding_boundary():
    prices={i*pv.HOUR:[i*pv.HOUR,100.] for i in range(50)}
    marks=prices
    funds={i*pv.HOUR:[i*pv.HOUR,8,.001,i*pv.HOUR] for i in (1,9,25)}
    for side,expected in ((1,-33.),(-1,7.)):
        r=pv.payoff({'source':0,'side':side},prices,marks,funds)
        assert r['funding_bp']==pytest.approx(-side*20)
        assert r['net_bp']==pytest.approx(expected)
        assert r['fees_bp']==pytest.approx(10)
        assert r['impact_bp']==pytest.approx(3)
    delayed=pv.payoff({'source':0,'side':1},prices,marks,funds,extra_delay=pv.HOUR)
    assert delayed['entry']==2*pv.HOUR and delayed['exit']==26*pv.HOUR


def test_future_mutation_cannot_change_existing_signals():
    bars=history();bars[125].update(o=102,h=104,l=101,c=104,rvol=2.)
    known=pv.detect(bars[:126])
    for b in bars[126:]:b.update(c=1e6,h=1e6,l=1,v=1e9,rvol=1e5)
    assert [e for e in pv.detect(bars) if e['source']<=126*4*pv.HOUR]==known


def test_cluster_bootstrap_empty_subset_not_zero_performance():
    events=[{'entry':i*pv.DAY,'net_bp':10.,'volume_pass':False} for i in range(90)]
    result=pv.uncertainty(events,0,90*pv.DAY,14)
    assert result['all']['ci95']==[10.,10.]
    assert result['volume_pass']['ci95'] is None
    assert result['pass_minus_fail']['ci95'] is None
