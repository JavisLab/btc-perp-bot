"""Publish verified ETH transfer results; preserve all candidates and diagnoses."""
import csv
import gzip
import html
import io
import json
import shutil
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/eth-transfer-performance-20261002';DOC=ROOT/'docs'
IDS=('A_ACCEPT','R_RETEST','F_REJECT','P_RESUME','C_CHANNEL')
LABELS=dict(zip(IDS,('돌파 유지','돌파 후 재시험','실패 돌파 복귀','추세 눌림 재개','55봉 채널 추종')))
SCENARIOS={'base':'기본 조건','cost_x2':'체결 비용 2배','delay60':'추가 60분 지연','stop_5bp':'손절 추가 5bp','risk_half':'위험 .25%','risk_double':'위험 1%','flow55':'공격적 체결 55%','min50':'최소금액50 · 진단만'}
verification=json.loads((RUN/'verification.json').read_bytes());reproduction=json.loads((RUN/'reproduction.json').read_bytes());exposure=json.loads((RUN/'conflict-exposure.json').read_bytes())
assert verification['experiments']==80 and reproduction['all_bytes_equal'] and reproduction['matched_files']==87
summaries={p:json.loads((RUN/f'{p}-summary.json').read_bytes()) for p in ('main','recent')}
selection=json.loads((RUN/'selection.json').read_bytes());assert selection['ranked_passes']==[]
data={'labels':LABELS,'periods':{'main':'2022–2025 · 4년','recent':'2026.01–08 · 8개월'},'scenarios':SCENARIOS,'results':{},'selection':selection,
      'diagnostics':json.loads((RUN/'diagnostics.json').read_bytes()),'uncertainty':{p:summaries[p]['uncertainty'] for p in summaries}}
summary_rows=[];trades=[]
for period in summaries:
    data['results'][period]={}
    for name in IDS:
        data['results'][period][name]={}
        for scenario in SCENARIOS:
            r=json.loads(gzip.decompress((RUN/f'{period}-{name}-{scenario}.json.gz').read_bytes()));s=r['summary']
            data['results'][period][name][scenario]={'summary':s,'curve':[[d['time'],d['equity']] for d in r['daily']]}
            summary_rows.append({'period':period,'family':name,'scenario':scenario,**{k:s[k] for k in ('return_pct','cagr_pct','dd_pct','sharpe','trades','net','fees','impact','funding','positive_years','ex_best_quarter_pct','unresolved_archive_exposure_bars')},'minimum_notional_rejects':s['sizing']['minimum_notional_rejects']})
            trades.extend({'period':period,'family':name,'scenario':scenario,**t} for t in r['trades'])
for label,rows in [('summary',summary_rows),('trades',trades)]:
    out=io.StringIO();w=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    (DOC/'downloads'/f'eth-results-{label}.csv').write_text(out.getvalue())
for name in ['verification.json','reproduction.json','diagnostics.json','selection.json','conflict-exposure.json']:
    shutil.copyfile(RUN/name,DOC/'downloads'/('eth-results-'+name))
