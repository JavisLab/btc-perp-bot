# BTC 잔돈 제외 전송 비중의 추가 정보 · 성과 전 고정

## 독립 경제 질문과 범위

**BTC 가격과 전체 온체인 회전량이 같아도, 잔돈을 제외했다고 추정된 전송 비중이 높을수록 다음7일 수익에 양의 추가 정보가 있는가?** 총출력은자동잔돈/자기이동의명목적회전에크게좌우되므로추정이용가치를분리해본다. Q151의장기관계/불안정leader,Q152의가격-보안복수균형,Q156의고점이후NVT해석과불명확문턱을함께반증으로보존. 원문의가격모형/평활/순익복제가아니다. DA_FLOW의비조정이동량증가대조를다시최적화/승격하지않고 **새잔돈제외집계의추가구성정보**를검정한다.

실제상거래/순매수/고객수/지갑소유권/내재가격의식별이아니다. 제공자의정확휴리스틱·사후라벨·최초빈티지가없으므로현재공개집계기반개발검정이다. 역사BTC경로는이미본탐색자료이며미사용OOS라하지않는다. BTC만거래·공개일집계만조회·개별주소/지갑/tx/소셜/노드/유료자료/다른자산연구/실전/하위에이전트없음.

## 입력·완료·결측

- 새공개Blockchain.com BTC-only estimated-transaction-volume(잔돈제외추정A)와 output-volume(잔돈포함O) 일집계만2020-01-01–2026-09-01배타끝확보. 원시응답/URL/조회시각/메타/정수Unix초/자료해시·8일표본을보존. sampled=false/JSON. 앞서Aug1–8표본각8행/UTC00·BTC/day·0<A≤O확인,전체피처/성과미계산. CM403지표우회가아닌별도공식공개자료이며CM휴리스틱과동일하다고하지않는다.
- S(일말native공급량)는이미검산된 data/btc-valuation-20261002/coinmetrics.json의SplyCur만재사용. 2435일/현재빈티지. 기존MVRV/PriceUSD를새피처로쓰지않음. 새Blockchain total-bitcoins의불규칙727표본/92–114BTC차이를대체입력으로쓰지않는다. 정확해시는자료동결에추가.
- 기존BTC시장 canonical SHA9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4/gzip7e596342c65607453bbc86eb8c632e98eee514c06c53bec8876cefb3fd38d1a8·329rawZIP·실제funding/mark·수량원장불변. 마스크SHA bfefb3a32526cfcdf2a5b8151cbfe87f0a749986bbf4cb7d31d7c0d65cf2dfcd의3무거래시간유지.
- UTC일d는正確00UTC관측표식·하루1행·양수유한A/O/S·A≤O를요구. 중복/시각이탈/비유한/음수·0/한쪽결측/표본중복값불일치면그날무효보존. 全calendarday行을만들되무효값null,ffill/임의보간/기존다른provider로3일공백복원없음. A/O상한위반을잘라맞추지않음. 제공자집계원시항등/표본일치는독립체인재구성이아님.
- 월요일T00UTC 신호,최신D=T−2일. 일집계완료후24h여유로가정,최초게시SLA증명아님. 추가7일자료지연은D=T−9일,학습피처도동일. D−27..D 연속28일모두유효여야4모형공통피처행유효. 공급은각일양수요구하되분모는D의S만쓴다. 原endpoint가끝다음날行을반환해도Sep1이후는입력·학습에서제외한다.
- 가격피처는같은완료cutoff C_(D+1),그7일/28일전UTC직전spot종가로만계산. 정확종료/양수유한/무거래mask제외,모든29일중간가격을추가필요로하지않음. Label은T직전close→T+7일직전close,피처와label의시계를혼동하지않음.

## 정확 피처·모형·양의 부호

A28=sum A_(D−27..D),O28=sum O_(D−27..D),S=S_D. **raw=log(O28/S)**(28日비조정회전량),**share=log(A28/O28)**(추정잔돈제외비중,≤0),**adjusted=log(A28/S)**. adjusted=raw+share 항등검사,전체표본분위/표준화없음. 당일같은USD가격을곱해도이native비율에선상쇄되지만90日USD-NVTS와동일식아님. 28일은완전4주달력평활로사전고정,다른창/문턱검색없음. 가격 r7=log(C_(D+1)/C_(D+1−7)),r28도같은28일.

1. **NV_INFO primary**:intercept+r7+r28+raw+share.
2. NV_RAW:intercept+r7+r28+raw.
3. NV_ADJ:intercept+r7+r28+adjusted.
4. NV_PRICE:intercept+r7+r28.
5. NV_INV:INFO와정확동일발동사건만반대방향.
6. NV_TREND:기존E_SPOT동일core/회계항등.

2020Jan6–2026Sep1배타끝주신호. U=T−105w..T−2w의104달력주/최소52공통유효행/label종료≤T−1일. 4모형동일행·centered SVD OLS·달력1주HAC/Bartlett.5/n/(n−k),계수모두무제약·rank부족/비유한무효. 음의정보도그대로오차/계수기록하고성과뒤부호를뒤집지않는다.

INFO는 **β_share>0**,예측|μ|>SE+log1p(.0023long/.0013short),δ=μ_INFO−μ_RAW와μ동부호(δμ>0,|δ|>1e−12)전부필요. ADJ는β_adjusted>0와자기비용+SEgate;RAW는β_raw>0와자기비용+SEgate(각회전량가설의부호대조). PRICE는자기비용+SEgate만. INFO/INV는정확같은발동주만정/역. 나머지는core=max(0,6추세sign평균),risk부족weightsNone유지. 주중평가시작은직전월요일판단,주방향고정/현재일별20日가격위험20%(stress10%)는불변.

