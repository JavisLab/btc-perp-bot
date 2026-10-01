# 최신 전략 문헌·실행성 조사 (2026-10-01)

검색 범위: 2025~2026년 원문을 우선하고, 수익원의 기초 근거는 이전 연구도 포함.
검색 결과·홍보 글·커뮤니티 인증샷은 수익 증거로 쓰지 않았다.
아래는 원문/공식 문서 또는 저자 공개 초록에서 직접 확인한 범위이다.
논문 수익률은 **우리 계좌의 기대수익률이 아니다**. 연도·시장·위험·비용·데이터 범위가 다르다.

## 전략군 비교

| 전략군 | 수익 원천 가설 | 확인한 근거 / 문제 | 이번 판단 |
|---|---|---|---|
| 다중기간 추세·돌파 | 느린 정보 반영·지속적 수급 | 추세 문헌은 있으나 최근 다자산 고성과를 BTC 단일에 이식 불가. 실제 펀딩이 장기 롱을 잠식할 수 있음 | 현물/선물/양방향·돌파를 구분해 정량 비교 |
| 비용인식 ML | 조건부 예측이 실행비용보다 클 때만 거래 | 2026 연구의 필터 원리는 검증 가능. 발표 성과의 원자료 출처·펀딩 누락은 별도 문제 | 고정 XGBoost와 단순 Ridge를 동일 워크포워드로 비교 |
| BTC–ETH 상대가치 | 일시적 가격관계 이탈의 정상화 | 2026 페어 연구는 안정성 선별을 강조. 높은 상관은 공적분/수렴 보장이 아님 | 제한된 두 자산 사례만 실험, 전체 페어 전략 대표로 주장하지 않음 |
| 현물–무기한 캐리 | 레버리지 수요자가 지불하는 펀딩 | 경제적 지불 주체는 명확. 실제 BTC 수량·베이시스·담보·양다리 비용 필요 | 단순 과거 연율 산술을 넘어 바 단위 모형으로 비교 |
| 거래소 간 펀딩 스프레드 | 시장 분절·자금이동/담보 제약 | DEX 합성률을 쓰는 연구와 실측 연구를 구분해야 함 | 동시 호가·두 거래소 담보·정산 이력 부족, 지금 실전 후보로 승격하지 않음 |
| 횡단면 모멘텀 | 코인 간 승자/패자 수익률 차이 | 2026.9 사전규칙·비용 포함 재검증에서 통계적 우위 미확인이라는 반대 근거도 존재 | 상장폐지 포함 시점별 전체 유니버스 없이는 상위 생존 코인만으로 재현하지 않음 |
| 5~15분 반전 | 유동성 공급 보상 | 2026.8 연구는 통계적 반전과 포착 가능한 순이익을 분리. 신호 크기가 소액 계좌 비용보다 작음 | 단순 반전 매매를 구현 우선순위에서 제외 |
| 주문장 마켓메이킹 | 스프레드·유동성 공급 보상 | 재고·역선택·대기열·지연이 핵심. OHLC 접촉=체결 가정은 부적절 | 실제 호가/체결 자료 축적이 먼저. maker 전량체결 수익곡선 금지 |
| 그리드/물타기 | 횡보 재고 회전 | 실현 그리드 이익과 보유 재고 손실을 합쳐야 함. 범위 이탈 때 손실·자본 소진 | 승률만으로 후보 채택하지 않음. 마틴게일 배제 |
| 옵션 변동성 보험료 | 꼬리위험을 떠안는 대가 | 위험 프리미엄 연구는 존재하지만 옵션 호가·IV·헤지 경로·증거금이 필요 | BTC 선물만의 자료로 수익을 추정하지 않음; 다른 상품·위험 형태 |
| ETF/온체인·뉴스 신호 | 시차 있는 자금흐름/정보 | 당일 동시상관과 거래 가능한 미래예측은 다름. 공개 시각·수정 이력 검증 필요 | 발표 시각이 보존된 데이터 확보 전 정량 순위 제외 |
| LLM/RL 직접 매매 | 복합 정보/정책학습 | 2026.9 전진 벤치마크에서 백테스트 성과가 실전으로 이전되지 않는 사례 | 언어모델을 수익 보증 장치로 삼지 않음. 이번에는 수치형 저복잡도 모델부터 |
| HLP 등 프로토콜 운용 | 마켓메이킹·청산·수수료·대여 수익 | 외부 운용 구조·예치 제약이 있고 손실 공유. 개인 봇 전략과 다른 상품 | 예치/매매하지 않음. 표시 APY를 자체 전략 실적으로 비교하지 않음 |

## 원문별 근거와 한계

### S01 · 비용인식 머신러닝 (2026.6 공개, 원문)

