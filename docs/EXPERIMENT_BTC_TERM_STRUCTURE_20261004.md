# BTC 만기간 forward carry의 추가 방향정보 · TS72 성과 전 고정

## 경제 질문과 증거 한계

BTC의 먼 만기 선물이 가까운 만기보다 비싼 정도는, 이미 알려진 무기한 funding·가격 추세·만기 달력을 통제한 후 다음 7일 BTC 수익에 음의 정보를 주는가? Q29 Crypto Carry의 차익거래 제약/레버리지 수요 기전에서 유도한 **자체 조건부 가설**이다. 원 Skew 유료 1/3개월 현물대비 carry 복제가 아니다. Q191–196 검색의 Grover 논문 초록은 같은 기간 futures/spot 수익 대응과 excess carry 회계관계이며 미래 순익 근거가 아니다. 기존 RC_BLEND의 잔여현금 matched spot/perp carry, CP_INT의 perp premium×8h flow, EX의 만기달력, funding threshold의 창/부호 변경과 다르다. 새 정보는 실제 BTC dated quotes의 동일통화 만기간 비율이다.

BTCUSD COIN-M 만기선물은 **정보만** 사용한다. 거래는 기존 BTCUSDT USDT무기한 양방향뿐이며 코인담보·만기선물·현물 매매 없음. USD만기 두 가격의 비율을 쓰며 BTCUSD/BTCUSDT 현물 basis로 통화 단위를 섞지 않는다. 이는 만기간 시장 분할/담보위험도 포함하는 관측치이며 실제 투자자 수요나 실현 무위험 carry가 아니다. BTC-only 공개 집계/오프라인, 개별거래·개인주소·키·유료·실주문·서비스·다른종목·하위에이전트 없음. 모든 평가기간은 반복개발 역사이며 미사용 OOS가 아니다.

## 원자료·계약 선택·시계

공식 data.binance.vision public S3 prefix BTCUSD_ 목록 Q197(26 dated 계약,200925..261225; PERP 제외)을 고정한다. 현재 목록의 과거 완전성/상장 당시 PIT vintage는 입증되지 않았으며 survival/revision 제한을 표시한다. BTC CM 1h monthly kline ZIP+CHECKSUM만 수집,2020Jan..2026Aug 및 각 계약의 명목 만기월 이하. 2026Sep 이후 가격 수집/평가 없음. 각 목록·요청실패·SHA·모든 유효/무효행을 보존. Q203의 이미 받은 2020Sep/2026Aug ZIP는 재사용. 만기 후2020Oct 전부 거래량0인 표본은 품질 증거로만 보존하고 새 input에서는 제외.

CM 열은 open_time,OHLC,계약수,close_time,**BTC base volume**,거래건수,taker계약수,takerBTC,ignore. 헤더의 quote_volume 명칭을 USD 금액으로 오인하지 않는다. timestamps ms/정시/close_time=t+1h−1, 유한 양수 OHLC/low≤open,close≤high, 계약수와BTC거래량>0, 정수 거래건수>0,0≤taker≤전체를 요구한다. 수집은 무효행도 저장하고 전략 사용 여부만 분리한다.

공식 새 exchangeInfo 문서는202/본문0으로 정확 intraday delivery time 미확보다. **계약명 YYMMDD를 UTC00 명목만기일 proxy로 사용**, 실제8UTC정산 시각이라고 주장하지 않는다. 월요일00 판단에서는 모든 고정 계약 만기가 금요일인 것을 검증한다. 같은 계약 쌍의 날짜 차를 분모로 하므로 공통 미확인 intraday 정산오프셋은 차분에서 소거되나, 가까운 만기까지의 τ는 날짜 proxy다. 거래/보유 만기계약이 없어 결제가격 적용 없음.

월요일 T00UTC 판단. curve cutoff C=T 기본; data_delay7은 C=T−7일. 각 계약에 대해 C 이전 실제 양수거래 valid hour를 처음 관측했고 명목만기 E>C인 계약을 만기 오름차순 정렬, **가장 가까운 2개를 먼저 선택**. 그 둘의 C−1h 봉이 없거나 무효이면 전체 곡선행 무효; 더 먼 계약으로 대신하지 않는다. 선택은 현재 quote의 크기/성과에 의존하지 않는다. 같은 날짜 복수계약·행 중복은 hard failure. 각 close는 C−1ms 완료. 미래신규계약 최초관측은 이전 C 후보에 들어오지 않는다. exact 종가 외 인접봉/ffill/최근양수봉 대체 없음.

고정 시장 data/search-1458/market.json.gz canonical9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4 및 기존 독립329rawZIP 영수증 재사용. 신규 전체329시장 재감사 안함. TP에서 Decimal 감사된 유일 zero execution hour1730145600000은 BP 시그널·label·집행에 사용 안함. TP 압력값/RV모형/옛성과는 새 신호에 사용 안함. 일별 risk/core는 기존 spot 가격6추세/20일 위험을 고정해 사용하나 BS 체결은0이다.

## 피처·label·학습

K=365일/(E_far−E_near) × ln(close_far/close_near), τ=(E_near−C)/(365일). E는 명목날짜 proxy다. 가격 단위 공통배율 불변·역가격순서 부호 반전·양수/음수 K 모두 보존. K 양수 크기를 과열 가설로 보며 값 클리핑/최적화 없음.

