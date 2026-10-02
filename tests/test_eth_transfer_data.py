"""Guard evidence boundaries, not strategy performance, for the ETH data adapter."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('eth_transfer_data',Path(__file__).parents[1]/'tools/collect_eth_transfer.py')
et=importlib.util.module_from_spec(spec);spec.loader.exec_module(et)


class EthSourceAuditTests(unittest.TestCase):
    def row(self, **kw):
        r=['1609459200000','100','110','90','105','2','1609459499999','200','4','1','100','0']
        fields={'time':0,'high':2,'volume':5,'end':6,'quote':7,'trades':8,'buy':9,'buy_quote':10}
        for k,v in kw.items(): r[fields[k]]=str(v)
        return ','.join(r).encode()

    def test_futures_microseconds_not_silently_normalized(self):
        with self.assertRaisesRegex(ValueError,'Timestamp'):
            et.parse_klines(self.row(time=1609459200000000,end=1609459499999000),et.STEP)

    def test_shortened_and_negative_end_rejected(self):
        for end in (1609459200000,1609459199999):
            with self.assertRaisesRegex(ValueError,'Timestamp'):
                et.parse_klines(self.row(end=end),et.STEP)

    def test_trade_zero_and_quote_bounds_cannot_be_hidden(self):
        for row in (self.row(trades=0),self.row(buy=3),self.row(quote=300)):
            with self.assertRaises(ValueError): et.parse_klines(row,et.STEP)

    def test_valid_empty_bar_preserved_not_dropped(self):
        r=et.parse_klines(self.row(volume=0,quote=0,trades=0,buy=0,buy_quote=0),et.STEP)
        self.assertEqual(len(r),1);self.assertEqual(r[0][5],0)

    def test_duplicate_and_unsorted_source_rows_fail(self):
        a=self.row();b=self.row(time=1609459500000,end=1609459799999)
        for raw in (a+b'\n'+a,b+b'\n'+a):
            with self.assertRaisesRegex(ValueError,'duplicate/reversed'):
                et.parse_klines(raw,et.STEP)

    def test_missing_bar_is_not_interpolated(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            et.complete([[0],[2*et.STEP]],0,3*et.STEP,et.STEP)

    def test_repair_requires_both_timeframes_and_price_conflict(self):
        b=et.parse_klines(self.row(),et.STEP)[0]
        c={'hourly':b,'price_conflict':True}
        self.assertTrue(et.can_repair(c,{'1m':b,'5m':b}))
        self.assertFalse(et.can_repair(c,{'5m':b}))
        altered=list(b);altered[8]+=1
        self.assertFalse(et.can_repair(c,{'1m':altered,'5m':b}))
        self.assertFalse(et.can_repair({**c,'price_conflict':False},{'1m':b,'5m':b}))

    def test_funding_raw_offset_preserved_and_bad_interval_rejected(self):
        r=et.parse_funding(b'1609459200003,8,0.0001')[0]
        self.assertEqual(r,[1609459200000,8,.0001,1609459200003])
        with self.assertRaises(ValueError):et.parse_funding(b'1609459200000,2,0.0001')
        with self.assertRaises(ValueError):et.parse_funding(b'1609459260000,8,0.0001')


if __name__=='__main__':unittest.main()
