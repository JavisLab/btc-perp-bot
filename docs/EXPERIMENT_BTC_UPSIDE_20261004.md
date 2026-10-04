# BTC 상방·하방 변동 구성의 추가 방향정보 · UV72 성과 전 명세

## 경제 질문·기존 실패와의 구분

같은 누적수익·총실현분산·상승/하락 횟수라 해도 **큰 움직임이 상승 쪽에 집중됐는가**는 다음7日BTC수익에추가양의정보를주는가? Q264새2026preprint초록의“상방주도변동성이랠리/다음기간양수수익과연결”을자체고정조건부모형으로반증한다. 원paper전문/훈련/비용/레버리지는미확보라복제·저자순익검증이라부르지않는다. Q263의5분semivariance는미래**변동성**이목표이고h1/h7부호불안정,그결론을미래방향수익으로바꿔읽지않는다. 미래targetquantile을현재regime로선택하지않는다.

새정보는총분산의부호별기여도,관측되는것은가격위험구성이지뉴스/매수자유형/구조인과가아니다. CT의28日부호횟수×누적수익,IC의하루경로면적,OF/CF체결압력·LQ가격범위·TP무부호flow위험의창/부호/레버리지재조정이아님. 부호횟수와총RV를직접통제해그것만으로얻은성과를새정보성공으로삼지않는다. 예를들어로그수익[.03,.01,−.02,−.02]와[.02,.02,−.03,−.01]은종점/총RV/부호횟수같고상방·하방분산차이는반대다.

MI마진가설과도다르며 **MI실제계수/성과를계산·열람하기전**독립질문으로사전고정한다. MI의공개잔고수집은진행중이다. 모든BTC역사는반복개발자료/미사용OOS아님. BTC-only 공개집계·오프라인만,현물/다른종목/개별체결/주소·키·지갑·유료·하위에이전트/실거래서비스없음. 체결은순수BTCUSDT perp롱숏,BS체결0.

## 고정 원자료·시계·새 순간분해

신규전체아카이브수집없음. TP에서별도Decimal감사한 `data/btc-pressure-20261004/daily.json.gz` canonical b7bcc90d73a29cf1f2d84dcd752025a6034d356ab337d7ce48eab82f09869d5f의BTCUSDT perp 원시1h OHLC/basevolume/endtimestamp를재사용한다. 이를실제VPIN/원5분논문복제로부르지않는다. 80개월raw입력receipt 및공통market canonical9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4/329ZIP감사SHA재사용,무변경전체재감사안함. 과거처음게시vintage/호가체결입증아님.

월요일T00UTC,기본새위험구성cutoff C=T;data_delay7은C=T−7日. 경계C−7日..C의169개직전1h완료종가로168개연속hour로그수익 r_i=ln(P_i/P_(i−1))。169개원시봉모두정확ms·close_end=boundary−1/양수유한OHLC·양수basevolume를요구,missing/zero봉이하나라도있으면해당위험구성무효. 시간압축/ffill/±인접봉대체없음. TP에서확인된유일zerohour1730145600000은가격·label·체결에서도제외.

V+=sum(r_i² I[r_i>0]),V−=sum(r_i² I[r_i<0]),V=V++V−。V>0필수,zero분산epsilon대체없음. **A=(V+−V−)/V**, Q=(n+−n−)/168(0return도분모168),R=ln((365/7)V)。A∈[−1,1],Q∈[−1,1],V의분해·부호계수·합수익항등검사. 가격단위공통배율/시간순서permutation에A/Q/R불변;전체수익부호반전시A/Q부호반전,R불변. 과거/미래에따른clip·threshold·tailpercentile·Hill튜닝없음. 1주형성/1주목표는자체사전고정이며원문의주기라고안함.

