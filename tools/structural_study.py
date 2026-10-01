"""Fixed structural hypotheses, offline account simulator. Never sends orders."""
import argparse
import gzip
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

from btc_perp_bot.research.archive import DAY, HOUR, canonical, ms, sha, utc
from price_volume_study import aggregate, write_fixed

ROOT=Path(__file__).resolve().parents[1]
STEP=300_000
IDS=('A_ACCEPT','R_RETEST','F_REJECT','P_RESUME','C_CHANNEL')
LABELS=dict(zip(IDS,('돌파 유지','돌파 후 재시험','실패 돌파 복귀','추세 눌림 재개','55봉 채널 추종')))
PERIODS={'main':(ms('2022-01-01'),ms('2026-01-01')),
         'recent':(ms('2026-01-01'),ms('2026-09-01'))}
SCENARIOS={'base':{},'cost_x2':{'cost':2},'delay60':{'delay':HOUR},
           'stop_5bp':{'stop_extra':.0005},'risk_half':{'risk':.0025},
           'risk_double':{'risk':.01},'flow55':{'flow_filter':True}}
MAX_DAYS=dict(zip(IDS,(5,10,5,14,30)))


def load():
    source=ROOT/'data/structure-1471'
    rows=json.loads(gzip.decompress((source/'bars-repaired.json.gz').read_bytes()))['rows']
    audit=json.loads((source/'resolution.json').read_text())
    if sha(canonical(rows))!=audit['repaired_rows_sha256']: raise ValueError('Fine dataset hash')
    hourly=json.loads(gzip.decompress((ROOT/'runs/price-volume-1462/ohlcv.json.gz').read_bytes()))['rows']
    if sha(canonical(hourly))!='1724851f889b7602fa4736dc71a9e6c76db1547be6a3d7be64092f55c27ba551':
        raise ValueError('Hourly dataset hash')
    raw=gzip.decompress((ROOT/'data/search-1458/market.json.gz').read_bytes())
    if sha(raw)!='9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4':
        raise ValueError('Funding dataset hash')
    p=json.loads(raw)['series']['BTCUSDT']; mark={r[0]:r[1] for r in p['mark']}
    funding={r[0]:{'rate':r[2],'reference':mark[r[0]],'raw_time':r[3]} for r in p['funding']}
    return rows,aggregate(hourly),funding,audit


