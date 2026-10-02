"""ETH independent raw-signal, Decimal cash and held-path audit; no simulator import."""
import csv
import gzip
import io
import json
import math
import zipfile
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

import numpy as np

from btc_perp_bot.research.archive import HOUR, DAY, canonical, ms, sha

ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/eth-transfer-performance-20261002';STEP=300_000
D=lambda x:Decimal(str(x))


def run():
    data_root=ROOT/'data/eth-transfer-20261002'
    assert sha((data_root/'audit.json').read_bytes())=='a3b8cb29c3749b2684aa15562ca0143356b7a462925386d3ec07087be3741771'
    audit=json.loads((data_root/'audit.json').read_bytes())
    def data(name):
        packed=(data_root/name).read_bytes();body=gzip.decompress(packed)
        assert sha(packed)==audit['artifacts'][name]['gzip_sha256']
        assert sha(body)==audit['artifacts'][name]['uncompressed_sha256']
        return json.loads(body)
    raw=data('bars-repaired.json.gz')['rows']
    rowmap={r[0]:r for r in raw};first=raw[0][0]
    # Raw official hourly CSVs, independently aggregated (not strategy arrays).
    hourly=[]
    paths=sorted((ROOT/'data/archive-1458/ETHUSDT/perp').glob('????-??.zip'))
    for path in paths:
        assert sha(path.read_bytes())==path.with_suffix('.CHECKSUM').read_text().split()[0]
        with zipfile.ZipFile(path) as z:
            hourly.extend([[int(r[0]),*map(float,r[1:6]),float(r[9])] for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())) if r[0].isdigit()])
    assert [r[0] for r in hourly]==list(range(ms('2020-02-01'),ms('2026-09-01'),HOUR))
    bars=[]
    for k in range(0,len(hourly),4):
        part=hourly[k:k+4]
        bars.append([part[0][0],part[0][1],max(x[2] for x in part),min(x[3] for x in part),part[-1][4],math.fsum(x[5] for x in part),math.fsum(x[6] for x in part)])
    arr=np.array(bars);ix={int(r[0])+4*HOUR:i for i,r in enumerate(arr)}
    tr=np.maximum(arr[:,2]-arr[:,3],np.maximum(abs(arr[:,2]-np.r_[arr[0,1],arr[:-1,4]]),abs(arr[:,3]-np.r_[arr[0,1],arr[:-1,4]])))
    atr=np.full(len(arr),np.nan);atr[20:]=np.lib.stride_tricks.sliding_window_view(tr,20)[:-1].mean(axis=1)
    q=np.divide(arr[:,4]-arr[:,3],arr[:,2]-arr[:,3],out=np.full(len(arr),.5),where=arr[:,2]>arr[:,3])
    dclose={int(r[0])+4*HOUR:r[4] for r in arr if (int(r[0])+4*HOUR)%DAY==0}
    plans=json.loads(gzip.decompress((RUN/'signals.json.gz').read_bytes()))
    validated_signals=0
    # Independently enumerate all positive AND negative candidate decisions.
    reconstructed={k:[] for k in ('A_ACCEPT','R_RETEST','F_REJECT','P_RESUME','C_CHANNEL')}
    for i in range(60,len(arr)):
        source=int(arr[i,0])+4*HOUR;day=source//DAY*DAY
        dc=[dclose.get(day-j*DAY) for j in range(19,-1,-1)]
        if any(x is None for x in dc) or atr[i]<=0:continue
        delta=dc[-1]-dc[0];length=sum(abs(y-x) for x,y in zip(dc,dc[1:]));er=abs(delta)/length if length else 0
        for s in (1,-1):
            col=2 if s==1 else 3;opp=3 if s==1 else 2
            extreme=max if s==1 else min;other=min if s==1 else max
            def level(j,n=20):return extreme(arr[j-n:j,col])
            def brk(j):return s*(arr[j,4]-level(j))>0 and (q[j]>=.75 if s==1 else q[j]<=.25)
            loc=q[i]>=.75 if s==1 else q[i]<=.25;trend=er>=.3 and s*delta>0
            def put(name,stop,target=None):reconstructed[name].append((source,s,float(stop),None if target is None else float(target)))
            if brk(i-1) and s*(arr[i,4]-level(i-1))>0 and s*(arr[i,4]-arr[i-1,4])>0:
                put('A_ACCEPT',other(arr[i-1:i+1,opp])-s*.1*atr[i])
            found=[j for j in range(i-6,i) if brk(j)]
            if found and trend and loc and s*(arr[i,4]-arr[i,1])>0:
                j=found[-1];lev=level(j)
                if all(s*(x-lev)>=0 for x in arr[j+1:i,4]) and s*(arr[i,opp]-lev)<=.1*atr[i] and s*(arr[i,4]-lev)>0:
                    put('R_RETEST',arr[i,opp]-s*.1*atr[i])
            upper=max(arr[i-21:i-1,2]);lower=min(arr[i-21:i-1,3]);p=arr[i-1]
            lev=lower if s==1 else upper
            failure=s*(p[opp]-lev)<0 and s*(p[4]-lev)>0 and (q[i-1]>=.75 if s==1 else q[i-1]<=.25)
            if er<.3 and failure and not(p[2]>upper and p[3]<lower) and s*(arr[i,4]-p[col])>0:
                put('F_REJECT',p[opp]-s*.1*atr[i],upper if s==1 else lower)
            struct=s*(max(arr[i-20:i,2])-max(arr[i-40:i-20,2]))>0 and s*(min(arr[i-20:i,3])-min(arr[i-40:i-20,3]))>0
            if trend and struct and s*(arr[i-3,4]-arr[i-2,4])>0 and s*(arr[i-2,4]-arr[i-1,4])>0 and s*(arr[i,4]-arr[i-1,col])>0 and s*(arr[i,4]-arr[i,1])>0 and loc:
                put('P_RESUME',other(arr[i-2:i+1,opp])-s*.1*atr[i])
            if trend and loc and s*(arr[i,4]-level(i,55))>0:put('C_CHANNEL',arr[i,4]-s*2*atr[i])
    for name,got in reconstructed.items():
        count={t:sum(x[0]==t for x in got) for t,_,_,_ in got};got=[x for x in got if count[x[0]]==1]
        expected=plans['signals'][name]
        assert len(got)==len(expected),(name,len(got),len(expected))
        for (t,s,stop,target),e in zip(got,expected):
            assert (t,s)==(e['source'],e['side']) and abs(stop-e['stop'])<1e-7
            assert target==e['target'];validated_signals+=1
            idx=ix[t];day=t//DAY*DAY;closes=[dclose[day-j*DAY] for j in range(19,-1,-1)]
            movement=sum(abs(y-x) for x,y in zip(closes,closes[1:]));delta=closes[-1]-closes[0]
            efficiency=abs(delta)/movement if movement else 0.
            regime='up' if efficiency>=.3 and delta>0 else 'down' if efficiency>=.3 and delta<0 else 'range'
            flow=(arr[idx,6]/arr[idx,5] if s==1 else 1-arr[idx,6]/arr[idx,5]) if arr[idx,5]>0 else None
            assert e['regime']==regime and abs(e['er']-efficiency)<1e-10
            assert e['flow'] is None if flow is None else abs(e['flow']-flow)<1e-10
            assert abs(e['atr']-atr[idx])<1e-8
    # Original funding CSV rate/timestamp vs events, not copied simulation flows.
    funds={};fund_paths=sorted((ROOT/'data/archive-1458/ETHUSDT/funding').glob('????-??.zip'))
    for path in fund_paths:
        assert sha(path.read_bytes())==path.with_suffix('.CHECKSUM').read_text().split()[0]
        with zipfile.ZipFile(path) as z:
            for r in csv.reader(io.StringIO(z.read(z.namelist()[0]).decode())):
                if r[0].isdigit():funds[int(r[0])//HOUR*HOUR]=(D(r[2]),int(r[0]))
    marks={r[0]:D(r[1]) for r in data('mark-funding.json.gz')['mark']}
    worst_cash=worst_daily=worst_dd=0.;n_events=n_trades=n_daily=n_path=0;checked=[];diagnostics={}
    for path in sorted(RUN.glob('*-*-*.json.gz')):
        result=json.loads(gzip.decompress(path.read_bytes()));start,end=result['start'],result['end'];conf=result['config'];sname=result['family']
        subset=raw[(start-first)//STEP:(end-first)//STEP];n=len(subset)
        deltas=np.zeros(n);inventory=np.zeros(n);stockcash=D(1000);signed=D(0);opened=None
        expected_fund=[]
        for trade in result['trades']:
            source=trade['source'];s=trade['side'];enter=trade['entry'];exit=trade['exit'];stop=trade['initial_stop'];target=trade['target']
            assert enter==source+STEP+conf['delay']
            assert any(e['source']==source and e['side']==s for e in plans['signals'][sname])
            # Every observed bar before entry must not invalidate the initial stop.
            for t in range(source,enter,STEP):
                rr=rowmap[t]
                assert rr[5]==0 or (rr[3]>stop if s==1 else rr[2]<stop)
            for t in range(enter,min(exit+STEP,end),STEP):
                rr=rowmap[t];n_path+=1
                completed=t-STEP-conf['delay']
                if sname in ('P_RESUME','C_CHANNEL') and completed>source and completed in ix:
                    idx=ix[completed];width=6 if sname=='P_RESUME' else 10
                    new=(min(arr[idx-width+1:idx+1,3])-.1*atr[idx]) if s==1 else (max(arr[idx-width+1:idx+1,2])+.1*atr[idx])
                    stop=max(stop,new) if s==1 else min(stop,new)
                if t>enter and t in funds:expected_fund.append((t,s,D(trade['qty'])))
                if rr[5]==0:continue
                ref=reason=None
                if s*(rr[1]-stop)<=0:ref,reason=rr[1],'stop_gap'
                elif t>=trade['deadline']:ref,reason=rr[1],'time'
                elif (rr[3]<=stop if s==1 else rr[2]>=stop):ref,reason=stop,'stop'
                elif target is not None and (rr[2]>=target if s==1 else rr[3]<=target):ref,reason=target,'target'
                if ref is not None:
                    assert t==exit and reason==trade['reason'] and abs(ref-trade['exit_reference'])<1e-7,(path.name,t,exit,reason)
                    break
                assert t<exit or trade['reason']=='period_end'
            n_trades+=1
        # Every accepted/rejected sizing attempt, including min20/min50 attribution.
        accepted=[]
        for a in result['sizing']:
            eq,ref,stop,side=map(D,(a['equity'],a['reference'],a['stop'],a['side']))
            fee,impact,extra=map(D,(a['fee_rate'],a['impact_rate'],a['stop_extra']))
            fill=ref*(1+side*impact);stopped=stop*(1-side*(impact+extra))
            perunit=side*(fill-stopped)+fee*(fill+stopped)
            upper=min(eq*D(a['risk_fraction'])/perunit,eq/fill)
            capped=min(upper,D(2000));rounded=(capped/D('.001')).to_integral_value(rounding=ROUND_FLOOR)*D('.001')
            reason='minimum_qty' if rounded<D('.001') else 'minimum_notional' if rounded*fill<D(conf['min_notional']) else None
            assert reason==a['reject_reason']
            for k,val in [('raw_qty',upper),('capped_qty',capped),('rounded_qty',rounded),('raw_stop_risk',upper*perunit),('rounded_stop_risk',rounded*perunit),('raw_notional',upper*fill),('rounded_notional',rounded*fill)]:
                assert abs(val-D(a[k]))<D('1e-8'),(path.name,k)
            assert D(a['accepted_qty'])==(rounded if reason is None else D(0)) or abs(D(a['accepted_qty'])-(rounded if reason is None else D(0)))<D('1e-10')
            if reason is None:accepted.append(a)
        assert len(accepted)==len(result['trades'])
        for a,t in zip(accepted,result['trades']):
            assert (a['source'],a['time'])==(t['source'],t['entry'])
            assert abs(D(a['accepted_qty'])-D(t['qty']))<D('1e-10')
        actual_fund=[]
        for e in result['events']:
            kind=e['kind'];t=e['time'];idx=min((t-start)//STEP,n-1)
            if kind=='trail':continue
            if kind=='funding':
                rate,rt=funds[t];amount=-signed*rate*marks[t]
                assert e['raw_time']==rt and D(e['rate'])==rate
                actual_fund.append((t,e['side'],D(e['qty'])))
                assert abs(amount-D(e['cashflow']))<D('1e-8');stockcash+=amount;deltas[idx]+=float(amount)
            else:
                rr=rowmap[t] if t<end else rowmap[end-STEP]
                ref=D(e['reference']);q=D(e['qty']);s=e['side'];impact=D('.00015')*D(conf['cost'])
                if kind=='entry':
                    assert ref==D(rr[1]) and rr[5]>0 and signed==0
                    new=s*q;fill=ref*(1+s*impact);opened=fill
                    cash_before=stockcash
                    targetstop=D(e['stop'])*(1-s*(impact+D(conf['stop_extra'])))
                    fee_rate=D('.0005')*D(conf['cost'])
                    perunit=s*(fill-targetstop)+fee_rate*(fill+targetstop)
                    upper=min(cash_before*D(conf['risk'])/perunit,cash_before/fill,D(2000))
                    assert q<=upper+D('1e-10') and abs(q/D('.001')-(q/D('.001')).to_integral_value())<D('1e-9')
                    assert q*fill>=D(conf['min_notional']) and q>=D('.001')
                    rounded=(upper/D('.001')).to_integral_value(rounding=ROUND_FLOOR)*D('.001')
                    assert abs(q-rounded)<D('1e-9'),(path.name,'quantity not floored')
                else:
                    assert signed==s*q
                    if e['phase']=='open':assert ref==D(rr[1])
                    if e['phase']=='close':assert ref==D(rr[4])
                    if e['reason'].startswith('stop'):impact+=D(conf['stop_extra'])
                    new=-signed;fill=ref*(1-s*impact)
                charge=q*fill*D('.0005')*D(conf['cost']);flow=-new*fill-charge
                assert abs(fill-D(e['fill']))<D('1e-7') and abs(charge-D(e['fee']))<D('1e-8')
                stockcash+=flow;signed+=new;deltas[idx]+=float(flow);inventory[idx]+=float(new)
            engine_cash=stockcash+signed*(opened or D(0))
            worst_cash=max(worst_cash,float(abs(engine_cash-D(e['cash']))));n_events+=1
        assert sorted(actual_fund)==sorted(expected_fund),(path.name,'missing settlement')
        equity=1000+np.cumsum(deltas)+np.cumsum(inventory)*np.array([r[4] for r in subset])
        peak=np.maximum.accumulate(np.r_[1000,equity])[1:];dd=float(np.max((1-equity/peak)*100))
        worst_dd=max(worst_dd,abs(dd-result['summary']['dd_pct']))
        for d in result['daily']:
            error=abs(equity[(d['time']-start)//STEP-1]-d['equity']);worst_daily=max(worst_daily,float(error));n_daily+=1
        assert abs(float(stockcash)-result['daily'][-1]['equity'])<1e-7
        sm=result['summary'];daily=np.array([1000.]+[d['equity'] for d in result['daily']])
        returns=daily[1:]/daily[:-1]-1
        assert abs(sm['return_pct']-(daily[-1]/1000-1)*100)<1e-8
        assert abs(sm['cagr_pct']-((daily[-1]/1000)**(365.25*DAY/(end-start))-1)*100)<1e-8
        independent_sharpe=float(np.mean(returns)/np.std(returns,ddof=1)*np.sqrt(365)) if np.std(returns)>0 else 0.
        assert abs(sm['sharpe']-independent_sharpe)<1e-8
        from datetime import datetime, timezone
        annual={};quarterly={}
        for d,growth in zip(result['daily'],1+returns):
            dt=datetime.fromtimestamp((d['time']-1)/1000,timezone.utc)
            year=str(dt.year);quarter=year+'Q'+str((dt.month-1)//3+1)
            annual[year]=annual.get(year,1.)*growth
            quarterly[quarter]=quarterly.get(quarter,1.)*growth
        for calculated,reported in [(annual,sm['annual']),(quarterly,sm['quarterly'])]:
            assert set(calculated)==set(reported)
            assert all(abs((value-1)*100-reported[k])<1e-8 for k,value in calculated.items())
        assert sm['positive_years']==sum(v>1 for v in annual.values())
        exbest=(math.prod(quarterly.values())/max(quarterly.values())-1)*100
        assert abs(sm['ex_best_quarter_pct']-exbest)<1e-8
        assert sm['trades']==len(result['trades'])
        assert abs(sm['net']-math.fsum(t['net'] for t in result['trades']))<1e-7
        for key in ('fees','impact','funding'):
            assert abs(sm[key]-math.fsum(t[key] for t in result['trades']))<1e-7
        fixed_cost2=0.
        for trd in result['trades']:
            s,q=trd['side'],trd['qty'];p0,p1=trd['reference'],trd['exit_reference']
            fill0=p0*(1+s*.0003);fill1=p1*(1-s*.0003)
            fixed_cost2+=s*q*(fill1-fill0)-q*(fill0+fill1)*.001+trd['funding']
        diagnostics[path.stem.removesuffix('.json')]={
            'mean_fine_close_notional_pct':float(np.mean(abs(np.cumsum(inventory))*np.array([r[4] for r in subset])/equity)*100),
            'time_in_position_pct':sum(t['exit']-t['entry'] for t in result['trades'])/(end-start)*100,
            'fixed_base_trades_cost2_net':fixed_cost2 if result['scenario']=='base' else None,
            'gross_price_pnl':math.fsum(t['price_gross'] for t in result['trades']),
            'warning':'Fixed-trade cost repricing is attribution, not a rebalanced account simulation. Time in position uses modeled bar timestamps.'}
        checked.append(path.name)
    assert len(checked)==80,(len(checked),'missing preregistered accounts')
    assert max(worst_cash,worst_daily,worst_dd)<1e-7
    result={'experiments':len(checked),'original_funding_records':len(funds),'independent_raw_signals':validated_signals,
        'events':n_events,'trades':n_trades,'held_bars_rechecked':n_path,'daily_equities':n_daily,
        'max_cash_error':worst_cash,'max_daily_error':worst_daily,'max_dd_percentage_point_error':worst_dd,
        'checks':'ETH min20/min50 sizing attempts, raw/floored risk and quantity caps; aggregate return/CAGR/Sharpe/annual/quarter/cost reconciliation and raw ATR/flow/regime; frozen normalized dataset hashes; original hourly/funding archive hashes; independent raw signal enumeration; every held 5m exit path; Decimal double-entry inventory ledger; funding inventory boundaries; all day-end equities and fine-close drawdowns',
        'not_proven':'actual fills, intrabar path, liquidation, future edge or out-of-sample superiority'}
    (RUN/'verification.json').write_bytes(canonical(result));(RUN/'diagnostics.json').write_bytes(canonical(diagnostics))
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,default=RUN);a=p.parse_args();RUN=a.run;run()
