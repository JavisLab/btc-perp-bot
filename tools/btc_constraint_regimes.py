"""Calendar/regime attribution of stored E ledgers only; no strategy reruns."""
import gzip,json,math
from collections import defaultdict
from pathlib import Path
from btc_perp_bot.research.archive import DAY,HOUR,ms,utc,canonical
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(gzip.decompress(p.read_bytes()))
def run():
 market=read(ROOT/'data/search-1458/market.json.gz')['series']['BTCUSDT'];spot={r[0]+HOUR:r[4] for r in market['spot'] if r[0]%DAY==23*HOUR};out={}
 for period in ('main','recent'):
  for name in ('E_SPOT','E_PERP','E_LS'):
   x=read(ROOT/f'runs/search-1458/{period}-{name}.json.gz');start,end=ms(x['start']),ms(x['end']);key='BS' if name=='E_SPOT' else 'BP';marks={r[0]:r for r in market['spot' if key=='BS' else 'mark']};bytime=defaultdict(list)
   for e in x['events']:bytime[e['time']].append(e)
   q={1:0.,-1:0.};cash={1:0.,-1:0.};prev={1:0.,-1:0.};annual=defaultdict(lambda:{'long':0.,'short':0.});regimes=defaultdict(lambda:{'long':0.,'short':0.});last=None
   def event(e):
    if e['kind']=='funding':cash[1 if e['position']>0 else -1]+=e['cashflow'];return
    if e['kind']!='fill':return
    dq=e['delta'];held=q[1]+q[-1];parts=[]
    if held*dq<0:
     v=min(abs(held),abs(dq));parts.append((1 if held>0 else -1,-math.copysign(v,held)))
     if abs(dq)-v>1e-12:parts.append((1 if dq>0 else -1,math.copysign(abs(dq)-v,dq)))
    else:parts.append((1 if dq>0 else -1,dq))
    for side,delta in parts:q[side]+=delta;cash[side]-=delta*e['price']+abs(delta/dq)*e['fee']
   for t in range(start,end,HOUR):
    for e in bytime.get(t,[]):event(e)
    r=marks.get(t);last=r[4] if r else last
    if t+HOUR==end:
     for e in bytime.get(end,[]):event(e)
    day=t//DAY*DAY;ds=[spot.get(day-j*DAY) for j in range(19,-1,-1)];reg='missing'
    if all(z is not None for z in ds):
     path=math.fsum(abs(b-a) for a,b in zip(ds,ds[1:]));change=ds[-1]-ds[0];er=abs(change)/path if path else 0.;reg='up' if er>=.3 and change>0 else 'down' if er>=.3 and change<0 else 'range'
    for side,label in [(1,'long'),(-1,'short')]:
     value=cash[side]+q[side]*last;delta=value-prev[side];annual[utc(t)[:4]][label]+=delta;regimes[reg][label]+=delta;prev[side]=value
   assert abs(sum(prev.values())-x['metrics']['net_pnl'])<1e-7
   for year,val in annual.items():assert abs(sum(val.values())-x['periods']['yearly'][year]['pnl'])<1e-7
   out[period+'-'+name]={'annual_net_usdt_by_side':dict(annual),'past20_daily_regime_net_usdt_by_side':dict(regimes),'regime_clock':'at start of UTC day; 20 prior completed closes, ER .3; mark-to-market increments, not causal effects'}
 p=ROOT/'runs/btc-continuation-20261002/regimes.json';p.write_bytes(canonical(out));print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':run()
