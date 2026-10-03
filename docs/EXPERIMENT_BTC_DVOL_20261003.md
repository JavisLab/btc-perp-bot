# BTC 옵션 내재위험의 전진 위험배분 · 성과 전 명세

## 질문·독립성·원문 범위
기본 **VI_INFO**: 옵션가격은 앞으로의 변동 위험/보험·투기 수요를 반영하므로, 과거 BTC 실현분산과 함께 사용한 DVOL이 앞으로30일 실현분산을 더 잘 예측하고, 동일 BTC 추세방향의 현물 위험배분을 개선하는가? 방향예측·옵션매도·위험프리미엄수취 가설이 아니다. 가격만 위험예측보다 나은 정보가 있는지를 따로 기각한다. 기존 실패의 창/레버리지를 조절하는 것이 아니라 **새 공개 옵션정보로 위험예측**을 검증한다. 과거경로를 이미 본 탐색이며 미사용OOS가 아니다. 기존198+외부954조건계좌는 보존한다. 새DVOL 전체수집/학습/계좌성과 아직 없음.

Q77 Almeida외 `Risk Premia in the Bitcoin Market` arxiv2410.15195v2(2025-08-01)는 기존 S10과 **동일 원문 재검토**, 독립새논문이 아니다. 전체표본 Ward RND군집·물리수익분포, 두군집 BP/BVRP 평균 음관계는 실시간 방향회귀가 아니다. RV는 **과거27일**; 미래RV사용이라고 오독하지 않는다. 본문1992일/5,384,537거래 vs 표1301일/7,832,590 및 call+put7,408,561의집계불일치를 기록한다. 전문52p중초록/서론앞·자료8–9·모형10–17·결과21–22·BVIX부록39열람, 모든증명재현주장없음.
Q79 Alexander/Imeraj `The Bitcoin VIX & its variance risk premium` DOI10.3905/jai.2020.1.112: Sussex figshare23306975 **초록만, 파일없음**. 2019Mar–2020Mar700만옵션가격·15분BVIX·여러RV격자; DVOL과동일지수/순익검증아님. Practical Applications동일family. Q80 Foley외2022 DOI10.1016/j.econlet.2021.110196: RePEc초록만, ElsevierXML메타만·SSRN403우회없음. 초록의연80%는 옵션에서추정한기대초과수익이지 실제비용후계좌수익이아니다. 방법전문은미확보.
Q78 Deribit공식DVOL설명은30일연율변동성·fear뿐아니라upsidegreed도반영한다고명시. 2만기분산보간/5%델타컷/2BTC5호가깊이·1분거래/과거markfallback/EMA240초. 미래물리변동성과다른위험중립보험가격을그대로정답으로삼지않고 과거완료훈련자료에서단순보정한다. BVIX복제나원논문전략복제가아닌자체축소모형. 다른자산/ETH/실옵션/선물거래 없음.

## 자료·시계·가용성
- 공개 Deribit `public/get_volatility_index_data`, currency=BTC,resolution=1D만주자료. 2021-04-01~2026-08-31완료일봉,180달력일이하요청·1초이상간격·원응답/URL/수신시각/SHA/continuation보존. `continuation`은다음end_timestamp; 중복동일성/요청범위/유한양수/OHLC관계/UTC00격자/중복·결측검사. 문서의vix_resolution서술과달리실제요청명은resolution. 제한숫자문서미표시이므로부분응답/연속토큰검사,추측완결금지.
- 공식설명최초datePublished2021-03-31T03:33:44UTC, API첫2021-03-24는발표전backfill가능. **Apr1이전입력전부제외**. 현시점역사응답이지처음공표빈티지아님. 화면Lastupdated2023Mar vs metadata2024Oct수정,모든역사방법변경/첫수신시각미복원. 지연조건이과거수정문제를없애지는않음.
- timestamp D는하루시작. 기본 일간결정T=00UTC에서 **D=T−2일**의close사용: 봉종료A=D+1일=T−1일에추가1일버퍼. `data_delay7`은D를추가7일이전으로이동; 현재/모든과거훈련DVOL피처동일지연. 일봉30일위험예상은이미1일(조건8일)지난것, 예측T~T+30과정확한동일만기라고안함.
- 미리정한시계probe2021Apr1/2022Jan1/2024Feb29/2026Aug30:24완료시간OHLC집계와native일봉대조. 기존Aug30probe재사용·inclusive다음날행제외. 가격/지수원천불일치숨기지않음. 누락·유효양수아님이면그T피처결측,보간/전방채움/최신다른빈티지로교체없음.
- 기존BTC spot/perp/mark/funding자료SHA(해제JSON)9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4. B_t는t직전시간 close_time=t−1완료종가,비양수거래량마스크3시간SHA bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd. RV의31개종가중하나라도누락/무거래이면결측.

