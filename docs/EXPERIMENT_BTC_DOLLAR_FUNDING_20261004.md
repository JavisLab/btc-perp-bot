# BTC 외부 달러 조달 압력 · DF72 성과 전 명세

## 경제 질문·범위

**담보부 overnight 현금조달금리 SOFR와 은행 unsecured EFFR의 차이**가 은행금리 수준·BTC 자체 settled funding·가격을 통제한 뒤 다음7일 BTC수익에 음의 추가 정보를 주는가? 외부 중개기관 자금조달 마찰이 BTC 위험수용능력을 제한할 수 있다는 자체 조건부 반증이다. 해당 금융기관이 BTC에 실제 자금을 공급했거나 담보/청산이 관측되었다는 뜻이 아니다. repo담보 수급·분기말 규제·시장구조·정책시행도 차이를 설명할 수 있다. 단순 정책금리 변경인 기존 M_RATE, BTC계약간CD 차이와는 **별도의 공개 거시 금융가격 정보**이며, 기존창/부호/레버리지 재조정이 아니다.

Q338 Augustin/Rubtsov/Shin의BTC선물도입연구는short제약·arbitrage마찰완화가가격동조에미친효과이지SOFR로미래BTC수익을예측한논문아니다. Q31/Q29의BTC차익자본제약도기전동기일뿐본규칙의성과증명아님. 우리음의부호가설이틀릴수있으며부호교체로구제하지않는다.

**BTCUSDT perp만** 오프라인 가상 롱숏 체결. SOFR/EFFR는BTC의macro입력뿐,채권·금리·외환·다른코인포지션/차입/개별repo거래 없음. 실계좌/키·지갑/주소/주문/서명/입출금/실서비스/유료/하위에이전트 없음. 모든BTC역사는반복개발자료,미사용OOS아님. DF_INFO만주규칙/유리한대조승격없음.

## 공식 입력·수집·시계

NYFed public `https://markets.newyorkfed.org/api/rates/secured/sofr/search.json` 및 `.../unsecured/effr/search.json`. 고정 **2019Dec..2026Aug의81월×2종류=162개** startDate=월첫날/endDate=월마지막날UTC문자열 조회. start/end관측일범위포함. 요청2초이상간격; 429/5xx는Retry-After 또는최소120초후최대2재시도,403우회0. 원응답bytes/SHA/요청시각/상태와모든부가필드보존. 기존Q332/336/339/340는부분주표본이라월응답을대체하지않고독립겹침비교에만사용한다. 범위/타입/중복/날짜/유한값/순서/월행수(0..23)검사,빈월도보존. 원응답은내림차순,내부canonical은오름차순으로정규화. 전체historical rate조회일뿐가격성과계산은자료동결전없음.

정확한필드는 실제JSON `refRates[].effectiveDate,type,percentRate,revisionIndicator`다. Q343공식YAML이rate필드를percent라고명세한것과다르므로**관측된percentRate**를사용한다. 단위는연율퍼센트(예3.65%=3.65),미국일중시각없는effectiveDate는관측일이지가용시각아님. 0/음수유한rate도유효,소수정밀도Decimal문자열보존. 주말effectiveDate/다른종류/중복/월밖날짜/비유한은hardfail. revisionIndicator빈값/Y는그대로보존(당일수정가능);다른flag 또는비어있지않은footnoteId는해석미확인으로해당행무효. percentile/volume/targetrange로사후필터·신호선택없음.

Q328/333: SOFR volumeweightedmedian국채담보현금조달비용/약08ET, EFFR은행자금거래/약09ET공표. 전영업일거래가다음영업일에알려지고휴일지연. 당일14:30ET의1bp초과정정,SOFR당일한정/EFFR extraordinary예외. SOFR SIFMAfullclosure와EFFRFedholiday가다를수있다. 별도분기지연수정통계는가져오지않으며일별API현재빈티지도완전한최초공표증거아님.

판단월요일T00UTC. 기본 **C=T−7日**,추가data_delay7은C=T−14日. effectiveDate가 [C−7日,C)인각종류관측을사용,관측일이최소7日이상오래된자료만쓴다. 이buffer는정상발표/당일정정에대한보수적가정이며비상정정·과거수정없음을증명하지않음. 주내SOFR/EFFR **날짜집합이정확히같고3..5개**,모든선택행유효일때만공통피처유효. 한쪽휴일차이·missing이있으면그주무효,교집합만취해구제/forwardfill/휴일값복제/0대체없음. 같은provider양쪽이동시에빠진날은이검사만으로완벽탐지못하며원응답달력/일수보존해범위를밝힌다.

E=선택동일일EFFR percentRate단순평균(연율percentage points), **M=100×mean(SOFRpercent−EFFRpercent)**(연율basis points). 동일한일집합/동일가중치,거래량가중아님. 배율을직접투자수익·채권레버리지로해석안함. extra7는새거시 E/M 둘만이동하고현재BTC가격·settled funding는고정한다.

