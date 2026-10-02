"""Six preserved archive conflicts: dependency/held/fill audit, not a new strategy."""
import argparse
import gzip
import json
from pathlib import Path

from eth_transfer_study import ROOT, HOUR, DAY, STEP, IDS, load, signals, engine, write_fixed
from btc_perp_bot.research.archive import ms, canonical

RUN=ROOT/'runs/eth-transfer-performance-20261002'
LOOKBACK={'A_ACCEPT':21,'R_RETEST':26,'F_REJECT':21,'P_RESUME':40,'C_CHANNEL':55}


def dependencies(event, name, conflicts):
    source=event['source'];current=source-4*HOUR;day=source//DAY*DAY
    dc={day-j*DAY-HOUR for j in range(20)}
    out=[]
    for c in conflicts:
        h=c['timestamp'];k=h//(4*HOUR)*(4*HOUR)
        ranges=[];material=[]
        if k==current:
            ranges.append('confirmation_4h')
            if c['price_conflict']:material.append('confirmation_price')
            if c['volume_conflict']:material.append('confirmation_flow_only_used_by_flow55')
        if current-LOOKBACK[name]*4*HOUR<=k<current:
            ranges.append('price_lookback')
            if c['price_conflict']:material.append('lookback_price_possible_not_extremum_proof')
        if h in dc:
            ranges.append('regime_daily_close')
            if c['close_conflict']:material.append('regime_daily_close')
        if ranges:out.append({'time':c['time'],'ranges':ranges,'potential_numeric_dependencies':material})
    return out