## 계좌·비용·기각

6×6(base,cost_x2,delay1,delay24,risk10,data_delay7)×2=**72조건계좌**. 주2022Jan1–2026Jan1/최근2026Jan1–Sep1각1000USDT. 現物BTC롱/USDT무기한BTC숏/현금택1·총명목≤1·현물차입/양다리없음. source+1h시가/추가1or24h·5%p밴드·atomic전환/postcost12회·step.00001/.001·min5/50USDT·선물감축예외·종료dust. 수수료spot10/perp5bp+불리1.5bpimpact·실제funding×hourmarkopen·시간DD/불리highmargin5%불변. 원시호가/부분체결/과거규정/순간청산/세금·운영비미복원.

주순익>52.838713%/DD≤13.561952%/vol≤13.343621%/Sharpe≥.8/≥3양수연도/≥20보유;최근순익>4.628391%/DD≤10.450946%/vol≤16.520409%;담보위반0. base/cost2/delay1/delay24/data_delay7각양기간순익>0. INFO순익이 **RAW/ADJ/PRICE/TREND 각양기간초과**,DD≤RAW양기간,공통MSE<RAW와PRICE각양기간,공통예측≥52main/20recent. 사후대조승격/관문삭제/최근.89%로기준완화없음.

전계좌·기각·역방향·무효·β≤0·무거래·연도·비용·지연보존. 日순익/4대조차7/14/28日원형블록2000회95%CI. 현재빈티지/선택편향해결이아님.

## 순서

명세커밋→2日집계응답수집/기존공급SHA·별도Decimal·시각/표본/항등/결측감사·동결→인과합성검사/구현커밋→새성과→독립raw329ZIP·별도normal/HAC/폐형식qty/무거래/Decimal계좌·funding·관문·CI·E_SPOT항등→새파일소켓차단재현→최소Pages/익명값·다운로드. provider추정필터자체의독립블록체인검증은하지않고한계를명시한다. 한실험/후보실패/게시완료/단일자료접근한계로전체연구종료하지않음.

## 성과 전 입력 동결 · 2026-10-03 11:06 UTC

사전명세 aeb13cc 이후 두 공개 일집계만 조회했다. adjusted 2026-10-03T10:54:06.460033Z/2428원시행/94430B, raw 10:54:07.444825Z/2434원시행/95315B. 두 응답의 Sep1행은 평가입력에서 제외. 2435일 중2425일 유효, adjusted 누락8일(2021-12-11/21/24,2023-07-14/11-14,2024-06-30/11-18,2025-06-24), raw 누락2일(2025-11-14/15). 기존 다른 지표의 누락마스크를 옮기거나 빈 날을 채우지 않았다. 사전8일 표본16값과 각각 정확일치, 최대 A/O=.4799278762581416.

공급은 사전고정 CM API SplyCur 2435일이다. 60자리 Decimal에서 CapMrktCurUSD=PriceUSD*SplyCur 전부 정확일치하나 이는 공급자 산식검사이지 독립 발행량 증명이 아니다. 이전 GitHub 공개배포본과 겹치는2335일은 **현재 API가 전부 정확히100 BTC 높다**. 이전 MVRV 비교가 공급량까지 동일함을 증명한 것으로 해석하지 않는다. Q160 공식 정의는 UTXO의 미사용 출력가치 합계이며 해당100BTC 차이의 원인/변경시점은 설명하지 않는다. BIP30/빈티지/계산법 차이를 원인으로 단정하지 않고, 두 배포본을 합치거나100을빼서 맞추지 않는다. 명세의 공급량 입력은 유지하고 차이목록을 보존한다. 공급량 계열의 최초빈티지/독립체인 복원은 검증하지 못했다.

초기 공급 산식검사는 Decimal 기본28자리 반올림 때문에 실패했다. 입력을 바꾸지 않고 정밀도를60자리로 고쳐2435항등을 검산했다. 초기/최종 로그보존, 피처/모형/성과계산 전 수정이다.

| 파일 | SHA256 |
| --- | --- |
| data/btc-turnover-20261003/raw-adjusted.json | 40d8396ab66e7550a5dbd725c0a5aaee8789f2e8bbb73b74017f8b6e0733575c |
| data/btc-turnover-20261003/raw-raw.json | 891bb8a56244c2c9f57a5f2e0cd1a4876605509e8d4a04de8a1ac3ccc9c18225 |
| data/btc-turnover-20261003/source.json | c5ca6afa23a87cd29d262bf0ac938946876032ccf6b64bad9f0dd79a4b1d93cd |
| data/btc-turnover-20261003/daily.json | dd175183838fb123c6bed86adca795e20d28ecaacdc9797b15e3c18b04003040 |
| data/btc-turnover-20261003/prepare-audit.json | f63745adaa097902fe4515ef48591a87861a9e942f5665f55150bd0bb4823cc7 |
| data/btc-turnover-20261003/independent-audit.json | 2b9bf64c8a1d4967ec6442fe5824d036429de8511feac7d6bc7a9971cc1eac57 |
| data/btc-valuation-20261002/coinmetrics.json | db696818880b69e8320e192c60eb5429a40db0ecf5845ece194a01b0524d4a61 |
| data/btc-mining-20261002/btc-community.csv | 06495ff8e643432e6948b7b4686ce44fc106217287dabdc1b38351d9ddec46c3 |
