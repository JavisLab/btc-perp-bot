"""Publish immutable research outputs, without fitting or selecting strategies."""
import csv
import gzip
import io
import json
import shutil
import zipfile
from pathlib import Path

from btc_perp_bot.research.archive import canonical,sha,utc
from btc_perp_bot.research.strategy_search import CANDIDATES,BENCHMARKS,LABELS

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/search-1458'
ASSETS=ROOT/'docs/assets'
OUT=ROOT/'docs/downloads'
DESCRIPTIONS={
 'E_SPOT':('trend','완료된 20·60·120일 수익률과 3개 EMA 교차의 평균. 양의 점수만 현물로 보유합니다.'),
 'E_PERP':('trend','현물 추세와 같은 신호·비중을 BTC 선물로 구현해 펀딩·비용 차이를 봅니다.'),
 'E_LS':('trend','같은 다중기간 신호로 상승에는 롱, 하락에는 숏을 취합니다.'),
 'B_SPOT':('trend','55일 종가 돌파 때 현물 진입, 20일 저점 이탈 때 현금으로 돌아옵니다.'),
 'C_ALWAYS':('carry','현물 롱·선물 숏을 같은 BTC 수량으로 유지합니다. 현물 목표 40%, 현물은 선물 담보에서 제외합니다.'),
 'C_FILTER':('carry','지난 7일 펀딩의 단순 연율이 6%를 넘을 때 캐리 진입, 음수가 되면 나옵니다.'),
 'P_PAIR':('relative','매월 직전 90일 관계를 추정해 BTC–ETH 가격차 회귀를 거래합니다. 공적분 보장은 없습니다.'),
 'M_GBDT':('ml','고정된 소형 XGBoost를 과거 1년으로 분기별 학습. 비용을 넘는 예측에서만 롱 진입합니다.'),
 'M_RIDGE':('ml','같은 입력·학습창·진입 규칙의 선형 Ridge 모델입니다. 복잡한 모델과 비교합니다.'),
 'V_SPOT':('benchmark','20% 변동성 목표로 비중을 조절하되 상승추세 필터 없이 항상 현물 롱입니다.'),
 'V_PERP':('benchmark','같은 위험 규칙의 항상 선물 롱입니다. 실제 펀딩 지출을 포함합니다.'),
 'H_SPOT':('benchmark','처음에 현물 100%를 매수한 뒤 유지합니다. 위험 수준이 후보와 다릅니다.'),
 'T1_OLD':('benchmark','기존 63일 신호·10% 위험 목표·50% 조정 한도의 원래 결과입니다.'),
 'T1_RISK20':('benchmark','기존 63일 신호는 유지하고 위험 목표만 20%·한도100%로 높인 대조군입니다.'),
 'CASH':('benchmark','이자를 가정하지 않고 현금을 유지합니다.')}


def read(path):return json.loads(gzip.decompress(path.read_bytes()))


def pack(r,curve=True):
    out={k:r[k] for k in ('metrics','periods','model')}
    if curve:out['curve']=[[p['time'],round(p['equity'],8),round(p['drawdown_pct'],8)] for p in r['daily']]
    return out


def build():
    audit=json.loads((RUN/'independent-audit.json').read_text())
    reproduction=json.loads((RUN/'reproduction.json').read_text())
    assert audit['runs']==120 and reproduction['runs_byte_identical']==120
    manifest=json.loads((ROOT/'data/search-1458/manifest.json').read_text())
    index={'build':'1001r2','date':'2026-10-01','initial':1000,'quote':'USDT',
      'candidates':list(CANDIDATES),'benchmarks':list(BENCHMARKS),
      'strategies':{k:{'label':LABELS[k],'family':DESCRIPTIONS[k][0],'description':DESCRIPTIONS[k][1]} for k in CANDIDATES+BENCHMARKS},
      'periods':{'main':{'label':'2022–2025 · 4년 비교','days':1461},'recent':{'label':'2026.01–08 · 최근 8개월','days':243}},
      'selection':json.loads((RUN/'selection.json').read_text()),
      'research_priority':'E_SPOT','priority_is_post_comparison_not_gate_pass':True,
      'live_selected':None,'forward_started':False,'live_started':False,
      'uncertainty':json.loads((RUN/'uncertainty.json').read_text()),
      'verification':{k:v for k,v in audit.items() if k!='audits'},
      'reproduction':{k:v for k,v in reproduction.items() if k!='files'},
      'dataset_sha256':manifest['dataset_sha256']}
    for stage in ('main','recent'):
        data={'results':{},'scenarios':{}}
        summary=json.loads((RUN/f'{stage}-summary.json').read_text())
        data.update({k:v for k,v in summary.items() if k!='results'})
        buf=io.StringIO();writer=csv.writer(buf,lineterminator='\n')
        writer.writerow(['date_utc','strategy','scenario','equity_USDT','drawdown_pct','spot_btc','perp_btc','perp_eth','cumulative_fees','cumulative_funding','cumulative_impact'])
        for n in CANDIDATES+BENCHMARKS:
            base=read(RUN/f'{stage}-{n}.json.gz');data['results'][n]=pack(base)
            scenarios={'base':base}
            if n in CANDIDATES:
                for s in ('cost_x2','delay1','delay24','risk10','risk30'):scenarios[s]=read(RUN/f'{stage}-{n}-{s}.json.gz')
                data['scenarios'][n]={s:pack(v) for s,v in scenarios.items() if s!='base'}
            for scenario,r in scenarios.items():
                for p in r['daily']:
                    writer.writerow([utc(p['time']-1)[:10],n,scenario,p['equity'],p['drawdown_pct'],*[p['positions'][k] for k in ('BS','BP','EP')],p['fees'],p['funding'],p['impact']])
        (ASSETS/f'search-{stage}.json').write_bytes(canonical(data))
        (OUT/f'search-{stage}.csv').write_text(buf.getvalue())
    (ASSETS/'search-index.json').write_bytes(canonical(index))
    for src,dst in [(RUN/'selection.json','search-selection.json'),(RUN/'uncertainty.json','search-uncertainty.json'),
                    (RUN/'independent-audit.json','search-accounting-audit.json'),(RUN/'reproduction.json','search-reproduction.json'),
                    (ROOT/'data/search-1458/manifest.json','search-data-manifest.json'),
                    (ROOT/'data/search-1458/market.json.gz','search-market.json.gz')]:shutil.copyfile(src,OUT/dst)
    # Stable ZIP metadata; preserve the exact gzip results, not a lossy chart export.
    with zipfile.ZipFile(OUT/'search-full.zip','w',compression=zipfile.ZIP_STORED) as z:
        files=sorted(RUN.glob('*.json.gz'))+sorted(RUN.glob('*.json'))
        for p in files:
            entry=zipfile.ZipInfo(p.name,date_time=(2026,10,1,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,p.read_bytes())
    published={p.relative_to(ROOT/'docs').as_posix():{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in list(ASSETS.glob('search-*.json'))+list(OUT.glob('search-*'))}
    (ROOT/'docs/evidence/strategy-search-1458.json').write_bytes(canonical({'build':'1001r2','files':published,'live_trading':False,'forward_evidence':False,'experiment_commits':['b8a49e7','483e63f']}))
    print('Published data package',len(published),'files',sum(v['bytes'] for v in published.values()),'bytes')


if __name__=='__main__':build()