def run(run_dir):
    rows,bars,funding,audit=load()
    plans=json.loads(gzip.decompress((run_dir/'signals.json.gz').read_bytes()))
    conflicts=[]
    for c in audit['unresolved_conflicts']:
        conflicts.append({**c,'timestamp':ms(c['time'].replace('Z','')),
            'volume_conflict':any(c['aggregate'][i]!=c['hourly'][i] for i in (5,7,8,9,10)),
            'close_conflict':c['aggregate'][4]!=c['hourly'][4]})
    # Only a diagnostic of signal-input version dependence: no alternate accounts.
    hourly=json.loads(gzip.decompress((ROOT/'data/eth-transfer-20261002/hourly-ohlcv.json.gz').read_bytes()))['rows']
    alternate={c['timestamp']:c['aggregate'] for c in conflicts}
    alt_bars=engine.aggregate([alternate.get(r[0],r) for r in hourly])
    alt_signals,alt_trails=signals(alt_bars)
    signal_changes=[];trail_changes=[]
    for name in IDS:
        a={(e['source'],e['side']):e for e in plans['signals'][name]}
        b={(e['source'],e['side']):e for e in alt_signals[name]}
        for key in sorted(set(a)|set(b)):
            if a.get(key)!=b.get(key):
                fields=sorted(k for k in set(a.get(key,{}) or {})|set(b.get(key,{}) or {}) if a.get(key,{}).get(k)!=b.get(key,{}).get(k))
                signal_changes.append({'family':name,'source':key[0],'side':key[1],'changed_fields':fields,'original':a.get(key),'diagnostic':b.get(key)})
    for width,after in alt_trails.items():
        before={int(k):v for k,v in plans['trails'][str(width)].items()}
        for t in sorted(set(before)|set(after)):
            if before.get(t)!=after.get(t):trail_changes.append({'width':width,'source':t,'original':before.get(t),'diagnostic':after.get(t)})
    raw=[]
    for name,events in plans['signals'].items():
        for e in events:
            d=dependencies(e,name,conflicts)
            if d:raw.append({'family':name,'source':e['source'],'side':e['side'],'dependencies':d})
    rowmap={r[0]:r for r in rows};accounts={};conflict_set={c['timestamp'] for c in conflicts}
    for path in sorted(run_dir.glob('*-*-*.json.gz')):
        r=json.loads(gzip.decompress(path.read_bytes()));name=r['family'];end=r['end']
        by_hour=[];signal_deps=[];empty_stress=[];pending_windows=[];invalidated=0
        for e in plans['signals'][name]:
            source=e['source']
            if not r['start']<=source<end:continue
            # Signals are evaluated before exits at the same boundary.
            if any(tr['entry']<source<=tr['exit'] for tr in r['trades']):continue
            if r['config']['flow_filter'] and (e['flow'] is None or e['flow']<.55):continue
            due=source+STEP+r['config']['delay'];visited=[];cancelled=None
            for t in range(source,min(due,end),STEP):
                rr=rowmap[t];visited.append(t)
                if rr[5]>0 and (rr[3]<=e['stop'] if e['side']==1 else rr[2]>=e['stop']):
                    cancelled=t;invalidated+=1;break
            pending_windows.append({'source':source,'due':due,'cancelled':cancelled,'evaluated_times':visited})
        assert invalidated==r['summary']['skips'].get('invalidated_before_entry',0),(path.name,'pending replay')
        for trade in r['trades']:
            ds=dependencies(trade,name,conflicts)
            if ds:signal_deps.append({'source':trade['source'],'entry':trade['entry'],'dependencies':ds})
        for c in conflicts:
            hour=c['timestamp'];holding=[];fills=[];pending=[]
            for trade in r['trades']:
                low=max(hour,trade['entry']);high=min(hour+HOUR,trade['exit']+STEP,end)
                holding.extend(range(low,high,STEP))
                if hour<=trade['entry']<hour+HOUR:fills.append({'kind':'entry','time':trade['entry'],'source':trade['source']})
                if hour<=trade['exit']<hour+HOUR:fills.append({'kind':'exit','time':trade['exit'],'reason':trade['reason']})
                overlap=list(range(max(hour,trade['source']),min(hour+HOUR,trade['entry']),STEP))
                if overlap:pending.append({'source':trade['source'],'entry':trade['entry'],'bars':overlap})
            # Pending potential includes non-filled raw signals too, not just successes.
            candidates=[{'source':e['source'],'side':e['side'],'due':e['source']+STEP+r['config']['delay']}
                        for e in plans['signals'][name]
                        if r['start']<=e['source']<end and e['source']<hour+HOUR and e['source']+STEP+r['config']['delay']>hour]
            by_hour.append({'time':c['time'],'held_bar_times':sorted(set(holding)),'fill_events':fills,
                'accepted_trade_pending_overlap':pending,'raw_potential_pending_overlap':candidates,
                'reconstructed_pending_overlap':[{**w,'evaluated_times':[t for t in w['evaluated_times'] if hour<=t<hour+HOUR]} for w in pending_windows if any(hour<=t<hour+HOUR for t in w['evaluated_times'])]})
        for trade in r['trades']:
            for t in range(trade['entry'],min(trade['exit']+STEP,end),STEP):
                rr=rowmap[t]
                if rr[5]==0:empty_stress.append({'time':t,'source':trade['source'],'side':trade['side'],
                    'adverse':rr[3] if trade['side']==1 else rr[2], 'conflict':t//HOUR*HOUR in conflict_set})
        held=sum(len(x['held_bar_times']) for x in by_hour)
        assert held==r['summary']['unresolved_archive_exposure_bars'],(path.name,held,r['summary']['unresolved_archive_exposure_bars'])
        for e in r['events']:
            if e['kind'] in ('entry','exit'):assert rowmap[min(e['time'],end-STEP)][5]>0
        accounts[path.name]={'conflicts':by_hour,'entered_signal_dependencies':signal_deps,
            'held_conflict_bars':held,'conflict_fills':sum(len(x['fill_events']) for x in by_hour),
            'zero_volume_held_stress_bars':empty_stress,'pending_invalidations_rechecked':invalidated}
    result={'schema':'ETH conflict exposure v1','accounts':accounts,'raw_signal_dependency_records':raw,
        'signal_input_version_diagnostic':{'changed_signals':signal_changes,'changed_trails':trail_changes,
            'alternate_performance_computed':False,'replacement':'six conflicting 1h records replaced by their monthly 5m aggregates for signals only'},
        'totals':{'accounts':len(accounts),'raw_dependency_records':len(raw),'changed_signal_records':len(signal_changes),
            'changed_trailing_records':len(trail_changes),'held_conflict_bars':sum(x['held_conflict_bars'] for x in accounts.values()),
            'conflict_fill_events':sum(x['conflict_fills'] for x in accounts.values()),
            'zero_volume_held_stress_bars':sum(len(x['zero_volume_held_stress_bars']) for x in accounts.values()),
            'reconstructed_pending_conflict_bars':sum(len(w['evaluated_times']) for x in accounts.values() for c in x['conflicts'] for w in c['reconstructed_pending_overlap'])},
        'limits':['Temporal lookback overlap is not proof a disputed value determined an extremum.',
            'Raw potential pending overlap includes busy/filtered/cancelled signals; accepted-trade pending is exact for fills.',
            'Zero-volume bars cannot fill or invalidate pending stops; inherited adverse-extreme stress still includes their prices.',
            'No data version or assumption was selected after outcomes.']}
    assert len(accounts)==80
    write_fixed(run_dir/'conflict-exposure.json',canonical(result))
    print(json.dumps(result['totals'],indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,default=RUN);a=p.parse_args();run(a.run)
