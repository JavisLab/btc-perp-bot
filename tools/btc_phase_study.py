"""Preregistered BTC protocol-phase and completed-price confirmation; public frozen headers only."""
import argparse,calendar,datetime as dt,json,math,struct,hashlib
from pathlib import Path
import numpy as np
from btc_persistence_study import Market,PERIODS
from btc_session_study import write,read,bootstrap,sha,canonical,DAY,HOUR,ROOT,ms
import btc_target_ledger as ledger
IDS=('PH_CONFIRM','PH_PRICE','PH_LONG','PH_CLOCK','PH_SHIFT');ledger.LABELS.update({n:n for n in IDS})
SCENARIOS={'base':{},'cost_x2':{'multiplier':2},'delay1':{'delay':1},'delay24':{'delay':24},'risk10':{'risk_target':.1}}
HEADER_SHA='640640402c22ef1f40c92ac774952b3787d6946892b1685ed746c3f83f5d7605'
def validate_header(h):
 raw=struct.pack('<I',h['version'])+bytes.fromhex(h['previousblockhash'])[::-1]+bytes.fromhex(h['merkle_root'])[::-1]+struct.pack('<III',h['timestamp'],h['bits'],h['nonce']);digest=hashlib.sha256(hashlib.sha256(raw).digest()).digest()[::-1].hex();target=(h['bits']&0x7fffff)*2**(8*((h['bits']>>24)-3))
 assert digest==h['id'] and int(digest,16)<=target
 return h['timestamp']*1000

def headers():
 p=ROOT/'data/btc-phase-20261002/halvings.json';assert sha(p.read_bytes())==HEADER_SHA;d=read(p);out=[]
 for e in d['events']:
  a=[x['header'] for x in e['sources'] if 'header' in x];assert len(a)==2 and a[0]==a[1] and a[0]['height']==e['height'];t=validate_header(a[0]);out.append({'height':e['height'],'time':t,'hash':a[0]['id']})
 assert [e['height'] for e in out]==[210000,420000,630000,840000]
 return out

def months(t,n):
 d=dt.datetime.fromtimestamp(t/1000,dt.timezone.utc);z=d.year*12+d.month-1+n;y,mo=divmod(z,12);d=d.replace(year=y,month=mo+1,day=min(d.day,calendar.monthrange(y,mo+1)[1]));return int(d.timestamp()*1000)

def phase(events,t,lag=DAY):
 known=[e for e in events if e['time']+lag<=t]
 if not known:return {'known':False,'height':None,'event_time':None,'available':None,'lower':None,'upper':None,'shift_lower':None,'phase':False,'shift_phase':False}
 e=max(known,key=lambda e:e['time']);lo,hi,shift=months(e['time'],18),months(e['time'],30),months(e['time'],6)
 return {'known':True,'height':e['height'],'event_time':e['time'],'available':e['time']+lag,'lower':lo,'upper':hi,'shift_lower':shift,'phase':lo<=t<hi,'shift_phase':shift<=t<lo}

def signal(name,s,e):
 if name=='PH_PRICE':return s
 if name=='PH_LONG':return max(0,s)
 if not e['known']:return 0.
 if name=='PH_CLOCK':return -1. if e['phase'] else 1.
 down=e['shift_phase'] if name=='PH_SHIFT' else e['phase']
 return min(0,s) if down else max(0,s)

def schedule(m,feats,name,start,end,risk=.2):
 table={e['source']:e for e in feats};out=[]
 for t in range(start,end,DAY):
  e={k:v for k,v in table[t].items() if k!='source'};obs=m.observation(t,risk)
  if obs is None:out.append({'source_time':t,'weights':None,'detail':dict(e,risk_missing=True)});continue
  score,w,vol=obs;s=signal(name,score,e)
  out.append({'source_time':t,'weights':{'BS':max(0,s)*w,'BP':min(0,s)*w},'rebalance':True,'hedge':False,'detail':dict(e,score=score,risk=w,vol=vol,signal=s)})
 return out

