# Hyperliquid 초기 조사

확인일: 2026-09-29. 아래는 당시 공식 문서 기준이며 실제 구현·운용 전 재확인한다.

## 접근과 개발

- 공식 온보딩은 일반 DeFi 지갑 연결 또는 이메일 로그인을 안내한다. 지갑 기반 접근이 가능하다는 점은 확인했지만, 이것만으로 모든 지역·입출금 경로에서 KYC가 없거나 이용이 허용된다고 단정하지 않는다. [온보딩](https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/how-to-start-trading)
- 공개 API 문서는 Python SDK와 메인넷·테스트넷의 API 주소를 제공한다. 자동화 개발을 시작할 수 있는 기반은 있다. [API](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api)
- 대상은 만기가 없는 BTC 무기한 선물이다. 펀딩이 있는 파생상품이지 BTC 현물 보유가 아니다. [계약 사양](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications)

이용 약관과 실제 사용자·운영 환경의 지역별 이용 가능 여부는 아직 검증 완료하지 않았다.
테스트넷 연결, 지갑 생성, 서명, 입금은 이번 조사에서 수행하지 않았다.

## 거래 비용

공식 무기한 선물 수수료표의 기본 Tier 0는 다음과 같다.

- Taker: 체결 거래금액의 **0.045%**.
- Maker: 체결 거래금액의 **0.015%**.
- 거래량 등급·할인·시장별 조건에 따라 달라질 수 있으므로 실제 적용 요율을 별도로 확인해야 한다.

진입·청산의 명목금액이 비슷하고 양쪽 모두 기본 taker라면 왕복 수수료는 약 **0.09%**다.
이는 증거금이 아닌 거래금액 기준이며, 스프레드·슬리피지·펀딩은 포함하지 않은 값이다.
잦은 매매일수록 작은 예측 우위가 비용으로 사라질 수 있으므로 비용 포함 검증이 우선이다.
[공식 수수료](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees)

펀딩은 매시간 정산되며 방향·펀딩률에 따라 지급하거나 수취한다. 항상 고정 지출이나 확정 수입으로 모델링하지 않는다.
[공식 펀딩 설명](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding)

## 증거금과 검증의 한계

자산이 유지증거금 아래로 내려가면 청산이 발생할 수 있다. 교차·격리 증거금은 손실 전파 범위가 다르다.
레버리지 설정 숫자만 보지 말고 계좌 자산 대비 총 포지션 노출을 관리해야 한다.
[공식 청산 설명](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations)

API 제공과 접근 편의는 수익성을 입증하지 않는다.
모의매매에서는 실제 체결 우선순위·지연·시장 충격을 완전히 재현할 수 없고, 테스트넷 유동성도 실거래와 다를 수 있다.
따라서 개발 가능성, 모의 성과, 실제 운용 성과는 구분해서 보고한다.
