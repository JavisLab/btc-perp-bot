import unittest,copy,math
from btc_residual_ledger import fractions,quantities,funding_cashflow,simulate
from btc_target_ledger import simulate as original
from btc_residual_carry_study import schedule
from btc_valuation_study import DAY,HOUR,ms
from test_btc_valuation_study import Fake as SignalFake
class MarketFake:
 def __init__(self):
  self.rowmaps={k:{} for k in ('BS','BP')};self.markmaps={k:{} for k in ('BS','BP')};self.funds={'BP':{}}
  for t in range(0,5*DAY,HOUR):
   price=10000+10*(t//HOUR);f=price*1.0001
   for k,p in [('BS',price),('BP',f)]:self.rowmaps[k][t]=[t,p,p*1.001,p*.999,p,t+HOUR-1];self.markmaps[k][t]=self.rowmaps[k][t]
   if t%(8*HOUR)==0:self.funds['BP'][t]=[t,8,.0001 if t%(16*HOUR)==0 else -.00003,t]
def plan(core,allocation=.8,source=0):return {'source_time':source,'weights':{'BS':core,'BP':0},'core_weight':core,'carry_allocation':allocation,'rebalance':True,'hedge':False}
class Tests(unittest.TestCase):
 def test_budget_and_collateral_extreme_basis(self):
  for w in (0,.1,.5,.9,1):
   for rho in (.7,1,1.4):
    h,v=fractions(w,.8,10000,rho*10000);self.assertAlmostEqual(sum(abs(x) for x in v.values()),w+.8*(1-w));self.assertLessEqual(sum(abs(x) for x in v.values()),1+1e-12);self.assertGreaterEqual(1-v['BS'],-v['BP']-1e-12)
 def test_matched_rounding_net_core(self):
  h,v=fractions(.37,.8,12345,12346);q,c,b=quantities(.37,h,999,12345);self.assertAlmostEqual(q['BS']+q['BP'],c);self.assertAlmostEqual(-q['BP'],b);self.assertAlmostEqual(b/.001,round(b/.001));q,c,b=quantities(0,.4,999,12345);self.assertEqual(q['BS'],-q['BP']);self.assertEqual(c,0)
 def test_trend_equivalent_original(self):
  m=MarketFake();p=[plan(.2,0),plan(.7,0,DAY),plan(0,0,2*DAY),plan(.4,0,3*DAY)];a=simulate(m,'RC_TREND',0,5*DAY,p);b=original(m,'E_SPOT',0,5*DAY,p)
  for k in ('return_pct','max_drawdown_pct','funding','fees','impact'):self.assertAlmostEqual(a['metrics'][k],b['metrics'][k],places=10)
  self.assertEqual(a['metrics']['core_round_trips'],2);self.assertEqual(a['daily_returns'],b['daily_returns'])
 def test_funding_income_only_haircut(self):
  self.assertEqual(funding_cashflow(-1,10000,.001,.5),(5,10));self.assertEqual(funding_cashflow(-1,10000,-.001,.5),(-10,-10));self.assertEqual(funding_cashflow(1,10000,-.001,.5),(5,10));self.assertEqual(funding_cashflow(0,10000,.001,.5),(0,0))
 def test_pair_funding_and_replay_identity(self):
  m=MarketFake();x=simulate(m,'RC_CARRY',0,5*DAY,[plan(0)]);events=x['events'];q={k:0 for k in ('BS','BP')};cash=1000
  for e in events:
   if e['kind']=='fill':q[e['instrument']]+=e['delta'];cash-=e['delta']*e['price']+e['fee']
   else:self.assertAlmostEqual(e['cashflow'],-q['BP']*e['reference']*e['rate']);cash+=e['cashflow']
  self.assertAlmostEqual(cash,x['metrics']['equity']);self.assertEqual(x['metrics']['core_round_trips'],0);self.assertEqual(x['metrics']['margin_buffer_breach_hours'],0);self.assertTrue(all(abs(d['positions']['BS']+d['positions']['BP'])<1e-12 for d in x['daily']))
 def test_minimum_pair_atomic(self):
  m=MarketFake();p=plan(.95);x=simulate(m,'RC_BLEND',0,5*DAY,[p]);self.assertEqual(len(x['events']),0);self.assertEqual(x['skips'][0]['reason'],'multileg_minimum');self.assertEqual(x['metrics']['equity'],1000)
 def test_delay_and_no_funding_before_fill(self):
  m=MarketFake();x=simulate(m,'RC_CARRY',0,5*DAY,[plan(0)],delay=24);first=min(e['time'] for e in x['events']);self.assertEqual(first,25*HOUR);self.assertTrue(all(e['time']>25*HOUR for e in x['events'] if e['kind']=='funding'))
 def test_rounding_core_not_count_hedge(self):
  m=MarketFake();p=[plan(.2),plan(.4,.8,DAY),plan(0,.8,2*DAY),plan(.3,.8,3*DAY)];x=simulate(m,'RC_BLEND',0,5*DAY,p);self.assertEqual(x['metrics']['core_round_trips'],2)
 def test_price_future_cannot_change_source_plan(self):
  m=SignalFake()
  # Use the production observation function against the synthetic daily arrays.
  from btc_persistence_study import Market,ema
  m.ema={s:ema(m.close,s) for s in (8,16,32,64,128)};m.observation=lambda t,r:Market.observation(m,t,r)
  t=ms('2022-01-03');a=schedule(m,'RC_BLEND',t,t+DAY);i=m.index[t];m.close[i:]*=10;m.ema={s:ema(m.close,s) for s in (8,16,32,64,128)};self.assertEqual(schedule(m,'RC_BLEND',t,t+DAY),a)
if __name__=='__main__':unittest.main()
