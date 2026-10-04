# BTC/USD 마진 숏 잔고 변화의 추가 정보 · MI72 성과 전 명세

## 질문·범위·증거 수준

BTC/USD 현물마진 **숏 잔고의 주간 증가**가 같은 시장 롱 잔고 변화·이미 settled 된 무기한 funding·가격 추세를 통제한 후 다음7日BTC수익에음의추가정보를주는가? 차입제약하의부정정보반영이라는**자체조건부가설**이다. Q238 Strych초록의short와marginlong의가격효율성차이는동기를제공할뿐, 원문/투자자신원/미래비용순익은확보·입증되지않았다. 논문복제/소매투자자flow/비합리성확증이라부르지않는다. 잔고차이는신규+청산의합성이고헤지/거래소운영위험도포함한다.

기존OF/CF체결flow,양방향동수futuresOI,CFTC기관net,만기carry TS와달리 **별도BTCUSD 현물마진의long/short stock**이새경제정보다. fBTC광역대차는다른BTC-quote pair까지포함할수있어대신사용하지않는다. MI_INFO만주규칙,INV/다른대조의최대수익을사후채택하지않는다. 모든역사는반복개발자료로미사용OOS아님.

공개aggregate만, BTC-only. 실제가상체결은BTCUSDT perp롱숏; Bitfinex거래/차입/현물/만기선물체결0. USD/USDT가격ratio혼합없음(마진수량의동일side주간비만사용). 계정/개인loan·trade/인증/지갑·비밀/서명/유료/다른종목/하위에이전트/실거래서비스없음.

## 원자료·사전 고정 수집·가용시계

Q241公式 `api-pub.bitfinex.com/v2/stats1/pos.size:1m:tBTCUSD:long|short/hist`,응답[MTS,VALUE],VALUE는baseBTC. 공식문서size1m,15requests/min。현재조회빈티지는당시최초게시·revision없음의증거가아니다.

월요일T00UTC. 기본margin cutoff C=T−1日,추가data_delay7은C=T−8日. 필요한snapshot은C−1분정확MTS와C−7日−1분정확MTS. 각side/각cutoff의직전60분 `[C−1h,C−1ms]`를sort1/limit100으로조회,정확마지막분행이없으면해당snapshot무효. 앞분ffill/가장가까운관측/zero대체없음. 같은MTS중복은hardfailure,2열·유한양수value·정수ms/정분·query범위·오름차순검사. 내부분누락은diagnostic보존하되선택한정확분의유효성과구분한다. 정분stamp가구간시작인지스냅샷즉시시각인지원문이완전명세하지않아선택분종료C부터**24h게시buffer**가있게설계;이것도당시게시를증명하지않는다. delayedmargin에서도가격/funding는현재T에서판단한다(새margin정보만추가지연).

고정cutoff2019Dec22..2026Aug30매7日,350×2=700개작은60분응답. Q246..2494개정확표본은재사용하여신규696요청,4.5秒이상요청간격으로공식15/min이하,약53분·정상raw약1.3MB/42000분행규모. 전체분봉역사/전체잔고서비스수집아님. timeout/retry각응답·SHA·시각·상태를보존,429/5xx는Retry-After또는최소120秒후최대2회재시도,403우회없음. 누락은결측/기각으로보존하고기간/창을줄여구제하지않는다. data2026Sep이후수집안함. 수집중다른문헌/합성검사를진행할수있으나첫성과는자료동결/감사/구현커밋이후.

기존market `data/search-1458/market.json.gz` canonical9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4와이미독립검산한329시장/80perp raw영수증재사용;전체옛아카이브재검사안함. BP 유일zero executionhour1730145600000은가격·label·체결제외. 기존signed6trend/20日spot risk는정보만,BS체결0.

## 피처·학습·인과경계

L=ln(long_(C−1min)/long_(C−7d−1min)),S=ln(short_(C−1min)/short_(C−7d−1min)). 레벨·확장분모·정규화시가총액·winsorization·최적창선택없음. 각side공통양수단위배율에불변,0/음수분모무효. position수준이큰것을새부정정보로단정하지않고변화를사전고정한다.

F=(365/7)sum(T직전7日settled funding21개),실제timestamp row[3]<T/8h bucket각정확1개,현재T정산(+ms포함)배제;lag7에서도F는T동일. 가격r7/r28는BP완료1h종가의T−28日..T 29개UTC경계,하나라도무효이면가격피처무효. label=ln(P_(T+7日)/P_T),현재피처와미래label가용별도보존.

