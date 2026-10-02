"""BTC realized-funding conditional impulses; no forecasts or live connections."""
import argparse,bisect,json,math
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,ms,sha
from btc_oi_study import engine,write,interval
ROOT=Path(__file__).resolve().parents[1];IDS=('P_FUND_MASK','F_JOIN','F_CROWD');PERIODS=engine.PERIODS
SCENARIOS={'base':{},'cost_x2':{'cost':2},'execution60':{'delay':HOUR},'stop5':{'stop_extra':.0005},'risk_half':{'risk':.0025},'availability0':{'availability':0},'availability240':{'availability':240},'availability1440':{'availability':1440},'fund3':{'threshold':.0003},'fund12':{'threshold':.0012}}
def known(times,funding,t,availability):
 end=t-availability*60000;lo=bisect.bisect_left(times,end-DAY);hi=bisect.bisect_left(times,end);part=times[lo:hi]
 if len(part)!=3 or any(b-a!=8*HOUR for a,b in zip(part,part[1:])) or any(funding[z]['raw_time']>=end for z in part):return None
 return {'known_funding':math.fsum(funding[z]['rate'] for z in part),'funding_buckets':part,'funding_raw_times':[funding[z]['raw_time'] for z in part],'funding_endpoint':end}
def plans(bars,funding,availability=60,threshold=.0006):
 out={k:[] for k in IDS};trails={6:{},10:{}};times=sorted(funding);stats={'price_impulses':0,'missing_funding_impulses':0}
 tr=[b['h']-b['l'] if i==0 else max(b['h']-b['l'],abs(b['h']-bars[i-1]['c']),abs(b['l']-bars[i-1]['c'])) for i,b in enumerate(bars)];daily={b['t']+4*HOUR:b['c'] for b in bars if (b['t']+4*HOUR)%DAY==0}
 for i in range(20,len(bars)):
  b=bars[i];t=b['t']+4*HOUR;atr=math.fsum(tr[i-20:i])/20
  trails[10][t]={'source':t,'long':min(z['l'] for z in bars[i-9:i+1])-.1*atr,'short':max(z['h'] for z in bars[i-9:i+1])+.1*atr};d=b['c']-bars[i-1]['c']
  if atr<=0 or abs(d)<atr:continue
  stats['price_impulses']+=1;info=known(times,funding,t,availability)
  if info is None:stats['missing_funding_impulses']+=1;continue
  ds=[daily.get(t//DAY*DAY-j*DAY) for j in range(19,-1,-1)];er=0;direction=0
  if all(v is not None for v in ds):
   length=math.fsum(abs(y-x) for x,y in zip(ds,ds[1:]));er=abs(ds[-1]-ds[0])/length if length else 0;direction=np.sign(ds[-1]-ds[0])
  regime='up' if er>=.3 and direction>0 else 'down' if er>=.3 and direction<0 else 'range';side=1 if d>0 else -1;f=info['known_funding']
  for name in IDS:
   if name=='F_JOIN' and side*f<threshold:continue
   if name=='F_CROWD' and side*f>-threshold:continue
   out[name].append({'family':name,'source':t,'side':side,'stop':b['c']-side*2*atr,'atr':atr,'target':None,'regime':regime,'er':float(er),'flow':None,'origin':None,'price_change':d,'signal_close':b['c'],**info})
 return out,trails,stats

def run(out):
 out=Path(out);rows,bars,funding,audit=engine.load();cache={};results={};summary={};uncertainty={};conflicts={ms(c['time'].replace('Z','')) for c in audit['unresolved']}
 for scenario,c in SCENARIOS.items():
  conf=dict(c);availability=conf.pop('availability',60);threshold=conf.pop('threshold',.0006);key=(availability,threshold)
  if key not in cache:
   cache[key]=plans(bars,funding,availability,threshold);ps,tr,stats=cache[key];write(out/f'signals-a{availability}-f{threshold:.4f}.json.gz',{'plans':ps,'trails':tr,'counts':stats,'availability_minutes':availability,'threshold':threshold})
  ps,tr,stats=cache[key]
  for period,(start,end) in PERIODS.items():
   for name in IDS:
    if scenario.startswith('fund') and name=='P_FUND_MASK':continue
    x=engine.simulate(rows,ps[name],tr,funding,'C_CHANNEL',start,end,conflict_hours=conflicts,**conf)
    x.update(family=name,period=period,scenario=scenario,funding_config={'availability_minutes':availability,'threshold':threshold},implementation_sha256=sha(Path(__file__).read_bytes()));x['summary']['signals']=sum(start<=e['source']<end for e in ps[name]);x['summary']['time_in_position_pct']=sum(t['exit']-t['entry'] for t in x['trades'])/(end-start)*100
    write(out/f'{period}-{name}-{scenario}.json.gz',x);results[(period,name,scenario)]=x;summary[f'{period}-{name}-{scenario}']=x['summary']
    if scenario=='base':print(json.dumps({'period':period,'name':name,**x['summary']}),flush=True)
 for period in PERIODS:
  for name in IDS:
   x=results[(period,name,'base')];uncertainty[f'{period}-{name}']={'mean':[interval(x,length=n) for n in (7,14,28)],'control_difference':[interval(x,results[(period,'P_FUND_MASK','base')],n) for n in (7,14,28)]}
 gates={}
 for name in IDS:
  m=summary['main-'+name+'-base'];r=summary['recent-'+name+'-base'];g={'main_return':m['return_pct']>52.8387132247115,'main_dd':m['dd_pct']<=13.561952026088653,'recent_return':r['return_pct']>4.62839056986033,'recent_dd':r['dd_pct']<=10.450945997063743,'years':m['positive_years']>=3,'sharpe':m['sharpe']>=.8,'trades':m['trades']>=100,'margin':m['margin_breaches']==r['margin_breaches']==0}
  for scenario in ('base','cost_x2','execution60','availability240'):g[scenario]=all(summary[p+'-'+name+'-'+scenario]['net']>0 for p in PERIODS)
  extra={}
  if name!='P_FUND_MASK':
   for p in PERIODS:
    a=summary[p+'-'+name+'-base'];b=summary[p+'-P_FUND_MASK-base'];extra[p]=a['net']>b['net'] and a['dd_pct']<=b['dd_pct']
   for scenario in ('cost_x2','availability240'):
    a=summary['main-'+name+'-'+scenario];b=summary['main-P_FUND_MASK-'+scenario];extra[scenario]=a['net']>0 and a['net']>b['net']
  gates[name]={'passed':all(g.values()),'checks':g,'incremental':extra,'incremental_passed':all(extra.values()) if extra else None}
 write(out/'summary.json',summary);write(out/'selection.json',gates);write(out/'uncertainty.json',uncertainty);print(json.dumps(gates),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
