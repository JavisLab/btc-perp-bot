# BTC 차익자본 제약 × 완료 주문흐름 · 성과 전 명세

## 근거와 반증 범위
Q29 BIS Crypto Carry(2023)는 **만기** basis·차익자금 제약·급락을 연구한다. Q30 Ackerer/Hugonnier/Jermann NBER32936(2024)는 위험중립 가격 이론이다. Q31 He/Manela/Ross/von Wachter arxiv2212.06888v7(2026-09-17,109쪽)은 무기한 가격과 clamp, 비용별 차익거래, 자본제약 상태별 주문흐름 가격영향을 다룬다. Q31 §5.4의 flow_(t+1)와 premium변화_(t+1)는 **동시** 회귀이며, 다자산 pooled/full-sample 분위수다. 미래 BTC 수익을 과거 흐름으로 예측한다는 증거가 아니다. 저자의 high비용도VIP maker 전제이며 우리taker 비용과 다르다.

우리 독립 질문: 가격반응을 통제한 뒤 **이미 완료된** 체결압력은 직전 프리미엄이 큰 상태에서 향후8시간 BTC수익에 다른 정보를 남기는가? 지속과 과도반응 중 방향은 순차학습으로 추정하되 단일 고정 선형 상호작용만 검사한다. 기존 OF_RES/FUND 충격조건/C_FILTER 실패를 변경·승격하지 않는다. 새논문의 동시 가격충격이나 큰 연율 숫자를 실행가능 alpha로 사용하지 않는다. 아래는 논문 재현이 아닌 별도 BTC 개발 가설이다.

## 자료·시계 고정
- BTC perp1h OHLCV 행SHA1724851f889b7602fa4736dc71a9e6c76db1547be6a3d7be64092f55c27ba551,5m027edb1a22e540dfda734b31b23fe59daf63c163e44b927b554a758ab47775e3,현물/mark/실제funding9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4. 기존198+새382계좌는 보존/재실행안함.
- 공식 BTCUSDT premiumIndexKlines1h2020-01~2026-08,80월+12일 ZIP/CHECKSUM. 193누락시간 중192는공식daily로만복구. 남은2020-12-01 23UTC1시간은daily도없고공개API빈배열. 표본수0인26행은현값그대로보존/사용금지. 월양수표본행은daily로교체안함,비교충돌0. 정상화58439행 SHA2da88be7e88ba42f540c3132aaf6ba79778ba2a24d57e27ac1c61ff82c6e76b2. 초기 실패와원월SHA3227582ce198eba7b8916e97736098615afb8c0d6b56c31218d29174c83cdfa5 보존.
- index의volume0은placeholder,price양수검사금지(지수음수/0가능). sampling count>0·종료시각정상만 유효. count빈도60→720변화는trade횟수아님. 최신API명세는공식modular connector의 GET /fapi/v1/premiumIndexKlines 로확인,공식웹문서는202빈본문. 모든과거첫수신시각/지수계산법빈티지 입증은아님. paper의(F−S)/F 와공식premium-index가같다고가정안함.
- UTC00/08/16 경계T에서 [T−8h,T)의완료8개perp봉: r=ln(C(T)/C(T−8h)), f=2Σtaker_buy_quote/Σquote−1. 모두양수quote/volume,0≤buy≤quote,정상close_time필수. 가격시작/끝close가양수거래량봉이어야한다. 기존4개volume상충시간이8h안에있으면무효.
- 상태는 흐름 구간 **시작 전** [T−16h,T−8h)의8개완료index종가를평균한값의절댓값 A=|mean(premium_close)|. 하나라도없거나count0이면무효. 현재8h안의지수는이번상태입력에사용하지않음.
- paper가격대용 대조 A_gap=|mean((perp_close−spot_close)/perp_close)|,같은초기8h. 현물은원시정상종료/가격>0(거래량은신규독립원시감사로별도확인). feature공통유효성은r/f/A/A_gap모두필요하며비교군도같은마스크.
- 위험은floor(T/24h)*24h까지완료된20개일별perp log수익의표본std√365. 이외현재일자료를일간위험에사용안함.

