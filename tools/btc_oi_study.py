"""BTC-only OI impulse study. Offline archives; no live-bot imports or order API."""
import argparse,gzip,importlib.util,json,math
from pathlib import Path
import numpy as np
from btc_perp_bot.research.archive import DAY,HOUR,canonical,ms,sha
ROOT=Path(__file__).resolve().parents[1]
ENGINE_SHA='8274d1ebdf8fd2a97448693847e761ba47ce5a2280b4dd8996a61cb6655b8451'
assert sha((ROOT/'tools/structural_study.py').read_bytes())==ENGINE_SHA
spec=importlib.util.spec_from_file_location('_btc_oi_frozen_engine',ROOT/'tools/structural_study.py');engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
engine.MAX_DAYS['C_CHANNEL']=5;engine.MAX_DAYS['O_FLUSH']=2
STEP=engine.STEP;IDS=('P_MOM','O_GROW','P_FADE','O_FLUSH');PERIODS=engine.PERIODS
SCENARIOS={'base':{},'cost_x2':{'cost':2},'execution60':{'delay':HOUR},'stop5':{'stop_extra':.0005},'risk_half':{'risk':.0025},'availability0':{'availability':0},'availability240':{'availability':240},'availability1440':{'availability':1440},'oi1':{'threshold':.01},'oi4':{'threshold':.04}}
def write(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);raw=canonical(value)
 if path.suffix=='.gz':raw=gzip.compress(raw,mtime=0)
 if path.exists() and path.read_bytes()!=raw:raise ValueError('Immutable output differs: '+str(path))
 path.write_bytes(raw)