## 변동성 예측 고정
T일피처 r_T=365/30 * Σ_{j=0..29} ln(B_(T−j일)/B_(T−j−1일))² (완료과거30일,평균차감없음); q_T=(DVOL_D.close/100)². 입력[ln(r),ln(q)]. DVOL의90은90%이지.90%가아님. 타겟 Y_T=365/30 * Σ_{j=1..30} ln(B_(T+j일)/B_(T+j−1일))². **미래30일은완료훈련label/사후오차만**,현재노출에는사용불가.
일간T범위2021-04-03~2026-08-31. 각T훈련U는[T−760일,T−31일] **730달력일**, 유효피처+양의Y且label끝U+30日≤T−1日. 최소365유효행, 초기에학습부족이면기존core. 중첩타겟365행은365독립월표본아님(약12개월), 최소기간을성과뒤줄이지않음.
동일유효훈련행의OLS:
- INFO lnY ~ 1+lnr+lnq, lnq계수≥0. 센터링SVD; 비제약계수음수면PRICE로재적합하고q계수0.
- PRICE lnY ~ 1+lnr, 제약없음.
각모형의분산예측 vhat=exp(현재선형예측)×mean(exp(훈련잔차)) (**훈련만 Duan smearing**). 양수/유한/rank검사,그외결측. 전체훈련날짜/label끝·피처·계수·제약활성·잔차smear·예측보존. 과적합불확실성을무시한통계유의성주장없음, 계수p값/SE필터없음. 성과전에검증과자료SHA고정.

## 다섯 규칙·60조건계좌
모든규칙 **방향은동일E_SPOT** max(0,s). s=20/60/120momentum 및EMA8/32,16/64,32/128 여섯부호평균. 기본risk=.20, risk10=.10, w0=min(1,risk/과거20일로그수익표본std×sqrt365), zero vol→0. core위험/방향준비안되면계획보류.
- **VI_INFO** w=min(1,risk/sqrt(vhat_INFO)), 모형결측이면w0.
- VI_PRICE w=min(1,risk/sqrt(vhat_PRICE)), 모형결측이면w0. 같은DVOL유효훈련행을써 표본차이통제.
- VI_RAW w=min(1,risk/sqrt(q)), q결측이면w0. 보험가격직접사용대조, 훈련준비이전도유효q면사용.
- VI_INV w=min(1,risk*sqrt(vhat_INFO)/vhat_PRICE), 두모형유효일만. PRICE기준위험크기에서INFO/PRICE위험비율을반대로적용하는 대조이며 **숏방향반전아님**. 그외w0.
- VI_TREND 항상w0,기존E_SPOT base일말/수수료/손익정확동일필수.
T마다 목표BS=max(0,s)*w,BP=0. 현물롱/현금만,차입/복수다리/레버리지증가없음. 지수자체/옵션미거래. 펀딩은원장검산하되이번계좌는BP0이라정확0이어야함.
5규칙×6조건(base,cost_x2,delay1,delay24,risk10,data_delay7)×2기간=60. 목표gross≤1. base체결T+1h, 실행지연추가1/24h는원목표고정. 자료지연은DVOL시점·모형재구성; 과거RV는여전히T까지완료값. 비용2배시예측/목표변경없음.

## 회계·선정·불확실성
주2022-01-01~2026-01-01,최근2026-01-01~2026-09-01각1000USDT. btc_target_ledger.py불변:spot10/perp5bp+불리impact1.5bp,실제funding×시간mark시가proxy(이번0),5%p밴드/postcost12회수량/spot.00001/perp.001절삭/최소5/50USDT·선물감소예외/atomic·최종dust정리. 빈시가/무거래체결없음. 시간DD/불리한시간극값담보5%·명목상한. 정확호가/부분체결/순간청산/역사규정/세금/운영비미복원.
기존문턱불변: 주수익>52.838713%,DD≤13.561952%,최근수익>4.628391%,DD≤10.450946%,vol≤13.343621/16.520409%;주Sharpe≥.8/4년중≥3양수/완료보유구간≥20/양기간marginbreach0. base/cost_x2/delay1/delay24/data_delay7 각각양기간순손익>0.
정보추가기각: base VI_INFO 순수익이VI_PRICE/VI_TREND보다양기간높고,DD가VI_PRICE보다크지않으며,**미래30일분산 MSE와QLIKE=ln(vhat)+Y/vhat가PRICE보다양기간엄격히낮아야함**. paired source/타겟끝이각평가기간안인유효동일행,초기결측누락수공개. RAW오차도같은행보고. 예측정확도향상만으로전략통과아님,낮은위험으로낙폭만줄여도통과아님. 역대다른대조를사후primary로교체하지않음.
모든계좌·연도·비용/펀딩/거래수·보유노출/무거래를보존. 순일수익 및PRICE/TREND대비7/14/28일블록2000회95%구간. 예측손실차이 INFO−PRICE의30/60/90 **달력일 블록**2000회95%구간,결측일NaN 유지하여중첩타겟을독립일처럼압축안함. 부족표본명시,같은역사반복선택의유효OOS/p값아님.
경계검사:단위/24h완료/+1일및+7일버퍼/발표전제외/미래지수·가격교란불변/30과거미래분리/365·730·31일purge/rank·음계수제약/훈련잔차smearing/위험반대대조/노출cap/부족자료fallback. 별도rawJSON Decimal시계/원BTC ZIP/정규방정식회귀/독립신호·폐형식수량/무거래·Decimal원장·시간DD·펀딩0검산. 새60계좌만소켓차단바이트재현후최소Pages게시·익명다운로드확인. 완료후다음실제인터넷BTC근거조사계속.
