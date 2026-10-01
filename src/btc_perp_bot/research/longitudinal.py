"""Offline, preregistered daily-trend experiments; deliberately no trading adapter."""
import argparse
import csv
import gzip
import io
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

from .archive import DAY, HOUR, canonical, ms, sha, utc

NAMES = {"T1":"일봉 추세 63일", "T2":"민감도 · 42일", "T3":"민감도 · 84일",
         "T4":"대조 · 고정 50%", "T5":"대조 · 롱/숏", "vol_long":"위험조절 상시 롱",
         "perp_hold":"선물 50% 보유", "spot_hold":"현물 50% 보유", "cash":"현금"}
PRIMARY = ("T1","T2","T3","T4","T5","vol_long","perp_hold","spot_hold","cash")


@dataclass(frozen=True)
class Costs:
    fee: float = 5
    impact: float = 1.5
    step: float = .001
    minimum: float = 50
    spot_fee: float = 10
    spot_step: float = .00001
    spot_minimum: float = 5


def load_data(path, manifest_path):
    raw = gzip.decompress(Path(path).read_bytes())
    manifest = json.loads(Path(manifest_path).read_text())
    if sha(raw) != manifest["dataset_sha256"]:
        raise ValueError("Dataset hash mismatch")
    data=json.loads(raw)
    # A missing primary series invalidates the experiment, never a silent fill.
    for kind in ("perp","mark","funding"):
        if manifest["validation"][kind]["missing_count"]:
            raise ValueError(f"Primary data gap: {kind}; review before running")
    return data, manifest


