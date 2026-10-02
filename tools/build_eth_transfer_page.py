"""Publish only verified ETH source-audit evidence. Never calculates strategy returns."""
import csv
import hashlib
import html
import io
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/eth-transfer-20261002'
RUN=ROOT/'runs/eth-transfer-20261002'
DOC=ROOT/'docs'
a=json.loads((SOURCE/'audit.json').read_text())
v=json.loads((RUN/'independent-verification.json').read_text())
r=json.loads((RUN/'reproduction.json').read_text())
assert not a['performance_computed'] and not v['performance_computed']
assert r['network_disabled'] and r['all_outputs_byte_identical']
assert v['source_audit_sha256']==hashlib.sha256((SOURCE/'audit.json').read_bytes()).hexdigest()
n=a['counts']
transfers={
 'eth-transfer-data-audit.json':SOURCE/'audit.json',
 'eth-transfer-verification.json':RUN/'independent-verification.json',
 'eth-transfer-reproduction.json':RUN/'reproduction.json',
 'eth-transfer-5m.json.gz':SOURCE/'bars-repaired.json.gz',
 'eth-transfer-hourly.json.gz':SOURCE/'hourly-ohlcv.json.gz',
 'eth-transfer-mark-funding.json.gz':SOURCE/'mark-funding.json.gz',
}
for target,source in transfers.items():shutil.copyfile(source,DOC/'downloads'/target)
cols=['utc','classification','volume_difference_eth_5m_minus_1h','trade_count_difference_5m_minus_1h']
buf=io.StringIO();writer=csv.writer(buf);writer.writerow(cols)
trs=[];mdrows=[]
for x in v['decimal_conflicts']:
 date=x['time'].replace('T',' ').replace(':00:00Z',' UTC')
 label='무거래 봉의 시가·저가' if x['empty_bar_price_explains'] else '거래량·체결수 미해결'
 vd=x['base_volume_difference'];td=x['trade_count_difference']
 writer.writerow([x['time'],label,vd,td])
 trs.append(f'<tr><th scope="row">{date}</th><td>{label}</td><td>{float(vd):+,.3f}</td><td>{td:+,}</td></tr>')
 mdrows.append(f'| {date} | {label} | {vd} | {td} |')
