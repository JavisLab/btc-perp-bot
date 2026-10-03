# BTC 외부 위험회피 정보 가설 · 성과 전 고정

## 질문과 반증

**미국 주식 옵션시장의 위험회피 증가가 BTC 자체 가격·실현위험 이후에도 다음7일 BTC 수익에 음의 추가 정보를 주는가?** 기관 위험수요의 축소 가능성과 BTC의 분리/안전자산 가능성을 구별한다. 다른자산은 거래하지 않으며 VIX는 BTC 예측 외부입력뿐이다. Q145 Bouri등2018 DOI10.1016/j.qref.2018.04.003의 유료GFSI·꼬리관계·중앙예측제한과 Q146 IMF2023WP163 초록의 위험감수경로를 근거/반증으로 함께 기록했다. GFSI/copula/crypto factor 복제가 아니다. FOMC순간금리surprise MB_RATE 및 BTC옵션DVOL 위험예측과 다른 질문이다. Q148–149 공식정의·가용/권리감사는 연구노트 참조.

이미 반복해서 본 BTC 2022–2026 역사 경로의 **개발/탐색**이며 미사용OOS가 아니다. VIX와BTC의인과나실전수익을보장하지않는다. 아직 아래 새 피처·적합·계좌성과는 계산하지 않았다. 이 명세 커밋→자료 동결→구현/경계검사 커밋→최초계산 순서다.

## 입력·관측 시계·무효

- 기존BTC 시장 canonical SHA9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4/gzip7e596342c65607453bbc86eb8c632e98eee514c06c53bec8876cefb3fd38d1a8,329 BTC raw ZIP/checksum·funding/mark·수량원장 재사용. 이전 전체계좌 재실행/새시세 수집 없음.
- 기존 `data/btc-liquidity-20261003/daily.json.gz`의 **close/rv/valid만** 사용. canonical2b7c5a957845d2df07c1d71f7cefb0da2c536cdeec598478e34a3340f5703c3b/gzip52fcd1b1b9bbb03a372951f1c72af419ceaf081d87fb84bcc65480bacbea1970,independent-audit9ef9e7e9d4d3d0d670be8d27fee9f61a11476cb96804264ebe0c4728a1307a40. CS/AR는 이번 피처 아님. 일RV=sum24(log시간close/open)^2. 기존16무효일·3무거래시간 보존;마스크SHA bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd. 재사용검산영수증≠이번일집계전체재계산.
- VIX 공식관측후보범위2019-01-01–2026-09-01배타끝. CBOE raw9286행 SHA6edc3e3928c4b164b9e4ed1ec874e0ed53c7d52997557adebb7d6b7451db565a;FRED비교 CSV SHA84f279d69e35eacf918b939875bf0ed7e0ad78d176cd289b24f2ebf364221510. 연구범위1958행동일. 2026Sep/Oct값은파일출처만,피처/학습/평가미사용.
- 정규화는 연구범위 CBOE관측일과 FRED비결측일의합집합만. FRED휴일공백을새관측으로만들지않음. 날짜중복/비평일/양수유한값실패/양원천값불일치/한쪽누락이면무효를보존·대체안함. 원시OHLC범위도검사. FRED의41공백일목록별도보존. 원시지수산식재구성/독립경제원천이아님.
- 월요일T00UTC 신호. VIX날짜D는 미국관측일 표식으로, **D+2일00UTC** 가용을가정;추가7일자료지연시D+9. 현행16:15ET 종료는20:15/21:15UTC로D안에있지만역사단축/배포시각/최초빈티지는미검증. 이번CBOE2026Oct2값은Oct3실제보임/FRED는아직Oct1이므로FRED당시가용이라고하지않음. 공식현재빈티지·방법변경·재공표한계는+7일로해결안됨.
- effectiveT=T−lag일에서 D+2≤effectiveT인 최신6개 **관측행**을선택. 무효행을버리고더과거정상값으로채우지않음. 전부유효,최신날짜age=effectiveT−D≤5달력일,최신−최초≤14달력일이어야함. 주말/휴일가격ffill·일변화0삽입없음. 데이터없음/오래됨/창부족이면 모든모형현재피처공통무효.
- BTC최신일B=T−(1+lag)일. B−28..B의29연속완료일이모두valid,양수close·유한비음rv·정확일종료≤effectiveT 필요. v1/v7/v28의인수가0이면무효·epsilon없음. 추가지연은학습피처에도동일적용. Label/실행시각은지연따라옮기지않음.

## 피처·학습·거래

C_B는B의UTC일종가. r7=log(C_B/C_(B−7)),r28=log(C_B/C_(B−28));v1=log(RV_B),v7=log(mean RV_(B−6..B)),v28=log(mean RV_(B−27..B)). 최신6VIX관측을V_0..V_5로정렬,**shock=log(V_5/V_0)**(5관측간격,휴일따라달력기간다름),**level=log(V_5)**(index percentage-points의로그). 전체표본표준화/분위문턱/추가변수없음. 날짜/age/창과가용가정을기록한다.

