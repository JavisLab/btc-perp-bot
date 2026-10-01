"""Economic/chronology tests for the research model, not evidence of alpha."""
import copy
import math
import unittest

try:
    import numpy as np
except ImportError:
    np=None

if np is not None:
    from btc_perp_bot.research.strategy_search import Market,simulate,schedule,ml_predictions,fit_pair
    from btc_perp_bot.research.archive import HOUR,DAY,ms


@unittest.skipIf(np is None,'Optional research numerical dependencies are not installed')
class SearchTests(unittest.TestCase):
    def tiny(self,days=2,rate=.0001,spotgap=None):
        start=ms('2022-01-01');end=start+days*DAY
        rows=[[t,100.,101.,99.,100.,t+HOUR-1] for t in range(start,end,HOUR)]
        spot=[r.copy() for r in rows if r[0]!=spotgap]
        funding=[[t,8,rate,t+1] for t in range(start,end,8*HOUR)]
        payload={'end':end,'series':{'BTCUSDT':{'spot':spot,'perp':rows,'mark':copy.deepcopy(rows),'funding':funding},
                                    'ETHUSDT':{'perp':copy.deepcopy(rows),'mark':copy.deepcopy(rows),'funding':copy.deepcopy(funding)}}}
        return Market(payload),start,end

    def decision(self,t,**weights):
        return {'source_time':t,'weights':{'BS':weights.get('BS',0.),'BP':weights.get('BP',0.),'EP':weights.get('EP',0.)},
                'detail':{},'rebalance':True,'hedge':False}

    def test_spot_cash_and_funding_separation(self):
        m,s,e=self.tiny(rate=.01)
        r=simulate(m,'V_SPOT',s,e,[self.decision(s,BS=1)])
        self.assertEqual(r['metrics']['funding'],0)
        self.assertLess(r['metrics']['net_pnl'],0)
        self.assertTrue(all(p['cash']>=0 for p in r['daily']))

    def test_long_short_funding_sign(self):
        m,s,e=self.tiny(rate=.01)
        long=simulate(m,'V_PERP',s,e,[self.decision(s,BP=.4)])
        short=simulate(m,'E_LS',s,e,[self.decision(s,BP=-.4)])
        self.assertLess(long['metrics']['funding'],0)
        self.assertGreater(short['metrics']['funding'],0)
        self.assertTrue(all(x['time']>s for x in short['events'] if x['kind']=='funding'))

    def test_carry_equal_quantities_and_collateral(self):
        m,s,e=self.tiny(rate=.01);p=self.decision(s,BS=.4,BP=-.4);p['hedge']=True
        r=simulate(m,'C_ALWAYS',s,e,[p])
        self.assertTrue(all(abs(x['positions']['BS']+x['positions']['BP'])<1e-12 for x in r['daily']))
        self.assertGreater(r['metrics']['funding'],0)
        self.assertLess(r['metrics']['min_adverse_margin_ratio'],2)
        self.assertGreater(r['metrics']['min_adverse_margin_ratio'],1)

    def test_hedge_missing_one_leg_skips_both(self):
        s=ms('2022-01-01');m,s,e=self.tiny(spotgap=s+HOUR)
        p=self.decision(s,BS=.4,BP=-.4);p['hedge']=True
        r=simulate(m,'C_ALWAYS',s,e,[p])
        self.assertEqual(r['metrics']['fills'],0)
        self.assertEqual(r['skips'][0]['reason'],'missing_execution_bar')

    def test_multileg_minimum_no_one_leg(self):
        m,s,e=self.tiny();p=self.decision(s,BS=.01,BP=-.01);p['hedge']=True
        r=simulate(m,'C_ALWAYS',s,e,[p])
        self.assertEqual(r['metrics']['fills'],0)
        self.assertEqual(r['skips'][0]['reason'],'multileg_minimum')

    def test_delayed_signals_are_original(self):
        m,s,e=self.tiny(days=4)
        p=[self.decision(s,BP=.4),self.decision(s+DAY)]
        r=simulate(m,'V_PERP',s,e,p,delay=24)
        first=r['events'][0]
        self.assertEqual(first['time'],s+25*HOUR)
        self.assertEqual(first['source_time'],s)
        self.assertEqual(r['executions'][0]['weights']['BP'],.4)

    def test_fee_stress_and_cash_identity(self):
        m,s,e=self.tiny(rate=0);p=[self.decision(s,BP=.4)]
        b=simulate(m,'V_PERP',s,e,p);d=simulate(m,'V_PERP',s,e,p,multiplier=2)
        self.assertLess(d['metrics']['net_pnl'],b['metrics']['net_pnl'])
        for r in (b,d):
            x=r['metrics'];self.assertAlmostEqual(x['net_pnl'],x['gross_pnl']+x['funding']-x['fees']-x['impact'],8)

    def test_stale_spot_is_valuation_only(self):
        s=ms('2022-01-01');m,s,e=self.tiny(spotgap=s+5*HOUR)
        r=simulate(m,'V_SPOT',s,e,[self.decision(s,BS=.5),self.decision(s+4*HOUR,BS=.8)])
        self.assertEqual(r['metrics']['stale_held_spot_hours'],1)
        self.assertTrue(all(x['time']!=s+5*HOUR for x in r['events'] if x['kind']=='fill'))

    def test_period_continuity_and_final_exit(self):
        m,s,e=self.tiny(days=35);r=simulate(m,'V_PERP',s,e,[self.decision(s,BP=.4)])
        months=list(r['periods']['monthly'].values())
        self.assertEqual(months[1]['start_equity'],months[0]['end_equity'])
        self.assertEqual(r['events'][-1]['reason'],'end_of_experiment')
        self.assertEqual(r['daily'][-1]['positions']['BP'],0)

    def test_full_future_prices_do_not_change_earlier_signals(self):
        start=ms('2020-02-01');end=start+600*DAY
        rows=[]
        for j,t in enumerate(range(start,end,HOUR)):
            price=100*math.exp(.000025*j+.02*math.sin(j/300))
            rows.append([t,price,price*1.001,price*.999,price,t+HOUR-1])
        f=[[t,8,.0001,t+1] for t in range(start,end,8*HOUR)]
        data={'end':end,'series':{'BTCUSDT':{'spot':copy.deepcopy(rows),'perp':rows,'mark':rows,'funding':f},
                                'ETHUSDT':{'perp':rows,'mark':rows,'funding':f}}}
        s=start+400*DAY;cut=s+30*DAY
        first=Market(data);perturbed=copy.deepcopy(data)
        for r in perturbed['series']['BTCUSDT']['spot']:
            if r[0]>=cut:
                for k in range(1,5):r[k]*=2
        second=Market(perturbed)
        a,_=schedule(first,'E_SPOT',s,cut);b,_=schedule(second,'E_SPOT',s,cut)
        self.assertEqual(a,b)
        self.assertTrue(all(sum(abs(v) for v in x['weights'].values())<=1+1e-12 for x in a))

    def test_ml_label_purge_and_future_invariance(self):
        start=ms('2020-02-01');end=ms('2022-02-01')
        rows=[]
        for j,t in enumerate(range(start,end,HOUR)):
            px=100*math.exp(.00001*j+.03*math.sin(j/100)+.01*math.sin(j/17))
            rows.append([t,px,px*1.001,px*.999,px,t+HOUR-1])
        f=[[t,8,.0001,t+1] for t in range(start,end,8*HOUR)]
        data={'end':end,'series':{'BTCUSDT':{'spot':rows,'perp':rows,'mark':rows,'funding':f},
                                'ETHUSDT':{'perp':rows,'mark':rows,'funding':f}}}
        s=ms('2022-01-01');e=s+DAY
        pred,train=ml_predictions(Market(data),'M_RIDGE',s,e)
        self.assertTrue(all(x['last_label_time']<=x['fit_time']-2*HOUR for x in train))
        other=copy.deepcopy(data)
        for r in other['series']['BTCUSDT']['perp']:
            if r[0]>=e:
                for k in range(1,5):r[k]*=1.3
        after,train2=ml_predictions(Market(other),'M_RIDGE',s,e)
        self.assertEqual(pred,after);self.assertEqual(train,train2)


if __name__=='__main__':unittest.main()