## 기본과 모든 대조·학습
각시점에이전365달력일의특징시각U∈[T−365d,T)를사용하되 U+8h≤T−8h(완료라벨 뒤추가8h purge),직접앞8h를훈련에서빼기. 라벨 y=ln(C(U+8h)/C(U));라벨8h도동일정상거래봉요건. 최소900개유효쌍·최소365일전체이력,미만공통현금. 입력열표준화는훈련자료만,OLS절편포함/SVD추정;상수0분산열은scale1,rank부족해당모형현금. 가격/flow/index 미래교란검사 필수.

- **CP_INT 기본**: [1,r,f,A,A×f]. A×f의추가정보만선택대상.
- CP_ADD: [1,r,f,A],상호작용제거.
- CP_FLOW: [1,r,f],상태제거.
- CP_PRICE: [1,r],가격예측만.
- CP_GAP: [1,r,f,A_gap,A_gap×f],논문의가격차대용/공식지수차이.
- CP_INV: CP_INT의완성목표정확반대,좋아도승격안함.

OLS μ예측평균표준오차 se=sqrt(SSE/(n−k)×x'(X'X)^−1x). 완전예측구간이아님. 8h지급근사로 T−1h보다엄격히이전인마지막확정funding F를사용(원시timestamp<T−1h,나이≤16h;미충족공통현금). μ>ln(1+.0013)+max(F,0)+se이면롱, μ<−[ln(1+.0013)+max(−F,0)+se]이면숏,나머지0. 아직확정안된T정산/다음funding은신호에사용안함. 실계좌에는기존원장의실제각정산부과. 비용스트레스에서도같은신호장벽,결측은0현금으로고정/장기보유연장안함. 이펀딩항은보수적비용근사지예측수익아님.

## 계좌·비교·기각
6규칙×5조건(base,cost_x2,추가delay60/240m,risk10)×2기간=60. 주2022~2025/최근2026-01~08 별도1000USDT. 모두이미본개발경로·새OOS아님. 기존btc_session_study5m BTCperp롱숏원장,기본T+5m시가·최신판단교체·0거래봉다음유효봉재시도. 목표sign×min(1,.20/vol),1배상한·5%p밴드·.001BTC/min50(감소예외),편도5bp+impact1.5bp/종료dust청산. 실제funding×rawhourlymark시가proxy. 호가/partial/역사규정/정산순간price미복원.

기본CP_INT 주수익>52.838713%,DD≤13.561952%,최근>4.628391%,DD≤10.450946%,연vol≤13.343621/16.520409%,주Sharpe≥.8,주양수연도≥3,주완료보유구간≥100,담보위반0. base/cost2/delay60/240 모두양기간순손익양수. **추가정보주장**은CP_ADD·CP_FLOW 대비양기간MSE감소와양기간순손익우위도필수. 기간끝넘는라벨은MSE에서제외,CP_GAP/PRICE/INV를기본으로바꾸지않는다. 낮은위험만통과/레버리지증가/한해선택으로기각기준을낮추지않음.

모든계수/훈련시각·라벨시각·표본수·신호·무효현금·표본출처·연도/분기·롱숏·수량/비용/펀딩/노출/무거래보존. 기본일수익과E_SPOT저장결과/CP_ADD/CP_FLOW차이7/14/28일블록2000회95%구간,누적연구선택·모형불확실성은남음. 독립raw92premium ZIP·가격rawZIP→특성/정규방정식(중심화SVD와다르게)·예측/시계·신호、폐형식수량/무거래·Decimal원장/mark/펀딩·5mDD검산. 새전체파일소켓차단바이트재현후만확정공개. 실패하면웹검색/원문/다음가설계속. 실거래/계좌/유료/다른자산/하위에이전트없음.
