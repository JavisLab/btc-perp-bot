"""Static, credential-free research note built from immutable event-study results."""
import html
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/price-volume-1462'
DOCS=ROOT/'docs'
report=json.loads((RUN/'results.json').read_text())
names={'B':'돌파 지속','F':'돌파 실패 후 복귀','P':'눌림 후 재개'}
periods={'main':'2022–2025 · 4년','recent':'2026.01–08 · 최근 8개월'}
conditions={'base':'기본 비용','cost_x2':'체결 비용 2배','delay1':'추가 1시간 지연'}
groups={'all':'가격만 · 전체','volume_pass':'가격 + 거래량','volume_fail':'거래량 조건 미통과'}


def signed(value):
    if value is None:return '—'
    return ('−' if value<0 else '+' if value>0 else '')+f'{abs(value):.2f}'


def table(headers,rows,ident=''):
    return f'<div class="scroll-table" tabindex="0" role="region" aria-label="가로 스크롤 가능한 결과 표"><table id="{ident}"><thead><tr>'+''.join('<th scope="col">'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(c)+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'


overview=''; stresses=''; years=''; intervals=''
for period,label in periods.items():
    data=[r for r in report['results'] if r['period']==period and r['scenario']=='base']
    rows=[];ir=[];cards=''
    for r in data:
        a,b=r['groups']['all'],r['groups']['volume_pass']
        rows.append([names[r['family']],a['n'],signed(a['mean_net_bp']),b['n'],signed(b['mean_net_bp']),signed(b['median_net_bp'])])
        cards+=f'<div class="result-card"><h4>{names[r["family"]]}</h4><div><span>가격만 · {a["n"]}건</span><b>{signed(a["mean_net_bp"])} bp</b></div><div><span>거래량 추가 · {b["n"]}건</span><b>{signed(b["mean_net_bp"])} bp</b></div><p>평균 순변화 · 거래량 추가 중앙값 {signed(b["median_net_bp"])} bp</p></div>'
        bounds=r['uncertainty'][0]['pass_minus_fail']['ci_bonferroni6']
        ir.append([names[r['family']], ' ~ '.join(signed(x) for x in bounds) if bounds else '표본 부족'])
    overview+=f'<article class="panel result-block"><h3>{label}</h3>'+table(['가격 구조','가격만 건수','평균 순bp','거래량 추가 건수','평균 순bp','중앙값 순bp'],rows,'overview-'+period)+f'<div class="mobile-results">{cards}</div></article>'
    intervals+=f'<h3>{label} · 통과−미통과 차이</h3>'+table(['구조','14일 블록 · 6비교 보정 구간 (bp)'],ir)
for r in report['results']:
    for g in ('all','volume_pass','volume_fail'):
        value=r['groups'][g]
        stresses+='<tr>'+''.join('<td>'+str(v)+'</td>' for v in [periods[r['period']],names[r['family']],conditions[r['scenario']],groups[g],value['n'],signed(value['mean_net_bp']),signed(value['median_net_bp'])])+'</tr>'
    if r['scenario']=='base':
        for year,sides in r['by_year_side']['volume_pass'].items():
            for side in ('long','short'):
                v=sides[side]
                years+='<tr>'+''.join('<td>'+str(x)+'</td>' for x in [year,names[r['family']],'롱' if side=='long' else '숏',v['n'],signed(v['mean_net_bp']),signed(v['median_net_bp'])])+'</tr>'

for source,target in (
 ('results.json','results.json'),('events.csv','events.csv'),('events.json.gz','events.json.gz'),
 ('data-audit.json','data-audit.json'),('ohlcv.json.gz','ohlcv.json.gz'),
 ('verification.json','verification.json'),('reproduction.json','reproduction.json')):
    shutil.copyfile(RUN/source,DOCS/'downloads'/('price-volume-'+target))

page=f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="가격·거래량 트레이더의 공개 원칙과 세 가지 고정 규칙의 사건 연구. 계좌 수익과 신호 검사를 구분합니다.">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>봉과 거래량, 그 너머 · BTC Research</title><link rel="icon" href="assets/icon.svg" type="image/svg+xml">
<link rel="stylesheet" href="assets/strategy-lab.css?v=1001r2"><link rel="stylesheet" href="assets/price-action.css?v=1001p1"></head>
<body><a class="skip" href="#results">검사 결과로 건너뛰기</a>
<header class="top"><a class="brand" href="./"><img src="assets/icon.svg" alt="">BTC <b>RESEARCH</b></a><nav aria-label="주 메뉴"><a href="#principles">공개 원칙</a><a href="#results">거래량 검사</a><a href="strategy-lab.html">이전 비교 ↗</a></nav></header>
<main><section class="hero"><div><p class="eyebrow">RESEARCH NOTE 004 <span>2026.10.01</span></p><h1>봉과 거래량,<br><em>그 너머의 판단.</em></h1><p class="intro">트레이더들이 공개한 원칙을 읽고,<br>가격 구조에 거래량을 더한 효과를 따로 검사했습니다.</p><div class="chips"><span>가격 구조 3가지</span><span>원자료 58,440시간</span><span>가격만 / 거래량 추가 비교</span></div></div>
<aside class="verdict-card"><p class="eyebrow">WHAT WE LEARNED</p><h2>핵심은 지표의 개수보다<br><strong>상황과 반응, 위험 관리</strong></h2><p>세 가지 단순 거래량 필터의 일관된 우위는 확인하지 못했습니다. 공개 매매 원칙과 검증된 수익을 구분합니다.</p><div class="status"><i></i> 추가 검사 대상 선정 0 / 3 · 실거래 미시작</div></aside></section>
<div class="context"><b>이번 숫자의 의미</b><p>아래는 <strong>계좌 백테스트가 아닌 신호별 24시간 사건 연구</strong>입니다. 겹친 신호를 합산한 누적·연간 수익률은 만들지 않았습니다. 이미 본 Binance 자료를 이용한 탐색이며 Hyperliquid 실적이 아닙니다.</p></div>

<section class="section" id="principles"><div class="section-head"><div><p class="eyebrow">PUBLIC PRINCIPLES, NOT SECRET FORMULAS</p><h2>‘봉만 본다’는 말의 실제 내용</h2></div></div>
<div class="source-grid"><article class="panel"><span class="source-number">01 / Al Brooks</span><h3>가격대에 도착한 뒤의 반응</h3><p>지지·저항과 거래 관리를 중시하면서도 20봉 EMA를 사용한다고 밝힙니다. 지표를 전부 지우는 것 자체가 비밀은 아닙니다.</p><a href="https://www.brookstradingcourse.com/how-to-trade-manual/technical-analysis-indicators/">본인 설명 · 2020 ↗</a></article>
<article class="panel"><span class="source-number">02 / Adam Grimes</span><h3>새로운 힘인가, 지나친 확장인가</h3><p>같은 큰 봉도 위치와 진행 정도에 따라 다르게 해석합니다. 이동평균·Keltner 채널도 설명하며, 모든 작은 차이에 의미를 붙이지 말라고 합니다.</p><a href="https://www.adamhgrimes.com/how-i-trade-part-2-2/">본인 설명 · 2023 ↗</a></article>
<article class="panel"><span class="source-number">03 / Wyckoff 계열</span><h3>거래량에 비해 가격이 얼마나 갔나</h3><p>눌림의 거래량 감소, 경계에서의 시험, 그 뒤의 강한 움직임을 함께 봅니다. ‘거래량 증가=매수’라는 단일 규칙과는 다릅니다.</p><a href="https://www.wyckoffanalytics.com/wyckoff-reaccumulation-vs-distribution-how-to-tell-which-one-youre-in/">공식 해설 · 2026.09.28 ↗</a></article></div>
<div class="two-col space"><article class="panel"><h3>매매 목록과 선택성</h3><p>SMB의 Mike Bellafiore는 반복할 매매 유형을 정의하고, 검증한 기회와 위험 크기를 연결하며 일일 손실을 관리하는 절차를 설명합니다. 글의 공격적인 비중 예시는 이 계좌에 적용하지 않았습니다.</p><a href="https://www.smbtraining.com/blog/14-keys-to-proper-position-sizing-to-grow-your-trading-account">SMB 원문 · 2018 ↗</a></article><article class="panel"><h3>재량에도 숫자로 확인할 부분이 있습니다</h3><p>Grimes의 2026년 9월 글도 재량과 정량적 현실을 함께 보며 변동성과 급격한 충격을 다룹니다. 유명세나 일부 성공 사례는 전체 실계좌 성적의 감사와 다릅니다.</p><a href="https://www.adamhgrimes.com/volatility-has-a-memory/">최근 원문 · 2026.09.24 ↗</a></article></div>
<p class="fine space">읽은 것은 공개 교육 자료입니다. 각 인물의 전체 연도별 실적을 독립 검증한 것이 아니며, 공개되지 않은 ‘진짜 비법’을 알아냈다고 주장하지 않습니다.</p></section>

<section class="section"><div class="section-head"><div><p class="eyebrow">CONTEXT → RESPONSE → INVALIDATION</p><h2>모양 하나보다, 일이 벌어진 순서</h2></div></div>
<div class="two-col"><figure class="panel illustration"><svg viewBox="0 0 480 245" role="img" aria-labelledby="concept-title concept-desc"><title id="concept-title">미리 정한 저항 위로 갔다가 복귀하는 개념도</title><desc id="concept-desc">가상의 가격이 저항100을 넘어101에 도달한 뒤99로 마감합니다. 미래 봉은 물음표로 표시합니다. 실제 시장 자료가 아닙니다.</desc><line class="level" x1="35" y1="95" x2="445" y2="95"/><text x="35" y="79">미리 정한 저항 100</text>
<g class="up"><line x1="72" y1="145" x2="72" y2="214"/><rect x="60" y="162" width="24" height="31"/><line x1="131" y1="120" x2="131" y2="187"/><rect x="119" y="135" width="24" height="37"/><line x1="190" y1="103" x2="190" y2="158"/><rect x="178" y="112" width="24" height="25"/></g>
<g class="down"><line x1="263" y1="38" x2="263" y2="153"/><rect x="251" y="111" width="24" height="24"/></g><text x="281" y="45">101까지 돌파</text><text x="281" y="145">99로 복귀 마감</text><text class="unknown" x="387" y="112">?</text></svg><figcaption>설명용 가상 그림 · 가격 눈금은 개념 표시이며 실제 신호가 아닙니다.</figcaption></figure>
<article class="panel"><h3>확인할 것은 ‘그다음’입니다</h3><ol class="steps"><li><b>위치</b> — 저항은 결과를 보기 전에 정의했는가?</li><li><b>반응</b> — 돌파 뒤 유지되는가, 안으로 밀려오는가?</li><li><b>무효화</b> — 다시 경계 위에 자리잡으면 숏 해석을 폐기하는가?</li><li><b>위험</b> — 틀렸을 때의 손실과 겹친 포지션을 감당할 수 있는가?</li></ol><p class="fine">큰 거래량에 가격이 못 가는 현상은 해석의 단서일 뿐, 특정 큰손의 의도를 확인하는 증거가 아닙니다.</p></article></div></section>

<section class="section" id="results"><div class="section-head"><div><p class="eyebrow">A SMALL, FROZEN TEST</p><h2>거래량 조건을 더하면 나아졌을까?</h2></div><span class="badge amber">두 구간 일관성 미확인</span></div>
<p class="body-copy">4시간봉에서 돌파·돌파 실패·추세 중 눌림을 롱/숏 대칭으로 정의했습니다. 각 가격 신호 전체와 거래량을 통과한 부분집합을 비교합니다. 규칙은 결과 계산 전 커밋으로 고정했습니다.</p>
<p class="unit-note"><b>단위: 사건당 평균 순bp · 1bp = 0.01%</b><br>신호 완성 1시간 후 진입 → 24시간 후 청산. 편도 수수료5bp + 가격 충격1.5bp + 펀딩 포함. 계좌 수익률이 아닙니다.</p>
{overview}
<div class="two-col space"><article class="panel"><h3>과거의 작은 개선이 지속되지는 않았습니다</h3><p>돌파에 큰 거래량을 추가했을 때 과거 평균은 +7.55bp였지만, 최근에는 −49.62bp였습니다. 과거도 체결 비용2배에서는 −5.46bp로 바뀝니다.</p></article><article class="panel"><h3>표본이 작은 좋은 숫자도 승격하지 않습니다</h3><p>눌림의 과거 +57.09bp는41건입니다. 최근 통과 사건은4건에 그쳐 판단하기 어렵습니다. 단순 실패 돌파도 완전한 Wyckoff 방식의 복제가 아닙니다.</p></article></div>
<details class="panel space"><summary>비용·지연 · 통과하지 않은 집단까지 보기</summary><p class="fine space">서로 겹친 신호를 포함합니다. 건수와 bp를 합산해 계좌 수익으로 해석하지 마세요.</p><div class="scroll-table" tabindex="0" role="region" aria-label="비용 지연 조건 비교"><table id="stress"><thead><tr><th>기간</th><th>구조</th><th>조건</th><th>집단</th><th>건수</th><th>평균 순bp</th><th>중앙값 순bp</th></tr></thead><tbody>{stresses}</tbody></table></div></details>
<details class="panel space"><summary>연도별 · 롱/숏 분해</summary><p class="fine space">거래량 통과 사건·기본 비용·진입 연도 기준. 연간 계좌 수익률이 아닙니다. 건수0은 ‘—’로 표시합니다.</p><div class="scroll-table" tabindex="0" role="region" aria-label="연도별 롱숏 결과"><table id="year-side"><thead><tr><th>연도</th><th>구조</th><th>방향</th><th>건수</th><th>평균 순bp</th><th>중앙값 순bp</th></tr></thead><tbody>{years}</tbody></table></div></details>
<details class="panel space"><summary>거래량 효과의 불확실성</summary><p class="fine space">달력14일 블록2,000회 · 세 가족×두 기간의6비교 보정. 모든 구간에0이 포함됩니다. 표본이 작은 경우의 정밀도는 낮으며, 선택 편향을 해결한 검사가 아닙니다. 7/28일 진단은 JSON에 있습니다.</p>{intervals}</details>
<div class="source-links"><a id="csv-download" href="downloads/price-volume-events.csv" download>전체 사건 CSV ↓</a><a href="downloads/price-volume-results.json" download>모든 결과·불확실성 JSON ↓</a></div></section>

<section class="section"><div class="section-head"><div><p class="eyebrow">WHAT COMES NEXT</p><h2>다음은 상황과 실행을 분리해서</h2></div></div><div class="next"><h3>단일 봉 필터 → 경계의 유지·복귀·재시험</h3><p>후속 반응을 사전에 정의하고, 추세/횡보 상태별로 롱과 숏의 역할을 구분하는 것이 다음 연구 방향입니다. 구조적 무효화·계좌 위험·겹친 포지션까지 명세한 뒤에야 실제 계좌 백테스트로 넘어갈 수 있습니다. 이 방향은 연구 가설이지 입증된 개선책이 아닙니다.</p></div>
<article class="panel space"><h3>선물이면 매년 수익이어야 할까?</h3><p>하락장 수익 기회를 검증해야 한다는 목표는 타당합니다. 그러나 숏도 반등·횡보·진입 시점 때문에 손실이 나므로 롱/숏 가능성 자체가 양의 기대값은 아닙니다. 매년 안정적인 수익을 목표로 삼되, 보장으로 전제하지 않습니다.</p><a href="https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management">CME의 선물 손익·위험관리 설명 ↗</a></article>
<details class="panel space"><summary>자료·모형·검산 범위</summary><div class="prose"><ul><li>공식80개 ZIP/58,440시간. OHLC 행은 기존 가격 자료와 전부 일치. 거래량0 한 시간은 그대로 보존, 공백·보간0.</li><li>taker buy는 매수 주도 체결량이지 신규 롱이나 순투자금이 아닙니다. 이번에는 열을 검증만 했으며 필터로 쓰지 않았습니다.</li><li>1시간봉에는 체결 순서·호가 대기열·footprint가 없습니다. Binance 거래량은 Hyperliquid와 다릅니다.</li><li>실제 펀딩률에 정산시각 시간봉 마크 시가를 대입합니다. 같은 시각 정산→거래 순서를 가정합니다. 정확한 정산가격·청산·마진·최소 주문·세금·운영비·과거 요율 변경은 복원하지 않았습니다.</li><li>1,016개 가족별 사건×3조건=3,048개 기록입니다. 겹친 사건 때문에 독립 표본이나 계좌 누적 성과로 합산할 수 없습니다.</li><li>전체98검사, 원본 신호 전수 재열거·Decimal 성분 검산 통과. 5개 산출물을 네트워크 차단 재계산해 바이트 일치를 확인했습니다.</li><li>이미 본 가격 경로의 탐색 검사이며 새 미사용 OOS가 아닙니다. 세 규칙의 실패가 모든 재량 매매의 실패를 뜻하지 않습니다.</li></ul></div></details>
<div class="source-links"><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/PRICE_ACTION_RESEARCH.md">전체 조사 보고서 ↗</a><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/EXPERIMENT_1462.md">계산 전 명세 ↗</a><a href="downloads/price-volume-data-audit.json" download>80개 원자료 출처·검사 ↓</a><a href="downloads/price-volume-ohlcv.json.gz" download>복구 OHLCV 자료 ↓</a><a href="downloads/price-volume-verification.json" download>독립 검산 ↓</a><a href="downloads/price-volume-reproduction.json" download>오프라인 재현 ↓</a></div></section>
</main><footer><span class="brand">BTC <b>RESEARCH</b></span><p>BUILD 1001p1 · 정적 연구 스냅샷 · 계좌 전략/전진 운용/실거래 미시작</p></footer></body></html>'''
(DOCS/'price-action.html').write_text(page)
print(json.dumps({'html_bytes':len(page.encode()),'copied_downloads':7,'tables':8}))
