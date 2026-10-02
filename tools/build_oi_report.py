"""Append verified OI data findings, without implying strategy performance."""
import gzip
import json
from pathlib import Path
import re
import shutil

ROOT=Path(__file__).resolve().parents[1];DOC=ROOT/'docs';H=ROOT/'data/oi-history-20261002';F=ROOT/'data/oi-availability-20261002';I=ROOT/'data/oi-inputs-20261002'


def section():
    return '''<section class="section" id="next"><div class="section-head"><div><p class="eyebrow">NEXT INFORMATION · AUDITED, NOT TRADED</p><h2>OI를 더하기 전에, 5분의 의미부터.</h2></div></div><div class="context"><b id="oi-counts">공식 일별 파일 3,408개 · 981,238행 독립 대조</b><p>BTC·ETH 각각 1,704일 파일이 있어도 내부에는 각각 <strong>133개 5분 시각 누락</strong>이 있었습니다. 파일 내 시간순서가 다른 날은 BTC107·ETH111일. OI수량 또는금액이0인 관측은 BTC475·ETH218개로 별도 마스크했습니다. 보간·앞채움은 하지 않았습니다.</p></div><div class="two-col space"><article class="panel"><h3>같은 시각 비교가 틀렸던 이유</h3><p>최근 하루에서 OI 아카이브의 시각보다 API 시각이 5분 뒤일 때 수량이 일치했습니다. 이 가설을 먼저 고정한 뒤 별도 두 날짜·두 종목의 <b id="oi-clock-count">1,152행 수량·금액</b>을 전부 대조했습니다. OI는 보수적으로 기록시각+5분을 관측완료로 취급합니다.</p><p>이는 확인한 날짜 밖에서는 가정이며, 실제 과거 공표시각·지연을 증명한 것이 아닙니다. 다른 비율컬럼까지 같은 보정을 적용하지 않습니다.</p></article><article class="panel"><h3>새 성과는 아직 없습니다</h3><p>일부 비율은 수만 행이 결측이고, taker API와 일별 Kline 수량에도 차이가 남습니다. 기존 검증된 시간봉의 공격적체결량·펀딩을 재사용하고 불명확한 비율로 대체하지 않습니다.</p><p>정렬·0값 마스크·원시시각 보존 입력은 <b>981,238행 별도검산</b> 및 <b id="oi-replay">3파일 소켓차단 재현</b>을 마쳤습니다. 다음은 추가 관측지연·OI 신호·가격만 대조군을 성과 전에 고정하는 단계입니다. OI 전략수익·새 OOS·실전가동은 없습니다.</p></article></div><div class="source-links"><a href="downloads/oi-data-audit.json.gz" download>전체 일별 품질·원본 해시 ↓</a><a href="downloads/oi-verification.json" download>독립 원자료 검산 ↓</a><a href="downloads/oi-clock-confirmation.json" download>고정 시각 가설 확인 ↓</a><a href="downloads/oi-input-manifest.json" download>입력 마스크·정렬 명세 ↓</a><a href="downloads/oi-input-reproduction.json" download>오프라인 입력 재현 ↓</a><a href="downloads/oi-api-clock-comparison.json" download>API·아카이브 상충 원자료 비교 ↓</a><a href="https://github.com/JavisLab/btc-perp-bot/blob/main/docs/OI_DATA_AUDIT_20261002.md">OI 자료 상세 보고서 ↗</a></div></section>'''


