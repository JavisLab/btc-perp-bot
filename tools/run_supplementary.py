"""Explicitly separate target-venue regression from an external-price cost scenario."""
import json
from pathlib import Path

from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,sha
from btc_perp_bot.research.longitudinal import Costs,PRIMARY,load_data,summarize_run

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs/longitudinal-1448'


def save(name, report):
    p=OUT/(name+'.json')
    if p.exists(): raise ValueError('Refusing to overwrite an experiment')
    p.write_bytes(canonical(report))
    print(name,report['results']['T1']['metrics']['return_pct'])


data,manifest=load_data(ROOT/'data/longitudinal-1448-repaired/binance-hourly.json.gz',ROOT/'data/longitudinal-1448-repaired/manifest.json')
hl_costs=Costs(fee=4.5,impact=1.5,step=.00001,minimum=10,spot_fee=7,spot_step=.00001,spot_minimum=10)
report=summarize_run(data,ms('2022-01-01'),ms('2026-01-01'),hl_costs)
report.update(period='hl_cost_scenario',venue='Binance BTCUSDT prices, HL cost/size assumptions',quote='USDT',
              dataset_sha256=manifest['dataset_sha256'],is_hyperliquid_performance=False,
              caveat='Binance funding and prices remain unchanged; fees AND quantity/minimum rules use HL assumptions, not a fee-only experiment.')
save('hl-cost-scenario',report)

legacy=json.loads((ROOT/'data/research-1428-btc-1h.json').read_text())
rows=[[b['t'],*[float(b[k]) for k in ('o','h','l','c')],b['t']+HOUR-1] for b in legacy['candles']]
bytime={r[0]:r for r in rows}
funding=[[f['time'],1,float(f['rate']),f['observed_time'],bytime[f['time']-HOUR][4]] for f in legacy['funding'] if f['time']-HOUR in bytime]
hl={'series':{'perp':rows,'mark':rows,'spot':[], 'funding':funding}}
start=(rows[0][0]//DAY+1)*DAY+85*DAY
end=(rows[-1][0]+HOUR)//DAY*DAY
report=summarize_run(hl,start,end,hl_costs,names=tuple(k for k in PRIMARY if k!='spot_hold'))
report.update(period='hl_regression',venue='Hyperliquid BTC perpetual',quote='USDC',dataset_sha256=legacy['sha256'],
              is_new_holdout=False,funding_reference_is_proxy=True,
              caveat='Previously used 120 days; 85 complete UTC warmup days; only the remaining 34 full days. Funding reference is the previous trade close, not historical oracle.')
save('hl-regression',report)