(DOC/'downloads/eth-transfer-conflicts.csv').write_text(buf.getvalue())
small_links=[('eth-transfer-data-audit.json','309개 원본·체크섬·감사 JSON'),('eth-transfer-verification.json','독립 검산·1분봉 차이 JSON'),('eth-transfer-reproduction.json','소켓 차단 재현 JSON'),('eth-transfer-conflicts.csv','6시간 상충 목록 CSV')]
large_links=[('eth-transfer-5m.json.gz','ETH 5분봉'),('eth-transfer-hourly.json.gz','ETH 시간봉·거래량'),('eth-transfer-mark-funding.json.gz','마크가격·펀딩')]
links=''.join(f'<a href="downloads/{name}" download>{label} ↓</a>' for name,label in small_links)
large=''.join(f'<a href="downloads/{name}" download>{label} · {(DOC/"downloads"/name).stat().st_size/1024**2:.1f} MiB ↓</a>' for name,label in large_links)
page=f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="BTC 구조 5후보를 바꾸지 않은 ETH 전이 연구. 성과 전 사전명세와 공식 309개 원본의 자료 감사.">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>ETH로 옮기기 전에 · BTC Research</title><link rel="icon" href="assets/icon.svg" type="image/svg+xml"><link rel="stylesheet" href="assets/eth-transfer.css?v=1002e1"></head>
<body><a class="skip" href="#findings">자료 결과로 건너뛰기</a><header><a class="brand" href="./">BTC <b>RESEARCH</b></a><nav aria-label="연구 탐색"><a href="structure-lab.html">BTC 5후보 결과</a><a href="#downloads">검증 자료 ↓</a></nav></header>
<main><section class="hero"><p class="eyebrow">CONTINUING RESEARCH 006 <span>2026.10.02</span></p><h1>ETH로 옮기기 <em>전에.</em></h1><p class="lead">전략은 그대로.<br>새 시장의 자료부터 검증했습니다.</p><div class="stage" id="stage">자료 감사 완료 · ETH 전략 성과 미계산</div>
<p class="boundary">기존 BTC 5개 구조 규칙과 통과 기준을 바꾸지 않았습니다. 이번 결과는 <strong>자료의 검증 상태</strong>이며 수익률이나 전략 통과를 뜻하지 않습니다.</p></section>
<div class="notice" id="latest-results"><h3>후속 계좌 검증 완료 · 2026.10.02</h3><p>이 페이지는 성과 계산 전 자료감사 기록입니다. <a href="eth-results.html">80개 ETH 계좌의 전체 성과·탈락·상충 노출 검산 결과 보기 ↗</a></p></div>
<section class="cards" aria-label="자료 감사 핵심 수치"><article><p>공식 ZIP · 체크섬 대조</p><strong data-metric="archives">{v['counts']['verified_archives']:,}</strong><small>기존 240 + 신규 월별59 · 일별10</small></article><article><p>5분봉 · 2021.10–2026.08</p><strong data-metric="bars">{n['rows_5m']:,}</strong><small>시각 공백0 · 보간0 · 무거래36</small></article><article><p>1시간봉과 집계 대조</p><strong data-metric="hours">{n['hours_compared']:,}</strong><small>시각 공백0 ≠ 모든 거래 기록 완전</small></article><article><p>상충 시간 · 전부 보존</p><strong data-metric="conflicts">{n['remaining_conflict_hours']}</strong><small>무거래 가격차1 + 거래량 미해결5</small></article></section>
<section id="findings"><p class="eyebrow">WHAT THE SOURCES SAY</p><h2>체크섬이 맞아도,<br>자료끼리 다를 수 있습니다.</h2><p>5분봉을 시간봉으로 합친 값과 기존 공식 시간봉을 전수 대조했습니다. 차이가 생긴 5일은 일별 1분·5분 원본까지 확인했고, 사전 복구 조건을 만족하지 않아 <strong>원본을 바꾼 시간은 0개</strong>입니다.</p>
<div class="notice"><h3>2024.10.28 21시 UTC · 무거래 봉의 영향</h3><p>첫 두 5분봉은 거래량0인데 이전 가격 2,503.77을 시가·저가로 갖고 있었습니다. 거래가 있는 봉만 진단 목적으로 집계하면 시간봉의 시가 2,518.92·저가 2,516.54와 같아집니다. 원본은 유지하고, 무거래 봉에서는 체결을 만들지 않습니다.</p></div>
<p class="table-note">수량 차이는 <b>5분 합계 − 시간봉</b>입니다. 모바일에서는 표를 좌우로 움직일 수 있습니다.</p>
<div class="table-scroll" tabindex="0" role="region" aria-label="상충 시간 상세 표"><table id="conflict-table"><caption>1시간 집계 차이 · UTC</caption><thead><tr><th>시간</th><th>분류</th><th>거래량 차이 · ETH</th><th>체결수 차이</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div>
<p>나머지 5시간은 거래량·체결수 차이가 남습니다. 추가로 일별 1분→5분 합계 1,440개 중 <strong id="minute-conflicts">3개</strong>도 공식 5분봉과 달랐습니다. 여러 시간단위 자료가 항상 일치한다는 가정은 사용할 수 없습니다. 후속 성과 계산에서는 상충 구간의 <strong>신호·보유·체결 노출</strong>을 따로 검사합니다.</p></section>
<section><p class="eyebrow">RULES BEFORE RETURNS</p><h2>5개 규칙, 같은 문턱.</h2><div class="two"><article class="panel"><h3>그대로 유지</h3><ul><li>A 유지 / R 재시험 / F 실패 복귀 / P 눌림 / C 55봉 채널</li><li>2022–25 주 구간, 2026.01–08 최근 구간</li><li>가상 1,000 USDT · 기본 위험 .5% · 진입 명목≤100%</li><li>편도 수수료5bp + 충격1.5bp · 실제 과거 펀딩</li><li>5분 지연 · 손절 우선 · 무거래 체결금지</li></ul></article><article class="panel"><h3>시장별 주문 단위는 분리</h3><p>공식 공개 조회에서 ETH의 수량 단위는 <b>.001 ETH</b>, 최소금액은 <b id="min-notional">20 USDT</b>였습니다. BTC의 최소금액50을 그대로 복사하지 않았습니다.</p><p><b>70개</b> 기본·비용·지연·위험 조건 계좌와 최소금액만50으로 맞춘 진단 <b>10개</b>를 사전 등록했습니다. 모두 아직 미계산입니다. 현재 주문 규정의 역사고정 가정이며, 과거 규정이나 실제 주문 수용성을 복원한 것은 아닙니다.</p></article></div>
<details id="gates"><summary>통과 기준·불확실성과 미복원 위험 보기</summary><div class="detail"><p>주 구간 기본 후보: CAGR≥10%, 일별 Sharpe≥.8, 5분 종가 DD≤25%, 양수연도≥3/4, 비용2배 순익&gt;0, 최고분기 제외 복리&gt;0, 담보진단 위반0, 최소100왕복을 모두 요구합니다. 민감도가 좋아도 기본 후보를 대신 선정하지 않습니다.</p><p>14일 원형블록 2,000회, 7/28일 민감도, 5후보 보정 구간을 공개할 예정입니다. ETH 과거도 이전 연구에서 보았으므로 <strong>새 미사용 OOS가 아닙니다.</strong> 거래소 정확 청산·호가·부분체결·가격필터 수용성·봉내 순서·세금/운영비는 미복원입니다. 기준 통과도 실전 수익 보장은 아닙니다.</p></div></details></section>
<section id="proof"><p class="eyebrow">INDEPENDENT CHECKS</p><h2>수치보다 먼저, 재현 가능한 근거.</h2><div class="two"><article class="panel"><h3>원본 전수 대조</h3><p>수집기와 별도의 Decimal 검산기로 309개 원본을 다시 읽었습니다. 517,248개 5분봉, 57,696개 시간봉과 마크가격, 7,212개 펀딩을 정규화 자료와 대조했습니다.</p><p>기존 mark 자료의 72시간 일별 보완도 재검증했습니다. 펀딩 원시시각의 경계 차이는 최대47ms이며 원시값을 보존합니다.</p></article><article class="panel"><h3>네트워크 없이 다시 생성</h3><p>소켓 접근을 차단한 뒤 원본에서 전체 <b id="replay-files">5개 산출물</b>을 다시 만들었고, 모두 바이트까지 같았습니다. 단위·누락·중복·무거래·복구 조건 등 감사 경계 <b id="tests-count">8개 검사</b>도 통과했습니다.</p><p>이 검산은 <strong>자료 파이프라인</strong>에 대한 것입니다. ETH 계좌 회계·성과 검증은 다음 단계입니다.</p></article></div></section>
<section id="downloads"><p class="eyebrow">OPEN EVIDENCE</p><h2>직접 확인할 수 있도록.</h2><div class="downloads">{links}</div><details id="raw-downloads"><summary>정규화 시세 자료 다운로드 · 약27 MiB</summary><div class="downloads detail">{large}</div></details><div class="downloads sources"><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/EXPERIMENT_ETH_TRANSFER_20261002.md">성과 전 고정 명세 ↗</a><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/ETH_TRANSFER_DATA_AUDIT.md">전체 자료 감사 보고서 ↗</a><a href="evidence/eth-transfer-exchange-info-20261002.json">공식 ETH 주문 조건 조회 근거 ↗</a><a href="https://github.com/binance/binance-public-data">Binance 공식 자료 설명 ↗</a></div><p class="fine">ZIP별 공식 출처와 SHA256은 감사 JSON에 포함돼 있습니다. 체크섬은 내려받은 파일의 무결성을 확인할 뿐, 경제적 기록의 완전성을 보장하지 않습니다.</p></section>
<section class="next"><p class="eyebrow">NEXT CHECKPOINT</p><h2>자료 동결 → ETH 실행 어댑터 → 계좌 검산</h2><p>다음 회차는 이 자료와 사전명세에서 이어갑니다. 신호·비용·기간을 성과에 맞춰 조정하지 않고, 실패 후보와 진단도 모두 남깁니다. BTC 기존 결과는 그대로 보존했습니다.</p><a href="structure-lab.html#next">이전 BTC 결과로 돌아가기 ↗</a></section></main>
<footer><b>BTC RESEARCH</b><p>BUILD 1002e1 · 정적 자료 감사 스냅샷 · 2026-10-02 UTC<br>ETH 성과 미계산 · 실전채택 없음 · 상시 모의매매·실거래 미시작</p></footer></body></html>
'''
(DOC/'eth-transfer.html').write_text(page)
md=f'''# ETH 전이 · 공식 원자료 감사 (2026-10-02 UTC)