def main():
    a=json.loads((H/'audit.json').read_bytes());v=json.loads((H/'verification.json').read_bytes());m=json.loads((I/'manifest.json').read_bytes());p=json.loads((I/'reproduction.json').read_bytes());c=json.loads((F/'clock-confirmation/verification.json').read_bytes())
    assert a['complete'] and v['independent_decimal_rows_equal'] and c['all_four_dates_match_288_quantity_and_value'] and p['byte_equal_files']==3
    for source,name in [(H/'audit.json','oi-data-audit.json.gz'),(F/'feasibility.json','oi-feasibility.json.gz')]:
        (DOC/'downloads'/name).write_bytes(gzip.compress(source.read_bytes(),mtime=0))
    for src,name in [(H/'verification.json','oi-verification.json'),(F/'clock-confirmation/verification.json','oi-clock-confirmation.json'),(F/'api-clock-comparison.json','oi-api-clock-comparison.json'),(F/'oi-lag-diagnostic.json','oi-lag-diagnostic.json'),(I/'manifest.json','oi-input-manifest.json'),(I/'reproduction.json','oi-input-reproduction.json')]:
        shutil.copyfile(src,DOC/'downloads'/name)
    path=DOC/'eth-results.html';page=path.read_text();page,n=re.subn(r'<section class="section" id="next">.*?</section>',lambda _:section(),page,flags=re.S);assert n==1;path.write_text(page)
    fields=['verified_days','rows','missing_rows','days_with_gaps','unordered_days','duplicates']
    lines=['# OI 공개자료·시각·입력 감사 · 2026-10-02','', '**OI 전략 성과 미계산. 이 자료는 새 OOS가 아니며 과거 실시간 가용성을 복원하지 않았다.**','',
        '[공개 결과 페이지](eth-results.html#next). ETH80계좌 계산/검산에 이어 같은회차에서 실제OI자료 조사도 진행했다. 기존BTC전체백테스트/ETH309자료감사 재실행 없음.','',
        '## 평가기간 전체 내부 감사','','[2022-01-01,2026-09-01) BTC·ETH 각각1704일, 총3408개 공식ZIP과CHECKSUM 대조. 목록이 끝날 때까지9페이지·7972객체를 열거했고 평가일 파일누락0. 고정22표본에서 결측이 나와 전기간 내부 감사로 확장한 범위를 먼저 커밋했다. 전체원본검사145.791초.','',
        '| 항목 | BTC | ETH |','|---|---:|---:|']
    for field in fields:lines.append(f'| {field} | {a["summary"]["BTCUSDT"][field]} | {a["summary"]["ETHUSDT"][field]} |')
    lines+=['','총981238관측/누락266. 시각범위밖/중복/잘못된symbol/음수0. raw의순서는고치지않고 별도입력만정렬한다. 독립검산기는수집기를import하지않고 모든ZIP/해시/정규화행을Decimal로재검산했다.','',
        '| 컬럼별 결측 | BTC | ETH |','|---|---:|---:|']
    for field in sorted(set(a['summary']['BTCUSDT']['null_counts'])|set(a['summary']['ETHUSDT']['null_counts'])):
        lines.append(f'| {field} | {a["summary"]["BTCUSDT"]["null_counts"].get(field,0)} | {a["summary"]["ETHUSDT"]["null_counts"].get(field,0)} |')
    lines+=['','OI수량0: BTC463/ETH208; OI금액0: BTC475/ETH218. 실제무포지션이라고확정하지않고 둘중하나가0이면별도마스크(BTC475/ETH218). 비율NaN/빈값은null,0으로대체금지. 원본0도삭제하지않는다. 모든누락시각과행별원자료해시는다운로드에보존.','',
        '## 시각 대조에서 발견한 선행정보 위험','',
        '- 공식개발자문서페이지는리디렉션후HTTP202/빈본문. 성공열람이라고인용하지않았다. 공식구커넥터는deprecated임을확인했고30일조회제한설명은과거문서근거로만사용. 실제인증없는API응답도4회200/각288행확인.',
        '- 2026-09-30 같은시각 OI API/CSV는288개전부불일치. 이초기대조실패를보존했다. ±60분범위검사에서는 archive time=API time−5분일때두종목각287겹치는수량전부일치.',
        '- 시각가설을 `dea3fc3`으로고정후 2026-09-10·09-20,두종목4표본에서 **기록시각+5분 API수량·금액 1152/1152 정확일치**. 날짜를고른뒤다른shift로수정하지않았다. 수익검증이나새OOS가아니다.',
        '- 따라서OI관측완료는기록시각+5분으로보수적으로정의. 그러나확인한9월밖역사전체의의미·최초공표시각·개정시점은입증되지않았다. 전체기간에적용하는가정과추가지연민감도를성과전명세에밝혀야한다.',
        '- taker API는요청범위보다5분앞선첫timestamp를반환했고,+5분이동하면CSV비율이맞지않았다. 같은timestamp비율도4자리반올림만으로설명되지않는작은차이(max BTC.000782/ETH.001913)가남는다. 같은opening timestamp의5m Kline buy/sell도287행전부일치하지않았다. 이컬럼에OI보정을일괄적용하지않고성과신호로채택하지않는다. 기존감사1h taker/funding재사용.',
        '- 공식공개자료README는일자료다음날게시와후속개정을명시한다. S3 LastModified를최초가용시각으로오인하지않는다. 웹API와아카이브의동일경제적가용성·빈티지미복원.','',
        '## 후속 입력 구현·재현','',
        '`c570288` 입력처리사전커밋. `tools/prepare_oi_inputs.py`: 원시시각·0·null보존,시간순정렬,OI양수조건마스크,별도 observation_complete_assumed_ms=source+300000. available_at이라고표시하지않음. 보간/앞채움0. 5개결측/중복/형식/시각/마스크경계검사통과. 원본독립검산에더해981238변환행을별도재검산하고네트워크소켓차단으로두gzip+manifest의3파일바이트일치.','',
        '## 다음 정확한 체크포인트','',
        '자료를재수집하지말것. 기존ETH성과80/소켓차단87파일은완료. OI원자료3408/입력2시장도완료. 다음은고정입력해시와+5분관측완료가정을그대로두고,추가관측지연·24h/기타룩백·누락전후처리·기본가격대조군·후보수를성과전에명세/커밋한다. 실제새정보가있는지를검증하고여전히이미본기간/탐색임을표시한다. 성과없이신호를승격하지않기. 미정의지연/필드의미가남으면그대로보류하며운영/실거래에연결하지않는다.','',
        '## 공식 출처','',
        '- https://github.com/binance/binance-public-data (README 다음날게시/개정가능/공식체크섬)',
        '- https://data.binance.vision/?prefix=data/futures/um/daily/metrics/ (원본URL·체크섬은감사JSON)',
        '- https://github.com/binance/binance-futures-connector-python (deprecated; 현재API단정근거로사용금지)',
        '- 인증없는 https://fapi.binance.com/futures/data/openInterestHist 및 takerlongshortRatio 의원시응답·URL/시각/해시를감사증거로보존.','']
    (DOC/'OI_DATA_AUDIT_20261002.md').write_text('\n'.join(lines))
    print(json.dumps({'daily_archives':3408,'rows':v['rows'],'input_replay_files':p['byte_equal_files'],'clock_confirmation_rows':1152}))


if __name__=='__main__':main()