가격통제r7/r28는현재T−28日..T의29개UTC일경계BP완료종가。F=(365/7)sum(T직전7日settledfunding21개),실제timestamp row[3]<T와8hbucket각1개,현재T(+ms포함)정산제외. 추가7日은A/Q/R만이동,가격/F는현재T유지. Label=ln(P_(T+7日)/P_T),현재피처와미래label의가용성을분리한다.

## 동일 학습과 주규칙·대조

월요일FIRST2020Jan6..2026Sep1배타,각T U=T−105週..T−2週의104달력주,유효fullfeature+label_end≤T−1日/min52로**4모형공통표본**. centeredSVD 무제약OLS/rank/nonfinite무효,calendar1주HAC/Bartlett.5/n/(n−k),누락주압축안함. 전체표본fitting/scaling·부호clipping없음.

1. **UV_INFO primary**: intercept+r7+r28+F+R+Q+A.
2. UV_COUNT: intercept+r7+r28+F+R+Q(상·하방분산기여도제거).
3. UV_SEMI: intercept+r7+r28+F+R+A(횟수제거).
4. UV_PRICE: intercept+r7+r28+F+R(둘제거,기존funding/총위험도포함).
5. UV_INV:INFO발동같은사건만반대방향,동일fallback.
6. UV_TREND:기존signed6trend그대로양방향perp.

INFO는β_A>0,|μ_INFO|>SE_INFO+ln1p(.0013),δ=μ_INFO−μ_COUNT,|δ|>1e−12,δμ_INFO>0모두필요하며signμ로override. COUNT는β_Q>0+자기costSE,SEMI는β_A>0+자기costSE,PRICE는자기costSE만. 회귀계수부호반대/무효는고정signed6trendfallback이며반대대조승격없음. 주중동일방향·일별20日risk갱신,위험자료무효HOLD. 같은7일r나Q로설명되는성과는A추가정보관문을통과하지못한다.

## 순수선물72계좌·기각기준·검증

6×6(base,cost_x2,delay1,delay24,risk10,data_delay7)×2기간=72. main2022Jan1..2026Jan1/recent2026Jan1..Sep1,각1000USDT。불변btc_target_ledger.py:기본source+1h시가,추가1/24h당시목표유지,perp편도5bp+불리impact1.5bp(cost2둘다2배),risk20%(stress10%),총목표명목≤1,.001BTC/min50USDT(감축예외),5%pband/postcost12회/최종청산. 실제ms funding×hourmarkopenproxy,시간DD·longlow/shorthigh불리margin5%. 현금이자0/부분체결·호가·당시전규정·진짜청산·세금·운영비미복원.

절대관문 main수익>52.838713%/DD≤13.561952%/vol≤13.343621%/Sharpe≥.8/양수年≥3/보유episode≥20;recent수익>4.628391%/DD≤10.450946%/vol≤16.520409%;margin0양기간。INFO base/cost2/delay1/delay24/data_delay7각양기간순익>0。COUNT/SEMI/PRICE/TREND각각양기간순익초과,DD≤COUNT양기간,commonMSE<COUNT&PRICE양기간。commonforecast≥52main/20recent·coverage≥80%,β_A중앙>0양기간,INFOoverride≥20週main/5週recent. 전부통과해도역사후보일뿐미사용/전진·실행증거아님. 대조승격·창/주기/부호·기준완화없음.

모든실패/대조/계수/무효/연도/비용·funding/롱숏/노출·발동저장,기본일수익및4대조차이7/14/28일원형block2000회95%CI。선정편향없어진OOS라고안함. 명세커밋→합성인과/同rRVQ異A·단위·0/누락·7日delay·fundingactualms·purge/calendarHAC·양방향검사/입력SHA고정구현커밋→최초72→독립이미감사된원시hours에서Decimal피처·다른OLS/HAC·원장수량/일말·선정/CI→socket차단byte재현→승인Pages새결과만최소공개/실제값·다운로드→다음근거. MI수집과독립적으로수행하고어느단일완료/45분도전체종료사유아님.