with zipfile.ZipFile(DOC/'downloads/eth-results-all-runs.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for f in sorted(RUN.iterdir()):
        if not f.is_file():continue
        info=zipfile.ZipInfo(f.name,date_time=(2026,10,2,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,f.read_bytes())
(DOC/'assets/eth-results-data.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False))
js=(DOC/'assets/structure.js').read_text().replace('assets/structure-data.json?v=1001s1','assets/eth-results-data.json?v=1002e2')
js=js.replace("$('diagnostics').innerHTML=", "$('diagnostics').innerHTML='<p>ETH 수량 .001 단위·최소금액 '+(c==='min50'?'50 USDT (진단만)':'20 USDT')+'. 수량 산정 '+s.sizing.attempts+'회, 최소금액 거절 '+s.sizing.minimum_notional_rejects+'회, 승인 수량 내림으로 미사용된 최초 손절위험 합계 '+plain(s.sizing.accepted_rounding_risk_loss)+' USDT (손실금액 아님).</p>'+ ")
(DOC/'assets/eth-results.js').write_text(js)

def pct(v):return f'{v:+.2f}%'
def table(period):
    out=[]
    for n in IDS:
        s=summaries[period]['summaries'][n];b=s['base'];c=s['cost_x2'];m=s['min50']
        out.append(f'<tr data-family="{n}"><th>{LABELS[n]}</th><td>{pct(b["return_pct"])}</td><td>{pct(b["cagr_pct"]) if period=="main" else "—"}</td><td>{b["dd_pct"]:.2f}%</td><td>{b["trades"]}</td><td>{pct(c["return_pct"])}</td><td>{pct(m["return_pct"])}</td></tr>')
    return ''.join(out)
comparison=[];md_comparison=[]
for n in IDS:
    btc=json.loads((ROOT/'runs/structure-1471/main-summary.json').read_bytes())['summaries'][n]['base'];eth=summaries['main']['summaries'][n]['base']
    br=json.loads((ROOT/'runs/structure-1471/recent-summary.json').read_bytes())['summaries'][n]['base'];er=summaries['recent']['summaries'][n]['base']
    comparison.append(f'<tr><th>{LABELS[n]}</th><td>{pct(btc["return_pct"])}</td><td>{pct(eth["return_pct"])}</td><td>{pct(br["return_pct"])}</td><td>{pct(er["return_pct"])}</td></tr>')
    md_comparison.append(f'| {n} | {pct(btc["return_pct"])} | {pct(eth["return_pct"])} | {pct(br["return_pct"])} | {pct(er["return_pct"])} |')
options=''.join(f'<option value="{n}">{v}</option>' for n,v in LABELS.items());conditions=''.join(f'<option value="{n}">{v}</option>' for n,v in SCENARIOS.items())
page=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="5개 고정 BTC 구조 규칙을 ETH에 전이한 80개 가상계좌 연구. 모든 실패·비용·상충 노출을 공개합니다."><meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'"><title>같은 규칙, 다른 시장 · ETH Research</title><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/strategy-lab.css?v=1001r2"><link rel="stylesheet" href="assets/structure.css?v=1001s1"><script defer src="assets/eth-results.js?v=1002e2"></script></head><body><a class="skip" href="#explorer">계좌 비교로 이동</a><header class="top"><a class="brand" href="./"><img src="assets/icon.svg" alt="">BTC <b>RESEARCH</b></a><nav aria-label="주 메뉴"><a href="#explorer">80계좌 비교</a><a href="eth-transfer.html">원자료 감사</a><a href="structure-lab.html">BTC 결과 ↗</a></nav></header>
<main><section class="hero"><div><p class="eyebrow">RESEARCH NOTE 007 <span>2026.10.02</span></p><h1>같은 규칙,<br><em>다른 시장.</em></h1><p class="intro">BTC에서 고정한 5개 가격 구조를<br>ETH에도 빠짐없이 적용했습니다.</p><div class="chips"><span>70개 고정 계좌</span><span>최소금액 진단 10개</span><span>독립 원장 검산</span></div></div><aside class="verdict-card"><p class="eyebrow">NO CANDIDATE PASSED</p><h2>종목을 바꿔도,<br><strong>충분한 우위는 없었습니다.</strong></h2><p>채널 추종의 과거 4년 수익은 +11.24%, 연복리 2.70%·43거래였습니다. 최근 8개월은 −0.76%. 기존 BTC보다 우수한 전략이라고 검증되지 않았습니다.</p><div class="status" id="verdict"><i></i> 기준 통과 0 / 5 · 실전채택 없음</div></aside></section>
<div class="context"><b>Binance USDT · 탐색적 역사 전이 연구</b><p>각 기간 가상 1,000 USDT. 기본 위험 .5%, 진입 명목≤100%, 편도 수수료5bp+가격충격1.5bp+실제 과거 펀딩. <strong>이미 본 ETH 자료이며 새 미사용 OOS·Hyperliquid 성과·실전 수익 보장이 아닙니다.</strong> 성과 전 명세 eaacfbd, 어댑터 b50e54b를 고정했습니다.</p></div>
<section class="section"><div class="section-head"><div><p class="eyebrow">ALL CANDIDATES, INCLUDING FAILURES</p><h2>기본 후보 5개, 같은 통과 문턱</h2></div></div><div class="panel scroll-table" tabindex="0" role="region" aria-label="주구간 전체 후보 결과"><table id="main-results"><thead><tr><th>후보</th><th>2022–25 누적</th><th>연복리</th><th>5분 DD</th><th>거래</th><th>비용2배 누적</th><th>최소금액50 진단</th></tr></thead><tbody>{table('main')}</tbody></table></div><p class="fine space">전부 기준미달. 최소금액50·위험확대·flow55에서 더 좋은 수치가 나와도 기본 후보를 대체하지 않습니다. 14일 블록·5후보 보정 구간은 모두 0을 포함합니다.</p>
<details class="panel space" id="criteria"><summary>성과 전 통과 기준과 탈락 이유</summary><div class="prose"><p>CAGR≥10%, Sharpe≥.8, 5분 종가 DD≤25%, 양수연도≥3/4, 비용2배 순익&gt;0, 최고분기 제외 복리&gt;0, 담보진단 위반0, 최소100왕복을 모두 요구합니다. C_CHANNEL은 연복리·거래수에서 탈락. R_RETEST도 18거래·연복리1.51%에 불과합니다. A_ACCEPT는 비용2배에서 손실입니다. 어떤 기준도 결과 뒤 완화하지 않았습니다.</p><p>최근 구간은 연환산 순위에 쓰지 않습니다. 모든 후보의 최근 기본·비용2배, 연도·분기·롱숏·국면·거절·원장을 아래 계좌 선택과 다운로드에 포함합니다.</p></div></details></section>
<section id="explorer" class="section"><div class="section-head"><div><p class="eyebrow">EXPLORE THE ACCOUNT</p><h2>수익·비용·위험을 함께 비교</h2></div></div><div class="panel filters"><label>평가 기간<select id="period"><option value="main">2022–2025 · 4년</option><option value="recent">2026.01–08 · 8개월</option></select></label><label>가격 구조<select id="family">{options}</select></label><label>조건<select id="scenario">{conditions}</select></label></div><p id="status-note" class="fine space" role="status">결과를 불러오는 중…</p><div class="metric-grid" id="metrics"></div><article class="panel space chart-panel"><div class="chart-heading"><h3 id="chart-title">계좌 자산 · USDT</h3><div class="chart-tabs"><button id="equity" type="button" aria-pressed="true">자산</button><button id="drawdown" type="button" aria-pressed="false">낙폭</button></div></div><svg id="chart" viewBox="0 0 920 310" role="img" aria-label="일말 계좌 자산 차트" tabindex="0"></svg><p class="fine" id="chart-readout">차트를 터치하거나 방향키로 날짜별 값을 확인하세요.</p><p class="fine">차트는 일말 값입니다. 최대낙폭 지표는 5분 종가라 차트보다 클 수 있습니다.</p></article><div class="two-col space"><article class="panel"><h3>연도별 수익률</h3><div id="years"></div></article><article class="panel"><h3>롱·숏 순손익</h3><div id="sides"></div><p class="fine space">수수료·가격충격·펀딩 포함, USDT.</p></article></div><article class="panel space"><h3>이 기간의 모든 기본 후보</h3><div id="comparison" class="candidate-grid"></div></article><details class="panel space" id="stress-details"><summary>선택 후보의 8가지 비용·위험·수량 조건</summary><div id="stress" class="scroll-table" tabindex="0" role="region" aria-label="조건별 ETH 계좌 비교"></div><p class="fine space">최소금액50은 별도 진단입니다. 비용/규모가 달라지면 수량·거래경로도 변할 수 있어 수익의 단조성이나 새로운 alpha를 뜻하지 않습니다.</p></details><details class="panel space" id="diagnostic-details"><summary>수량 내림·노출·손익 원인·통계적 불확실성</summary><div id="diagnostics" class="prose"></div></details><div class="source-links"><a id="summary-csv" href="downloads/eth-results-summary.csv" download>80계좌 요약 CSV ↓</a><a id="trade-csv" href="downloads/eth-results-trades.csv" download>2,101개 조건별 거래 CSV ↓</a><a id="account-zip" href="downloads/eth-results-all-runs.zip" download>전체 신호·계좌·원장·수량 ZIP ↓</a></div></section>
<section class="section" id="archive-impact"><div class="section-head"><div><p class="eyebrow">CONFLICTS STAY VISIBLE</p><h2>자료 상충은 결과에서 지우지 않았습니다.</h2></div></div><div class="context"><b>80계좌 합산: 보유 322봉 · 체결 14건</b><p>같은 거래가 민감도 조건마다 반복되므로 독립된 14건의 시장 사건이 아닙니다. 기본 A_ACCEPT는 상충시간 보유39봉·시간청산1건, P_RESUME는 7봉·손절1건입니다. 다른 기본 후보·최근 구간의 상충 보유/체결은0입니다.</p></div><div class="two-col space"><article class="panel"><h3>신호 입력·대기 구간</h3><p>원신호 6개의 가격 룩백에 거래량 상충시간이 포함됐으나 해당 거래량을 룩백에서 사용하지 않습니다. 상충6시간을 월별5분 집계로 대체한 입력 진단에서도 원신호·추적값 변화0. 실제 진입대기 구간의 상충노출0입니다. 대체 계좌성과는 계산하지 않았습니다.</p></article><article class="panel"><h3>무거래는 체결 가격이 아닙니다</h3><p>무거래 봉에서는 체결·대기손절 취소0. 보유 중 무거래175봉(조건별 합산)은 기존 극단값 스트레스에만 포함됩니다. A_ACCEPT의 2024.10.28 21:10UTC 시간청산은 거래 재개 뒤 월별5분 시가를 사용했습니다. 이 시각의 일별1분·5분 가격도 상충하여 해당 성과에 자료 한계가 남습니다.</p></article></div><p class="fine space">체크섬·시각 공백0이 경제적 완전성을 보장하지 않습니다. 원자료/기본 우선순위를 결과 뒤 바꾸지 않았습니다. 월별5분·일별5분·일별1분 간 차이와 상세 노출을 보존했습니다.</p><div class="source-links"><a href="downloads/eth-results-conflict-exposure.json" download>상충 의존성·체결 전체 JSON ↓</a><a href="eth-transfer.html">309개 공식 원자료 감사 ↗</a></div></section>
<section class="section"><div class="section-head"><div><p class="eyebrow">BTC AND ETH, NO PORTFOLIO CLAIM</p><h2>잘 된 후보만 고르지 않은 시장 비교</h2></div></div><div class="panel scroll-table" tabindex="0" role="region" aria-label="동일 규칙 BTC ETH 비교"><table id="cross-market"><thead><tr><th>기본 후보</th><th>BTC 2022–25</th><th>ETH 2022–25</th><th>BTC 최근8개월</th><th>ETH 최근8개월</th></tr></thead><tbody>{''.join(comparison)}</tbody></table></div><p class="fine space">BTC는 기존 검증 결과를 참조했으며 다시 계산하지 않았습니다. 동일 .001 수량도 경제적 규모는 다르고 최소금액도 BTC50/ETH20입니다. ETH 내 min50 진단을 별도로 공개합니다. 50:50 포트폴리오·공동증거금 수익은 계산하지 않았습니다.</p></section>
<section class="section" id="proof"><div class="section-head"><div><p class="eyebrow">INDEPENDENT REPLAY</p><h2>계산의 정확성과 전략의 우위는 다릅니다.</h2></div></div><div class="two-col"><article class="panel"><h3>원자료·원장 검산</h3><p id="proof-counts">80계좌 · 원신호733개 · 거래2,101건 · 보유경로1,454,165봉 · 일말68,160개. 원본1h/펀딩에서 독립 열거하고 Decimal 이중부기·모든5분 낙폭을 대조했습니다.</p><p>최대 자산 오차 {verification['max_daily_error']:.3g} USDT. 수량 내림·최소금액/수량·상한·flow·국면·연도·분기·비용도 대조했습니다.</p></article><article class="panel"><h3>인터넷 없이 전체 재생성</h3><p id="reproduction-count">87개 최종 산출물 전체 바이트 일치.</p><p>socket 연결·송신·이름 조회 차단을 직접 확인한 상태에서 80계좌, 신호, 요약, 선정, 독립검산·노출 결과까지 재현했습니다. 미래가격 교란·롱숏 비용/펀딩·지연/무거래 등 17개 경계검사도 통과했습니다.</p></article></div><details class="panel space" id="limits"><summary>검증하지 못한 위험과 재현 한계</summary><div class="prose"><p>현재 ETH .001/최소20/최대2000 조건의 역사 고정이며, 역사 규정·가격틱 기반 주문 수용성은 미복원입니다. 이론 손절/목표·비용 체결가는 연속값입니다. 호가·부분체결·봉내 실제 순서·정확 청산·ADL·세금·운영비는 재현하지 않습니다. 펀딩은 실제율×해당 시간 mark 시가 근사이며 원시시각의 수ms 차이를 시간 경계로 정렬했습니다.</p><p>처음 독립검산 실행은 검산기의 경로/신호시각 변수명 충돌로 실패했습니다. 검산기만 수정했고 동결 어댑터·전략·자료·80계좌 결과는 변경하지 않았습니다. 최초 테스트 환경에는 연구 의존성이 없어 건너뛰어졌고, 보존된 연구 환경에서 17개 검사를 완료했습니다. 이전 실행 증거도 보존합니다.</p><p>부트스트랩은 7/14/28일 원형블록 각2,000회와95%·5후보 보정구간. 반복 연구 선택 편향이나 BTC·ETH의 상관성을 제거하지 못합니다. 기준통과도 미래 수익 보장이 아닙니다.</p></div></details><div class="source-links"><a href="downloads/eth-results-verification.json" download>독립검산 JSON ↓</a><a href="downloads/eth-results-reproduction.json" download>소켓차단 재현 JSON ↓</a><a href="downloads/eth-results-selection.json" download>모든 후보 탈락 기준 JSON ↓</a><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/ETH_TRANSFER_RESULTS.md">상세 보고서 ↗</a><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/EXPERIMENT_ETH_TRANSFER_20261002.md">성과 전 명세 ↗</a></div></section>
<section class="section" id="next"><div class="next"><h3>다음: 실제 파생시장 정보의 자료 경제성 감사</h3><p>실제 미결제약정·펀딩·공격적체결 자료의 보유 범위와 시각 지연을 확인합니다. 추가 정보가 없다면 반복 최적화 대신 일정을 조정합니다. 새 전략 성과·새 OOS·전진 모의운영을 시작했다는 뜻은 아닙니다.</p></div></section></main><footer><span class="brand">BTC <b>RESEARCH</b></span><p>BUILD 1002e2 · 정적 연구 스냅샷 · 정규 09·15·21 KST 연구<br>기준통과0 · 상시 모의매매·실거래 없음</p></footer></body></html>'''
if (ROOT/'data/oi-inputs-20261002/reproduction.json').exists():
    import re
    from build_oi_report import section
    page=re.sub(r'<section class="section" id="next">.*?</section>',lambda _:section(),page,flags=re.S)
(DOC/'eth-results.html').write_text(page)
md=['# ETH 전이 · 80계좌 검증 결과 (2026-10-02 UTC)','',
'**기본후보 5개 모두 기준 미달. 실전채택·전진가동 없음. 이미 본 역사 자료이며 새 OOS가 아니다.**','',
'사전명세 eaacfbd → 자료감사 786ca85 → 성과 전 어댑터 b50e54b. [대화형 전체 결과](eth-results.html). 기존 BTC 결과는 재계산하지 않았다.','',
'## 모든 기본 후보','', '| 후보 | 주 누적 | CAGR | Sharpe | DD | 거래 | 비용2배 누적 | 최근 누적 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
for n in IDS:
    b=summaries['main']['summaries'][n]['base'];c=summaries['main']['summaries'][n]['cost_x2'];r=summaries['recent']['summaries'][n]['base']
    md.append(f'| {n} | {pct(b["return_pct"])} | {pct(b["cagr_pct"])} | {b["sharpe"]:.4f} | {b["dd_pct"]:.4f}% | {b["trades"]} | {pct(c["return_pct"])} | {pct(r["return_pct"])} |')
md+=['','通과기준은 CAGR10%, Sharpe.8, DD25%이내, 양수연도3/4, 비용2배/최고분기제외양수, 담보진단위반0,100거래를 모두 요구한다. C는 CAGR/거래수 미달. 어떤 기준도 완화하지 않았다. 최근는 별도 8개월 가상계좌이며 연환산 순위에 사용하지 않았다.','',
'## 시장 비교 (기본, 누적)','', '| 후보 | BTC 주 | ETH 주 | BTC 최근 | ETH 최근 |','|---|---:|---:|---:|---:|',*md_comparison,'',
'공동증거금·포트폴리오 성과가 아니다. ETHmin20을 BTC50과 혼동하지 않으며, ETH 내 min50진단10개를 모두 보존한다. 최소금액 때문에 생긴 차이나 위험확대를 새 alpha라고 하지 않는다.','',
'## 최소금액50 진단 (선정에 미사용)','','| 후보 | 주min20 | 주min50 | 주거절수 | 최근min20 | 최근min50 | 최근거절수 |','|---|---:|---:|---:|---:|---:|---:|']
for n in IDS:
    a=summaries['main']['summaries'][n];b=summaries['recent']['summaries'][n]
    md.append(f'| {n} | {pct(a["base"]["return_pct"])} | {pct(a["min50"]["return_pct"])} | {a["min50"]["sizing"]["minimum_notional_rejects"]} | {pct(b["base"]["return_pct"])} | {pct(b["min50"]["return_pct"])} | {b["min50"]["sizing"]["minimum_notional_rejects"]} |')
md+=['','## 자료 상충·경계','',
'상충6시간: 80조건별 계좌 합산 보유322봉/체결14건. 동일시장사건 중복이며 독립표본14건이 아니다. 기본A 보유39봉/시간청산1, 기본P7봉/손절1, 나머지기본/최근0. 무거래보유175봉은 기존 극단값 스트레스에 포함되나 체결/대기손절취소 없음. A의 2024-10-28 21:10UTC 거래 재개후 시간청산은 월별5m 시가를 사용한다. 이 시각은 일별1m/5m도 가격차가 있어 경제적 자료 불확실성이 남는다.','',
'원신호6개 룩백의 거래량 상충은 해당 룩백 가격변수에 수치차를 만들지 않는다. 6시간의1h를5m집계로 치환한 신호입력 진단: 신호·추적변화0, 대체성과계산0. 실제 진입대기 상충0. 기본자료를 사후 유리하게 대체하지 않았다.','',
'현재수량.001/최소20/최대2000은 역사고정. 연속값 체결/손절, tick수용성·정확청산·부분체결·호가·봉내경로·ADL·세금/운영비 미복원. 펀딩 mark시가/시간버킷 근사. 모든 보정 평균수익 CI가0포함; 선택편향/시장상관성 미제거.','',
'## 검산·재현','',f'- {verification["experiments"]}계좌, 원신호{verification["independent_raw_signals"]}, {verification["events"]}이벤트, {verification["trades"]}거래, 보유{verification["held_bars_rechecked"]}봉, {verification["daily_equities"]}일말 독립검산.',
f'- 최대금액오차 {verification["max_daily_error"]} USDT. 원본1h/fund, Decimal원장·5mDD·수량거절·ATR/flow/국면·연도분기·비용 대조.',
'- 17경계검사. 최초 봇환경 numpy 부재로skip→기존 연구환경에서통과. 최초 독립검산기 경로/시각변수 충돌→검산기만수정. 전략·어댑터·성과파일변경0, 실패로그보존.',
'- 소켓연결/송신/이름조회 차단 확인 후 전체87산출물 바이트일치. [증거](downloads/eth-results-reproduction.json). 전체ZIP은80계좌/원신호/요약/검산/노출/재현88파일.',
'- 실행: `PYTHONPATH=src /path/to/research-python tools/eth_transfer_study.py --out runs/eth-transfer-performance-20261002 --period main` 및 `recent`; `verify_eth_transfer_study.py`; `audit_eth_transfer_exposure.py`; `reproduce_eth_transfer_study.py --source runs/eth-transfer-performance-20261002 --out <new-directory>`. 연구환경 의존성 requirements-research.lock, 원자료는감사JSON의공식URL/체크섬.',
'','## 결과와 다음','', '수익을 충분히 높인 전략으로 확인되지 않았다. 다음은 실제OI/펀딩/공격적체결 정보의 공개자료 범위·시각·경제성 감사. 실질정보가없으면반복최적화대신연구일정조정. 정규09·15·21KST/회차45분,상시paper/실거래아님.']
(DOC/'ETH_TRANSFER_RESULTS.md').write_text('\n'.join(md).replace('通과','통과')+'\n')
print(json.dumps({'accounts':len(summary_rows),'trades':len(trades),'files_reproduced':reproduction['matched_files'],'page_bytes':len(page.encode())}))