[Bysik & Ślepaczuk, Machine Learning-Based Bitcoin Trading Under Transaction Costs](https://arxiv.org/html/2606.00060v1).
거래비용을 넘어서는 예측에만 포지션 변경을 허용하는 원리를 검토했다.
논문 §3.1은 2017.12부터 Binance USD-M 선물 자료라고 설명하지만, [Binance 공식 출시 공지](https://www.binance.com/en/support/announcement/detail/360033314152)는 2019.9 출시를 확인한다. 그 이전 자료가 무엇인지 원문 설명만으로 해소되지 않는다.
§6~7은 펀딩·호가·부분체결 미포함 및 수동 보유 대비 통계적 우위 불확실성을 명시한다.
따라서 발표된 높은 연율을 재현 가능 수익으로 인용하지 않는다. 우리 실험은 2020 이후 검증된 자료·실제 펀딩·고정 소형 모델을 사용한 **독립 가설**이다.

### S02 · AdaptiveTrend (2026.2, 원문 / 미재현)

[Bui & Nguyen, Systematic Trend-Following with Adaptive Portfolio Construction](https://arxiv.org/html/2602.11708v1).
6시간 신호, 월별 종목 선별, 롱/숏 배분을 결합한다. 저자 보고 Sharpe 2.41을 우리 기대치로 삼지 않는다.
§4.2의 8시간 펀딩 처리와 §5.6의 하루 4회 펀딩 설명이 맞지 않는다. 공개 코드/시점별 전체 종목·상장폐지 장부를 원문에서 확인하지 못했다. 많은 선택·조합을 거친 결과이므로 BTC 단일의 간단한 6시간 규칙으로 복제했다고 말할 수 없다.

### S03 · 초단기 반전 (2026.8, 원문)

[Kitron & Wengrowicz, Short-horizon mean reversion in cryptocurrency markets](https://arxiv.org/html/2608.21888v1).
방향 예측의 통계적 유의성과 거래 경제성을 분리한 점이 유용하다. 저자 분석의 gross 이익은 가장 선택적인 경우에도 거래당 약 1.3bp로, 저자가 둔 최저 왕복 현물 비용 5bp에 못 미친다. 전체 표본·생존 종목 선택 등의 한계도 명시한다.
이는 모든 평균회귀를 부정하는 결과는 아니지만, 단순 직전 봉 반전 신호를 소액 taker 전략으로 채택할 근거는 약하다.

### S04 · 횡단면 모멘텀 비용 포함 재검증 (2026.9, 저자 설명·초록)

[Arefev, SSRN 7404139](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7404139), [저자 연구 페이지](https://karaptic.com/blog/cross-sectional-momentum-net-of-costs/).
832개 아카이브 종목을 대상으로 사전 고정한 두 구성을 조사하며, 순수익 스프레드의 유의성을 확인하지 못했다고 보고한다. 저자도 미심사 프리프린트임을 표시한다. 독립 실행/원자료 감사를 수행한 것은 아니므로, 오래된 광범위 gross 모멘텀 성과의 반대 근거로만 취급한다.

### S05 · 페어 트레이딩 (2026.2 게시, 저자 초록만 확인)

[Stoikov 외, Pairs Trading in Crypto](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6188418).
500개 이상 코인의 2년 시간별 데이터에서 상관·구조 메타정보·안정성으로 선별하고 Hummingbot을 이용한 실거래도 보고한다. 전문 PDF는 이번 접근에서 확보하지 못해 정확한 비용·성과·생존편향 처리까지 확인했다고 주장하지 않는다. 우리 BTC–ETH 사례는 그 500개 선별 과정의 복제가 아니다.

### S06 · 마켓메이킹 (2025 게시, 저자 초록)

[Stoikov 외, Market Making in Crypto](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5066176).
재고 위험을 조절하는 실제 실행 연구의 방향을 검토했다. [Hyperliquid 시장조성 문서](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/market-making)와 대조한다. maker 수수료는 taker보다 작아도 체결 확률·역선택이 없어지는 것은 아니며, 현재 시간봉 자료만으로 해당 우위를 검증할 수 없다.

### S07 · 캐리의 경제적 원천 (BIS, 2025.10 수정판 원문)

[Schmeling·Schrimpf·Todorov, Crypto Carry](https://www.bis.org/publ/work1087.pdf).
레버리지 수요와 제한된 차익거래 자본이 선물 프리미엄을 유지할 수 있다는 근거다. 이 연구의 만기 선물 베이시스와 수시로 달라지는 무기한 펀딩을 같은 확정 수익률로 취급하지 않는다. 마진 제약과 가격 급변은 차익거래의 일부다.

### S08 · CEX–DEX 캐리 위험 분해 (2026.8, 전문)

[Pindza, Digital Finance](https://link.springer.com/article/10.1007/s42521-026-00213-3).
§4.1의 전체 표본은 **합성 DEX 펀딩률**을 쓴다. 별도의 실제 dYdX v4 자료 검사가 있지만 더 짧은 기간이며 전체 표본이 실측 DEX 자료로 바뀌는 것은 아니다. 저자도 통제 시나리오로 읽을 것을 명시한다. 위험 분해에는 참고하되 Hyperliquid 차익거래 수익의 증거로 쓰지 않는다.

### S09 · 거래소 펀딩 분절 (2026.1, 공개 초록/메타정보)

[The Two-Tiered Structure of Cryptocurrency Funding Rate Markets](https://www.mdpi.com/2227-7390/14/2/346).
거래소별 펀딩·비용 차이를 다룬다. 전문 접근 실패로 실제 매매회계·동기화 가정을 모두 검증하지 못했다. 높은 표시 스프레드만으로 실행 후보를 선택하지 않는다.

### S10 · 옵션 위험 프리미엄 (2025.8 수정판, 전문)

[Risk Premia in the Bitcoin Market](https://arxiv.org/html/2410.15195v2).
옵션가격에 내재한 위험 프리미엄과 상태별 차이를 분석한다. 순수 옵션 매도 봇의 비용 포함 실현 수익 보고서와는 다르다. 위험 프리미엄은 손실 위험의 대가이며, 꼬리위험과 증거금을 빼고 수익만 비교할 수 없다.

### S11 · ETF/선물 캐리 분절 (2026.5, 전문)

[Implied ETF Carry Rates and the Limits of Arbitrage in Segmented Bitcoin Markets](https://arxiv.org/html/2605.29309v1).
ETF 옵션·보유량·CME 자료의 시장 간 차이를 분석한다. 개인의 실제 차입 가능성·거래시간·옵션 비용이 확인되지 않은 차이를 무위험 매매로 삼지 않는다. 이번 BTC 단일 거래소 실행 범위와도 다르다.

### S12 · 최신 AI 전진 벤치마크 (2026.9.28, 전문)

[Yu 외, Can AI Make Money in Crypto?](https://arxiv.org/html/2609.34510v1).
32개 기법의 과거 평가 후 일부를 모의/실거래로 진행한 연구다. 실거래 창은 2026.8.24~9.21로 짧다. 해당 창에서 4개 실거래 방법 중 수익이 난 것은 하나였고 BTC 보유를 이긴 방법은 없었다고 보고한다. 모든 AI 전략의 불가능성을 증명하지는 않지만, 백테스트 최고 점수와 전진 성과가 다름을 보여준다. 본문에 5개/4개 진출 수 표현도 혼재해 표·실거래 비교의 4개를 기준으로 읽었다. 우리 실거래를 실시한 것이 아니다.

### S13 · ETF 유입 신호 (2026.4, 저자 초록)

[Lim, The Price Impact of Spot Bitcoin ETF Flows](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6592830).
같은 날 가격과 자금흐름의 연관 및 다음날 예측을 보고한다. 313거래일 표본의 관측 시각/수정된 유입 정보가 언제 사용 가능했는지를 확보하지 않은 상태에서는 당일 종가 매매로 구현하지 않는다. 동시상관을 미래 수익으로 바꾸지 않는다.

### S14 · 연구 선택 편향 (2026.8, 저자 초록)

[Nefedov, How Much Sharpe is Illusory?](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7350238).
비용·중첩 선택·다중검정 처리에 따라 팩터 성과가 달라진다고 보고한다. 이번에는 기존 자료의 재사용을 탐색으로 명시하고, 새 규칙과 순위 기준을 계산 전에 기록한다. 초록을 넘는 독립 재현을 완료한 자료는 아니다.

### S15 · 기초 추세 연구 (원문)

[Trend-following Strategies for Crypto Investors](https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf).
매매 빈도·위험조절·현금 대기의 조합을 검토하는 출발점이다. 주로 오래된 상승 구간을 포함하며 여러 기간·비중 비교 결과다. 현물/지수 연구를 현재 무기한선물의 순이익으로 옮기지 않고, 저자 성과를 목표치로 채택하지 않는다.

## 실제 조건을 확인한 공식 출처

- [Hyperliquid 수수료](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees): 기본 BTC perp taker 4.5bp / maker 1.5bp, spot taker 7bp. VIP·스테이킹·추천 혜택을 기본값으로 가정하지 않음.
- [펀딩](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding), [오라클/마크](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices): 시간별 정산과 오라클 금액 기준. Binance 마크 시가 대용값 실험은 HL 실적이 아님.
- [청산](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations), [ADL](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/auto-deleveraging): 현물 보유만으로 별도 선물 담보가 보호되지 않음.
- [프로토콜 vault](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/vaults/protocol-vaults): HLP의 복수 수익원·4일 잠금. 외부 예치 상품과 자체 전략 연구를 구분.
- [공식 Binance 데이터](https://github.com/binance/binance-public-data): 공개 zip+체크섬, 현물 마이크로초 전환 등. 새 원자료의 실제 검사는 수집 manifest에 기록.
- [Hummingbot fixed grid](https://hummingbot.org/strategies/fixed-grid/): 범위·재고를 사용하는 규칙 설명이지 미래 수익 보장 아님.

## 이 조사에서 하지 않은 일

외부 저자의 코드 실행, 유료 데이터 구매, 지갑 접근, 실제 주문, 상품 가입/예치, 소셜 계정 로그인·연락은 하지 않았다. 공개 원자료와 로컬 연구만 사용한다. 수익률이 높은 논문만 남기거나 음의 재현을 숨기지 않는다.