1. **RF_INFO primary**:intercept+r7+r28+v1+v7+v28+shock.
2. RF_RISK:intercept+같은5 BTC변수.
3. RF_LEVEL:intercept+같은5 BTC변수+level. 수준 대조,실패후승격없음.
4. RF_PRICE:intercept+r7+r28.
5. RF_INV:INFO와정확같은발동주만반대방향.
6. RF_TREND:기존E_SPOT동일 core/회계항등.

모형주2020Jan6–2026Sep1배타끝. 목표y_U=U직전현물종가→U+7일직전현물종가의logreturn. U=T−105w..T−2w의104달력주,최소52공통유효행,label종료≤T−1일. 4모형같은행·centered SVD OLS·달력1주HAC(Bartlett.5,n/(n−k)). 결측주붙이기/rank부족회귀/제약적합없음. 모든무제약계수·예측·SE·오차보존.

INFO는β_shock<0,LEVEL은β_level<0이어야 위험회피가설 매매가능. β≥0이면사후안전자산가설로바꾸지않고core복귀. 동시에 |μ|>SE+log1p(.0023 long/.0013 short),δ=μ−μ_RISK와μ동부호(δμ>0,|δ|>1e−12)필수. RF_RISK/PRICE는자기비용+SEgate만. INFO/INV는동일사건만정/역방향. gate부족/모형·피처무효core=max(0,6추세sign평균),risk준비없으면weightsNone보유유지. 주중기간시작도직전월요일;주방향·일별20일변동성위험(20%/stress10%)은불변.

각기간1000USDT,주2022Jan1–2026Jan1/최근2026Jan1–Sep1. 6규칙×6조건(base,cost_x2,delay1,delay24,risk10,data_delay7)×2=**72조건계좌**. longBTCspot/shortBTCUSDTperp/cash택1,총명목≤1·현물차입/동시2legs없음. sourceT+1h기본체결(+1/24h조건),5%p밴드/atomic전환/postcost12회/step.00001/.001/min5/50USDT/감축예외/종료dust 불변. 현물10/perp5bp+편도1.5bpimpact·실제funding×hourmarkopen,시간DD·불리hourmargin5%. VIX로원장비용낮추지않음. 실제호가/부분체결/역사규정/순간청산/세금/운영비 미복원.

## 기각 기준·검산·공개

주순익>52.838713%,DD≤13.561952%,vol≤13.343621%,Sharpe≥.8,양수연도≥3/4,보유구간≥20;최근순익>4.628391%,DD≤10.450946%,vol≤16.520409%;담보위반0. base/cost2/delay1/delay24/data_delay7 양기간순익>0. INFO순익이 **RISK/LEVEL/PRICE/TREND 각양기간초과**,DD≤RISK양기간,공통MSE<RISK및PRICE양기간,공통예측주≥52main/20recent. 최근수익기준을TREND.89%로낮추지않음. LEVEL까지이기는대조도사후삭제없음.

무효/β≥0/무거래/모든계좌·연도·비용·지연보존. 일순익 및4대조차7/14/28일원형블록2000회95%CI. 동일자료/같은새실험만소켓차단재현.

검사:두공식CSV 별도Decimal재파싱/주말·휴일·중복/시계·stale/6관측/5간격·log단위/미래교란·BTC29일완료·RV정의/0로그/lag7·동일학습행/104/52/purge/HAC틈/rank·계수음양0·cost+SE+delta·INV정확사건·주방향/일risk/회계. 별도정규방정식·독립BTC raw329ZIP가격·Decimal수량/실제funding/무거래/계좌/CI/선정/저장TREND검산. 과거VIX옵션산식·원문순익복제를주장하지않음.

공식원문PDF/전체CBOE·FREDCSV는공개ZIP미포함;출처CBOE/FRED 링크·SHA·자체변환과계좌를기록. 공식원시입력이별도로필요한재현자료임을명시. 공개자료/오프라인계좌만,실전승격·주문·다른자산매매/ETH/개인자료/하위에이전트없음. 한가설기각/게시완료로연구종료하지않음.

### 성과 전 입력 동결

기존공식2응답을재수집없이정규화·별도Decimal검산했다. CBOE전체9286행,선택1958=FRED비결측1958,전값일치/현재범위무효0·최대4일간격·FRED빈행41개별도보존. 정규화SHA **2531b2d4b51c4fe775dafbeac152ff579875b25d3a709c2d60250f7ab43ba82b**, prepare-audit **6070ac61b95902d421400737a528686f783415d3594be55025a24a37c6a15049**, independent-audit **9fcb6dc8324862c28ff82ac64310b9dca713c24b8d592b4ab848b687fdc74e9e**. 두배포본은독립경제원천/최초빈티지증명이아니며,새BTC결합피처·회귀·수익미계산.

### 성과 전 구현 경계 검사

19합성검사 초회통과. D+2/+7·BTC29일완료·정확6관측5간격·휴일미보간·무효행미건너뜀·5일age/14일span·빈창/오래된값·0/음수/비유한/시계오류·미래교란·VIX단위/level상수이동불변·BTC가격단위·RV평균/0로그·두CSV불일치/중복/공백·104/52동일행/purge/HAC틈/rank·무제약계수보존/음의부호gate·cost/SE/delta/INV·주중시작/일위험·수량·무거래·실제funding부호·24h비용시계 검사. 원장·기준·규칙변경없음. 구현커밋후새72조건만계산한다.