FIRST2020Jan6..2026Sep1배타의월요일. 4회귀는**동일유효학습행** U=T−105週..T−2週(104달력주),label_end≤T−1日,min52。현재fullfeature무효면4모형모두무효/공통마스크. centeredSVD 무제약OLS,rank/nonfinite실패시무효. 달력1주HAC/Bartlett .5,n/(n−k),누락주압축안함. 전체표본fitting/scaling/사후부호변경/제약계수cut없음.

## 규칙·대조

1. **MI_INFO**: intercept+r7+r28+F+L+S.
2. MI_LONG: intercept+r7+r28+F+L(숏추가정보제거).
3. MI_SHORT: intercept+r7+r28+F+S(롱정보제거).
4. MI_PRICE: intercept+r7+r28+F(두마진정보제거,명칭과달리既知funding도통제).
5. MI_INV: INFO발동같은날방향만반대,공통fallback.
6. MI_TREND: 기존signed6trend를양방향BTCUSDTperp에그대로적용.

INFO는β_S<0,|μ_INFO|>SE_INFO+ln1p(.0013),δ=μ_INFO−μ_LONG,|δ|>1e−12,δμ_INFO>0일때만signμ override. LONG은β_L>0와자기비용/SE,SHORT는β_S<0와자기비용/SE,PRICE는자기비용/SE. 양/음회귀계수모두저장,gate실패/현재피처·학습무효는**signed**6trend(−1..1)fallback,방향재해석안함. override는다음월요일전까지유지,일별risk갱신. 위험자료무효HOLD。pureperp양방향왕복13bp동일gate,실제funding은원장별도. INFO증분이동부호라고구조인과입증된것아님.

## 72가상계좌·거래조건·기각

6규칙×base/cost_x2/delay1/delay24/risk10/data_delay7×주/최근=72。main2022Jan1..2026Jan1,recent2026Jan1..Sep1,각1000USDT. 불변btc_target_ledger.py:기본T+1h시가/추가1h·24h실행시당시목표고정,perp편도5bp+불리impact1.5bp(cost2둘다2배),risk20%(stress10%),총명목≤1,.001BTC/min50USDT(감축예외),5%p재조정band/postcost12회/최종청산. funding실제시각×hourmarkopenproxy,시간DD·longlow/shorthigh불리margin5%. 현금이자0. 실제호가/depth/부분체결/과거규정/진짜청산·운영비/세금미복원,Bitfinex차입이자부과없음(거기서차입·거래안함).

절대기준고정: main수익>52.838713%/DD≤13.561952%/vol≤13.343621%/Sharpe≥.8/양수연도≥3/보유episode≥20;recent수익>4.628391%/DD≤10.450946%/vol≤16.520409%;양기간margin0。INFO base/cost2/delay1/delay24/data_delay7각양기간순익>0。INFO는LONG/SHORT/PRICE/TREND각각양기간순익초과,DD≤LONG양기간,commonMSE<LONG&PRICE양기간. commonforecast≥52main/20recent 및labelvalid전체판단주대비coverage≥80%,β_S중앙<0양기간,INFOoverride≥20週main/5週recent. 모두통과해야역사후보일뿐미사용/전진·실행증거아님.

모든실패/대조/지연·비용/연도/계수·결측/발동보존. 기본일수익및4대조차이7/14/28일원형block2000회95%CI. 최대대조승격/최근사후선택/기준완화금지. 자료결측·정보무발동·계좌실패도정직하게기각하고다른BTC근거로이어간다.

## 수행 순서

명세·Q218–250노트gitcommit→고정700응답수집·별도Decimal원시/선택분감사·SHA동결→인과(미래/게시+1min/1day/추가7일)·단위·0/결측/중복·funding실제ms·purge/HAC/공통대조·양방향합성검사·구현commit→최초성과72→독립원시피처/다른정규방정식HAC·계좌/선정/CI→socket차단byte재현→승인Pages변경결과만최소공개·실제값/다운로드검사→다음근거조사。계좌검산통과≠전략성공。단일완료/회차/45분으로전체종료안함.

## 성과 전 구현 검사 (수집 중)

사전명세d08d271 이후24합성검사통과:exact분선택/게시buffer·추가7일margin만지연/미래자료교란·누락·0·중복·소수정밀도/현재settled펀딩실제ms·공통학습purge·무제약OLS/별도정규방정식HAC·signedfallback/롱숏부호대조·비용·펀딩·수량·지연·불리마진. 원자료수집진행중,실제계수/성과계산0。inputs는UNFROZEN해시로막혀있으며700응답완료/별도Decimal감사후해시만고정하여첫성과전다시커밋한다.
