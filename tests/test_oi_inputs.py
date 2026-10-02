import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
from prepare_oi_inputs import transform


def test_raw_timestamp_and_zero_preserved_without_claiming_publication_time():
    r=transform([1000,'0','30',None,'1','2','3'])
    assert r['source_time_ms']==1000 and r['observation_complete_assumed_ms']==301000
    assert not r['oi_usable'] and r['oi_qty']=='0' and r['ratios'][0] is None
    assert 'available_at' not in r


def test_both_quantity_and_value_must_be_positive_without_rounding():
    assert not transform([0,'1','0',None,None,None,None])['oi_usable']
    assert not transform([0,None,'1',None,None,None,None])['oi_usable']
    r=transform([0,'123.00000000000000001','456.78',None,None,None,None])
    assert r['oi_usable'] and r['oi_qty']=='123.00000000000000001'