def load_oi():
 p=ROOT/'data/oi-inputs-20261002/BTCUSDT.jsonl.gz';assert sha(p.read_bytes())=='76acc5bba07b27e50f2c780eb58e557e1c003c35a7cf2cacc69024c19c695b0f'
 records=[json.loads(s) for s in gzip.decompress(p.read_bytes()).splitlines()];first=records[0]['observation_complete_assumed_ms'];last=records[-1]['observation_complete_assumed_ms']
 a=np.full((last-first)//STEP+1,np.nan)
 for r in records:
  assert r['observation_complete_assumed_ms']==r['source_time_ms']+STEP
  if r['oi_usable']:a[(r['observation_complete_assumed_ms']-first)//STEP]=float(r['oi_qty'])
 return first,a

def oi_change(first,a,t,availability):
 endpoint=t-availability*60_000;i=(endpoint-first)//STEP
 if endpoint<first or (endpoint-first)%STEP or i>=len(a) or i<48:return None
 window=a[i-48:i+1]
 if not np.all(np.isfinite(window)) or np.any(window<=0):return None
 return {'oi_change':float(window[-1]/window[0]-1),'oi_start_qty':float(window[0]),'oi_end_qty':float(window[-1]),'oi_observation_end':endpoint,'oi_observation_start':endpoint-4*HOUR,'oi_assumed_available':endpoint+availability*60_000}

def plans(bars,first,oi,availability=60,threshold=.02):
 out={k:[] for k in IDS};trails={6:{},10:{}};stats={'price_impulses':0,'missing_oi_impulses':0}
 tr=[b['h']-b['l'] if i==0 else max(b['h']-b['l'],abs(b['h']-bars[i-1]['c']),abs(b['l']-bars[i-1]['c'])) for i,b in enumerate(bars)]
 daily={b['t']+4*HOUR:b['c'] for b in bars if (b['t']+4*HOUR)%DAY==0}
 for i in range(20,len(bars)):
  b=bars[i];t=b['t']+4*HOUR;atr=math.fsum(tr[i-20:i])/20
  trails[10][t]={'source':t,'long':min(z['l'] for z in bars[i-9:i+1])-.1*atr,'short':max(z['h'] for z in bars[i-9:i+1])+.1*atr}
  d=b['c']-bars[i-1]['c']
  if atr<=0 or abs(d)<atr:continue
  stats['price_impulses']+=1;info=oi_change(first,oi,t,availability)
  if info is None:stats['missing_oi_impulses']+=1;continue
  ds=[daily.get(t//DAY*DAY-j*DAY) for j in range(19,-1,-1)]
  er=0.;direction=0
  if all(v is not None for v in ds):
   path=math.fsum(abs(y-x) for x,y in zip(ds,ds[1:]));er=abs(ds[-1]-ds[0])/path if path else 0.;direction=np.sign(ds[-1]-ds[0])
  regime='up' if er>=.3 and direction>0 else 'down' if er>=.3 and direction<0 else 'range'
  s=1 if d>0 else -1
  for name in IDS:
   if name=='O_GROW' and info['oi_change']<threshold:continue
   if name=='O_FLUSH' and info['oi_change']>-threshold:continue
   side=s if name in ('P_MOM','O_GROW') else -s;fade=name in ('P_FADE','O_FLUSH')
   out[name].append({'family':name,'source':t,'side':side,'stop':b['c']-side*2*atr,'atr':atr,'target':b['c']+side*3*atr if fade else None,'regime':regime,'er':float(er),'flow':None,'origin':None,'price_change':d,'signal_close':b['c'],**info})
 return out,trails,stats

def interval(r,other=None,length=14):
 eq=np.array([1000.]+[d['equity'] for d in r['daily']]);a=eq[1:]/eq[:-1]-1
 if other is not None:
  eq2=np.array([1000.]+[d['equity'] for d in other['daily']]);a-=eq2[1:]/eq2[:-1]-1
 rng=np.random.default_rng(1486+length);idx=(rng.integers(0,len(a),(2000,math.ceil(len(a)/length),1))+np.arange(length))%len(a)
 v=a[idx.reshape(2000,-1)[:,:len(a)]].mean(axis=1)*100
 return {'block_days':length,'mean_daily_pct':float(a.mean()*100),'ci95':np.quantile(v,[.025,.975]).tolist(),'ci_bonferroni2':np.quantile(v,[.0125,.9875]).tolist(),'replicates':2000}

def run(out):
 out=Path(out);rows,bars,funding,audit=engine.load();first,oi=load_oi();cache={};results={};summary={};uncertainty={}
 conflicts={ms(c['time'].replace('Z','')) for c in audit['unresolved']}
 for scenario,c in SCENARIOS.items():
  config=dict(c);available=config.pop('availability',60);threshold=config.pop('threshold',.02);key=(available,threshold)
  if key not in cache:
   cache[key]=plans(bars,first,oi,available,threshold);ps,tr,st=cache[key]
   write(out/f'signals-a{available}-q{threshold:.2f}.json.gz',{'plans':ps,'trails':tr,'counts':st,'availability_minutes':available,'threshold':threshold})
  ps,tr,st=cache[key]
  for period,(start,end) in PERIODS.items():
   for name in IDS:
    if scenario.startswith('oi') and name.startswith('P_'):continue
    alias='C_CHANNEL' if name in ('P_MOM','O_GROW') else 'O_FLUSH'
    x=engine.simulate(rows,ps[name],tr,funding,alias,start,end,conflict_hours=conflicts,**config)
    x.update(family=name,period=period,scenario=scenario,oi_config={'availability_minutes':available,'threshold':threshold},implementation_sha256=sha(Path(__file__).read_bytes()))
    x['summary']['signals']=sum(start<=e['source']<end for e in ps[name])
    x['summary']['time_in_position_pct']=sum(t['exit']-t['entry'] for t in x['trades'])/(end-start)*100
    write(out/f'{period}-{name}-{scenario}.json.gz',x);results[(period,name,scenario)]=x;summary[f'{period}-{name}-{scenario}']=x['summary']
    if scenario=='base':print(json.dumps({'period':period,'name':name,**x['summary']}),flush=True)
 for period in PERIODS:
  for name in IDS:
   ctrl='P_MOM' if name=='O_GROW' else 'P_FADE' if name=='O_FLUSH' else None
   x=results[(period,name,'base')];uncertainty[f'{period}-{name}']={'mean':[interval(x,length=n) for n in (7,14,28)],'control_difference':[interval(x,results[(period,ctrl,'base')],n) for n in (7,14,28)] if ctrl else None}
 gates={}
 for name in IDS:
  m=summary['main-'+name+'-base'];r=summary['recent-'+name+'-base']
  gate={'main_return':m['return_pct']>52.8387132247115,'main_dd':m['dd_pct']<=13.561952026088653,'recent_return':r['return_pct']>4.62839056986033,'recent_dd':r['dd_pct']<=10.450945997063743,'years':m['positive_years']>=3,'sharpe':m['sharpe']>=.8,'trades':m['trades']>=100,'margin':m['margin_breaches']==r['margin_breaches']==0}
  for s in ('cost_x2','execution60','availability240'):gate[s]=all(summary[p+'-'+name+'-'+s]['net']>0 for p in PERIODS)
  ctrl='P_MOM' if name=='O_GROW' else 'P_FADE' if name=='O_FLUSH' else None
  info={}
  if ctrl:
   for p in PERIODS:
    b=summary[p+'-'+ctrl+'-base'];a=summary[p+'-'+name+'-base'];info[p]=a['return_pct']>b['return_pct'] and a['dd_pct']<=b['dd_pct']
   for s in ('cost_x2','availability240'):
    a=summary['main-'+name+'-'+s];b=summary['main-'+ctrl+'-'+s];info[s]=a['net']>0 and a['net']>b['net']
  gates[name]={'improvement':gate,'passed':all(gate.values()),'oi_incremental':info,'oi_passed':all(info.values()) if info else None}
 write(out/'summary.json',summary);write(out/'uncertainty.json',uncertainty);write(out/'selection.json',gates)
 print(json.dumps(gates),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
