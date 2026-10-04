# BTC 집계 체결건수의 위험 추가정보 · TC72 성과 전 고정

## 별도 경제 질문과 한계

**같은 BTC 거래대금·순불균형·시간별 절대불균형·기존 실현위험에서도, 완료된 체결건수 증가는 다음 날 위험에 양의 추가정보를 주는가?** 총 거래대금이 같아도 적은 큰 체결과 많은 작은 체결은 구분된다. 정보도착의 혼합분포 가설을 동기로 삼되 실제 정보사건·개별 투자자·주문 수를 알아냈다는 주장이 아니다. 매칭엔진의 주문 쪼개기/규칙/봇활동도 관측건수를 바꿀 수 있다. 평균크기나 whale/retail 신원을 추정하지 않고, 모든 부호·실패를 보존하는 자체 미래위험 검정이다.

Q301 Barjašić/Antulov-Fantulin2021 DOI10.3389/fphy.2021.644102는2019년58,000분/50,000fit·8,000test의 외생volume/spread/tweet GARCH 위험연구. 최대lead1분·위험손실이지 비용후 방향수익이 아니며 거래건수 자체를 검정한 것도 아니다. Q302 Schnaubelt외2019 DOI10.3390/jrfm12010025는 거래크기·빈도 및 낮은 빈도 return무상관의 설명 통계이며 미래계좌 아님. 기존Q122의 MDH/ITIH는 당기회귀일 뿐 미래위험 근거로 세지 않는다. 원문 모델·주문장·trade·tweet 자료는 수집/복제하지 않는다.

기존TP는시간별절대flow G,PS는달력요일,VI/CP는volume×price 또는premium×flow,OF/CF는부호flow,CT는가격방향 지속이다. **새 정보는 기존raw에 있었지만 이전 predictor에 쓰이지 않은 양의 정수 trade count**이며 창·부호·레버리지를 조정한 후보가 아니다. TC_INFO만주후보. 현재까지반복BTC역사는개발자료/미사용OOS아님. 모든실제체결은BTCUSDTperp롱숏,현물은추세·위험참조만. BTC-only/공개aggregate/offline only,개인trade·주소/계좌/비밀/유료/실거래서비스/하위에이전트/타자산0.

## 원자료·피처시계 동결

기존 data/btc-pressure-20261004/daily.json.gz canonical SHA `b7bcc90d73a29cf1f2d84dcd752025a6034d356ab337d7ce48eab82f09869d5f`,gzip `9529f16033f2229e9ebaff6333e9bb0a4d8becab180eb737a8a834b9b065add7`. 공식80개월1h BTCUSDTperp의이미검산한시간별원시문자열에 `trades`(원열8),quote,buy_quote,OHLC/end가보존돼있다. 동일80ZIP/329시장·이전계좌전체재감사/수집안함. 원rawtuple영수증 SHA `67d0cf710240cfd75409d31300fcb35f4c1502c2289bb1657f7abe55e9fd7250` 재사용.

새 일별 N=sum24시간trades. 24개 정확UTC시간·end=time+1h−1·시간중복없음·기존day/hour valid·각trades 유한양의정수 요구. 소수·0·음수·결측·추가시간·end이탈은그날무효,중복은hardfailure. 기존4일품질무효를되살리지않음. Decimal60자리원필드합/정수합서로검사, 새counts/무효사유/hash를보존한다. ffill/평균크기대체/epsilon없음. count×상수의단위불변성과같은Q/flow에다른N의구분을합성검사한다.

판단T=매일00UTC. 현재flow D=T−1일은 기존Q=sumquote,Nflow=abs(sumsigned)/Q,G=sumabs(hourlysigned)/Q,0≤Nflow≤G≤1. v=ln(Q_D/meanQ_(D−28..D−1)),D포함29연속유효일. count최신C=T−1일,**c=ln(N_C/meanN_(C−28..C−1))**,현재일분모제외/29연속유효일. 추가data_delay7은C=T−8일로 **새c만7일지연**,기존Q/Nflow/G와RV는현재T시계를유지한다. 단공통valid행을요구하므로늦춘count의결측이대조학습마스크에도영향을줄수있다. 이때대조계좌가무조건동일하다고가정하지않는다.

기존검산perp5m일RV canonical `2da197d43eb2275681050988c888093975eb8f34368f05570b146a6cc46a6c47`,gzip `61b3b68aa4ac96116f30986e76303a8cb394837edff6a22242dbb226f20ef1ee`,raw검산receipt `f70aceabfe3016dc26a15404478e4b8bd314e1b974885226aaae3b9ed4bd640e` 재사용. z1=ln RV_(T−1),z5=ln meanRV_(T−5..T−1),z22=ln meanRV_(T−22..T−1),22일모두완료/valid/양수. 현재truth는RV_[T,T+1일),신호/학습에미래truth혼입없음. 데이터의분산단위는log수익²합이지sqrt연율아님.

