# OI 공개자료·시각·입력 감사 · 2026-10-02

**OI 전략 성과 미계산. 이 자료는 새 OOS가 아니며 과거 실시간 가용성을 복원하지 않았다.**

[공개 결과 페이지](eth-results.html#next). ETH80계좌 계산/검산에 이어 같은회차에서 실제OI자료 조사도 진행했다. 기존BTC전체백테스트/ETH309자료감사 재실행 없음.

## 평가기간 전체 내부 감사

[2022-01-01,2026-09-01) BTC·ETH 각각1704일, 총3408개 공식ZIP과CHECKSUM 대조. 목록이 끝날 때까지9페이지·7972객체를 열거했고 평가일 파일누락0. 고정22표본에서 결측이 나와 전기간 내부 감사로 확장한 범위를 먼저 커밋했다. 전체원본검사145.791초.

| 항목 | BTC | ETH |
|---|---:|---:|
| verified_days | 1704 | 1704 |
| rows | 490619 | 490619 |
| missing_rows | 133 | 133 |
| days_with_gaps | 4 | 4 |
| unordered_days | 107 | 111 |
| duplicates | 0 | 0 |

총981238관측/누락266. 시각범위밖/중복/잘못된symbol/음수0. raw의순서는고치지않고 별도입력만정렬한다. 독립검산기는수집기를import하지않고 모든ZIP/해시/정규화행을Decimal로재검산했다.

| 컬럼별 결측 | BTC | ETH |
|---|---:|---:|
| count_long_short_ratio | 5387 | 5389 |
| count_toptrader_long_short_ratio | 91815 | 91819 |
| sum_taker_long_short_vol_ratio | 36850 | 36847 |
| sum_toptrader_long_short_ratio | 91781 | 91781 |

OI수량0: BTC463/ETH208; OI금액0: BTC475/ETH218. 실제무포지션이라고확정하지않고 둘중하나가0이면별도마스크(BTC475/ETH218). 비율NaN/빈값은null,0으로대체금지. 원본0도삭제하지않는다. 모든누락시각과행별원자료해시는다운로드에보존.

## 시각 대조에서 발견한 선행정보 위험

- 공식개발자문서페이지는리디렉션후HTTP202/빈본문. 성공열람이라고인용하지않았다. 공식구커넥터는deprecated임을확인했고30일조회제한설명은과거문서근거로만사용. 실제인증없는API응답도4회200/각288행확인.
- 2026-09-30 같은시각 OI API/CSV는288개전부불일치. 이초기대조실패를보존했다. ±60분범위검사에서는 archive time=API time−5분일때두종목각287겹치는수량전부일치.
- 시각가설을 `dea3fc3`으로고정후 2026-09-10·09-20,두종목4표본에서 **기록시각+5분 API수량·금액 1152/1152 정확일치**. 날짜를고른뒤다른shift로수정하지않았다. 수익검증이나새OOS가아니다.
- 따라서OI관측완료는기록시각+5분으로보수적으로정의. 그러나확인한9월밖역사전체의의미·최초공표시각·개정시점은입증되지않았다. 전체기간에적용하는가정과추가지연민감도를성과전명세에밝혀야한다.
- taker API는요청범위보다5분앞선첫timestamp를반환했고,+5분이동하면CSV비율이맞지않았다. 같은timestamp비율도4자리반올림만으로설명되지않는작은차이(max BTC.000782/ETH.001913)가남는다. 같은opening timestamp의5m Kline buy/sell도287행전부일치하지않았다. 이컬럼에OI보정을일괄적용하지않고성과신호로채택하지않는다. 기존감사1h taker/funding재사용.
- 공식공개자료README는일자료다음날게시와후속개정을명시한다. S3 LastModified를최초가용시각으로오인하지않는다. 웹API와아카이브의동일경제적가용성·빈티지미복원.

## 후속 입력 구현·재현

`c570288` 입력처리사전커밋. `tools/prepare_oi_inputs.py`: 원시시각·0·null보존,시간순정렬,OI양수조건마스크,별도 observation_complete_assumed_ms=source+300000. available_at이라고표시하지않음. 보간/앞채움0. 5개결측/중복/형식/시각/마스크경계검사통과. 원본독립검산에더해981238변환행을별도재검산하고네트워크소켓차단으로두gzip+manifest의3파일바이트일치.

## 다음 정확한 체크포인트

자료를재수집하지말것. 기존ETH성과80/소켓차단87파일은완료. OI원자료3408/입력2시장도완료. 다음은고정입력해시와+5분관측완료가정을그대로두고,추가관측지연·24h/기타룩백·누락전후처리·기본가격대조군·후보수를성과전에명세/커밋한다. 실제새정보가있는지를검증하고여전히이미본기간/탐색임을표시한다. 성과없이신호를승격하지않기. 미정의지연/필드의미가남으면그대로보류하며운영/실거래에연결하지않는다.

## 공식 출처

- https://github.com/binance/binance-public-data (README 다음날게시/개정가능/공식체크섬)
- https://data.binance.vision/?prefix=data/futures/um/daily/metrics/ (원본URL·체크섬은감사JSON)
- https://github.com/binance/binance-futures-connector-python (deprecated; 현재API단정근거로사용금지)
- 인증없는 https://fapi.binance.com/futures/data/openInterestHist 및 takerlongshortRatio 의원시응답·URL/시각/해시를감사증거로보존.
