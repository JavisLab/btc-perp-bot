# BTC 감정 합성지표의 시장정보 이후 추가가치 · 성과 전 사전명세

## 독립 질문·원문 범위

**공개 Bitcoin Fear & Greed(FGI) 수준은 과거 가격·위험·거래량을 통제하고도 다음 주 BTC 수익에 추가정보를 주는가?** 군집심리·추종수요/과잉반응은 상승을연장하거나되돌릴수있다. 부호를미리성공으로단정하지않고완료과거자료에서만추정한다. 기존EPU의정책기사빈도,NA의네트워크이용량,CF의체결순압력과다른공개합성지표를검정한다. 기존실패의창·문턱·레버리지변경이아니다. 기존104/52주학습·7일목표·원장규칙유지.

Q130 [Alternative.me 공식정의](https://alternative.me/crypto/fear-and-greed-index/)는현재BTC-only지표라고명시. volatility/maxDD25%,momentum/volume25%가포함되므로순수심리가아니다. social15%,survey15%(중단),BTCdominance10%,GoogleTrends10%;중단분재배분/정확함수/역사구성변경불명. 다른자산자료/개별트윗을수집하지않는다. 공식extremefear매수·greed조정설명은가설이지순익증거아니다.

Q132 Bourghelle/Jawadi/Rozin2022 JEBO196294–306, DOI10.1016/j.jebo.2022.01.026, HAL14쪽PDF SHA99206aaaebb37a1cf60a50fe9aa78f2dec2d71e4c975bed1c18c5b265b5b6258. 자료/정의/전체VAR·체제선택/표2/결론선별감사.2018Feb–2021May절대수익/Parkinson/GK와logFGI의전체모형이고미래forecastperformance는저자가후속과제로명시. FGI→절대수익p.196은'항상양방향'본문과상충. 비용·펀딩·실시간상태/계좌증거아님. 우리는원문regime/최적cutoff를차용하지않고단순선형추가정보를반증한다. FGI가가격함수를포함하므로조건부추가예측을통과해도심리의인과효과라하지않는다.

## 동결 자료와 가용 시계

- 공식 `https://api.alternative.me/fng/?limit=0&format=json`, 2026-10-03T09:02:43Z확보 `data/btc-web-20261003/q131-fng-history.json` SHA **67b25d3d98f5a46c90868cdc9f3119dc24d264989fa8347d35d9cbdaf174f4ff**. 3163일/2018Feb1–2026Oct3,현재timestamp모두00UTC. latest10별도응답값/분류/시각10행일치. 누락2018Apr14–16/2024Oct26을채우지않는다. 값0..100정수허용(관측5..95),분류문자열은기록만하며피처/선정에쓰지않는다.
- 자료품질만감사했고새FG 피처·적합·PNL은아직계산하지않았다. 연구입력은2020Jan1–2026Sep1배타끝. 원응답그밖의값을보관해도피처·목표/학습은사용하지않는다. 새정규화와독립parse결과SHA를후속자료동결커밋에추가하며전략명세는바꾸지않는다.
- `data/btc-cashflow-20261003/daily.json` SHA **30fc996715649844cb1dc224a88b60f07e6cf9e0e211722b44ec8579252190cf**의spot일별quote turnover만재사용. independent-audit SHA68d4439905e4122e11bd29640450be8e222ccf5ef5f821b2a68d9032812bac37,prepare-audit SHAc7f6082c497607c834abef84768a6f8ed70a7c970940ff873cb2fe0573076509. 현물16무효일(31시간누락/8문제시간·3zero포함)/1공식일봉불완전표본의기존mask불변,재수집/기존실험재실행없음.
- BTC가격/실제funding/mark는기존 `data/search-1458/market.json.gz` canonical SHA9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4. 현물zero mask `data/btc-venue-20261003/masks.json` SHAbfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd. 완료현물23h close/time/양가격만사용. USD와USDT동일시/다른코인없음.
- 현재time_until_update는다음00UTC와맞지만공식문서2019예제는05UTC/현재과거응답은00UTC다. 이timestamp가당시최초공표/완료시각을증명하지않음. 현재사후빈티지·방법변경은미복원이다. **일D의FGI와시장집계기본가용 D+2일00UTC**:완료뒤여유1일,추가stress+7일. 월요일T에최신일D=T−2일(추가지연은T−9일). 과거전체실제수신시각을재현했다거나이여유가빈티지문제를해결한다고말하지않는다.

## 완전히 사전고정한 피처

각월요일T00UTC,source시각으로2020Jan6부터2026Sep1배타끝. 기본D=T−2일. close C_d는day d의마지막완료현물1h종가(끝d+1일−1ms),zero mask제외.91개연속close C_(D−90)..C_D모두양수/유한/정상끝시각;기간내90개일별quote(D−89..D)전부기존valid/양수/유한이어야한다. FGI도D−6..D의7달력일모두원자료존재/정수0..100. 하나라도실패하면4모형모두동일피처행무효·보간/ffill안함.

- r30=log(C_D/C_(D−30)),r90=log(C_D/C_(D−90)).
- lv30=log(sample std(ddof1) of30daily logreturns),lv90=log(sample std of90returns). 연율아닌일std의로그. std0/비유한은결측,로그용epsilon안넣음.
- dd30/dd90:해당31/91종가의시간순최대고점대비이후종가하락률max(1−C_b/max_(a≤b)C_a). 마지막날현재drawdown만이아님·범위0..1.
- qratio=log(mean(최근30일quote)/mean(최근90일quote)),USDT quote금액을그대로사용·BTC가격을다시곱하지않음. 가격변화에의한규모효과가포함되므로수량유입/개인매수로해석않음.
- g=(mean(7일FGI)−50)/50,범위[−1,1]. 50은공급자척도중앙을표현할뿐매매임계값아님. FGI0/100도그대로유효,극단시그널선정/로그변환/전표본정규화없음.

30/90일은공식지표의선언비교창이고7일평균은다음주목표의고정주기평활이다. 계수나성공여부에따라창을바꾸지않는다.7시장통제로공식비공개함수를완벽하게제거했다고주장하지않는다. 원시91종가·90quote·7FGI와날짜/가용/무효이유보존.

## 학습·가상계좌 전부

목표 y_U=log(C_(U+7d−1day)/C_(U−1day)),즉신호UTC직전완료종가에서다음주UTC직전종가. 104달력주 U=T−105w..T−2w,완료labelend≤T−1d·최소52공통유효주. 일별재추정/새튜닝없음. centered SVD OLS·계수무제약,달력1주 HAC(Bartlett.5,n/(n−k));결측주를붙여HAC를만들지않음. rank부족/비유한은모형무효. 학습계수/공분산/원피처/현재예측μ·SE/label마지막시각보존.

1. **FG_INFO primary**:intercept+r30+r90+lv30+lv90+dd30+dd90+qratio+g.
2. FG_MKT:intercept+7시장통제,FGI제거의핵심대조.
3. FG_SENT:intercept+r30+r90+g,위험/거래량통제부족시지표처럼보이는효과와분리.
4. FG_PRICE:intercept+r30+r90.
5. FG_INV:INFO와같은주/사건에서만반대방향,독립재학습없음.
6. FG_TREND:기존E_SPOT방향/20일위험그대로·원저장일수익/주요회계항등검사.

예측|μ|>SE+log1p(.0023 if μ>0 else .0013)일때signμ. INFO는추가로δ=μ_INFO−μ_MKT와μ_INFO동부호(δμ>0,|δ|>1e−12). gate미달·자료/모형무효는기존E_SPOT추세max(0,6sign평균)에복귀. 각대조는자기gate,INV같은INFO발동주의반대. 주의방향고정/일위험만갱신,period가주중시작이면이전월요일의완료판단이용. 원래current20일현물daily로그std×sqrt365 위험min(1,.20/vol),risk10=.10;위험준비부족weightsNone보유유지. 현물롱/USDT무기한선물숏/현금중하나·양다리없음/gross≤1.

6×6(base,cost_x2,delay1,delay24,risk10,data_delay7)×2=**72조건계좌**. 주2022Jan1–2026Jan1/최근2026Jan1–Sep1,각1000USDT. 기존불변원장 `btc_target_ledger.py`:sourceT+1h시가(+추가지연),원래목표유지·spot10/perp5bp+불리impact1.5bp,실제funding×hourmarkopenproxy,postcost12회/.00001/.001step·5/50USDT최소/선물축소예외·5%p조절밴드·atomic전환·종료dust비용·무차입. 시간DD·불리한시간극값5%margin. 실제호가/부분체결/역사규정/순간청산/세금/운영비미복원.

## 변경하지 않을 통과 기준·검산

기본 주순익>52.838713%,DD≤13.561952%,vol≤13.343621%,Sharpe≥.8,4년중3양수·보유구간≥20;최근순익>4.628391%,DD≤10.450946%,vol≤16.520409%;담보위반0양기간. base/cost_x2/delay1/delay24/data_delay7양기간순익>0. **INFO순익이MKT/SENT/PRICE/TREND각각양기간초과·DD≤MKT양기간·공통MSE<MKT및PRICE양기간**,공통예측주최소52main/20recent. 대조/기간/위험·지연사후승격없음.

일순수익·각네대조차7/14/28일원형블록2000회95%CI,유효/무효/변환/공통예측/전계좌/선정실패보존. 이미본개발/현재빈티지이며새OOS아님. 논문결론권위·검산통과는전략성공아님.

공식FGI parse/동결·재사용spot quote/시세SHA→합성미래교란/30·90완료/7FGI범위·누락/단위·scale/dd/가용D+2와+7/104·52/purge/동일학습/HAC/주방향·일위험/수량·funding·지연→구현커밋→성과。別독립rawCSVquote·정규방정식HAC/계획/폐형식수량·무거래/Decimal원장·연도·DD·funding·MSE·선정CI·항등→새72만소켓차단→최소Pages/익명확인. 출처Alternative.me를지표표시/자료옆에명시,공급자와자체변환구분. 논문PDF미재배포. 이한실험으로전체연구종료하지않는다.

### 성과 전 정규화·독립 자료 동결

`data/btc-sentiment-20261003/daily.json` SHA **e366fcfcf63483c1c93c9052fa40655cc4e2daa3ef2add578cf4473860b2864a**. 고정기간2,435일 중2,434관측/2024Oct26누락1일을명시적무효로보존. 원시전체3,163행의Decimal정수/범위/UTC고유성,고정기간값2,434개,별도10행응답을독립대조했다. 미래9월이후행은정규화에없음. 공식성분공식·최초공표시계검증은아니다. 기존16현물오류일이나90일창을줄이지않으며따라서과거훈련·평가가능주도줄어들수있다. 이자료검사에는새FG 피처·적합·수익계산이없었다.

### 성과 전 구현 경계검사

18합성검사 통과: D+2/+7·91종가/90quote/7FGI정확창·30/90수익/표본std·화폐/거래량단위불변·FGI0/50/100·결측/범위/비정수/늦은가용·미래가격/FGI/volume/target교란·완료시계/0vol·회복뒤최대DD·104/52/common/purge·계수양음무제약·랭크/HAC달력틈·비용/추가정보gate·반대대조·주중시작/일위험·자료무효core/위험결측보유·펀딩부호/비용/지연source를검사했다. 원시자료·룰변경없음,구현커밋뒤새72계좌만계산.
