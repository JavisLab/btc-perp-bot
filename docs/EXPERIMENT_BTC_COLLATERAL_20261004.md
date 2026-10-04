# BTC 담보계약별 펀딩 차이 · CD72 성과 전 명세

## 새 경제 질문과 한계

같은 Binance의 BTCUSD_PERP 코인 담보 무기한계약과 BTCUSDT 선형 무기한계약 사이의 **이미 지급된 funding rate 차이 D**가 기존 BTCUSDT funding F·가격추세 너머 다음7일 BTC 수익에 음의 추가 정보를 주는가? 코인 담보 롱의 담보가치와 포지션이 같은 방향으로 움직여 위험청산 수요가 커질 수 있다는 **자체 조건부 crowding 반증**이다. 실제 담보·포지션·청산수요를 관측하는 실험은 아니며, 헤저 선호·계약 유동성·펀딩 공식/한도 변화·USD와USDT 시장 차이로도 설명 가능하다. 같은 거래소라는 이유로 담보의 구조적 인과효과가 식별되지 않는다.

기존 USDT 단일 funding/CF/OI/OF, TS 만기 USD선물 곡선과 달리 **새 BTC 코인 담보 PERP의 정산율**이 추가 시장정보다. 기존 창·부호·레버리지를 조정해 실패를 구제하지 않는다. Q318 Ledger 원문은 역선물과 선형선물의 담보 구조·자료 오류를 설명하지만 미래 alpha를 증명하지 않는다. Q312/Q320 Haghani/White의 공식·역사표도 설명과 가설이지 새 방향 예측 근거가 아니다. 논문 복제/차익거래라 부르지 않는다.

주규칙 CD_INFO 하나. BTCUSDT perp만 가상 양방향 체결, 코인 담보계약은 정보만/코인 거래·BTC 담보보유·현물매매 0. BTC-only 공개 aggregate와 오프라인 계산. 계정/개별trade/주소/키·지갑/서명/입출금/실주문/유료/다른종목/하위에이전트 없음. 전 기간 반복개발 역사, 미사용 OOS 아님.

## 수집·단위·가용시계

공식 public GET https://dapi.binance.com/dapi/v1/fundingRate , symbol=BTCUSD_PERP만, startTime/endTime 정수ms 포함경계,limit1000. 공식GitHub cm_futures/market.py의query 경로 확인(Q314 SHA734e517e6736fede9d483a6cd3b29ea6f9df8044cd4dd1aed60bd1406128d2df). 문서의aggregate-trade라는 복사 문구를 정산시계 정의로 신뢰하지 않는다.

**고정80달 2020Jan..2026Aug** 각 UTC월 시작~다음월시작−1ms를 2초 간격으로 조회. Q319의 정확한2022Jul 응답 재사용; 기타79신규. 초기 계약 부재의 빈 배열도 그대로 보존. 1000행 도달·범위밖·역순·중복·다른symbol·비정수ms·비유한rate는 hard failure,자동 period축소나누락보간 없음. 빈markPrice는 funding 결측 아님(코인 시장을 체결하지 않음). rateType이 있을 때 Regular이외는 명시 진단/무효, 원응답 추가필드 모두 보존. 429/5xx는최소120초또는Retry-After 후최대2재시도,403우회없음. 요청상태·원bytes/SHA·현재조회빈티지 기록. dataSeptember이후 수집 없음.

Q307공식 archive 목록48달2022Jul..2026Jun은 REST 전체 역사와 다르다. **Q321 checksum 검증 July2022ZIP90행은 REST93행 중 정확부분집합으로 마지막 하루3행이 빠졌다.** checksum통과≠월완전성. 전체실험은 REST 원시응답을 독립재구성, ZIP로 보충/합성하지 않는다. 이 입력표본비교는 피처/수익계산 전.

rate는 각 지급기간의 무차원 비율(0.0001=1bp), APR/일율/100달러계약 수량이 아님. 금액·BTC와USDT 가격을 빼는 것이 아니라 동일7일 정산율합을 비교한다. 단순연율365/7은표현만,복리이익·정산간무위험수익이라고하지않음. 과거공식변경/현재APIvintage≠당시처음게시보장.

월요일 T00UTC. 기본 C=T,extra data_delay7은 C=T−7日. 8시간 명목bucket은 관측완전성만검사: 각 u in [C−7日,C),step8h에 row의 floor(actual_timestamp/8h)*8h=u인 관측 **정확1개**, actual_timestamp<C를 먼저 적용. 21개필수, 각row 유한rate/Regular. T정산과T+ms정산 제외. floor한 시각을 가용시간으로 쓰지 않는다. 구간내 누락·중복·가변주기 발견시 해당 주 무효,결측zero/ffill/사후window변경 없음.

