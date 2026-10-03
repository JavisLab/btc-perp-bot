# BTC 가격 변화 연속성의 추가 정보 · 성과 전 고정

## 독립 경제 질문·반증·범위

같은 BTC7/28일 누적수익이라도, 28일 안에서 상승/하락일이 이어진 구성은 다음7일 수익의 방향에 추가 정보를 주는가? 작은 동부호 정보의 주의 문턱/지연 반영이라는 Q170 공개 2차요약 기전을 자체 BTC4주 규칙으로 단순화한다. Q164의 실제 기대는 Sentix 설문이고, Q167은 큰 충격에도 BTC 과소반응이 있다고 하므로 원 기전을 사실로 가정하지 않는다.

원12개월 횡단면 연구·BTC 설문·점프 논문의 복제가 아니며, 관측되는 것은 가격경로이지 주의/뉴스/정보의 실제 도착이 아니다. IC_PATH의 하루24시간 예측곡선 및 사후극값 거래나 기존 V_SRV 위험창 수정과 다르다. 성과를 보고 창·부호·관문·위험을 바꾸지 않는다. BTC-only 공개OHLCV·오프라인, 개인주소/지갑/거래기록/유료·다른자산거래/ETH연구/실전/타서비스/하위에이전트 없음. 역사기간은 반복해서 본 개발자료이며 미사용 OOS가 아니다.

## 입력과 시계

새 데이터 수집 없이 고정 BTC시장 data/search-1458/market.json.gz (canonical SHA9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4,gzip7e596342c65607453bbc86eb8c632e98eee514c06c53bec8876cefb3fd38d1a8)·329rawZIP/checksum·실제funding/mark를 사용한다. 무거래마스크 data/btc-venue-20261003/masks.json SHAbfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd 유지. NV의 온체인결측이나 RF/LQ의 일중RV 품질마스크를 가격경로에 덧씌우지 않는다.

월요일 T00UTC, 기본 cutoff=T. UTC 경계 C_u는 u 직전1h spot종가이며 close_time=u−1/양수유한/무거래mask제외를 요구한다. cutoff−28일..cutoff 총29개의 일별 경계종가가 모두 필요하고, 해당 경계봉 아닌 하루 중간의 누락을 별도 결측으로 만들지 않는다. 다음 시가가 아니라 완료 종가만 피처다. source+1h 시가 집행, +1h/+24h 추가지연은 별도. data_delay7은 모든 학습/현재피처 cutoff=T−7일,위험·label·판단일은 여전히 T. ffilling/근처봉대체/누락 무시/미래값/전체표본 표준화 없음.

## 정확28일 피처

r_i=ln(C_i/C_(i−1)),총28개 완료 일수익.
r28=ln(C_cutoff/C_(cutoff−28)),r7도같은7일. n+=양수일수,n−=음수일수,n0=정확0일수. **q=(n+−n−)/28**,0일도 분모28에포함.
s=sign(r28),연속성 c=s*q,ID=−c.
**z=r28*c=abs(r28)*q**: 동부호 일수가 많을 때 누적수익의 지속 정보를 크게 평가하는 정확 상호작용. r28*abs(q)와 다르며 그 식으로 바꾸지 않는다.
a=sum(abs(r_i)),경로효율 er=abs(r28)/a,**e=r28*er**. 0≤er≤1(부동오차1e−12확인,클리핑없음). a=0이면 전체행무효;0 나눗셈 회피 epsilon이나 다른창 대체 없음. n++n−+n0=28,합일수익=r28,ID=−s*q,z=abs(r28)*q 항등검사. 가격통화단위 배율은 모든 피처를 바꾸지 않아야 한다.

4주는 완전 주단위의 자체 고정 형성창이며 원12개월/6개월 투자결과의 복제가 아니다. 다른 길이를 비교하거나 최적화하지 않는다. q는 변화 횟수/방향 정보,e는 크기 기반 경로효율 대조라 구분한다.