def signals(bars):
    """Every field depends only on bars whose close time is <= source."""
    out={name:[] for name in IDS}; trails={6:{},10:{}}
    daily={b['t']+4*HOUR:b['c'] for b in bars if (b['t']+4*HOUR)%DAY==0}
    tr=[b['h']-b['l'] if i==0 else max(b['h']-b['l'],abs(b['h']-bars[i-1]['c']),abs(b['l']-bars[i-1]['c']))
        for i,b in enumerate(bars)]
    clv=[(b['c']-b['l'])/(b['h']-b['l']) if b['h']>b['l'] else .5 for b in bars]
    a=[None if i<20 else math.fsum(tr[i-20:i])/20 for i in range(len(bars))]
    bounds={i:(max(b['h'] for b in bars[i-20:i]),min(b['l'] for b in bars[i-20:i])) for i in range(20,len(bars))}
    def brk(j,s):
        u,l=bounds[j]
        return (bars[j]['c']>u and clv[j]>=.75) if s==1 else (bars[j]['c']<l and clv[j]<=.25)
    for i in range(60,len(bars)):
        b=bars[i]; p=bars[i-1]; source=b['t']+4*HOUR; atr=a[i]
        if atr<=0: continue
        day=source//DAY*DAY
        ds=[daily.get(day-j*DAY) for j in range(19,-1,-1)]
        if any(x is None for x in ds): continue
        path=math.fsum(abs(y-x) for x,y in zip(ds,ds[1:])); change=ds[-1]-ds[0]
        er=abs(change)/path if path>0 else 0.; direction=1 if change>0 else -1 if change<0 else 0
        regime='up' if er>=.3 and direction==1 else 'down' if er>=.3 and direction==-1 else 'range'
        for n in (6,10):
            trails[n][source]={'source':source,'long':min(z['l'] for z in bars[i-n+1:i+1])-.1*atr,
                               'short':max(z['h'] for z in bars[i-n+1:i+1])+.1*atr}
        for side in (1,-1):
            trend=er>=.3 and direction==side
            loc=clv[i]>=.75 if side==1 else clv[i]<=.25
            body=side*(b['c']-b['o'])>0
            flow=(b['buy']/b['v'] if side==1 else 1-b['buy']/b['v']) if b['v']>0 else None
            def add(name,stop,target=None,origin=None):
                out[name].append({'family':name,'source':source,'side':side,'stop':stop,
                    'atr':atr,'target':target,'regime':regime,'er':er,'flow':flow,'origin':origin})
            # Acceptance: original breakout boundary, not a new rolling boundary.
            u,l=bounds[i-1]; level=u if side==1 else l
            if brk(i-1,side) and side*(b['c']-level)>0 and side*(b['c']-p['c'])>0:
                stop=min(b['l'],p['l'])-.1*atr if side==1 else max(b['h'],p['h'])+.1*atr
                add('A_ACCEPT',stop,origin=p['t']+4*HOUR)
            # Most recent breakout is selected independently of later retest success.
            j=next((j for j in range(i-1,i-7,-1) if brk(j,side)),None)
            if j is not None and trend and loc and body:
                upper,lower=bounds[j]; level=upper if side==1 else lower
                held=all(side*(z['c']-level)>=0 for z in bars[j+1:i])
                test=b['l']<=level+.1*atr if side==1 else b['h']>=level-.1*atr
                if held and test and side*(b['c']-level)>0:
                    add('R_RETEST',b['l']-.1*atr if side==1 else b['h']+.1*atr,origin=bars[j]['t']+4*HOUR)
            failure=(p['l']<l<p['c'] and clv[i-1]>=.75 and b['c']>p['h']) if side==1 else (
                     p['h']>u>p['c'] and clv[i-1]<=.25 and b['c']<p['l'])
            if er<.3 and failure and not (p['h']>u and p['l']<l):
                add('F_REJECT',p['l']-.1*atr if side==1 else p['h']+.1*atr,
                    target=u if side==1 else l,origin=p['t']+4*HOUR)
            u,l=bounds[i]; old=bars[i-40:i-20]
            old_u,old_l=max(z['h'] for z in old),min(z['l'] for z in old)
            structure=(u>old_u and l>old_l) if side==1 else (u<old_u and l<old_l)
            pull=side*(bars[i-3]['c']-bars[i-2]['c'])>0 and side*(bars[i-2]['c']-p['c'])>0
            resumed=b['c']>p['h'] if side==1 else b['c']<p['l']
            if trend and structure and pull and resumed and body and loc:
                part=bars[i-2:i+1]
                add('P_RESUME',min(z['l'] for z in part)-.1*atr if side==1 else max(z['h'] for z in part)+.1*atr)
            level=max(z['h'] for z in bars[i-55:i]) if side==1 else min(z['l'] for z in bars[i-55:i])
            if trend and loc and side*(b['c']-level)>0: add('C_CHANNEL',b['c']-side*2*atr)
    # Conflicting directions at one source are excluded, not resolved after outcome.
    for name in IDS:
        counts=Counter(e['source'] for e in out[name]); out[name]=[e for e in out[name] if counts[e['source']]==1]
    return out,trails


def exit_at_bar(row,side,stop,target,time_exit=False):
    """Returns conservative price/reason; zero-volume bars are unfillable."""
    _,o,h,l,c,v=row[:6]
    if v<=0: return None
    gap=side*(o-stop)<=0
    touch=l<=stop if side==1 else h>=stop
    profit=target is not None and (h>=target if side==1 else l<=target)
    if gap: return (o,'stop_gap',bool(touch and profit))
    if time_exit: return (o,'time',False)
    if touch: return (stop,'stop',bool(profit))
    if profit: return (target,'target',False)
    return None


def sized(equity,reference,stop,side,fee,impact,risk,stop_extra=0):
    fill=reference*(1+side*impact); stopped=stop*(1-side*(impact+stop_extra))
    perunit=side*(fill-stopped)+fee*(fill+stopped)
    if perunit<=0 or equity<=0: return 0.
    amount=min(equity*risk/perunit,equity/fill)
    qty=math.floor((amount+1e-12)/.001)*.001
    return qty if qty*fill>=50 else 0.