> 후속 80계좌 성과·검산 완료: [ETH 전이 결과](eth-results.html). 아래는 성과 계산 전 감사 시점의 기록입니다.

**성과 계산 전 자료 관문 완료. ETH 전략 성과는 미계산이며, 실전채택·전진가동·실거래 없음.**

- 사전명세: `eaacfbd`, [고정 명세](EXPERIMENT_ETH_TRANSFER_20261002.md). 5고정후보×7조건×2기간70계좌 + 최소금액50 USDT 진단10계좌는 예정이며 미계산.
- 기존 BTC 규칙/자료/계좌 성과는 재실행·변경하지 않았다. 이번 Python 도구는 연구 전용 `tools/`에 분리했고 stdlib만 사용한다. 비밀·실계좌·주문·서명·입출금·유료자료·하위에이전트는 사용하지 않았다.
- 공개 HTML: [ETH로 옮기기 전에](eth-transfer.html). 새 미사용 OOS 또는 Hyperliquid 성과가 아니다.

## 자료와 검사 범위

| 항목 | 확인 수치 |
|---|---:|
| 체크섬 검증 ZIP | 309 (기존240 + 신규5분59 + 추가일별10) |
| 5분봉 / 시간 대조 | 517,248 / 43,104 |
| 기존 ETH 거래량 복원 시간봉 / 마크봉 | 각각57,696 |
| 원본 펀딩 | 7,212, 원시 버킷 차이3,253개·최대47ms |
| 기존 마크 일별 보완 재검증 | 72시간 |
| 시각 공백 / 보간 / 가격 복구 | 0 / 0 / 0 |
| 무거래 5분봉 | 36 (체결금지) |
| 시간봉 집계 상충 | 6 (가격차 설명1 + 거래량/체결수 미해결5) |
| 추가일별 1분→5분 비교 | 1,440개 중3개 상충 |
| 독립검산 / 네트워크차단 | Decimal 원본 전수 / 전체5파일 바이트일치 |
| 감사 경계 테스트 | 8개 통과 |

