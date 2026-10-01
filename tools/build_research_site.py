"""Package existing immutable experiment outputs; never run trading or optimize rules."""
import csv
import gzip
import io
import json
from pathlib import Path
from btc_perp_bot.research.archive import canonical,sha,utc

ROOT=Path(__file__).resolve().parents[1]
SITE=ROOT/'docs/assets'
DOWNLOADS=ROOT/'docs/downloads'
SITE.mkdir(parents=True,exist_ok=True);DOWNLOADS.mkdir(parents=True,exist_ok=True)
index={'build':'1001r1','date':'2026-10-01','initial':1000,'primary':'T1','studies':[],
       'forward_started':False,'live_started':False}
labels={'evaluation':('2022–2025 · 역사 평가','주 평가 · 16개 분기, 연속 계좌'),
        'recent':('2026.01–05 · 최근 역사 점검','규칙 수정 없이 확인한 역사 구간 · 전진 검증 아님'),
        'design':('2020–2021 · 설계 검증','2020.03.26 시작 · 85일 준비 구간 제외'),
        'hl-cost-scenario':('외부 시세 + HL 조건 · 참고','Binance 가격·펀딩에 HL 수수료·주문 단위를 가정 · HL 성과 아님'),
        'hl-regression':('Hyperliquid · 회귀 확인','2026.08.27–09.29 · 이미 사용한 자료 · 펀딩 금액은 오라클 대용치')}
for name,(label,note) in labels.items():
    raw=(ROOT/'runs/longitudinal-1448'/f'{name}.json').read_bytes()
    r=json.loads(raw)
    packed={k:v for k,v in r.items() if k not in ('results','stress')}
    packed['results']={k:{a:b for a,b in v.items() if a not in ('events','decisions','skips','daily_returns','daily')}|
                         {'curve':[[p['time'],round(p['equity'],8),round(p['drawdown_pct'],8)] for p in v['daily']]} for k,v in r['results'].items()}
    packed['stress']={k:{'metrics':v['metrics'],'model':v['model'],
                        'curve':[[p['time'],round(p['equity'],8),round(p['drawdown_pct'],8)] for p in v['daily']]} for k,v in r['stress'].items()}
    packed['label']=label;packed['note']=note
    (SITE/f'{name}.json').write_bytes(canonical(packed))
    archive=gzip.compress(raw,mtime=0)
    (DOWNLOADS/f'{name}.json.gz').write_bytes(archive)
    buf=io.StringIO();writer=csv.writer(buf,lineterminator="\n")
    writer.writerow(['date_utc','strategy','equity_'+r['quote'],'drawdown_pct','position_btc','fees','funding','impact'])
    for k,run in r['results'].items():
        for p in run['daily']:writer.writerow([utc(p['time']-1)[:10],k,*[p[x] for x in ('equity','drawdown_pct','position','fees','funding','impact')]])
    (DOWNLOADS/f'{name}.csv').write_text(buf.getvalue())
    index['studies'].append({'id':name,'label':label,'note':note,'quote':r['quote'],
                            't1':r['results']['T1']['metrics'],'gate1':r['gate1'],'raw_sha256':sha(raw),'gzip_sha256':sha(archive)})
for source,name in [(ROOT/'data/longitudinal-1448-repaired/manifest.json','data-manifest.json'),
                    (ROOT/'experiments/longitudinal-20261001.json','experiment.json'),
                    (ROOT/'runs/longitudinal-1448-audit.json','accounting-audit.json')]:
    (DOWNLOADS/name).write_bytes(source.read_bytes())
index['data_summary']={'monthly_files':308,'daily_files':23,'verified_files':331,'perp_hours':56232,'mark_hours':56232,
                      'funding_events':7029,'recovered_mark_hours':192,'spot_missing_hours':32,'spot_short_bars':7,
                      'spot_rejected_rows':1,'spot_overlap_conflicts':1,'interpolated_rows':0}
# Separate scenario arithmetic. Not an executable carry backtest or forecast.
index['carry']={'status':'보류 · 정밀 검증 자료 부족','capital':1000,'spot':400,'collateral':400,'reserve':200,
                'historical_funding_annualized_pct':8.0804763,'constant_notional_30d_gross':2.65659495,
                'roundtrip_fees':.92,'after_fees_before_other_costs':1.73659495,
                'shock_rows':[{'btc_change_pct':x,'short_collateral_before_costs':400-4*x,
                               'illustrative_5pct_buffer':.05*400*(1+x/100)} for x in (0,20,50,100)],
                'note':'기존120일 평균 펀딩률×고정명목400의 산술 예시. 실제 고정 BTC 수량의 백테스트·미래 예상수익 아님. 5% 담보완충은 설명용 가정이며 실제 청산 공식 아님.'}
(SITE/'index.json').write_bytes(canonical(index))
(ROOT/'docs/.nojekyll').touch()
print('Packaged',len(labels),'studies;',sum(p.stat().st_size for p in SITE.glob('*.json')),'JSON bytes')