def metrics(daily,trades,maxdd,start,end):
    equities=np.array([1000.]+[x['equity'] for x in daily]); ret=equities[1:]/equities[:-1]-1
    net=equities[-1]-1000.; years=(end-start)/DAY/365.25
    sharpe=float(ret.mean()/ret.std(ddof=1)*math.sqrt(365)) if len(ret)>1 and ret.std(ddof=1)>0 else 0.
    annual={};quarter={}
    for d,r in zip(daily,ret):
        date=utc(d['time']-1); year=date[:4]; q=year+'Q'+str((int(date[5:7])-1)//3+1)
        annual[year]=annual.get(year,1.)*(1+r);quarter[q]=quarter.get(q,1.)*(1+r)
    annual={k:(v-1)*100 for k,v in annual.items()};quarter={k:(v-1)*100 for k,v in quarter.items()}
    all_growth=math.prod(1+v/100 for v in quarter.values())
    exbest=(all_growth/(1+max(quarter.values())/100)-1)*100 if quarter else 0.
    profits=[t['net'] for t in trades]; wins=math.fsum(max(0,x) for x in profits);losses=-math.fsum(min(0,x) for x in profits)
    sides={s:{'trades':sum(t['side']==sign for t in trades),'net':math.fsum(t['net'] for t in trades if t['side']==sign)} for s,sign in [('long',1),('short',-1)]}
    return {'net':net,'return_pct':net/10,'cagr_pct':((equities[-1]/1000)**(1/years)-1)*100 if equities[-1]>0 else -100.,
        'sharpe':sharpe,'dd_pct':maxdd,'trades':len(trades),'profit_factor':wins/losses if losses>0 else None,
        'win_rate':sum(x>0 for x in profits)/len(profits)*100 if profits else 0.,'annual':annual,'quarterly':quarter,
        'positive_years':sum(v>0 for v in annual.values()),'ex_best_quarter_pct':exbest,'sides':sides,
        'mean_hold_hours':float(np.mean([(x['exit']-x['entry'])/HOUR for x in trades])) if trades else 0.,
        'regimes':{r:{'trades':sum(t['regime']==r for t in trades),'net':math.fsum(t['net'] for t in trades if t['regime']==r)} for r in ('up','down','range')}}


def simulate(rows,events,trails,funding,name,start,end,*,cost=1.,delay=0,risk=.005,stop_extra=0.,flow_filter=False,conflict_hours=()):
    fee=.0005*cost;impact=.00015*cost
    source_map={e['source']:e for e in events if start<=e['source']<end}
    trail_map=trails[6 if name=='P_RESUME' else 10] if name in ('P_RESUME','C_CHANNEL') else {}
    cash=1000.;pos=None;pending=None;ledger=[];trades=[];daily=[];skips=Counter()
    peak=1000.;maxdd=0.;stressdd=0.;minmargin=None;breaches=0;ambiguous=0;conflict_exposure=0;max_participation=0.
    last_exit=-1;halt=False;fund_total=fee_total=impact_total=0.
    def equity(price): return cash+(pos['qty']*pos['side']*(price-pos['fill']) if pos else 0.)
    def close(t,ref,reason,phase):
        nonlocal cash,pos,fee_total,impact_total,last_exit
        s,q=pos['side'],pos['qty']; extra=stop_extra if reason.startswith('stop') else 0.
        fill=ref*(1-s*(impact+extra)); f=q*fill*fee; imp=q*ref*(impact+extra)
        pnl=s*q*(fill-pos['fill']); cash+=pnl-f;fee_total+=f;impact_total+=imp
        net=pnl-pos['entry_fee']-f+pos['funding']
        trades.append({**pos,'exit':t,'exit_reference':ref,'exit_fill':fill,'exit_fee':f,'net':net,'reason':reason,
                       'price_gross':s*q*(ref-pos['reference']),'impact':pos['entry_impact']+imp,'fees':pos['entry_fee']+f})
        ledger.append({'kind':'exit','time':t,'phase':phase,'reference':ref,'fill':fill,'fee':f,'impact':imp,'cash':cash,
                       'qty':q,'side':s,'reason':reason,'stop':pos['stop'],'target':pos['target']})
        pos=None;last_exit=t
    for row in rows:
        t,o,h,l,c,v=row[:6]
        if t<start or t>=end: continue
        # Settlement belongs to carried inventory, before fills at this boundary.
        if pos and t in funding:
            f=funding[t]; flow=-pos['side']*pos['qty']*f['rate']*f['reference']
            cash+=flow;pos['funding']+=flow;fund_total+=flow
            ledger.append({'kind':'funding','time':t,'cashflow':flow,'cash':cash,'qty':pos['qty'],'side':pos['side'],**f})
        if t in source_map:
            e=source_map[t]
            if pos: skips['signal_while_open']+=1
            elif flow_filter and (e['flow'] is None or e['flow']<.55): skips['flow_filter']+=1
            elif not halt: pending=dict(e,due=t+STEP+delay)
        # A completed bar can tighten, never widen, a stop after the fixed lag.
        source=t-STEP-delay
        if pos and source in trail_map and source>pos['source']:
            rule=trail_map[source];new=rule['long' if pos['side']==1 else 'short']
            if pos['side']*(new-pos['stop'])>0:
                pos['stop']=new
                ledger.append({'kind':'trail','time':t,'source':source,'stop':new})
        if pos:
            if t//HOUR*HOUR in conflict_hours:conflict_exposure+=1
            adverse=l if pos['side']==1 else h; stressed=equity(adverse)
            stressdd=max(stressdd,100*(1-stressed/peak))
            ratio=stressed/(pos['qty']*adverse)
            minmargin=ratio if minmargin is None else min(minmargin,ratio);breaches+=int(ratio<.05)
            action=exit_at_bar(row,pos['side'],pos['stop'],pos['target'],t>=pos['deadline'])
            if equity(o)<=0 and v>0: close(t,o,'insolvent','open');halt=True
            elif action:
                ref,reason,amb=action;ambiguous+=int(amb)
                close(t,ref,reason,'open' if reason in ('stop_gap','time') else 'intrabar')
        if pending:
            if t==pending['due']:
                e=pending;pending=None;s=e['side'];distance=s*(o-e['stop'])
                if pos or t<=last_exit:skips['busy_at_entry']+=1
                elif v<=0:skips['zero_volume_entry']+=1
                elif not .25*e['atr']<=distance<=4*e['atr']:skips['stop_distance']+=1
                elif name=='F_REJECT' and s*(e['target']-o)<1.5*distance:skips['reward_distance']+=1
                else:
                    qty=sized(cash,o,e['stop'],s,fee,impact,risk,stop_extra)
                    if qty==0:skips['minimum_size']+=1
                    else:
                        target=e['target']
                        if name in ('A_ACCEPT','R_RETEST'): target=o+s*distance*(2 if name=='A_ACCEPT' else 3)
                        fill=o*(1+s*impact);charge=qty*fill*fee;im=qty*o*impact
                        cash-=charge;fee_total+=charge;impact_total+=im
                        pos={**e,'entry':t,'qty':qty,'reference':o,'fill':fill,'entry_fee':charge,'entry_impact':im,
                             'initial_stop':e['stop'],'target':target,'funding':0.,'deadline':t+MAX_DAYS[name]*DAY,
                             'risk_budget':risk*(cash+charge)}
                        max_participation=max(max_participation,qty/v)
                        ledger.append({'kind':'entry','time':t,'phase':'open','source':e['source'],'qty':qty,'side':s,
                            'reference':o,'fill':fill,'fee':charge,'impact':im,'cash':cash,'stop':e['stop'],'target':target})
                        if t//HOUR*HOUR in conflict_hours:conflict_exposure+=1
                        adverse=l if s==1 else h;stressed=equity(adverse)
                        stressdd=max(stressdd,100*(1-stressed/peak));ratio=stressed/(qty*adverse)
                        minmargin=ratio if minmargin is None else min(minmargin,ratio);breaches+=int(ratio<.05)
                        # The entry bar is NOT exempt from stops/targets.
                        action=exit_at_bar(row,s,pos['stop'],target)
                        if action:
                            ref,reason,amb=action;ambiguous+=int(amb);close(t,ref,reason,'intrabar')
            elif t<pending['due'] and v>0:
                crossed=l<=pending['stop'] if pending['side']==1 else h>=pending['stop']
                if crossed:pending=None;skips['invalidated_before_entry']+=1
        if t+STEP==end and pos:
            if v<=0:raise ValueError('Cannot fabricate terminal fill in empty bar')
            close(end,c,'period_end','close')
        eq=equity(c);peak=max(peak,eq);maxdd=max(maxdd,100*(1-eq/peak))
        if t+STEP==end or (t+STEP)%DAY==0:
            daily.append({'time':t+STEP,'equity':eq,'cash':cash,'qty':pos['qty']*pos['side'] if pos else 0.,
                          'entry_fill':pos['fill'] if pos else None,'close':c})
        if eq<=0:halt=True
    if pos:raise ValueError('Unclosed position')
    summary=metrics(daily,trades,maxdd,start,end)
    if abs(math.fsum(x['net'] for x in trades)-(cash-1000))>1e-7:raise ValueError('Trade/account mismatch')
    summary.update({'fees':fee_total,'impact':impact_total,'funding':fund_total,'ambiguous_bars':ambiguous,
        'adverse_extreme_stress_dd_pct':stressdd,'min_margin_ratio':minmargin,'margin_breaches':breaches,
        'unresolved_archive_exposure_bars':conflict_exposure,'max_entry_bar_participation':max_participation,
        'skips':dict(skips),'halted':halt})
    return {'family':name,'start':start,'end':end,'config':{'cost':cost,'delay':delay,'risk':risk,'stop_extra':stop_extra,'flow_filter':flow_filter},
            'summary':summary,'daily':daily,'trades':trades,'events':ledger}


def bootstrap(daily,length):
    eq=np.array([1000.]+[d['equity'] for d in daily]);r=eq[1:]/eq[:-1]-1
    rng=np.random.default_rng(1471+length);blocks=math.ceil(len(r)/length)
    indices=(rng.integers(0,len(r),size=(2000,blocks,1))+np.arange(length))%len(r)
    vals=r[indices.reshape(2000,-1)[:,:len(r)]].mean(axis=1)*100
    return {'block_days':length,'mean_daily_pct':float(r.mean()*100),'ci95':np.quantile(vals,[.025,.975]).tolist(),
            'ci_bonferroni5':np.quantile(vals,[.005,.995]).tolist(),'replicates':2000}


def run(out,period,prepare=False):
    out=Path(out);rows,bars,funding,audit=load();plans,trails=signals(bars)
    signaldata={'signals':plans,'trails':trails,'fine_sha256':audit['repaired_rows_sha256']}
    write_fixed(out/'signals.json.gz',gzip.compress(canonical(signaldata),mtime=0))
    if prepare:
        print(json.dumps({'signal_counts':{k:len(v) for k,v in plans.items()},'fine_rows':len(rows)}));return
    start,end=PERIODS[period];summaries={};uncertainty={}
    conflicts={ms(c['time'].replace('Z','')) for c in audit['unresolved']}
    for name in IDS:
        summaries[name]={}
        for scenario,config in SCENARIOS.items():
            result=simulate(rows,plans[name],trails,funding,name,start,end,conflict_hours=conflicts,**config)
            result['period']=period;result['scenario']=scenario
            write_fixed(out/(period+'-'+name+'-'+scenario+'.json.gz'),gzip.compress(canonical(result),mtime=0))
            summaries[name][scenario]=result['summary']
            if scenario=='base':uncertainty[name]=[bootstrap(result['daily'],n) for n in (7,14,28)]
        print(json.dumps({'period':period,'family':name,**summaries[name]['base']},ensure_ascii=False),flush=True)
    result={'period':period,'summaries':summaries,'uncertainty':uncertainty}
    if period=='main':
        selection=[];gates={}
        for name,s in summaries.items():
            b,c=s['base'],s['cost_x2']
            gate={'cagr':b['cagr_pct']>=10,'sharpe':b['sharpe']>=.8,'drawdown':b['dd_pct']<=25,
                  'years':b['positive_years']>=3,'cost_x2':c['net']>0,'ex_best_quarter':b['ex_best_quarter_pct']>0,
                  'margin':b['margin_breaches']==0,'trades':b['trades']>=100}
            gates[name]=gate
            if all(gate.values()): selection.append(name)
        selection.sort(key=lambda n:min(summaries[n][s]['cagr_pct']/max(summaries[n][s]['dd_pct'],1e-9) for s in ('base','cost_x2')),reverse=True)
        result['gates']=gates;result['ranked_passes']=selection
        write_fixed(out/'selection.json',canonical({'ranked_passes':selection,'gates':gates,'recent_used':False}))
    write_fixed(out/(period+'-summary.json'),canonical(result))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--period',choices=PERIODS,default='main');p.add_argument('--prepare',action='store_true')
    a=p.parse_args();run(a.out,a.period,a.prepare)
