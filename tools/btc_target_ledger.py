"""BTC-only two-instrument research ledger, explicitly adapted from strategy_search.
Original source SHA256: a2d032515887e9afe2a8553cc8b323d934e7474d59c279eb15700db1fd42b123
Changes: remove ETH instrument/data; preflight every adjustment; assert no spot borrowing.
No live-bot modules, credentials or network calls.
"""
import math
from btc_perp_bot.research.archive import DAY,HOUR,utc
from btc_perp_bot.research.longitudinal import metrics,periods
INSTRUMENTS=('BS','BP')
LABELS={x:x for x in ('E_MIX','B_MIX','E_STRICT','H_MIX','H_STRICT','E_SPOT')}

def simulate(m,name,start,end,plan,initial=1000.,multiplier=1.,delay=0,band=.05):
    fee={'BS':10.,'BP':5.};step={'BS':.00001,'BP':.001};minimum={'BS':5.,'BP':50.}
    fees=funding=impact=turnover=0.;cash=float(initial);qty={k:0. for k in INSTRUMENTS}
    events=[];daily=[];skips=[];executions=[];cursor=0;peak=initial;maxdd=0.;halted=False
    margin_min=None;breaches=0;max_exposure=0.;exposure_sum=0.;stale_hours=0
    latest={k:None for k in INSTRUMENTS};entered_hold=False;roundtrips=0
    plan=[dict(p,time=p['source_time']+HOUR+delay*HOUR) for p in plan]

    def equity(prices):return cash+math.fsum(qty[k]*prices[k] for k in INSTRUMENTS)

    def observe(prices):
        nonlocal peak,maxdd,max_exposure
        eq=equity(prices);peak=max(peak,eq);maxdd=max(maxdd,100*(1-eq/peak))
        if eq>0:max_exposure=max(max_exposure,sum(abs(qty[k])*prices[k] for k in INSTRUMENTS)/eq)
        return eq

    def fill(k,new,t,reference,source_time,reason,force=False):
        nonlocal cash,fees,impact,turnover,roundtrips
        dq=new-qty[k]
        if abs(dq)<step[k]/10:return True
        reducing=qty[k]*dq<0 and abs(new)<abs(qty[k])
        px=reference*(1+math.copysign(1.5*multiplier/10000,dq))
        if not force and abs(dq)*px<minimum[k] and (k=='BS' or not reducing):
            skips.append({'time':t,'instrument':k,'reason':'minimum','notional':abs(dq)*px});return False
        charge=abs(dq)*px*fee[k]*multiplier/10000;loss=abs(dq)*reference*1.5*multiplier/10000
        cash-=dq*px+charge;fees+=charge;impact+=loss;turnover+=abs(dq)*px
        if qty[k] and (not new or qty[k]*new<0):roundtrips+=1
        qty[k]=new
        events.append({'kind':'fill','time':int(t),'instrument':k,'source_time':source_time,'delta':dq,
                       'reference':reference,'price':px,'fee':charge,'impact':loss,'position':new,'reason':reason})
        return True

    for t in range(start,end,HOUR):
        rows={k:m.rowmaps[k].get(t) for k in INSTRUMENTS}
        marks={k:m.markmaps[k].get(t) for k in INSTRUMENTS}
        opens={};closes={}
        for k in INSTRUMENTS:
            r=marks[k]
            if r is None:
                if k!='BS' or latest[k] is None:raise ValueError('Missing required valuation: '+k+' '+utc(t))
                opens[k]=closes[k]=latest[k]
                if qty[k]:stale_hours+=1
            else:opens[k]=r[1];closes[k]=r[4];latest[k]=r[4]
        for k in ('BP',):
            fr=m.funds[k].get(t)
            if fr is not None and qty[k]:
                amount=-qty[k]*opens[k]*fr[2]
                cash+=amount;funding+=amount
                events.append({'kind':'funding','time':t,'instrument':k,'cashflow':amount,'rate':fr[2],
                               'reference':opens[k],'position':qty[k],'observed_time':fr[3]})
        eq=observe(opens)
        if eq<=0 and not halted:
            halted=True
            for k in INSTRUMENTS:
                if qty[k] and rows[k] is not None:
                    fill(k,0.,t,rows[k][1],None,'nonpositive_equity',force=True)
        while cursor<len(plan) and plan[cursor]['time']<=t:
            p=plan[cursor];cursor+=1;weights=p['weights']
            if weights is None or halted:continue
            relevant=[k for k in INSTRUMENTS if qty[k] or weights[k]]
            if any(rows[k] is None for k in relevant):
                skips.append({'time':t,'reason':'missing_execution_bar','source_time':p['source_time']});continue
            if name=='H_SPOT' and entered_hold:continue
            if p.get('hedge') and qty['BS'] and weights['BS'] and not p.get('rebalance',True):continue
            eq=equity(opens)
            # Band skips an entire multi-leg adjustment, keeping hedge structure intact.
            needs=any((qty[k]==0 and weights[k]!=0) or qty[k]*weights[k]<0 or (qty[k]!=0 and weights[k]==0) or
                      abs(weights[k]-qty[k]*opens[k]/eq)>=band for k in INSTRUMENTS)
            if not needs:continue
            # Solve post-cost equity simultaneously; rounding only reduces exposure.
            desired={k:0. for k in INSTRUMENTS};post=eq
            for _ in range(12):
                for k in INSTRUMENTS:desired[k]=weights[k]*post/opens[k]
                if p.get('hedge'):desired['BP']=-desired['BS']
                estimated=0.
                for k in relevant:
                    dq=desired[k]-qty[k];reference=rows[k][1]
                    px=reference*(1+math.copysign(1.5*multiplier/10000,dq)) if dq else reference
                    estimated+=dq*(opens[k]-px)-abs(dq)*px*fee[k]*multiplier/10000
                post=eq+estimated
            for k in INSTRUMENTS:
                desired[k]=math.copysign(math.floor((abs(desired[k])+1e-12)/step[k])*step[k],desired[k])
            if p.get('hedge'):
                hedge_qty=math.floor((abs(desired['BS'])+1e-12)/step['BP'])*step['BP']
                desired['BS']=hedge_qty;desired['BP']=-hedge_qty
            # Multi-leg min-order preflight: no phantom one-legged carry/pair fills.
            multi=True  # preflight transitions: never open a short against uncloseable spot dust
            if multi:
                invalid=[]
                for k in relevant:
                    dq=desired[k]-qty[k]
                    if abs(dq)<step[k]/10:continue
                    reducing=qty[k]*dq<0 and abs(desired[k])<abs(qty[k])
                    px=rows[k][1]*(1+math.copysign(1.5*multiplier/10000,dq))
                    if abs(dq)*px<minimum[k] and (k=='BS' or not reducing):invalid.append(k)
                if invalid:
                    skips.append({'time':t,'reason':'multileg_minimum','instruments':invalid});continue
            # Reductions precede openings. Reversal costs cover both sides via total delta.
            order=sorted(relevant,key=lambda k:abs(desired[k])-abs(qty[k]))
            filled=False
            for k in order:
                if abs(desired[k]-qty[k])<step[k]/10:continue
                filled=fill(k,desired[k],t,rows[k][1],p['source_time'],'target') or filled
            if filled:
                entered_hold=True;executions.append({'time':t,'source_time':p['source_time'],'weights':weights})
            observe(opens)
            if not qty['BP'] and cash < -1e-7:
                raise AssertionError('Spot cash borrowing')
        notional=sum(abs(qty[k])*closes[k] for k in INSTRUMENTS)
        eq=observe(closes);exposure_sum+=notional/eq if eq>0 else 0.
        perp_notional=sum(abs(qty[k])*closes[k] for k in ('BP',))
        if perp_notional:
            # Simultaneous adverse extrema: conservative diagnostic, not executable path.
            adverse={k:marks[k][3] if qty[k]>0 else marks[k][2] for k in ('BP',)}
            collateral=cash+sum(qty[k]*adverse[k] for k in ('BP',))
            ratio=collateral/sum(abs(qty[k])*adverse[k] for k in ('BP',))
            margin_min=ratio if margin_min is None else min(margin_min,ratio);breaches+=int(ratio<.05)
        if t%DAY==23*HOUR:
            daily.append({'time':t+HOUR,'equity':eq,'cash':cash,'positions':dict(qty),'marks':closes,
                          'fees':fees,'funding':funding,'impact':impact,'drawdown_pct':100*(1-eq/peak),
                          'exposure':notional/eq if eq>0 else 0.})
    finalprices={k:m.rowmaps[k][end-HOUR][4] for k in INSTRUMENTS}
    for k in INSTRUMENTS:
        # Exempt final dust as an explicit liquidation convention, not normal order fills.
        fill(k,0.,end,finalprices[k],None,'end_of_experiment',force=True)
    final=observe(finalprices)
    if daily:daily[-1].update(equity=final,cash=cash,positions=dict(qty),fees=fees,funding=funding,impact=impact,drawdown_pct=100*(1-final/peak),exposure=0.)
    replay=initial+math.fsum(-e['delta']*e['price']-e['fee'] if e['kind']=='fill' else e['cashflow'] for e in events)
    gross=math.fsum(-e['delta']*e['reference'] for e in events if e['kind']=='fill')
    if abs(replay-final)>1e-6 or abs(initial+gross+funding-fees-impact-final)>1e-6:raise AssertionError('Cash ledger mismatch')
    prev=initial;returns=[]
    for p in daily:returns.append(p['equity']/prev-1 if prev>0 else 0.);prev=p['equity']
    # Shared metric function assumes 1000; all production experiments use 1000.
    met=metrics(daily,returns)
    met.update(initial=initial,equity=final,return_pct=100*(final/initial-1),net_pnl=final-initial,
               max_drawdown_pct=maxdd,fees=fees,funding=funding,impact=impact,gross_pnl=gross,
               fills=sum(e['kind']=='fill' for e in events),round_trips=roundtrips,turnover=turnover,
               mean_exposure=exposure_sum/((end-start)/HOUR),max_exposure=max_exposure,
               min_adverse_margin_ratio=margin_min,margin_buffer_breach_hours=breaches,
               stale_held_spot_hours=stale_hours,accounting_residual=final-replay,halted=halted)
    met['calmar']=met['cagr_pct']/maxdd if maxdd>1e-12 and met['cagr_pct'] is not None else None
    return {'strategy':name,'name':LABELS[name],'start':utc(start),'end':utc(end),'metrics':met,'daily':daily,
            'daily_returns':returns,'periods':periods(daily),'events':events,'skips':skips,'executions':executions,
            'model':{'fee_bps':{k:v*multiplier for k,v in fee.items()},'impact_bps':1.5*multiplier,
                     'extra_delay_hours':delay,'funding_reference':'hourly mark open proxy',
                     'final_dust_liquidation_exemption':True,'multileg_simultaneous_fills_assumed':True}}