## 모형·행동·비교군

1. **CT_INFO primary**: intercept+r7+r28+q+z.
2. CT_COUNT: intercept+r7+r28+q (상호작용을 제외한 일수 구성).
3. CT_EFF: intercept+r7+r28+e (가격변화 크기 기반 경로효율).
4. CT_PRICE: intercept+r7+r28.
5. CT_INV:INFO와 같은 발동 사건만 정확 반대방향.
6. CT_TREND:기존E_SPOT core·회계 항등.

주간2020Jan6..2026Sep1배타끝. Label은 T직전close→T+7일직전close. 모든4모형은 같은유효행으로 U=T−105주..T−2주의104달력주/최소52행,종료label≤T−1일. centeredSVD무제약OLS·rank/비유한무효·달력1주HAC/Bartlett.5/n/(n−k). 0/음의계수는 그대로 보존하며 fit에서 잘라내지 않는다.

INFO는 **β_z>0**,abs(μ)>SE+ln1p(.0023롱/.0013숏),δ=μ_INFO−μ_COUNT,δμ>0 및absδ>1e−12 전부 요구. COUNT/EFF는 자기 추가계수>0+자기 비용/SE gate만,INFO의δgate를 대조에 넣지 않는다. PRICE는 자기 비용/SE gate만. 실패·무효는 기존core=max(0,6추세sign평균),위험자료부족은weightsNone기존포지션유지. INV의fallback도core이며 INFO반대발동 외 사건은 만들지 않는다. 주중시작은 직전월요일 판단,주방향고정·일별 기존20일std/위험20%(stress10%)만 적용한다.

## 계좌·보존할 조건·선정

6규칙×6조건(base,cost_x2,delay1,delay24,risk10,data_delay7)×2기간=**72조건계좌**. 주2022Jan1–2026Jan1/최근2026Jan1–Sep1,각1000USDT/현금이자0. BTC현물롱/USDT무기한숏/현금택1,총명목≤1,차입·양다리없음. 기존 btc_target_ledger.py 불변: spot10bp/perp5bp+편도1.5bp불리impact,실제funding×hourmarkopen,수량step.00001/.001,min5/50USDT(선물감축예외),5%p밴드,atomic전환,postcost12회,최종dust청산. 시간DD·불리high마진5%. 호가/부분체결/과거규정/순간청산/세금·운영비미복원.

주수익>52.838713%/DD≤13.561952%/vol≤13.343621%/Sharpe≥.8/3양수연도이상/20보유이상;최근수익>4.628391%/DD≤10.450946%/vol≤16.520409%;마진위반0. base/cost2/delay1/delay24/data_delay7 각양기간순익>0.
INFO는COUNT/EFF/PRICE/TREND 각각 양기간 순익초과,DD≤COUNT양기간,공통MSE<COUNT&PRICE양기간,공통예측≥52main/20recent. 사후기준완화·대조승격·단순최대수익조건 선택 금지.

전체회귀/음의계수·공통무효/무거래/연도·역방향·6조건·기각 보존. 일수익 및4대조 차이7/14/28일 원형블록2000회95%CI. 반복개발과 선택편향을 해소하는 새로운 독립증거가 아니다.

## 실행·검증 순서

사전명세커밋→순수 가격경로의 합성경계(미래/0/결측/단위/두상호작용구분/진짜 추가항/공통purge/역부호/수량·비용) 및 구현커밋→새72성과→329BTCrawZIP 기반29경계/정규방정식·달력HAC/폐형식수량/무거래/Decimal원장·funding·마진·연도·관문·CI·추세항등 독립검산→새파일소켓차단byte재현→승인범위 최소Pages/익명값·다운로드. 원문의 실제기대·정보를 복원한 것으로 표현하지 않는다. 실패/게시완료는 전체 연구 종료사유가 아니다.
