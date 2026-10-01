"""Preregistered cross-family *exploratory* research. Offline only, no order adapter.

Separate spot value from futures collateral; all positions use an independently
replayable cash-flow ledger. Fills at bar opens are a model, not exchange evidence.
"""
import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np

from .archive import DAY, HOUR, canonical, ms, sha, utc
from .longitudinal import bootstrap, metrics, periods

ROOT = Path(__file__).resolve().parents[3]
INSTRUMENTS = ('BS', 'BP', 'EP')
CANDIDATES = ('E_SPOT','E_PERP','E_LS','B_SPOT','C_ALWAYS','C_FILTER','P_PAIR','M_GBDT','M_RIDGE')
BENCHMARKS = ('V_SPOT','V_PERP','H_SPOT','T1_OLD','T1_RISK20','CASH')
LABELS = dict(zip(CANDIDATES+BENCHMARKS, (
    '다중기간 추세 · 현물','다중기간 추세 · 선물','다중기간 추세 · 양방향',
    '55일 돌파 · 현물','현물–선물 캐리','펀딩 필터 캐리','BTC–ETH 상대가치',
    '비용인식 XGBoost','비용인식 Ridge','위험조절 현물 보유','위험조절 선물 보유',
    '현물 100% 매수보유','기존 T1 · 위험 10%','T1 · 위험 20%','현금')))


def load_market(directory):
    directory=Path(directory)
    raw=gzip.decompress((directory/'market.json.gz').read_bytes())
    manifest=json.loads((directory/'manifest.json').read_text())
    if sha(raw)!=manifest['dataset_sha256']: raise ValueError('Dataset digest differs')
    for key,v in manifest['validation'].items():
        if not key.endswith('_spot') and v['missing_count']:
            raise ValueError('Primary data not complete: '+key)
    return json.loads(raw),manifest


def ema(values,span):
    result=np.full(len(values),np.nan); last=np.nan; alpha=2/(span+1)
    for i,x in enumerate(values):
        if not np.isfinite(x): last=np.nan;continue
        last=x if not np.isfinite(last) else alpha*x+(1-alpha)*last
        result[i]=last
    return result