def run(out):
 out=Path(out);m=Market();events=headers();feats=[dict(source=t,**phase(events,t)) for t in range(ms('2020-01-01'),ms('2026-09-01'),DAY)];write(out/'features.json.gz',feats);results={};summary={};unc={};identity={};activity={}
 for period,(start,end) in PERIODS.items():
  ff=[e for e in feats if start<=e['source']<end];activity[period]={'phase_days':sum(e['phase'] for e in ff),'shift_phase_days':sum(e['shift_phase'] for e in ff),'epoch_days':{str(h):sum(e['height']==h for e in ff) for h in (210000,420000,630000,840000)},'strategies':{}}
  for name in IDS:
   for scenario,c in SCENARIOS.items():
    cfg=dict(c);risk=cfg.pop('risk_target',.2);plan=schedule(m,feats,name,start,end,risk);write(out/f'{period}-{name}-plan-risk{risk:.2f}.json.gz',plan);x=ledger.simulate(m,name,start,end,plan,**cfg);x.update(period=period,scenario=scenario,risk_target=risk,schedule_sha256=sha(canonical(plan)),implementation_sha256=sha(Path(__file__).read_bytes()),ledger_sha256=sha((ROOT/'tools/btc_target_ledger.py').read_bytes()),headers_sha256=HEADER_SHA);write(out/f'{period}-{name}-{scenario}.json.gz',x);results[period,name,scenario]=x;summary[f'{period}-{name}-{scenario}']={'metrics':x['metrics'],'annual':x['periods']['yearly']}
    if scenario=='base':
     print(json.dumps({'period':period,'name':name,**{k:x['metrics'][k] for k in ('return_pct','max_drawdown_pct','sharpe','realized_vol_pct','round_trips','fees','funding')}}),flush=True);activity[period]['strategies'][name]={'long_days':sum(e['detail'].get('signal',0)>0 for e in plan),'short_days':sum(e['detail'].get('signal',0)<0 for e in plan),'cash_days':sum(e['detail'].get('signal',0)==0 for e in plan),'risk_missing_days':sum(e['weights'] is None for e in plan)}
  for name,oldpath in [('PH_LONG',f'runs/search-1458/{period}-E_SPOT.json.gz'),('PH_PRICE',f'runs/btc-persistence-20261002/{period}-E_MIX-base.json.gz')]:
   old=read(ROOT/oldpath);ctrl=results[period,name,'base'];errors={k:abs(ctrl['metrics'][k]-old['metrics'][k]) for k in ('return_pct','max_drawdown_pct','fees','impact','funding')};daily=max(abs(a-b) for a,b in zip(ctrl['daily_returns'],old['daily_returns']));assert len(ctrl['daily_returns'])==len(old['daily_returns']) and daily<1e-9 and max(errors.values())<1e-7,(period,name,errors,daily);identity[period+'-'+name]={'metric_errors':errors,'daily_return_max_error':daily,'saved_control':oldpath}
  for name in IDS:
   r=np.array(results[period,name,'base']['daily_returns']);unc[period+'-'+name]={'mean':[bootstrap(r,n) for n in (7,14,28)]}
   for ctrl in ('PH_PRICE','PH_SHIFT'):unc[period+'-'+name]['vs_'+ctrl]=[bootstrap(r-np.array(results[period,ctrl,'base']['daily_returns']),n) for n in (7,14,28)]
 a=results['main','PH_CONFIRM','base']['metrics'];b=results['recent','PH_CONFIRM','base']['metrics'];g={'main_return':a['return_pct']>52.838713,'main_dd':a['max_drawdown_pct']<=13.561952,'recent_return':b['return_pct']>4.628391,'recent_dd':b['max_drawdown_pct']<=10.450946,'main_vol':a['realized_vol_pct']<=13.343621,'recent_vol':b['realized_vol_pct']<=16.520409,'sharpe':a['sharpe'] is not None and a['sharpe']>=.8,'years':sum(v['return_pct']>0 for v in results['main','PH_CONFIRM','base']['periods']['yearly'].values())>=3,'episodes':a['round_trips']>=20,'margin':a['margin_buffer_breach_hours']==b['margin_buffer_breach_hours']==0}
 for c in ('base','cost_x2','delay1','delay24'):g[c]=all(results[p,'PH_CONFIRM',c]['metrics']['net_pnl']>0 for p in PERIODS)
 extra={}
 for n in ('PH_PRICE','PH_SHIFT'):extra['net_beats_'+n+'_both']=all(results[p,'PH_CONFIRM','base']['metrics']['net_pnl']>results[p,n,'base']['metrics']['net_pnl'] for p in PERIODS)
 for n in ('PH_PRICE','PH_CLOCK'):extra['dd_no_worse_'+n+'_both']=all(results[p,'PH_CONFIRM','base']['metrics']['max_drawdown_pct']<=results[p,n,'base']['metrics']['max_drawdown_pct'] for p in PERIODS)
 extra['main_sharpe_no_worse_clock']=a['sharpe'] is not None and results['main','PH_CLOCK','base']['metrics']['sharpe'] is not None and a['sharpe']>=results['main','PH_CLOCK','base']['metrics']['sharpe']
 for n,v in [('summary',summary),('uncertainty',unc),('control-identity',identity),('activity',activity),('selection',{'primary':'PH_CONFIRM','passed':all(g.values()) and all(extra.values()),'checks':g,'information_increment':extra,'scope':'development only; few observed cycles, public protocol header not first-seen publication, causal clock not causal halving proof; controls not promotable'})]:write(out/f'{n}.json',v)
 print(json.dumps({'gates':g,'increment':extra,'activity':activity}),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();run(a.out)
