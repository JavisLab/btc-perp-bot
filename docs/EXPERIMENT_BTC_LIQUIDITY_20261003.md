# BTC 유동성 악화 보상 가설 · 성과 전 고정

## 경제 질문과 사전 반증

**가격 변화·실현위험 이후에도 BTC 자체의 유동성 악화 상태에 양의 후속 보상이 있는가?** 즉시거래 비용·재고위험을 감수하는 보상과 계속되는 매도압력이라는 반대 가능성을 구별한다. 기존 시각/큰가격충격 반전의 창·문턱 수정이 아니라, 완료된 두 봉의 가격범위로 측정한 유동성 구성의 추가 정보다. 부호가 반대인 모형을 보상 성공으로 채택하지 않는다.

Q136 Brauneis 등2021 DOI10.1016/j.jbankfin.2020.106041 [공식본](https://madoc.bib.uni-mannheim.de/62108/1/1-s2.0-S0378426620303022-main.pdf)26쪽 SHAa75b5126cddfa0fc70b220f288ab18fee860922f103cc25e68001e75d80154ef:2017–19 3BTCUSD거래소에서 CS/AR가 시간별 유동성 변화에 유용하나 일간 비용수준은 편향된다. Amihud 수준/횡단면 결과와 혼동하지 않는다. Q140 Ahmed2024 DOI10.1186/s40854-023-00598-9 32쪽 SHAd3761d6f5c9176a572ae4e2a8d2575b76f7f9b01b2c7d14c7f729cbfbae650e2: 전체EBA의realizedvol 주요 동시효과,얇은시장 가격대체/주말보간·구조변화 한계. Q143 Zhang/Li DOI10.1002/ijfe.2431 초록만: 횡단면 보상과 달리 주요3코인 시계열 관계는 유의하지 않음. Q137/141 양의 보상/폭락위험 주장은 초록만,전문403이며 선행시계 미입증. 자세한 원문 접근·반증은 연구노트 참조.

CS는 실제 bid/ask나 시장깊이가 아니다. Binance BTCUSDT에서 이번 지표를 실제 호가로 검증한 것이 아니며,가격범위 변동성 혼입 가능성 때문에 realized variance 통제를 둔다. 계수/성과는 경제 인과 입증이 아니다. 문헌모형 복제·새OOS가 아니라 이미 본 BTC 개발 역사에 대한 자체 단순화다.

## 입력과 시각 · 새 수집 없음

- `data/search-1458/market.json.gz` canonical SHA **9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4**, gzip SHA **7e596342c65607453bbc86eb8c632e98eee514c06c53bec8876cefb3fd38d1a8**. 현물1h OHLC와기존실제funding/mark 원장을 재사용. 329raw BTC ZIP/checksums의 기존 원시 입력을 보존한다. 다른자산 자료를 사용하지 않는다.
- `data/btc-venue-20261003/masks.json` SHA **bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd**, 현물3무거래시간 제외.
- `data/btc-cashflow-20261003/daily.json` SHA **30fc996715649844cb1dc224a88b60f07e6cf9e0e211722b44ec8579252190cf**, independent-audit SHA **68d4439905e4122e11bd29640450be8e222ccf5ef5f821b2a68d9032812bac37**, prepare-audit SHAc7f6082c497607c834abef84768a6f8ed70a7c970940ff873cb2fe0573076509. 기존16현물무효일 **valid mask만** 보수적으로 재사용. 거래량/개별체결 피처 추가 없음. 이 마스크에는 범위/시각 이외 품질 실패도 있어 보수적인 제외이며 규칙을 완화하지 않는다.
- 일집계범위2020-01-01–2026-09-01 배타끝. 일D는 정확24개의00–23UTC봉,각종료D+h+1h−1ms/양수유한OHLC/low≤open,close≤high/전체35일이기존valid/무거래시간없음. 하루라도 결측/품질실패면 해당일무효;ffill·80%허용·3000거래문턱/이상치절삭없음.
- 월요일T00UTC의최신D=T−1일. 모든사용봉은T전에완료,기본실행T+1h시가. 추가7일자료지연은D=T−8일이며학습피처도같이옮긴다. 현재거래소아카이브빈티지가당시최초게시/실제수신시각을증명하지않음. 봉완료와거래소파일사후공개를구별한다.
- 현재까지 이새피처·학습·수익을계산하지않았다. 사전커밋후새일집계생성/독립raw감사SHA를별도추가,구현·합성경계검사커밋후처음성과계산. 이전전체실험재실행/시세재수집없음.

## 정확한 일집계·주피처

각일D의24개현물봉에 대해 **일 안의23개 인접쌍만** 사용(전날/다음날봉 섞지 않음). i는첫봉,j=i+1은이미완료된둘째봉.

- β=log(H_i/L_i)^2+log(H_j/L_j)^2,γ=log(max(H_i,H_j)/min(L_i,L_j))^2.
- α=(sqrt(2β)−sqrt(β))/(3−2sqrt2)−sqrt(γ/(3−2sqrt2)),수학적으로(sqrt2+1)×(sqrtβ−sqrtγ).
- CS_pair=max(0,2×tanh(α/2)),음수값0은문헌정의. CS_D=23개쌍단순평균,상한·분위수튜닝없음.
- m_i=(logH_i+logL_i)/2,c_i=logC_i, AR_pair=sqrt(max(4(c_i−m_i)(c_i−m_j),0)),AR_D=23개평균. 둘째봉완료전에는사용불가. AR로그근사척도를실제체결%로오인하지않음.
- RV_D=sum_24(log(C_i/O_i)^2),정확한각봉open→close로그수익제곱합. close→nextclose나5mRV와혼동하지않음. 원시OHLC확인값·CS/AR각23값과0절삭개수·RV·valid/이유를보존.

월요일 최신D에서연속35일 D−34..D가모두유효여야4모형같은행이유효. C_d=일d23h봉종가.

- r7=log(C_D/C_(D−7)),r28=log(C_D/C_(D−28)).
- v1=log(RV_D),v7=log(mean RV_(D−6..D)),v28=log(mean RV_(D−27..D)). 세로그인수가0/비유한이면무효,임의epsilon없음. 일RV0자체는금지하지않으며해당로그조건을판정한다.
- cs=log1p(10000×mean CS_(D−6..D))−log1p(10000×mean CS_(D−34..D−7)). ar도같은식. 최근7일vs**직전28일 비중첩창**. 10000은bp척도,1bp의고정log1p단위로0도정상이며숨겨진매매문턱아님.

## 계좌와 학습·보상 부호

주목표 y_U=신호UTC직전현물종가→다음7일UTC직전종가의로그수익. 주신호2020Jan6부터2026Sep1배타끝. U=T−105w..T−2w의104달력주,최소52공통유효주,목표종료≤T−1d. Centered SVD OLS,달력1주HAC(Bartlett.5,n/(n−k)),rank부족/비유한무효. 결측주를붙이지않고4모형같은학습행. 계수/공분산/SE/학습시각보존.

1. **LQ_INFO primary**:intercept+r7+r28+v1+v7+v28+cs.
2. LQ_RISK:intercept+r7+r28+v1+v7+v28.
3. LQ_ALT:intercept+r7+r28+v1+v7+v28+ar. 측정대안이지기각후승격후보아님.
4. LQ_PRICE:intercept+r7+r28.
5. LQ_INV:INFO와같은발동주에서만반대방향.
6. LQ_TREND:기존E_SPOT 일별/회계항등검사,방향·위험불변.

모든계수는무제약으로과거에서추정하고전예측오차를보존하되, **INFO는추가유동성계수β_cs>0일때만** 보상가설매매가능. β≤0이면반대부호를채택하지않고core로복귀한다. ALT도β_ar>0동일. 양의β만으로거래하지않고, |μ|>SE+log1p(.0023 long/.0013 short),δ=μ_INFO−μ_RISK와μ_INFO동부호(δμ>0,|δ|>1e−12)를모두요구. ALT도자신의δ대RISK를동일검사. RISK/PRICE는자기μ의비용+SE gate. INV는정확INFO발동만반대로. gate미달·피처/모형무효는E_SPOT max(0,6sign평균),위험준비미달weightsNone보유유지. 주중기간시작은직전월요일판단. 주방향고정·매일원래20일현물종가std위험갱신.

각기간1000USDT,주2022Jan1–2026Jan1/최근2026Jan1–Sep1. 6규칙×6조건(base,cost_x2,delay1,delay24,risk10,data_delay7)×2=**72조건계좌**. 기본위험20%,stress10%,명목≤1. 현물롱/USDT무기한숏/현금중하나·현물차입/양다리없음. 원래5%p조절밴드·atomic전환·postcost12회수량/step.00001/.001·min5/50USDT·perp감축예외·종료dust비용.

현물10/perp5bp수수료+편도1.5bp불리impact·실제funding×hourmarkopen·실행sourceT+1h(+추가1/24h)불변. CS/AR로이비용을낮추거나대체하지않는다. 시간최대DD·불리hour극값margin5%;실제호가·부분체결·과거규정·순간청산·세금·운영비는미복원.

## 사후 변경 금지 관문

기본 주순익>52.838713%,DD≤13.561952%,vol≤13.343621%,Sharpe≥.8,4년중3양수·보유구간≥20;최근순익>4.628391%,DD≤10.450946%,vol≤16.520409%;담보위반양기간0. base/cost2/delay1/delay24/data_delay7양기간순익>0. INFO순익이 **RISK/ALT/PRICE/TREND각각양기간초과**,DD≤RISK양기간,공통MSE<RISK및PRICE양기간,공통예측≥52주main/20주recent. ALT까지이기는엄격비교를성과뒤삭제하지않는다. 최근기간수익기준을TREND의.89%로낮추지않는다.

모든계좌·기각·역방향·무거래·β≤0주수·예측MSE·연도·롱숏비용·지연을보존. 일순수익및4대조차7/14/28일원형블록2000회95%CI. 이번기각으로전체연구종료하지않는다.

## 검증 순서

기존SHA→日집계/독립rawOHLC·정확24/23시간·mask감사→미래두번째봉교란/완료·결측·가격단위/불변0·비중첩7/28·RV정의·0로그·T−1/+7·104/52/purge/HAC틈·β正/0/負·increment·週方向/日risk·수량/무거래/funding/遅延합성검사→구현커밋→새72성과. 별도정규방정식/HAC·원시highlow·폐형식수량/Decimal회계·가용시각·비용·실제funding·선정/원저장TREND항등·불확실성검산→새결과만소켓차단재현→최소Pages/익명값·다운로드. 공개자료와오프라인가상검증만,실전승격/주문없음.

### 성과 전 일집계 동결·별도 원시 검산

2,435일/2,419유효일,기존16무효일 그대로. 새 `daily.json.gz` canonical SHA **2b7c5a957845d2df07c1d71f7cefb0da2c536cdeec598478e34a3340f5703c3b**, gzip SHA **52fcd1b1b9bbb03a372951f1c72af419ceaf081d87fb84bcc65480bacbea1970**. independent-audit SHA **9ef9e7e9d4d3d0d670be8d27fee9f61a11476cb96804264ebe0c4728a1307a40**, prepare-audit SHA **837628e7073f97fe6ee342ce6cb4c275b682ed6529b6e0b5ab4464865fad847e**. 기존80현물ZIP 체크섬·58,408정규화OHLC의원시일치·58,056유효일시간봉·55,637인접쌍을별도Decimal log/exp/원형CS식으로검산했다. 최대절대오차1.2738626072e−13,CS0경계모호0개. 미래성과계산없음.

초기독립검산이2020-12-21의진단명차이를검출했다. 원시에는무거래이면서종료시각이틀린14UTC봉이있고,기존정규화에는그봉이제외돼있어missing으로보인다. 양쪽모두그날무효. 원시/정규화진단을각각전수대조하고차이를영수증에보존했으며입력값·16일mask·가설은변경하지않았다. 초기로그 `btc-liquidity-data-audit.log`와`...-diagnosis.log`를보존,보강검산`...-normalized.log`통과.

### 성과 전 구현 경계 검사

19합성검사 통과: 동일범위 CS/AR 폐형식·가격단위 불변·RV의open→close정의,당일23쌍/다음날미사용,누락/늦은종료/범위오류/무거래/기존무효 보존,음수CS/AR0정의,완료D+1/+7·35일창·7/직전28비중첩·bp척도,0CS/AR정상·0RV로그미정 처리,미래교란/가격단위/현재열가용,104/52동일행/purge·양음계수보존·rank/HAC달력틈,양의보상계수만 INFO/ALT발동·INV정확같은사건·비용/SE/추가정보부호,주중기간시작/주방향·일위험/위험누락보유,수량원장·실제펀딩부호·비용2배·24h실행시각. 구현작성시구문1곳은성과전수정;검사초회19통과. 원래원장/비용·규칙변경없고구현커밋후새72계좌만계산한다.
