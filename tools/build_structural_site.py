"""Build a static, local-data-only account research dashboard."""
import csv
import gzip
import io
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/structure-1471';DOC=ROOT/'docs'
from structural_study import IDS,LABELS,SCENARIOS

data={'labels':LABELS,'periods':{'main':'2022–2025 · 4년','recent':'2026.01–08 · 8개월'},
      'scenarios':{'base':'기본 조건','cost_x2':'체결 비용 2배','delay60':'추가 60분 지연','stop_5bp':'손절 추가 5bp',
                   'risk_half':'위험 .25%','risk_double':'위험 1%','flow55':'공격적 체결 55%'},'results':{},
      'selection':json.loads((RUN/'selection.json').read_text()),'diagnostics':json.loads((RUN/'diagnostics.json').read_text()),
      'uncertainty':{p:json.loads((RUN/(p+'-summary.json')).read_text())['uncertainty'] for p in ('main','recent')}}
summary=[];trades=[]
for period in data['periods']:
    data['results'][period]={}
    for family in IDS:
        data['results'][period][family]={}
        for scenario in SCENARIOS:
            path=RUN/f'{period}-{family}-{scenario}.json.gz'
            result=json.loads(gzip.decompress(path.read_bytes()));s=result['summary']
            data['results'][period][family][scenario]={'summary':s,'curve':[[d['time'],d['equity']] for d in result['daily']]}
            summary.append({'period':period,'family':family,'scenario':scenario,**{k:s[k] for k in ('return_pct','cagr_pct','dd_pct','sharpe','trades','net','fees','impact','funding')}})
            for t in result['trades']:
                trades.append({'period':period,'family':family,'scenario':scenario,**{k:t[k] for k in ('source','entry','exit','side','qty','reference','exit_reference','initial_stop','target','net','fees','impact','funding','reason','regime')}})