F=(365/7)sum T직전7일BTCUSDT실제settled21개,nominal8h각정확1개/actualtimestamp<T,현재T및T+ms제외. r7/r28는T−28..T 29개완료BPUTC일경계1h종가모두유효. 미래label=ln(P_(T+7d)/P_T)별도. 기존marketcanonical9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4와329시장/80perp독립영수증재사용,옛전체재감사안함. zeroexecutionhour1730145600000제외.

## 학습·규칙

FIRST2020Jan6..2026Sep1배타월요일. 4모형동일현재fullfeature·동일유효과거학습행. U=T−105週..T−2週(104calendar주),label_end≤T−1日,min52. centeredSVD무제약OLS·달력1주HAC/Bartlett.5,n/(n−k),rank/nonfinite무효. 미래fit/전체표본선정·누락주압축·계수0clipping없음.

1. **DF_INFO** intercept+r7+r28+F+E+M. βM<0,|μ|>SE+ln1p(.0013),δ=μINFO−μBANK,|δ|>1e−12,δμINFO>0이면signμoverride.
2. DF_BANK intercept+r7+r28+F+E. βE<0 및자기비용SEgate.
3. DF_GAP intercept+r7+r28+F+M. βM<0 및자기비용SEgate.
4. DF_PRICE intercept+r7+r28+F. 자기비용SEgate. 명칭과달리기존BTCfunding포함.
5. DF_INV INFO와같은발동방향만반대.
6. DF_TREND 기존signed6trend−1..1의pureBTCUSDTperp.

모든gate실패/현재피처·모형무효는signed6trendfallback. 다음월요일전까지override유지/위험매일갱신,spot20日risk는정보뿐BS체결0. 위험무효HOLD. 실제조달shock인과효과/통화정책surprise라고명명하지않음.

## 72계좌·비용·관문

6규칙×base/cost_x2/delay1/delay24/risk10/data_delay7×main2022Jan1..2026Jan1/recent2026Jan1..Sep1=72,각1000USDT. 기존불변btc_target_ledger:기본T+1h시가·추가1h/24h에당시목표고정,perp편도5bp+1.5bp불리impact(cost2둘다2배),risk20%(stress10),명목목표≤1,.001BTC/min50USDT·감축예외,5%pband/postcost12회/최종청산. 실제BTC펀딩×hourmarkopenproxy·시간DD/longlow-shorthigh불리margin5%. 현금이자0,repo/EFFR차입금리는가상계좌에부과안함(대출/채권포지션없음). 호가·depth·부분체결·과거규정·정확강제청산·운영비·세금미복원.

固定 mainreturn>52.838713%/DD≤13.561952%/vol≤13.343621%/Sharpe≥.8/양수연도≥3/episode≥20;recentreturn>4.628391%/DD≤10.450946%/vol≤16.520409%;margin0둘. INFO base/cost2/delay1/delay24/data_delay7 각각양기간순익>0. INFO net>BANK/GAP/PRICE/TREND각각양기간,DD≤BANK양기간,MSE<BANK&PRICE양기간. commonforecast≥52main/20recent/coverage≥80%,βMmedian<0둘,override≥20週main/5週recent. 전부통과해도역사후보일뿐전진·미사용/실행증거아님.

기본일수익+4대조차이7/14/28日원형block2000회95%CI·모든조건/실패/모형·원자료·발동·결측보존. 부호변경/사후후보교체/지연최고값선택/기준완화금지.

명세commit→162월응답/별도Decimal원시/4기존probe겹침/달력·단위감사/SHA동결→인과·buffer境界·delay7·비대칭휴일·동일日mask·금리単位/미래label·양방향계좌합성/구현commit→최초72→별도정규방정식HAC·원자료피처·계좌·선정·CI독립검산→socketbyte재현→승인Pages최소새공개/실제값·다운로드→다음근거조사. 검산성공≠전략성공,회차/45분/단일완료로목표종료안함.

## 첫 성과 전 자료·구현 동결

사전bf1ca9f후162월원응답/메타独立Decimal일치,SOFR1685/EFFR1695행,빈월0/무효행0. 기존4소량probe22원행부가필드까지정확일치. SOFR-only0, EFFR-only10일(별도영수증날짜전부보존/휴일정책차이가능성);해당주를동일날짜집합관문대로무효처리하며교집합재표본화없음. 요청최소간격2.000067949초. 25합성인과·7日buffer/추가7·금리단위/비대칭달력·양방향비용펀딩·수량검사통과,실제회귀/수익은아직0.
CanonicalSHA `e5070c9d570d7af17c093b5a4dbbc075e07b90cbb816c4ad44baf3243d3e2a33` / gzipSHA `5ab1df19eddd1f92480b4cd629c487c375851a6a3e65f4b1989a4d25f59617d4`. 규칙·관문변경없이해시만동결,이구현커밋뒤최초72계좌를계산한다.