class Market:
    def __init__(self,payload):
        self.payload=payload
        self.rows={'BS':payload['series']['BTCUSDT']['spot'],
                   'BP':payload['series']['BTCUSDT']['perp'],
                   'EP':payload['series']['ETHUSDT']['perp']}
        self.marks={'BS':self.rows['BS'],'BP':payload['series']['BTCUSDT']['mark'],
                    'EP':payload['series']['ETHUSDT']['mark']}
        self.rowmaps={k:{int(r[0]):r for r in v} for k,v in self.rows.items()}
        self.markmaps={k:{int(r[0]):r for r in v} for k,v in self.marks.items()}
        self.funds={k:{int(r[0]):r for r in payload['series'][s]['funding']} for k,s in [('BP','BTCUSDT'),('EP','ETHUSDT')]}
        self.days=np.arange(ms('2020-02-01'),payload['end'],DAY,dtype=np.int64)
        self.dayindex={int(t):i for i,t in enumerate(self.days)}
        self.closes={}
        for k in INSTRUMENTS:
            c=[]
            for t in self.days:
                r=self.rowmaps[k].get(int(t+23*HOUR))
                c.append(r[4] if r is not None and r[5]==t+DAY-1 else np.nan)
            self.closes[k]=np.array(c)
        self.ema={span:ema(self.closes['BS'],span) for span in (8,16,32,64,128)}
        self.ml_features=None

    def risk(self,source,instrument='BS',target=.2,cap=1.):
        idx=self.dayindex.get(source//DAY*DAY-DAY,-1)
        if idx<20:return None
        p=self.closes[instrument][idx-20:idx+1]
        if not np.all(np.isfinite(p)):return None
        vol=float(np.std(np.diff(np.log(p)),ddof=1)*math.sqrt(365))
        return min(cap,target/vol) if vol>1e-12 else 0.

    def known_funding(self,source,days=7):
        return math.fsum(r[2] for t,r in self.funds['BP'].items()
                         if source-days*DAY<=t<source and r[3]<source)


def fit_pair(m,day):
    idx=m.dayindex.get(day-DAY,-1)
    if idx<89:return None
    btc=m.closes['BP'][idx-89:idx+1]; eth=m.closes['EP'][idx-89:idx+1]
    if not np.all(np.isfinite(btc)) or not np.all(np.isfinite(eth)):return None
    x,y=np.log(btc),np.log(eth)
    beta=float(np.cov(x,y,ddof=1)[0,1]/np.var(x,ddof=1)); intercept=float(y.mean()-beta*x.mean())
    resid=y-intercept-beta*x; sd=float(resid.std(ddof=1))
    if sd<=1e-12:return None
    phi=float(np.cov(resid[:-1],resid[1:],ddof=1)[0,1]/np.var(resid[:-1],ddof=1))
    half=-math.log(2)/math.log(phi) if 0<phi<1 else None
    corr=float(np.corrcoef(np.diff(x),np.diff(y))[0,1])
    spreadvol=float(np.std((np.diff(y)-beta*np.diff(x))/(1+abs(beta)),ddof=1)*math.sqrt(365))
    valid=.25<=beta<=4 and corr>.6 and half is not None and half<=20
    return {'beta':beta,'alpha':intercept,'sd':sd,'phi':phi,'half_life_days':half,
            'correlation':corr,'vol':spreadvol,'valid':valid,'last_train_time':int(day)}


def prepare_features(m):
    if m.ml_features is not None:return m.ml_features
    r=np.asarray(m.rows['BP'],dtype=float)
    times=r[:,0].astype(np.int64)+HOUR; c=r[:,4]; logs=np.log(c)
    returns=np.r_[np.nan,np.diff(logs)]
    em24,em168=ema(c,24),ema(c,168)
    samples=[];features=[];labels=[];funds=[]
    fsorted=sorted(m.funds['BP'].items());fi=0;last=0.;known=[]
    for i,t in enumerate(times):
        while fi<len(fsorted) and fsorted[fi][1][3]<t:
            last=fsorted[fi][1][2];known.append((fsorted[fi][0],last));fi+=1
        if i<168 or t%(6*HOUR):continue
        previous=times[i-168:i+1]
        if np.any(np.diff(previous)!=HOUR):continue
        f24=math.fsum(v for ft,v in known if t-DAY<=ft<t)
        f=[float(logs[i]-logs[i-h]) for h in (1,6,24,72,168)]
        f += [float(np.std(returns[i-h+1:i+1],ddof=1)) for h in (24,168)]
        f += [float(math.log(c[i]/em24[i])),float(math.log(c[i]/em168[i])),
              float((r[i-23:i+1,2].max()-r[i-23:i+1,3].min())/c[i])]
        for h in (14,168):
            delta=np.diff(c[i-h:i+1]);up=float(np.maximum(delta,0).mean());down=float(np.maximum(-delta,0).mean())
            f.append(up/(up+down) if up+down>0 else .5)
        hour=(t//HOUR)%24;weekday=(t//DAY+3)%7
        f += [last,f24,math.sin(2*math.pi*hour/24),math.cos(2*math.pi*hour/24),
              math.sin(2*math.pi*weekday/7),math.cos(2*math.pi*weekday/7)]
        y=float(logs[i+24]-logs[i]) if i+24<len(logs) and times[i+24]==t+DAY else np.nan
        samples.append(t);features.append(f);labels.append(y);funds.append(f24)
    m.ml_features=(np.asarray(samples,dtype=np.int64),np.asarray(features),np.asarray(labels),np.asarray(funds))
    return m.ml_features


def ml_predictions(m,name,start,end):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from xgboost import XGBRegressor
    times,x,y,funds=prepare_features(m)
    selected=np.flatnonzero((times>=start)&(times<end))
    predictions={};training=[];current=None
    for i in selected:
        date=utc(int(times[i]));quarter=date[:4]+'-'+str((int(date[5:7])-1)//3)
        if quarter!=current:
            fit=int(times[i]);mask=(times>=fit-365*DAY)&(times<=fit-26*HOUR)&np.isfinite(y)
            assert np.max(times[mask]+DAY)<=fit-2*HOUR
            if mask.sum()<1000: raise ValueError('Insufficient ML training window')
            if name=='M_GBDT':
                model=XGBRegressor(max_depth=3,n_estimators=300,learning_rate=.03,min_child_weight=20,
                    subsample=.8,colsample_bytree=.8,reg_lambda=10,reg_alpha=.1,random_state=1458,
                    n_jobs=1,objective='reg:squarederror',tree_method='hist')
            else:model=make_pipeline(StandardScaler(),Ridge(alpha=10))
            model.fit(x[mask],y[mask])
            training.append({'fit_time':fit,'samples':int(mask.sum()),'last_label_time':int(np.max(times[mask]+DAY)),
                             'train_features_sha256':sha(x[mask].tobytes()),'train_labels_sha256':sha(y[mask].tobytes())})
            current=quarter
        predictions[int(times[i])]=(float(np.clip(model.predict(x[i:i+1])[0],-.1,.1)),float(funds[i]))
    return predictions,training


def schedule(m,name,start,end,risk_target=.2):
    decisions=[];state=0;entered=None;pair=None;month=None;training=[]
    ml=None
    if name.startswith('M_'):ml,training=ml_predictions(m,name,start,end)
    sources=sorted(ml) if ml is not None else range(start,end,DAY)
    for source in sources:
        weights={k:0. for k in INSTRUMENTS};detail={};rebalance=True;hedge=False
        risk=m.risk(source,'BP' if name.startswith('M_') or name.startswith('T1') else 'BS',risk_target)
        idx=m.dayindex.get(source//DAY*DAY-DAY,-1)
        if idx<128 or risk is None:
            decisions.append({'source_time':int(source),'weights':None,'detail':{'missing_warmup':True}});continue
        history=m.closes['BS'];c=history[idx]
        if name.startswith('E_'):
            vals=[float(np.sign(c-history[idx-n])) for n in (20,60,120)]
            vals += [float(np.sign(m.ema[a][idx]-m.ema[b][idx])) for a,b in ((8,32),(16,64),(32,128))]
            score=sum(vals)/6
            if not math.isfinite(score):weights=None
            else:weights['BS' if name=='E_SPOT' else 'BP']=risk*(score if name=='E_LS' else max(0,score))
            detail={'score':score if math.isfinite(score) else None}
        elif name=='B_SPOT':
            if not state and c>np.max(history[idx-55:idx]):state=1
            elif state and c<np.min(history[idx-20:idx]):state=0
            weights['BS']=risk*state
        elif name.startswith('C_') and name!='CASH':
            rate=m.known_funding(source)*365/7
            if name=='C_ALWAYS':state=1
            elif not state and rate>.06:state=1
            elif state and rate<0:state=0
            weights={'BS':.4*state,'BP':-.4*state,'EP':0.};hedge=True
            rebalance=(source//DAY+3)%7==0
            detail={'trailing_7d_annualized_funding':rate,'active':bool(state)}
        elif name=='P_PAIR':
            this_month=utc(source)[:7];changed=month!=this_month
            if changed:pair=fit_pair(m,source);month=this_month
            if changed and state:state=0;entered=None
            elif pair and pair['valid']:
                z=(math.log(m.closes['EP'][idx])-pair['alpha']-pair['beta']*math.log(m.closes['BP'][idx]))/pair['sd']
                if state and (abs(z)<=.5 or abs(z)>=4 or source-entered>=20*DAY):state=0;entered=None
                elif not state and 2<=abs(z)<4:state=-1 if z>0 else 1;entered=source
                gross=min(.8,risk_target/max(pair['vol'],1e-12))
                weights['EP']=state*gross/(1+pair['beta']);weights['BP']=-state*gross*pair['beta']/(1+pair['beta'])
                detail={'z':z,'formation':pair}
            else:state=0;entered=None
        elif name.startswith('M_'):
            prediction,f24=ml[source];threshold=2*(2*6.5/10000+max(f24,0))
            if not state and prediction>threshold:state=1;entered=source
            elif state and (prediction < -threshold or source-entered>=7*DAY):state=0;entered=None
            weights['BP']=risk*state;detail={'prediction':prediction,'threshold':threshold,'state':state}
        elif name in ('V_SPOT','V_PERP'):weights['BS' if name=='V_SPOT' else 'BP']=risk
        elif name=='H_SPOT':weights['BS']=1.
        elif name.startswith('T1'):
            risk=m.risk(source,'BP',.1 if name=='T1_OLD' else risk_target,.5 if name=='T1_OLD' else 1.)
            p=m.closes['BP'];weights['BP']=risk if p[idx]>p[idx-63] else 0.
        elif name!='CASH':raise ValueError(name)
        decisions.append({'source_time':int(source),'weights':weights,'rebalance':rebalance,'hedge':hedge,'detail':detail})
    return decisions,training


def simulate(m,name,start,end,plan,initial=1000.,multiplier=1.,delay=0,band=.05):
    fee={'BS':10.,'BP':5.,'EP':5.};step={'BS':.00001,'BP':.001,'EP':.001};minimum={'BS':5.,'BP':50.,'EP':20.}
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
        for k in ('BP','EP'):
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
            multi=p.get('hedge') or name=='P_PAIR'
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
            if name in ('E_SPOT','B_SPOT','V_SPOT','H_SPOT') and cash < -1e-7:
                raise AssertionError('Spot cash borrowing')
        notional=sum(abs(qty[k])*closes[k] for k in INSTRUMENTS)
        eq=observe(closes);exposure_sum+=notional/eq if eq>0 else 0.
        perp_notional=sum(abs(qty[k])*closes[k] for k in ('BP','EP'))
        if perp_notional:
            # Simultaneous adverse extrema: conservative diagnostic, not executable path.
            adverse={k:marks[k][3] if qty[k]>0 else marks[k][2] for k in ('BP','EP')}
            collateral=cash+sum(qty[k]*adverse[k] for k in ('BP','EP'))
            ratio=collateral/sum(abs(qty[k])*adverse[k] for k in ('BP','EP'))
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


def select_candidates(base,double):
    decisions={};eligible=[]
    for name in CANDIDATES:
        r=base[name];b=r['metrics'];d=double[name]['metrics']
        qs=[1+p['return_pct']/100 for p in r['periods']['quarterly'].values()]
        exbest=(math.prod(sorted(qs)[:-1])-1)*100
        checks={'cagr_ge_10':b['cagr_pct'] is not None and b['cagr_pct']>=10,'sharpe_ge_08':(b['sharpe'] or -99)>=.8,
                'drawdown_le_25':b['max_drawdown_pct']<=25,
                'positive_years_ge_3':sum(p['return_pct']>0 for p in r['periods']['yearly'].values())>=3,
                'cost_x2_positive':d['net_pnl']>0,'excluding_best_quarter_positive':exbest>0,
                'margin_ok':b['margin_buffer_breach_hours']==0 and d['margin_buffer_breach_hours']==0 and not b['halted']}
        score=min(b['calmar'] or -999,d['calmar'] or -999)
        decisions[name]={'pass':all(checks.values()),'checks':checks,'score':score,'ex_best_quarter_pct':exbest}
        if all(checks.values()):eligible.append(name)
    eligible.sort(key=lambda n:(-decisions[n]['score'],base[n]['metrics']['turnover'],CANDIDATES.index(n)))
    return {'ranking':eligible,'selected_for_recent_review':eligible[0] if eligible else None,
            'decisions':decisions,'scope':'research screening only; prior price knowledge; not trading approval'}


def write_new(path,obj):
    path=Path(path);blob=canonical(obj)
    if path.exists():raise ValueError('Refusing result overwrite: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(gzip.compress(blob,mtime=0) if path.suffix=='.gz' else blob)


def run(stage,out):
    payload,manifest=load_market(ROOT/'data/search-1458');m=Market(payload)
    start=ms('2022-01-01') if stage=='main' else ms('2026-01-01')
    end=ms('2026-01-01') if stage=='main' else payload['end']
    if stage=='recent' and not (out/'selection.json').exists():raise ValueError('Freeze main selection before recent review')
    reports={};double={}
    for name in CANDIDATES+BENCHMARKS:
        plan,training=schedule(m,name,start,end)
        result=simulate(m,name,start,end,plan);result['training']=training
        result['schedule_sha256']=sha(canonical(plan))
        reports[name]=result
        print(stage,name,json.dumps({k:result['metrics'][k] for k in ('return_pct','cagr_pct','max_drawdown_pct','sharpe','fills')}),flush=True)
        write_new(out/(stage+'-'+name+'.json.gz'),result)
        if name in CANDIDATES:
            double[name]=simulate(m,name,start,end,plan,multiplier=2)
            write_new(out/(stage+'-'+name+'-cost_x2.json.gz'),double[name])
            for delay in (1,24):write_new(out/(stage+'-'+name+'-delay'+str(delay)+'.json.gz'),simulate(m,name,start,end,plan,delay=delay))
            # Reuse ML fitted forecasts; only sizing changes for sensitivities.
            for risk in (.1,.3):
                altered=[]
                for p in plan:
                    q=dict(p)
                    if p['weights'] is not None:
                        if name.startswith('C_'):q['weights']=dict(p['weights'])
                        elif name=='P_PAIR':
                            formation=p['detail'].get('formation');scale=1.
                            if formation:scale=min(.8,risk/max(formation['vol'],1e-12))/min(.8,.2/max(formation['vol'],1e-12))
                            q['weights']={k:v*scale for k,v in p['weights'].items()}
                        else:
                            inst='BP' if name.startswith('M_') else 'BS'
                            old=m.risk(p['source_time'],inst,.2);new=m.risk(p['source_time'],inst,risk)
                            q['weights']={k:v*new/old if old else 0. for k,v in p['weights'].items()}
                    altered.append(q)
                write_new(out/(stage+'-'+name+'-risk'+str(int(risk*100))+'.json.gz'),simulate(m,name,start,end,altered))
    summary={'stage':stage,'start':utc(start),'end':utc(end),'quote':'USDT','venue':'Binance historical scenario',
             'dataset_sha256':manifest['dataset_sha256'],'spec_sha256':sha((ROOT/'experiments/strategy-search-1458.json').read_bytes()),
             'code_sha256':sha(Path(__file__).read_bytes()),'forward_evidence':False,
             'results':{n:{'metrics':r['metrics'],'periods':r['periods']} for n,r in reports.items()}}
    if stage=='main':write_new(out/'selection.json',select_candidates(reports,double))
    write_new(out/(stage+'-summary.json'),summary)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['main','recent']);p.add_argument('--out',required=True)
    args=p.parse_args();run(args.stage,Path(args.out))
