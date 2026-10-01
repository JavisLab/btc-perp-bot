"""Financial edge cases: real causal boundaries, not implementation snapshots."""
import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip('numpy')
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import structural_study as st


def rows(days=1):
    return [[i*st.STEP,100.,100.5,99.5,100.,100.] for i in range(days*288)]


def signal(source=0,side=1,stop=None):
    return dict(family='A_ACCEPT',source=source,side=side,stop=stop or (98. if side==1 else 102.),
                atr=1.,target=None,regime='up' if side==1 else 'down',er=.5,flow=.6,origin=source)


def sim(r,e=None,**kw):
    return st.simulate(r,e or [signal()],{6:{},10:{}},kw.pop('funding',{}),kw.pop('name','A_ACCEPT'),
                       0,len(r)*st.STEP,**kw)


def test_both_touches_stop_first_and_gap_loss_not_capped():
    assert st.exit_at_bar([0,100,110,90,100,10],1,98,104)==(98,'stop',True)
    assert st.exit_at_bar([0,100,110,90,100,10],-1,102,96)==(102,'stop',True)
    assert st.exit_at_bar([0,90,100,89,95,10],1,98,104)[0]==90


def test_entry_bar_stop_is_active_and_not_delayed_one_bar():
    r=rows();r[1][2:5]=[105,97,100]
    result=sim(r)
    assert result['trades'][0]['entry']==result['trades'][0]['exit']==st.STEP
    assert result['trades'][0]['reason']=='stop'
    assert result['summary']['ambiguous_bars']==1
    assert result['summary']['net']<0


def test_invalidation_between_signal_and_entry_cancels_trade():
    r=rows();r[3][3]=97
    result=sim(r,delay=st.HOUR)
    assert result['summary']['trades']==0
    assert result['summary']['skips']['invalidated_before_entry']==1


def test_zero_volume_is_not_fabricated_execution():
    r=rows();r[1][5]=0
    result=sim(r)
    assert result['summary']['trades']==0 and result['summary']['skips']['zero_volume_entry']==1
    assert st.exit_at_bar([0,90,110,80,100,0],1,98,104) is None


def test_funding_at_entry_not_charged_then_sign_is_correct():
    funds={st.STEP:{'rate':.001,'reference':100.,'raw_time':st.STEP},
           2*st.STEP:{'rate':.001,'reference':100.,'raw_time':2*st.STEP}}
    for side in (1,-1):
        result=sim(rows(),[signal(side=side)],funding=funds)
        q=result['trades'][0]['qty']
        assert result['summary']['funding']==pytest.approx(-side*q*.1)
        assert len([e for e in result['events'] if e['kind']=='funding'])==1
        assert result['summary']['net']==pytest.approx(sum(t['net'] for t in result['trades']))


def test_position_risk_and_minimum_round_down_not_up():
    q=st.sized(1000,100,98,1,.0005,.00015,.005)
    loss=q*(100*1.00015-98*.99985+.0005*(100*1.00015+98*.99985))
    assert loss<=5 and q*100*1.00015<=1000 and round(q/.001)==pytest.approx(q/.001)
    assert st.sized(1,100,98,1,.0005,.00015,.005)==0


def test_no_stale_reentry_after_exit_and_one_position_only():
    r=rows();r[4][3]=97
    # Source at bar2 while carrying must be discarded even if its delayed fill
    # could happen after an earlier stop in that same bar.
    result=sim(r,[signal(),signal(2*st.STEP),signal(6*st.STEP)])
    assert result['summary']['trades']==2
    assert result['trades'][1]['source']==6*st.STEP


def test_trailing_only_tightens_after_known_source_and_delay():
    r=rows();r[5][3]=98.5
    trails={6:{2*st.STEP:{'source':2*st.STEP,'long':99.,'short':101.},
               3*st.STEP:{'source':3*st.STEP,'long':97.,'short':103.}},10:{}}
    res=st.simulate(r,[signal()],trails,{},'P_RESUME',0,st.DAY)
    updates=[e for e in res['events'] if e['kind']=='trail']
    assert len(updates)==1 and updates[0]['time']==3*st.STEP
    assert res['trades'][0]['exit']==5*st.STEP
    assert res['trades'][0]['exit_reference']==99


def test_target_gap_does_not_award_better_than_target():
    assert st.exit_at_bar([0,110,111,109,110,10],1,98,104)==(104,'target',False)


def test_daily_equity_reconciles_mark_to_market_not_just_closed_trades():
    r=rows(2)
    for x in r[288:]:x[1:5]=[101,101.5,100.5,101]
    result=sim(r);t=result['trades'][0];d=result['daily'][0]
    assert d['equity']==pytest.approx(d['cash']+t['qty']*(100-t['fill']))
    assert result['daily'][-1]['qty']==0
    assert result['summary']['net']==pytest.approx(t['price_gross']-t['fees']-t['impact']+t['funding'])


def test_future_bars_do_not_change_past_signals_or_trails():
    b=[dict(t=i*4*st.HOUR,o=100+i*.1,h=101+i*.1,l=99+i*.1,c=100.5+i*.1,v=100,buy=60,rvol=1) for i in range(400)]
    before,bt=st.signals(b[:350]);after,at=st.signals(b)
    for name in st.IDS: assert before[name]==[e for e in after[name] if e['source']<=350*4*st.HOUR]
    for n in (6,10):assert bt[n]=={k:v for k,v in at[n].items() if k<=350*4*st.HOUR}


def test_short_is_not_long_returns_with_incorrect_fees():
    r=rows();r[2][1:5]=[103,104,102.5,103]
    result=sim(r,[signal(side=-1)])
    t=result['trades'][0]
    assert t['reason']=='stop_gap' and t['exit_fill']>103 and t['fill']<100
    assert result['summary']['fees']>0 and t['net'] < -t['risk_budget']