def daily_closes(rows):
    # Use only actual, completed UTC day-end observations. No ffill/interpolation.
    return {r[0]//DAY*DAY: r[4] for r in rows if r[0]%DAY == 23*HOUR and (len(r)<6 or r[5]==r[0]+HOUR-1)}


def signal(history, name):
    if len(history)<85 or any(not math.isfinite(p) or p<=0 for p in history):
        return None
    logs=[math.log(history[i]/history[i-1]) for i in range(len(history)-20,len(history))]
    vol=statistics.stdev(logs)*math.sqrt(365)
    if not math.isfinite(vol) or vol<=1e-12:
        return 0.0
    risk=min(.5,.10/vol)
    lookback={"T2":42,"T3":84}.get(name,63)
    momentum=history[-1]/history[-lookback-1]-1
    if name=="vol_long": return risk
    if name=="T4": return .5 if momentum>0 else 0.0
    return risk if momentum>0 else (-risk if name=="T5" and momentum<0 else 0.0)


def schedules(rows, name, start, end, delay=0):
    closes=daily_closes(rows)
    result=[]
    for day in range(start,end,DAY):
        history=[closes.get(day-i*DAY) for i in range(85,0,-1)]
        if None in history:
            result.append({"time":day+HOUR+delay*HOUR,"source_time":day,"target":None})
        else:
            target=.5 if name in ("spot_hold","perp_hold") else 0.0 if name=="cash" else signal(history,name)
            result.append({"time":day+HOUR+delay*HOUR,"source_time":day,"target":target})
    return result


def desired_quantity(equity, old, weight, mark, opening, fee, impact, step):
    if not weight: return 0.0
    sign=1 if weight>0 else -1
    w=abs(weight)
    def after(mag):
        dq=sign*mag-old
        fill=opening*(1+(impact/10000 if dq>0 else -impact/10000))
        return equity + dq*(mark-fill)-abs(dq)*fill*fee/10000
    # Monotonic for the small, bounded costs in this experiment.
    low,high=0.0, w*equity/mark*1.1
    for _ in range(55):
        mid=(low+high)/2
        if mid*mark<=w*after(mid): low=mid
        else: high=mid
    return sign*math.floor((low+1e-12)/step)*step


def simulate(data, name, start, end, costs=Costs(), delay=0, multiplier=1.0, funding_scale=1.0):
    spot=name=="spot_hold"
    rows=[r for r in data["series"]["spot" if spot else "perp"] if start<=r[0]<end]
    markmap={r[0]:r for r in data["series"]["mark"]}
    fundmap={r[0]:r for r in data["series"]["funding"]}
    if not rows or rows[-1][0] != end-HOUR:
        raise ValueError("Missing final valuation bar")
    if rows[0][0]!=start:
        raise ValueError("Missing initial valuation bar")
    fee=(costs.spot_fee if spot else costs.fee)*multiplier
    impact=costs.impact*multiplier
    step=costs.spot_step if spot else costs.step
    minimum=costs.spot_minimum if spot else costs.minimum
    plan=schedules(data["series"]["perp"],name,start,end,delay)
    cursor=0
    cash=1000.0
    qty=0.0
    fees=funding=impact_total=turnover=price_pnl=0.0
    last_mark=rows[0][1] if spot else markmap[rows[0][0]][1]
    peak=1000.0
    maxdd=0.0
    peak_time=start
    recovery_days=0.0
    underwater_start=None
    underwater_open=False
    max_exposure=exposure_sum=0.0
    exposed=up_hours=down_hours=up_active=down_active=0
    min_margin_ratio=None
    margin_breaches=0
    events=[]
    curves=[]
    daily=[]
    skips=[]
    holding_entered=False
    halted=False
    roundtrips=0
    episode_sign=0
    side_pnl={"long":0.0,"short":0.0}
    decision_log=[]

    def observe(price,t):
        nonlocal peak,maxdd,peak_time,underwater_start,recovery_days,underwater_open,max_exposure
        eq=cash+qty*price
        if eq>=peak:
            if underwater_start is not None:
                recovery_days=max(recovery_days,(t-underwater_start)/DAY)
            peak=eq;peak_time=t;underwater_start=None;underwater_open=False
        elif underwater_start is None:
            underwater_start=peak_time;underwater_open=True
        maxdd=max(maxdd,100*(1-eq/peak))
        max_exposure=max(max_exposure,abs(qty)*price/eq if eq>0 else 0)
        return eq

    def execute(new,t,reference,mark,reason,source_time=None):
        nonlocal cash,qty,fees,impact_total,turnover,roundtrips,episode_sign
        dq=new-qty
        if abs(dq)<step/10: return False
        # Reversals are two legs so reduction and minimum rules are not conflated.
        if qty*new<0:
            execute(0.0,t,reference,mark,reason+"_close",source_time)
            return execute(new,t,reference,mark,reason+"_open",source_time)
        reducing=qty*dq<0 and abs(new)<abs(qty)
        fill=reference*(1+(impact/10000 if dq>0 else -impact/10000))
        if abs(dq)*fill<minimum and (spot or not reducing):
            skips.append({"time":t,"reason":"below_minimum","notional":abs(dq)*fill})
            return False
        charge=abs(dq)*fill*fee/10000
        cost=abs(dq)*reference*impact/10000
        cash-=dq*fill+charge
        fees+=charge;impact_total+=cost;turnover+=abs(dq)*fill
        # Attribute trading costs to the direction being opened/adjusted/closed.
        side="long" if (qty if reducing else new)>0 else "short"
        side_pnl[side]+=dq*(mark-reference)-charge-cost
        before=qty
        qty=new
        if before and not qty: roundtrips+=1
        events.append({"kind":"fill","time":t,"source_time":source_time,"delta":dq,
                       "reference":reference,"price":fill,"fee":charge,"impact":cost,
                       "position":qty,"reason":reason})
        observe(mark,t)
        return True

    previous_t=start-HOUR
    for row in rows:
        t,opening,high,low,close=row[:5]
        if t-previous_t>HOUR: skips.append({"time":t,"reason":"unobserved_hours","hours":(t-previous_t)//HOUR-1})
        previous_t=t
        markrow=row if spot else markmap[t]
        mark_open,mark_close=markrow[1],markrow[4]
        gap_pnl=qty*(mark_open-last_mark)
        price_pnl+=gap_pnl
        if qty: side_pnl["long" if qty>0 else "short"]+=gap_pnl
        if not spot and qty and t in fundmap:
            rate=fundmap[t][2]
            reference=(fundmap[t][4] if len(fundmap[t])>4 else mark_open)*funding_scale
            payment=-qty*reference*rate
            cash+=payment;funding+=payment
            side_pnl["long" if qty>0 else "short"]+=payment
            events.append({"kind":"funding","time":t,"cashflow":payment,"rate":rate,"reference":reference,"position":qty})
        equity=observe(mark_open,t)
        if equity<=0 and qty:
            execute(0.0,t,opening,mark_open,"nonpositive_equity")
            halted=True
        while cursor<len(plan) and plan[cursor]["time"]<=t:
            decision=plan[cursor];cursor+=1
            target=decision["target"]
            decision_log.append({**decision,"observed_execution_opportunity":t})
            if target is None:
                skips.append({"time":t,"reason":"incomplete_daily_warmup"});continue
            if halted or name=="cash": continue
            if name in ("perp_hold","spot_hold") and holding_entered: continue
            current=qty*mark_open/(cash+qty*mark_open)
            same_sign=(target*qty>0) or (target==0 and qty==0)
            if same_sign and abs(target-current)<.05: continue
            if qty*target<0:
                execute(0,t,opening,mark_open,"signal_close",decision["source_time"])
            eq=cash+qty*mark_open
            new=desired_quantity(eq,qty,target,mark_open,opening,fee,impact,step)
            filled=execute(new,t,opening,mark_open,"target",decision["source_time"])
            if name in ("perp_hold","spot_hold") and filled: holding_entered=True
        # Adverse mark extreme is only a margin-buffer diagnostic, not a liquidation simulator.
        if not spot and qty:
            adverse=markrow[3] if qty>0 else markrow[2]
            ratio=(cash+qty*adverse)/(abs(qty)*adverse)
            min_margin_ratio=ratio if min_margin_ratio is None else min(min_margin_ratio,ratio)
            margin_breaches+=int(ratio<.05)
        move_pnl=qty*(mark_close-mark_open)
        price_pnl+=move_pnl
        if qty: side_pnl["long" if qty>0 else "short"]+=move_pnl
        # Trades and marks can differ (basis). Attribute the instantaneous reference-to-mark gap.
        # The independent close ledger below validates the total decomposition.
        equity=observe(mark_close,t+HOUR)
        exposure=abs(qty)*mark_close/equity if equity>0 else 0
        exposure_sum+=exposure;exposed+=int(bool(qty))
        rising=mark_close>last_mark
        falling=mark_close<last_mark
        up_hours+=rising;down_hours+=falling
        up_active+=bool(qty) and rising;down_active+=bool(qty) and falling
        last_mark=mark_close
        if t%DAY==23*HOUR:
            daily.append({"time":t+HOUR,"equity":equity,"position":qty,"fees":fees,"funding":funding,
                          "impact":impact_total,"drawdown_pct":100*(1-equity/peak),"exposure":exposure})
    execute(0.0,end,rows[-1][4],last_mark,"end_of_experiment")
    final=observe(last_mark,end)
    if daily: daily[-1].update(equity=final,position=qty,fees=fees,funding=funding,impact=impact_total,drawdown_pct=100*(1-final/peak))
    if underwater_start is not None: recovery_days=max(recovery_days,(end-underwater_start)/DAY)
    # Independent cash-flow replay (same fills, separately summed, no state mutation).
    replay=1000 + math.fsum(-e["delta"]*e["price"]-e["fee"] if e["kind"]=="fill" else e["cashflow"] for e in events) + qty*last_mark
    if not math.isclose(replay,final,abs_tol=1e-7): raise AssertionError("Cash-flow replay failed")
    gross=math.fsum(-e["delta"]*e["reference"] for e in events if e["kind"]=="fill")+qty*last_mark
    if not math.isclose(1000+gross+funding-fees-impact_total,final,abs_tol=1e-7): raise AssertionError("PnL decomposition failed")
    # Basis mark shifts enter and leave the cash ledger; report directional totals including them.
    if not math.isclose(sum(side_pnl.values()),final-1000,abs_tol=1e-7):
        raise AssertionError("Directional PnL decomposition failed")
    returns=[];prev=1000.0
    for point in daily:
        returns.append(point["equity"]/prev-1 if prev>0 else 0);prev=point["equity"]
    summary=metrics(daily,returns)
    summary.update(initial=1000,equity=final,net_pnl=final-1000,return_pct=(final/1000-1)*100,
                   max_drawdown_pct=maxdd,fees=fees,funding=funding,impact=impact_total,gross_pnl=gross,
                   fills=sum(e["kind"]=="fill" for e in events),round_trips=roundtrips,
                   turnover=turnover,turnover_initial_multiple=turnover/1000,mean_exposure=exposure_sum/len(rows),
                   max_exposure=max_exposure,active_hours_pct=100*exposed/len(rows),
                   up_participation_pct=100*up_active/up_hours if up_hours else None,
                   down_participation_pct=100*down_active/down_hours if down_hours else None,
                   longest_underwater_days=recovery_days,underwater_at_end=underwater_start is not None,
                   min_adverse_margin_ratio=min_margin_ratio,margin_buffer_breach_hours=margin_breaches,
                   halted=halted,remaining_position=qty,skipped=len(skips),accounting_residual=final-replay,
                   directional_pnl=side_pnl)
    return {"strategy":name,"name":NAMES[name],"start":utc(start),"end":utc(end),"metrics":summary,
            "daily":daily,"daily_returns":returns,"events":events,"skips":skips,"decisions":decision_log,
            "periods":periods(daily),"model":{"fee_bps":fee,"impact_bps":impact,"quantity_step":step,
            "min_notional":minimum,"delay_hours":delay,"funding_reference_scale":funding_scale}}


def sharpe(values):
    if len(values)<2:return None
    sd=statistics.stdev(values)
    return statistics.mean(values)/sd*math.sqrt(365) if sd>1e-14 else None


def metrics(daily,returns):
    if not daily:return {}
    worst={}
    equities=[1000]+[p["equity"] for p in daily]
    for length in (1,7,30):
        vals=[equities[i]/equities[i-length]-1 for i in range(length,len(equities)) if equities[i-length]>0]
        worst[f"worst_{length}d_pct"]=min(vals)*100 if vals else None
    tail=sorted(returns)[:max(1,math.ceil(len(returns)*.05))]
    return {**worst,"sharpe":sharpe(returns),"realized_vol_pct":statistics.stdev(returns)*math.sqrt(365)*100 if len(returns)>1 else None,
            "daily_mean_pct":statistics.mean(returns)*100,"cvar_5pct_daily_pct":statistics.mean(tail)*100,
            "cagr_pct":((equities[-1]/1000)**(365/len(returns))-1)*100 if equities[-1]>0 else None}


def periods(daily):
    groups={"monthly":{},"quarterly":{},"yearly":{}}
    prev=1000.0
    for p in daily:
        date=utc(p["time"]-1)
        keys={"monthly":date[:7],"yearly":date[:4],"quarterly":date[:4]+"-Q"+str((int(date[5:7])-1)//3+1)}
        for group,key in keys.items():
            part=groups[group].setdefault(key,{"start_equity":prev,"end_equity":prev})
            part["end_equity"]=p["equity"]
        prev=p["equity"]
    for group in groups.values():
        for v in group.values():
            v["return_pct"]=(v["end_equity"]/v["start_equity"]-1)*100
            v["pnl"]=v["end_equity"]-v["start_equity"]
    return groups


def percentile(values, p):
    s=sorted(values);pos=(len(s)-1)*p;i=int(pos)
    return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(pos-i)


def bootstrap(primary, benchmark, resamples=2000, blocks=(14,7,28), seed=1448):
    if len(primary)!=len(benchmark) or len(primary)<28: raise ValueError("Insufficient aligned daily observations")
    n=len(primary);result=[]
    def fast_sharpe(s,s2):
        v=max(0,(s2-s*s/n)/(n-1))
        return s/n/math.sqrt(v)*math.sqrt(365) if v>1e-28 else 0
    # Precompute circular block sums and squares. O(n*L + B*n/L), same paired resampling.
    for length in blocks:
        rng=random.Random(seed+length)
        sums=[]
        for i in range(n):
            x=[primary[(i+j)%n] for j in range(length)]
            y=[benchmark[(i+j)%n] for j in range(length)]
            sums.append((sum(x),sum(z*z for z in x),sum(y),sum(z*z for z in y)))
        means=[];diffs=[]
        whole,rem=divmod(n,length)
        for _ in range(resamples):
            sx=sx2=sy=sy2=0.0
            for __ in range(whole):
                a,b,c,d=sums[rng.randrange(n)];sx+=a;sx2+=b;sy+=c;sy2+=d
            if rem:
                j=rng.randrange(n)
                for k in range(rem):
                    x=primary[(j+k)%n];y=benchmark[(j+k)%n]
                    sx+=x;sx2+=x*x;sy+=y;sy2+=y*y
            means.append(sx/n*100)
            diffs.append(fast_sharpe(sx,sx2)-fast_sharpe(sy,sy2))
        result.append({"block_days":length,"resamples":resamples,"seed":seed+length,
                       "mean_daily_pct_ci95":[percentile(means,.025),percentile(means,.975)],
                       "sharpe_difference_ci95":[percentile(diffs,.025),percentile(diffs,.975)],
                       "mean_daily_pct_bonferroni10":[percentile(means,.0025),percentile(means,.9975)],
                       "sharpe_difference_bonferroni10":[percentile(diffs,.0025),percentile(diffs,.9975)]})
    return result


def gate(results, stresses):
    t=results["T1"];m=t["metrics"];b=results["vol_long"]["metrics"]
    q=list(t["periods"]["quarterly"].values());positive=sum(x["return_pct"]>0 for x in q)
    checks={"base_and_double_cost_positive":m["net_pnl"]>0 and stresses["cost_x2"]["metrics"]["net_pnl"]>0,
            "two_thirds_positive_quarters":positive/len(q)>=2/3,
            "drawdown_at_most_12pct":m["max_drawdown_pct"]<=12,
            "neighbors_not_both_losing":not all(results[k]["metrics"]["net_pnl"]<=0 for k in ("T2","T3")),
            "sharpe_above_risk_matched_hold":m["sharpe"] is not None and b["sharpe"] is not None and m["sharpe"]>b["sharpe"],
            "no_margin_buffer_breach":m["margin_buffer_breach_hours"]==0 and not m["halted"]}
    # Compound all quarters except the best; do not sum percentage returns.
    factors=sorted([1+x["return_pct"]/100 for x in q])
    return {"pass":all(checks.values()),"checks":checks,"positive_quarters":positive,"total_quarters":len(q),
            "excluding_best_quarter_return_pct":(math.prod(factors[:-1])-1)*100}


def summarize_run(data, start, end, costs, names=PRIMARY):
    results={name:simulate(data,name,start,end,costs) for name in names}
    stresses={"cost_x2":simulate(data,"T1",start,end,costs,multiplier=2),
              "delay_1h":simulate(data,"T1",start,end,costs,delay=1),
              "delay_24h":simulate(data,"T1",start,end,costs,delay=24),
              "funding_price_minus1pct":simulate(data,"T1",start,end,costs,funding_scale=.99),
              "funding_price_plus1pct":simulate(data,"T1",start,end,costs,funding_scale=1.01)}
    boot=bootstrap(results['T1']['daily_returns'],results['vol_long']['daily_returns'])
    ci=boot[0]
    return {"start":utc(start),"end":utc(end),"results":results,"stress":stresses,"gate1":gate(results,stresses),
            "bootstrap":boot,"gate2_historical_ci_pass":ci['mean_daily_pct_ci95'][0]>0 and ci['sharpe_difference_ci95'][0]>0,
            "forward_evidence":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--data',required=True);p.add_argument('--manifest',required=True)
    p.add_argument('--period',choices=['design','evaluation','recent'],required=True);p.add_argument('--out',required=True)
    args=p.parse_args()
    out=Path(args.out)
    if out.exists():raise ValueError('Output exists; choose a new immutable experiment file')
    data,manifest=load_data(args.data,args.manifest)
    spec_path=Path(__file__).resolve().parents[3]/'experiments/longitudinal-20261001.json'
    spec=json.loads(spec_path.read_text())
    start,end=map(ms,spec[args.period])
    report=summarize_run(data,start,end,Costs())
    report.update(period=args.period,quote='USDT',venue='Binance BTCUSDT',dataset_sha256=manifest['dataset_sha256'],
                  spec_sha256=sha(canonical(spec)),code_sha256=sha(Path(__file__).read_bytes()),model='daily-trend-v1')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(canonical(report))
    print(json.dumps({'period':args.period,'T1':report['results']['T1']['metrics'],'gate1':report['gate1'],'bootstrap':report['bootstrap']},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