for name,rows in [('summary',summary),('trades',trades)]:
    output=io.StringIO();writer=csv.DictWriter(output,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    (DOC/'downloads'/f'structure-{name}.csv').write_text(output.getvalue())
for f in ('verification.json','diagnostics.json','reproduction.json','selection.json'):
    shutil.copyfile(RUN/f,DOC/'downloads'/('structure-'+f))
shutil.copyfile(ROOT/'data/structure-1471/resolution.json',DOC/'downloads/structure-data-audit.json')
shutil.copyfile(ROOT/'data/structure-1471/bars-repaired.json.gz',DOC/'downloads/structure-5m.json.gz')
with zipfile.ZipFile(DOC/'downloads/structure-all-runs.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for f in sorted(RUN.glob('*-*-*.json.gz')):
        info=zipfile.ZipInfo(f.name,date_time=(2026,10,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,f.read_bytes())
(DOC/'assets/structure-data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False))
page='''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="돌파·재시험·무효화와 청산을 함께 검증한 BTC 선물 계좌 연구. 5분봉·5후보·70개 조건별 계좌.">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>진입 다음의 전략 · BTC Research</title><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/strategy-lab.css?v=1001r2"><link rel="stylesheet" href="assets/structure.css?v=1001s1"><script defer src="assets/structure.js?v=1001s1"></script></head>
<body><a class="skip" href="#explorer">결과로 건너뛰기</a><header class="top"><a class="brand" href="./"><img src="assets/icon.svg" alt="">BTC <b>RESEARCH</b></a><nav aria-label="주 메뉴"><a href="#explorer">계좌 비교</a><a href="#next">후속 연구</a><a href="price-action.html">봉·거래량 연구 ↗</a></nav></header>
<main><section class="hero"><div><p class="eyebrow">RESEARCH NOTE 005 <span>2026.10.01</span></p><h1>진입 다음의<br><em>전략.</em></h1><p class="intro">가격이 돌파한 뒤의 반응부터<br>틀렸을 때의 손절, 맞았을 때의 청산까지.</p><div class="chips"><span>5개 가격 구조</span><span>5분봉 체결 모형</span><span>롱 · 숏 분리</span></div></div>
<aside class="verdict-card"><p class="eyebrow">RESEARCH CONTINUES</p><h2>연도별 플러스와<br><strong>충분한 수익은 다릅니다</strong></h2><p>채널 추종은 과거 4개 연도 모두 플러스였지만 누적 +13.42%, 36회 거래에 그쳤습니다. 사전 기준을 통과한 후보는 아직 없습니다.</p><div class="status"><i></i> 실전 채택 0 / 5 · 연구 진행 중</div></aside></section>
<div class="context"><b>이전 사건 연구와 달라진 점</b><p>포지션 중첩 없이 가상 1,000 USDT 계좌를 계산했습니다. 진입 시 위험 .5%·명목100% 이내, 손절·목표·펀딩·비용을 포함합니다. <strong>Binance의 이미 본 역사 자료를 이용한 탐색이며, Hyperliquid 실적·새 미사용 평가가 아닙니다.</strong></p></div>

<section id="explorer" class="section"><div class="section-head"><div><p class="eyebrow">EXPLORE THE ACCOUNT</p><h2>수익과 손실, 함께 보기</h2></div></div>
<div class="panel filters"><label>평가 기간<select id="period"><option value="main">2022–2025 · 4년</option><option value="recent">2026.01–08 · 8개월</option></select></label><label>가격 구조<select id="family"><option value="A_ACCEPT">돌파 유지</option><option value="R_RETEST">돌파 후 재시험</option><option value="F_REJECT">실패 돌파 복귀</option><option value="P_RESUME">추세 눌림 재개</option><option value="C_CHANNEL">55봉 채널 추종</option></select></label><label>조건<select id="scenario"><option value="base">기본 조건</option><option value="cost_x2">체결 비용 2배</option><option value="delay60">추가 60분 지연</option><option value="stop_5bp">손절 추가 5bp</option><option value="risk_half">위험 .25%</option><option value="risk_double">위험 1%</option><option value="flow55">공격적 체결 55%</option></select></label></div>
<p id="status-note" class="fine space" role="status">결과를 불러오는 중…</p><div class="metric-grid" id="metrics"></div>
<article class="panel space chart-panel"><div class="chart-heading"><h3 id="chart-title">계좌 자산 · USDT</h3><div class="chart-tabs"><button id="equity" type="button" aria-pressed="true">자산</button><button id="drawdown" type="button" aria-pressed="false">낙폭</button></div></div><svg id="chart" viewBox="0 0 920 310" role="img" aria-label="일말 계좌 자산 차트" tabindex="0"></svg><p class="fine" id="chart-readout">차트를 터치하거나 좌우 방향키로 날짜별 값을 확인할 수 있습니다.</p><p class="fine">차트는 일말 값입니다. 위 최대낙폭은 5분 종가 관측값이라 차트보다 클 수 있습니다.</p></article>
<div class="two-col space"><article class="panel"><h3>연도별 수익률</h3><div id="years"></div></article><article class="panel"><h3>롱과 숏의 실제 기여</h3><div id="sides"></div><p class="fine space">수수료·슬리피지·펀딩 포함, 종료한 거래의 순손익 합계. 연도별 수익률과는 구분합니다.</p></article></div>
<article class="panel space"><h3>이 기간의 모든 기본 후보</h3><div id="comparison" class="candidate-grid"></div></article>
<details class="panel space"><summary>선택 후보의 비용·지연·위험·체결량 진단</summary><div id="stress" class="scroll-table" tabindex="0" role="region" aria-label="조건별 계좌 비교"></div><p class="fine space">위험과 체결량 조건은 민감도이며 기본 후보를 대신해 선정하지 않았습니다. 비용이 달라지면 위험 예산에 맞춰 수량을 다시 내리므로 일부 짧은 구간의 순익은 비단조적일 수 있습니다.</p></details>
<details class="panel space"><summary>노출·손익 원인과 통계적 불확실성</summary><div id="diagnostics" class="prose"></div></details>
<div class="source-links"><a id="summary-csv" href="downloads/structure-summary.csv" download>70개 계좌 요약 CSV ↓</a><a id="trade-csv" href="downloads/structure-trades.csv" download>전체 거래 기록 CSV ↓</a><a href="downloads/structure-all-runs.zip" download>전체 계좌·원장 ZIP ↓</a></div></section>

<section class="section"><div class="section-head"><div><p class="eyebrow">WHAT CHANGED</p><h2>봉 하나가 아닌, 사건의 순서</h2></div></div><div class="source-grid"><article class="panel"><span class="source-number">01 / 확인</span><h3>돌파가 유지되는가</h3><p>다음 봉에서도 가격대를 유지하거나, 재시험 후 돌아서는지를 먼저 정의했습니다. 이미 무효화된 신호는 늦게라도 따라 들어가지 않습니다.</p></article><article class="panel"><span class="source-number">02 / 무효화</span><h3>손절을 넓히지 않기</h3><p>가격 구조에 최초 손절을 두고, 계좌 위험에 맞춰 수량을 줄입니다. 갭으로 손절가를 건너뛰면 더 큰 손실이 가능합니다.</p></article><article class="panel"><span class="source-number">03 / 유지</span><h3>이익을 자를지, 따라갈지</h3><p>일부 후보는 고정 목표, 일부는 완료 봉을 따라 손절을 올립니다. 같은 5분봉 안에서 손절·목표가 모두 닿으면 손절이 먼저라고 계산했습니다.</p></article></div>
<p class="fine space">공개 교육 자료를 수치화한 연구 가설이지, 유명 트레이더의 실제 계좌나 비공개 기법을 복제한 것이 아닙니다. <a href="https://www.adamhgrimes.com/fundamental-trading-patterns/">Grimes</a> · <a href="https://www.smbtraining.com/blog/wp-content/uploads/2024/03/Technical-Analysis-Range-Break-Trading-Cheat-Sheet.pdf">SMB</a> · <a href="https://www.cmegroup.com/education/courses/building-a-trade-plan/trading-strategies-in-your-trade-plan">CME</a></p></section>

<section id="next" class="section"><div class="section-head"><div><p class="eyebrow">NEXT RESEARCH</p><h2>수익 숫자보다, 부족한 정보를 보완</h2></div></div><div class="next"><h3>종목 이전 검증 → 정보 추가 → 잠근 새 기간</h3><p>한 종목의 드문 기회에 의존하는지 먼저 확인합니다. 다음 순서는 파라미터를 바꾸지 않은 ETH 이전 검증, 거래량·파생시장 정보의 추가 가치, 이후 새로 쌓이는 기간의 확인입니다. 결과가 좋을 때만 남기는 방식으로 과거 자료를 반복 최적화하지 않습니다.</p></div>
<details class="panel space"><summary>자료와 검증의 범위</summary><div class="prose"><ul><li>공식 월별 59개+추가 일별 10개 ZIP. 517,248개의 5분봉, 시각 누락·보간0. 2시간은 일별 원본으로 복구했습니다.</li><li>4시간의 거래량/체결수 상충과 선행 무거래 봉의 시가 차이를 보존했습니다. 이번 70개 계좌는 남은 상충 시간에 포지션·체결 노출이 없었습니다. 무거래 봉36개에서는 체결을 만들지 않습니다.</li><li>편도 taker5bp·가격충격1.5bp, 수량.001 BTC·최소신규50 USDT를 과거에 고정했습니다. 실제 과거 규정·호가·부분체결·청산·ADL·세금·운영비는 복원하지 않았습니다.</li><li>펀딩은 실제 과거율×시간봉 마크 시가 근사입니다. 원시 정산시각의 수ms 차이는 시간 경계로 정렬했습니다.</li><li>110개 자동검사, 원본 신호722개 독립 전수 재열거, 70개 계좌의 보유 중5분봉 경로·Decimal 회계·일말59,640개를 독립 대조했습니다. 모형 정확성이 수익성 입증은 아닙니다.</li><li>부트스트랩 구간에0이 포함되어 우위를 확정하지 못했습니다. 이미 본 자료에서 반복 연구한 선택 편향도 남아 있습니다.</li></ul></div></details>
<div class="source-links"><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/STRUCTURAL_RESULTS.md">전체 보고서 ↗</a><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/EXPERIMENT_1471.md">사전 명세 ↗</a><a href="downloads/structure-data-audit.json" download>원자료 감사 ↓</a><a href="downloads/structure-5m.json.gz" download>5분봉 자료 ↓</a><a href="downloads/structure-verification.json" download>독립 검산 ↓</a><a href="downloads/structure-reproduction.json" download>오프라인 재현 ↓</a></div></section></main>
<footer><span class="brand">BTC <b>RESEARCH</b></span><p>BUILD 1001s1 · 정적 연구 스냅샷 · 연구 일정과 실시간 모의매매는 별개 · 실거래 미시작</p></footer></body></html>'''
(DOC/'structure-lab.html').write_text(page)
print(json.dumps({'accounts':len(summary),'trade_rows':len(trades),'html_bytes':len(page.encode())}))
