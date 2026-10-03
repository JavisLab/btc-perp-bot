# BTC 이동 물량의 연령 정보 · 성과 전 사전명세

## 경제 질문·원문·독립성

**이번 주 실제로 이동한 BTC의 평균 보유기간이 이동량과 이미 발생한 가격변화를 통제한 뒤 다음 주 BTC 수익에 추가 정보를 주는가?** 오래 보유된 물량의 활성화는 공급 변화일 수도 있지만 수탁 이전·자기전송일 수도 있고, 가격 상승의 결과일 수도 있다. 방향을 미리 음수로 단정하지 않는다. 기존 VA_INC의 MVRV 재고가치, NA_INFO의 주소 건수, BQ_INFO의 혼잡·수수료, CF_INFO의 거래소 순체결흐름과 다른 **이동 물량의 연령 구성** 질문이다. CVDD의 미래고점 선정·장기 바닥 임계값을 재사용하지 않는다. 아래는 원문 복제가 아닌 자체 단순화이며 기존 실패의 문턱·창·레버리지 구제가 아니다.

- Q117 Smith2018 `Bitcoin Average Dormancy: A Measure of Turnover and Trading Activity`, Ledger DOI10.5195/ledger.2018.99. 확보판은 [arxiv1712.10287v2](https://arxiv.org/abs/1712.10287), 2018Feb8·14쪽 저자판, SHA44f697645974b8060ffffdb409b638d71c5107b4437634e2987e669cb278e39f. 정의/본문1–11쪽 위주 텍스트를 읽었으며 모든 그림의 독립 수치감사는 아니다. D=ΣBTC×age, B=Σ이동BTC, D/B는 **이동한 코호트**의 가중 평균 연령이지 전체 BTC 재고의 휴면기간/통화속도가 아니다. 원문의 OXT CDD와 change 제외 추정거래량 분모는 이번 raw spent-output 분모와 같지 않다. 2009–2017Nov27 관측, 30/90일 그림·가격≥$1000 사후 하위표본 상관 .68은 선행 순익이 아니다. 큰 단일 거래가 일 CDD를 지배하며 내부이동·오프체인·Little법칙의 정상성 제약이 있다. 개별 거래/주소/지갑을 조회하지 않는다.
- Q118 Llanos2026 [Open Bitcoin Metrics](https://arxiv.org/abs/2607.03124), v1 July3, SHA c1fc9e1a691621e832e6bdffeb8150117124cd89418d410f8cd9348d665d2af6, 200쪽 중 소개·시계·indexer·CDD/휴면/이동량·배포/한계 및 해당 지표 README만 선별 감사. 모든 부록/노드 결과를 재현한 것이 아니다. raw 입력의 spent value는 비Coinbase 입력이 소비한 이전 출력의 BTC 합, CDD는 value×max(0,(지출블록시각−생성블록시각)/86400). 자기전송·change·수탁재편 포함, 소유주/거래소 매도를 식별하지 않는다. 음의 겉보기 연령은0, 지표 분모0은NaN. 같은 공급자의 비율 항등식 통과가 독립 체인 재구성은 아니다.

## 고정 출처·가용 시계·품질 정책

허용 자료는 공개 BTC **일별 집계 CSV만**이다. 외부 코드 실행/전체노드 구축/개별 거래 조회 없음. [공개 저장소](https://github.com/diegorllanos/open-bitcoin-metrics)의 정확한 commit **ab99e2609a257dfc0e1e4c7ec21708930909ec19**(2026Oct3 02:52:31UTC)을 동결했다. CDD, spent value, dormancy, block count, transaction count 5파일만 사용한다. 데이터/문서 CC BY4.0: 원저자·지표·SHA·변환 여부·라이선스를 공개한다.

- CDD SHA276b4d34599c9c44bba10a79bab4f22c97d09eeee036414e1e3e4828c6ba28af (BTC-days), spent SHA81c812d6778d5d857c77c6bca7504f6a840aebf93621853ca4474dbfd6afc0c3 (BTC), dormancy SHAfca7fc078523d6c9d886e2dc6aed414aeb1b1cf00529562f8aeda6b892f45e98 (days). block SHA9abcc302799fede71c6b41ae070e32f8cf46294176774c65549fea5551329350, tx SHA93de2c8a8b2f64484d53d7dae018b8808974295db9fe2fe1c0143049806e9ae7.
- [Zenodo v0.1.0](https://doi.org/10.5281/zenodo.21156871)의 공개 tar.gz SHA d5caa010dd0dfc08b6a428fe733b15265b5a159ebfe8a38c24ad6c799641a26c, MD5 99f21fe7ad4c0865949b49ecab4b4ca9와 메타 일치. 5개 CSV만 안전 추출/비교했고 코드는 읽기만 했다. 2026Jun28까지 최초 배포와 현재의 중복 각6386/6388행 **모두 값 동일**. GitHub release URL404이므로 GitHub 릴리스 자체를 확보했다고 하지 않는다.
- 과거2026Sep29/30/Oct1/2/3 5commit과 July3 archive는 모두 게시일보다5일 전 날짜까지 제공. 기본은 **일D→D+6일00UTC 가용 가정**, `data_delay7`은 추가7일(D+13). 월요일T의 최신 관측일D=T−6일 또는T−13일. 이6일은 확인한 소수 스냅샷보다 여유를 둔 연구 시계이지 과거 전기간 실제 배포 SLA가 아니다. 공급자 첫 공개가2026July3이므로 2022–2025 및 최근 전반의 CSV가 당시 존재했다는 주장을 할 수 없다. **이미 본 역사에 대한 재구성 탐색**이며 새 OOS/과거 실행가능성/불변 최초빈티지가 아니다. July3 이전 기간을 숨기거나 새 OOS라 부르지 않는다.
- raw 전체에는 초기2009 NaN/0이 있다. 새 입력은 **2020Jan1–2026Aug31**만 정규화, 관측범위 밖 보간 없음. 모든 날짜 고유·연속·정확 UTC·단위·비음수/유한/정수검사; spent>0, block>0, tx>0, CDD≥0, 0≤dormancy≤genesis부터경과일+1, |CDD/spent−dormancy|≤2e−12. 분모0·결측·불일치는 무효, 승률을 보고 메우지 않는다. 2019이후2828일 사전 비율 최대오차5.12e−13, 초기2009Sep16의1.85e−9는 공개 반올림/작은 분모 구간이며 이번 입력범위 밖으로 기록한다.
- **독립 날짜 gate**: 기존 `data/btc-mining-20261002/n-transactions.json`의 고정된 공개 Blockchain.com 일별 BTC 전체거래 건수와 OBM tx count가 정확히 같은 날짜만 유효. Blockchain 원본 SHA50756100c7848fe2a7715d39705d7de55338ffc4a9aa4db18a1e990ef7b93adb, 재수집 없음. 공통2460일 중2438일 같고,22일은 인접11쌍의 이틀합 일치(경계시계 차이와 양립하지만 원인 증명 아님). 22일 모두 및 외부 결측일 무효, 평균/인접 합으로 수선하지 않는다. 이 gate는 CDD의 독립 원시 체인 검증을 대신하지 못한다. 학습·모든 대조에 같은 유효행 적용.
- CoinMetrics BTC 공개 고정 CSV와 block count2700/2700일 동일. CM TxCnt는 Coinbase 제외/OBM 포함이나 이를 뺀 뒤에도2699일 차이; 이유 미해결. 정상화시계 공식 페이지403은 우회하지 않았다. CM tx를 이번 피처/분모/동일값 gate로 섞지 않는다. Q116 CM active-supply community probe403도 우회/유료 접근 없이 보존. 다른 출처 거래금액을 CDD 분모로 대체하지 않는다.

## 고정 피처·학습·비용 관문

매주 월요일00UTC T. 최신D를 포함하는 **7일[D−6,D]**과 그 앞 **28일[D−34,D−7]**은 겹치지 않는다. 35일 전부 세 연령/이동량 및 외부 날짜 gate를 통과해야 한다. 과거 경계 전2020이전 날짜는 없으므로 해당 초기 주 무효. A7=ΣCDD7/ΣSpent7, A28=ΣCDD28/ΣSpent28(days), **x=log1p(A7/1day)−log1p(A28/1day)**. CDD0도 양의 spent가 있으면 유효. 단순 일별 dormancy 평균이 아닌 합의 비율. 이동량 f=log((ΣSpent7/7)/(ΣSpent28/28)), BTC-native이며 USD 환산/가격재곱/전표본표준화/사후 winsorization 없음. 원시합/비율/날짜/무효사유 보존. 연령 구성과 turnover 변화를 분리한다.

가격통제 r7=log(C_T/C_(T−7d)),r28=log(C_T/C_(T−28d));목표 y_T=log(C_(T+7d)/C_T). C는 완료된 BTC spot 마지막1h 종가, 기존3개zero mask 제외. 104달력주 U=T−105w..T−2w, label-end≤T−1d, 최소52공통유효주. 매 예측 주의 유효 피처/과거 완료목표만, 미래 학습 없음. 중심화 SVD OLS, 모든계수 무제약, 달력1주 HAC/Bartlett.5·n/(n−k), 결측 주를 이어붙이지 않는다. 랭크부족/비유한이면 무효.

- DA_INFO: 1+r7+r28+f+x. **primary 고정**.
- DA_FLOW: 1+r7+r28+f (연령의 추가정보 주 대조).
- DA_AGE: 1+r7+r28+x (이동량을 빼는 대조).
- DA_PRICE: 1+r7+r28.

예측 μ가 |μ|>SE+log1p(.0023 if μ>0 else .0013)일 때만 방향 발동. INFO는 δ=μ_INFO−μ_FLOW와 μ_INFO 동부호 및 |δ|>1e−12 추가 필요. 개별 대조는 각각 자기 비용gate. DA_INV는 **같은INFO발동주** 반대방향, DA_TREND는 E_SPOT core. 무효/미달은 core, 위험자료부족은 계획보류. 매일 현재 완료20일 log수익 표본표준편차(ddof1)×√365, 위험량 min(1,.20/vol),risk10=.10. core는20/60/120 momentum+EMA8/32,16/64,32/128 부호평균 max(0,s). 주방향 고정·일위험 갱신, 부분 첫 주는 이미 계산된 직전 월요일 방향. 기본6일시계와+7의 모든 과거 피처도 각각 같은 지연 적용.

## 72계좌·사전 성공 기준·검증

6규칙×6조건(base,cost_x2,delay1,delay24,risk10,data_delay7)×주/최근=**72조건계좌**. 주2022Jan1–2026Jan1(1461일),최근2026Jan1–Sep1(243일),각1000USDT. 기존 `btc_target_ledger.py` 불변: 신호t의t+1h시가, 추가1/24h당시목표고정, spot10/perp5bp+불리impact1.5bp, 실제funding×hourmarkopen proxy;postcost12회·.00001/.001step·5/50USDT최소(선물축소예외),5%p밴드/atomic전환/종료dust비용/gross≤1/무차입/양다리없음. 시간DD·시간극값 margin5% 검사. 정확호가·부분체결·역사규정·순간청산·세금/운영비 미복원.

기본 주순익>52.838713%,DD≤13.561952%,vol≤13.343621%,Sharpe≥.8,4년중3양수,보유구간≥20;최근순익>4.628391%,DD≤10.450946%,vol≤16.520409%;양기간담보위반0. base/cost_x2/delay1/delay24/data_delay7 각각 양기간순익>0. **기본INFO 순익이 FLOW/AGE/PRICE/TREND 모두를 양기간 넘고 DD≤FLOW 양기간, 공통목표 MSE<FLOW 및 PRICE 양기간**이어야 한다. 공통예측0개는실패. 대조·지연·위험조건 사후승격 금지. 이 관문을 통과해도 최초빈티지/독립미사용기간 부재가 해결되거나 실전권한이 생기는 것은 아니다.

순일수익 및 네 대조 대비차7/14/28일 원형블록2000회95%CI. 다중개발편향 해결/독립검증이라는 뜻아님. 정규화·독립 Decimal 공개집계 감사→합성 인과/단위/ratio·분모0·경계/결측/시계·104/52/purge·HAC·관문·위험/원장검사→구현커밋→성과. 별도 정상방정식/HAC/폐형식수량/무거래/Decimal원장/연도/관문/CI·추세항등 감사, 신규72만 소켓차단 재현·최소Pages 게시. 결과에 관계없이 실패·계좌·모든비교군·출처한계를 보존한다. 이번 실험 종료는 전체 BTC 연구 종료가 아니다.

## 성과 전 자료 동결·독립 집계 감사

정규화 SHA **780b76bc69729251ee979882036f63b3e423296461fbdf017bf2d851ae35c185**. 2,435일 중2,410유효, 거래건수 불일치22일·외부집계누락3일(2025Nov13–15)은 원형 보존/무효. 원시5CSV 32,398행, 최초 공개와 중복총31,938행 값 동일. 별도 Decimal의 현재 연구구간 dormancy 비율 최대오차5.066e−13. 기존원시집계 재사용·새네트워크재수집0. 5commit 각각 종료일/배포일5일차와 SHA를 저장했다. 데이터감사 성공은 CDD 전체체인 검산이나 전략 성공이 아니다.