COIN(C)=365/7 sum(coin settled rates), U(C)=365/7 sum(USDT settled rates), D=COIN(C)−U(C). **현재F=U(T)는extra7에서도현재**, 새 차이D와COIN만7일 오래된것. D를지연할때비교대상U(C)도동일과거window라변화는새cross-contract정보에만적용. 가격 r7/r28는 현재T완료BP1h 종가와T−28..T의29개UTC일경계 모두 양수/유효. 미래label=ln(P_(T+7日)/P_T),피처와label따로보존.

기존data/search-1458/market.json.gz canonical9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4와329시장/80perp 독립감사 영수증 재사용. 전체옛자료/계좌 재검사안함. BP zero executionhour1730145600000 가격·label·체결 제외.

## 학습·주규칙·대조

FIRST2020Jan6..2026Sep1 배타의 월요일. 현재 fullfeature 무효면 4모형 공통무효. 공통유효 학습 U=T−105週..T−2週(104calendar週),label_end≤T−1日,min52. centeredSVD 무제약OLS,달력1주HAC/Bartlett .5,n/(n−k). 누락주 압축/전체표본scale/미래fit/부호제약없음. rank/nonfinite 실패는무효,계수0으로채우지않음.

1. **CD_INFO** intercept+r7+r28+F+D. βD<0,|μ|>SE+ln1p(.0013),δ=μINFO−μFUND,|δ|>1e−12,δμINFO>0이면 signμ override.
2. CD_FUND intercept+r7+r28+F. βF<0/자기비용SE gate.
3. CD_COIN intercept+r7+r28+COIN(C). βCOIN<0/자기비용SE gate.
4. CD_PRICE intercept+r7+r28. 자기비용SE gate.
5. CD_INV INFO와같은발동의방향만반대,공통fallback.
6. CD_TREND 기존 signed6trend−1..1을 양방향BTCUSDT perp에적용.

gate실패/현재피처·모형무효는signed6trend fallback,일별20日spot 위험자료는정보만,BS체결0. override 다음월요일전까지/일별risk갱신,위험자료무효HOLD. 모형부호·발동·결측/공통예측 모두보존. coin rate만높으면항상숏이아니라가격·현재F조건부신호다.

## 72계좌·비용·기각 기준

6규칙×base/cost_x2/delay1/delay24/risk10/data_delay7×main/recent=72.
main2022Jan1..2026Jan1,recent2026Jan1..Sep1,각1000USDT. 불변btc_target_ledger.py:기본T+1h시가/추가1h·24h시각에판단당시목표고정,편도5bp+불리impact1.5bp(cost2둘다2배),risk20%(stress10),총명목≤1,.001BTC/min50USDT(감축예외),5%p band/postcost12회·최종청산. USDT계약의실제funding×hourmarkopenproxy,시간DD·longlow/shorthigh불리margin5%,현금이자0. 코인펀딩을USDT원장에이중부과하지않음. 실제호가/depth/부분체결/과거규정/진짜청산·운영비·세금 미복원.

고정절대관문:main return>52.838713%,DD≤13.561952%,vol≤13.343621%,Sharpe≥.8,양수연도≥3,보유episode≥20;recent return>4.628391%,DD≤10.450946%,vol≤16.520409%;양기간margin0. INFO base/cost2/delay1/delay24/data_delay7 각각양기간순익>0. INFO순익>FUND/COIN/PRICE/TREND 각각양기간,DD≤FUND양기간,MSE<FUND&PRICE양기간. commonforecast≥52main/20recent,전체labelvalid판단주대비coverage≥80%,βD중앙<0양기간,INFOoverride≥20週main/5週recent. 전부통과해야반복개발의역사후보일뿐새OOS·실행증거아님.

7/14/28日원형block2000회95%CI:기본일수익 및4대조차이 모두보존. 최고대조/지연수익승격·기간축소·부호변경·기준완화없음. 검산통과≠전략성공.

명세gitcommit→80응답수집/독립Decimal원시·bucket감사/SHA동결→인과·공통마스크/실제ms·lag7단독·단위·결측·양방향원장합성검사/구현commit→첫72→별도정규방정식HAC/피처·원장·선정·CI검산→소켓차단byte재현→승인Pages새결과만공개·실제값/다운로드검증→다음BTC근거조사. 한계·실패를보존하며단일실험/보고/자체시간컷으로목표종료안함.