기존시장canonical9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4/독립329ZIP검산receipt38f6da0357b82a2067fed0869fd27e7a8cb1ad937044a392486fdd0d9a9e0382 유지. BTCperp거래량0시간1730145600000집행제외. 현재월아카이브+1h실행buffer는과거원게시/PIT증거아님.

## 고정 모형·순수선물 배분

T의과거365달력신호일 U∈[T−365d,T−1d],truth종료≤T,최소300공통유효행. 네모형동일행/현재fullfeature마스크. log(RV_U)를절편포함centeredSVD OLS로학습·훈련잔차exp평균smearing으로평균분산복원. rank부족/overflow/비유한무효,임의ridge없음. floor1e−8/모형계수무제약·전체표본표준화/최적창없음.

- **TC_INFO**:1+z1+z5+z22+v+Nflow+G+c.
- TC_FLOW:1+z1+z5+z22+v+Nflow+G,새건수제거/주ablation. 기본의가용행이같으면既存TP_INFO와같을수있지만새성공가설이아니다.
- TC_COUNT:1+z1+z5+z22+c,거래대금·flow제거대조.
- TC_HAR:1+z1+z5+z22,기존위험만.
- TC_INV:동일날 V_FLOW²/V_INFO를log에서계산/같은floor,반대위험배율이지방향반전아님.
- TC_TREND:기존signed6추세×20완료현물일수익표본std의위험량.

INFO count계수의사전경제부호는양수이지만추정치를제약하거나음수날을고쳐쓰지않는다. 평가양기간 β_c중앙>0관문만별도검정한다. 방향은기존20/60/120완료수익과EMA8/32,16/64,32/128 부호평균score∈[−1,1]그대로,새c로방향을바꾸지않는다. targetBP=score×min(1,risk/sqrt(365V)),risk.20기본/.10stress,BS=0. 현재features/예측/추세부족이면weightsNone보유유지. TC_TREND는원20일risk이고다른모형결측에종속하지않음. 미래RV를사용한oracle배분없음.

## 72계좌·비용·고정 기각

6×base/cost_x2/delay1/delay24/risk10/data_delay7×2기간=72. main2022Jan1–2026Jan1,recent2026Jan1–Sep1각1000USDT. 동일btc_target_ledger:기본T+1h시가/추가1h·24h(원목표고정),편도선물5bp+불리impact1.5bp/2배둘다2배,.001BTC/min50USDT·감축예외/5%pband/postcost12회/마지막dust청산/총목표명목≤1배. 실제펀딩×시간mark시가대용/실제settlementtimestamp,시간DD·longlow/shorthigh5%margin. 시간지연/봉결측은원규칙대로;호가/부분체결/과거규정/진짜청산/운영비·세금·첫게시빈티지미복원. 예측손실은전체다음UTC일에대해평가하므로첫1h가집행전이라는점도명시한다.

고정주순익>52.838713%/DD≤13.561952%/vol≤13.343621%/Sharpe≥.8/양수년≥3/보유episode≥20;최근순익>4.628391%/DD≤10.450946%/vol≤16.520409%;양기간margin0. INFO base/cost2/delay1/delay24/data_delay7각양기간순손익>0. INFO순익이 FLOW/COUNT/HAR/TREND 각각양기간초과,DD≤FLOW양기간. 각기간공통predictioncoverage≥90%,floor≤1%,INFO QLIKE<FLOW및HAR,MSE≤FLOW,β_c중앙>0. 모두통과해도미사용/전진·실행증거없는역사후보일뿐채택·성공보장아님.

모든대조/실패/비용·지연·연도/롱숏·수량·노출·funding/계수·무효·floor/원예측보존. 기본순日수익·각4대조차와對FLOW/HAR MSE/QLIKE손실차7/14/28日원형block2000회95%CI. 중복개발선정편향해소아님. INV/COUNT/최대수익조건승격·부호/기준완화금지.

## 검증·공개 순서

명세/문헌노트commit→새건수일집계·별도Decimal원필드감사/SHA동결→합성(동일Q異N/단위/整數·0/중복·현재분모제외/새c만7일/미래교란/365달력·300공통·라벨시계/음수계수·smearing/floor/양방향costfundingqtydelaymargin)·구현commit→최초72→독립원시문자열/별도정규방정식·손실/선정/Decimal원장·폐형식수량/CI→소켓차단新전체byte一致→승인Pages변경결과만최소공개·익명값/다운로드→次근거。계좌검산≠전략성공。한실험·한source실패·45분으로연구끝내지않음.
