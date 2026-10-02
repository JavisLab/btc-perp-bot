"""Missing/nonfinite OI must remain missing rather than become executable data."""
import csv
import io
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,str(Path(__file__).parents[1]/'tools'))
import audit_oi_history as audit


def archive(rows,columns=audit.COLS):
    stream=io.StringIO();w=csv.writer(stream);w.writerow(columns);w.writerows(rows)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:z.writestr('metrics.csv',stream.getvalue())
    return out.getvalue()


def test_null_ratio_stays_null_and_missing_timestamp_is_not_imputed():
    row=['2022-01-01 00:00:00','ETHUSDT','123.456','10000','NaN','','1.5','2']
    stats,data=audit.parse_csv(archive([row]),'ETHUSDT','2022-01-01')
    assert stats['rows']==1 and len(stats['missing_times_ms'])==287
    assert data[0][1]=='123.456' and data[0][3:5]==[None,None]
    assert stats['null_counts']=={'count_toptrader_long_short_ratio':1,'sum_toptrader_long_short_ratio':1}


def test_duplicates_wrong_day_and_negative_oi_are_reported_not_silently_repaired():
    row=['2022-01-02 00:00:00','BTCUSDT','-1','0','1','1','1','1']
    stats,_=audit.parse_csv(archive([row,row]),'ETHUSDT','2022-01-01')
    assert stats['duplicates']==1 and not stats['strictly_ordered']
    assert len(stats['unexpected_times_ms'])==2 and stats['wrong_symbol_rows']==2
    assert stats['negative_counts']['sum_open_interest']==2 and stats['zero_counts']['sum_open_interest_value']==2


def test_schema_drift_is_rejected():
    import pytest
    with pytest.raises(ValueError,match='Schema'):audit.parse_csv(archive([],['time','OI']),'ETHUSDT','2022-01-01')