F=(365/7)×sum(직전7일 실제 settled funding21개). 각 실제 timestamp를8h bucket으로 묶고 C−7일..C의21기대 bucket 각각1개이며 actual timestamp<C를 요구. C시점(+ms 포함)의 새 정산은 포함하지 않는다. 누락/중복/다른 간격이면 무효; 미래 funding 추정/게시시각 복원 안함. data_delay7은 F와K/τ 모두 C=T−7일. 현재가격은 T에 둬 지연된 새 derivative정보와 현재가격을 구분한다.

가격 통제는 BP 완료1h 종가의 UTC 일경계29개가 T−28일..T에 모두 유효할 때 r7=ln(P_T/P_(T−7일)), r28도같음. label=ln(P_(T+7일)/P_T), 경계봉 유효 필요. 전체28일 중 다른시간 누락으로 추가 마스크 만들지 않는다. label 미래가용과 현재피처를 별도 저장한다.

주간 FIRST2020Jan6..END2026Sep1배타. 4개 모형은 **동일 유효행** U=T−105주..T−2주의104달력주, label_end≤T−1일, 최소52행. 현재 full feature 유효와 common train을 요구하여 PRICE/FUND가 더 많은자료로 유리해지지 않는다. centered SVD 무제약 OLS; rank/nonfinite 무효. 달력1주 HAC/Bartlett .5/n/(n−k), 없는 주를 인접관측으로 압축하지 않는다. 전체표본 fitting/scaling·튜닝/계수 잘라내기 없음.

## 주규칙·대조·행동

1. **TS_INFO primary**: intercept+r7+r28+τ+F+K.
2. TS_FUND: intercept+r7+r28+τ+F (만기간 quote 정보 없음).
3. TS_TERM: intercept+r7+r28+τ+K (perp funding 정보 없음).
4. TS_PRICE: intercept+r7+r28+τ (단순 가격/만기 달력).
5. TS_INV: INFO의 발동 사건만 반대방향, fallback은 동일.
6. TS_TREND: 기존 signed6trend 그대로 BTCUSDT perp 양방향 적용.

INFO override는 β_K<0, |μ_INFO|>SE_INFO+ln1p(.0013), δ=μ_INFO−μ_FUND, |δ|>1e−12, δμ_INFO>0 모두 필요. FUND는 β_F<0 및 자기 비용/SE gate, TERM은 β_K<0 및 자기 비용/SE gate, PRICE는 자기 비용/SE만. 비용 gate는 양방향 동일 perp 왕복13bp이며 실제 funding은 계좌에 별도 적용한다. 음/양 계수 전부 회귀결과 보존; 부호gate 실패/무효는 **signed** core(−1..1) fallback. β반대라고 방향을 뒤집어 채택하지 않는다. INFO 발동은 signμ, INV는−signμ. 주중시작은 직전월요일 방향, 매일 위험만 갱신. risk자료무효는 HOLD(weightsNone). 실제새정보발동과fallback 분리 집계.

## 72조건계좌·반증 기준

6규칙×6조건(base,cost_x2,delay1,delay24,risk10,data_delay7)×2기간=72. main2022Jan1..2026Jan1, recent2026Jan1..Sep1, 각1000USDT. 기존 btc_target_ledger.py 불변: 1h후시가·추가지연1/24h, perp5bp+1.5bp 편도불리impact(cost2는양쪽2배), risk20%/stress10%,총명목≤1, .001BTC/min50USDT(감축예외),5%p재조정밴드,postcost12회,실제funding timestamp×hour markopen,최종청산. long low/short high 불리마진5%,시간DD. 호가/부분체결/과거규정/진짜청산/세금·운영비 미복원. 현금이자0,만기선물roll 체결비 없음(거래하지않음).

사전 공통 절대기준 유지: main수익>52.838713%/DD≤13.561952%/vol≤13.343621%/Sharpe≥.8/양수연도≥3/보유episode≥20; recent수익>4.628391%/DD≤10.450946%/vol≤16.520409%; 양기간마진위반0. base/cost2/delay1/delay24/data_delay7 양기간 순익>0. INFO는FUND/TERM/PRICE/TREND 각각 양기간 순익 초과, DD≤FUND양기간, commonMSE<FUND&PRICE양기간. common예측≥52main/20recent, 유효label있는전체판단주 대비 common≥80%양기간, β_K중앙값<0양기간. INFO override≥20주main/5주recent(새정보발동없는추세상속성공배제).

모든실패/비교/지연/연도/추가정보/발동/계수/결측 보존, 사후대조승격·조건최대수익선택·기준완화 금지. 기본일수익과4대조 차이7/14/28일 원형block2000회95%CI; 이는 반복개발 선택편향을 없애지 않는다. 새피처의 미사용/전진 실행 증거는 별도이며 가상역사 통과만으로 사용가능/성공보장 선언 안함.

## 순서

이 명세+Q191–203노트 커밋→신규만기 raw수집·독립Decimal입력감사/SHAs고정→합성인과·계약선택/만기/funding실제ms·HAC/purge/단위/대조/양방향검사·구현커밋→최초72계좌→독립원자료피처/정규방정식HAC/계좌원장·수량·비용·펀딩·마진·선정·CI검산→소켓차단byte재현→승인 연구Pages만 최소공개/실제값·다운로드→다른새근거조사계속. 단일 실험 실패나 게시완료는 전체목표 완료/종료 사유가 아니다.