5분 자료 범위 `[2021-10-01,2026-09-01)` UTC. 기존 시간봉/마크/펀딩은 `[2020-02-01,2026-09-01)`, 준비 자료 포함. 모든 펀딩 시간에 mark 기준값이 존재한다. mark 시가는 실제 펀딩 오라클의 근사일 뿐이다.

## 남겨 둔 상충 · 5분 합계−기존 시간봉

| UTC | 분류 | 거래량 차이 ETH | 체결수 차이 |
|---|---|---:|---:|
{chr(10).join(mdrows)}

2024-10-28 21UTC 첫 두 5분봉은 거래량0, 시가·저가2503.77. 거래가 있는 봉만 **진단상** 집계하면 시가2518.92·저가2516.54로 기존 시간봉과 일치한다. 원본 가격은 고치지 않았다. 나머지 5시간의 차이는 미해결이며 일별원본끼리도 불일치가 있어 어느 시간단위를 완전한 참값이라고 확정하지 않는다.

추가 일별1분→5분 불일치: 2023-11-14 11:40UTC (시가·고가·거래량·체결수), 2024-10-28 21:10UTC (시가·저가; 거래 재개 구간), 2025-01-29 01:35UTC (시가·고가·저가·거래량·체결수). 상세 수치와 모든 출처는 [독립검산](downloads/eth-transfer-verification.json), [자료감사](downloads/eth-transfer-data-audit.json)에 있다.

규칙상 일별1분·5분의 가격/체결수 모두 기존시간봉을 지지하는 가격상충만 복구할 수 있는데 해당 사례가 없어 복구0. 시각 공백0과 checksum 일치를 경제적 완전성으로 표현하지 않는다. 이후 실행에서 신호·보유·체결의 상충시간 노출을 검산해야 한다.

## 주문 단위와 비용의 경계

[인증 없는 공식 exchangeInfo](evidence/eth-transfer-exchange-info-20261002.json)에서 ETH .001 수량단위/최소량, minNotional20, marketMax2000, tick .01 확인. 이를 과거 전체에 고정하며 역사 주문 규정은 복원하지 않는다. 편도 taker5bp+충격1.5bp는 BTC와 동일한 고정 가정. 이론적 손절/체결가의 tick 반올림 및 거래소 조건부주문 수용성은 미복원. BTC min50과 ETH min20을 구분하고 최소금액50 진단10개를 미리 고정했다.

## 독립 검산과 재현

`tools/verify_eth_transfer_data.py`는 수집기를 가져오지 않고 raw CSV를 Decimal로 읽어 모든 정규화 행과 43,104개 시간 집계를 검산한다. 공식 ZIP309개와 CHECKSUM 바이트를 다시 해시검증했다. 1분 보완까지8,640행 추가검사. [소켓차단 재현](downloads/eth-transfer-reproduction.json)은 다른 출력 경로에 전체5파일을 다시 생성해 바이트일치를 확인했다. 첫 재현 실행기의 socket 차단이 stdlib SSL 초기화보다 빨라 자료읽기 전에 실패했으며, SSL import 후 차단하도록 실행기만 고쳐 통과했다. 자료/분석 코드/규칙 수정은 없었다.

- 데이터 SHA256 (전체 감사 JSON): `{hashlib.sha256((SOURCE/'audit.json').read_bytes()).hexdigest()}`
- 정규화5분 비압축 SHA256: `{a['artifacts']['bars-repaired.json.gz']['uncompressed_sha256']}`
- 독립검산 SHA256: `{hashlib.sha256((RUN/'independent-verification.json').read_bytes()).hexdigest()}`
- 재실행: `python3 tools/collect_eth_transfer.py --offline --output runs/eth-transfer-20261002/recheck` → `python3 tools/verify_eth_transfer_data.py`. 명령은 현 서버에 보존한 기존 `data/search-1458`, `data/archive-1458/ETHUSDT`, 신규 `data/eth-transfer-20261002` 원본 캐시가 준비된 상태에서 실행한다. 새 복제본은 감사 JSON의 공식 URL/CHECKSUM으로 원본을 먼저 준비해야 한다. 네트워크 비활성화 증거는 별도 실행기의 실제 socket 차단을 포함한다.

## 다음 체크포인트

고정 자료/명세를 유지하여 ETH 전용 수량 어댑터와 원장·독립 신호검산을 구현/커밋한 뒤 70+10계좌를 계산한다. `.001/50` BTC 하드코딩·BTC 자료 로더를 무심코 재사용하지 않는다. 미래자료 교란·지연/무거래·가격틱 한계·최소수량·수수료/펀딩·상충시간의 신호 의존성 및 포지션 노출을 검증한다. 실패/거절을 포함한 전부를 보존하고 기준통과 후에도 자동 실전채택하지 않는다. 합성 포트폴리오는 별도 명세 전 미실행.
'''
(DOC/'ETH_TRANSFER_DATA_AUDIT.md').write_text(md)
print(json.dumps({'html_bytes':len(page.encode()),'downloads':len(transfers)+1,'performance_computed':False}))
