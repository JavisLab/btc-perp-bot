# BTC Perp Bot

**가격 구조·손절·청산 계좌 연구:** [후속 대화형 비교](https://arcadot.com/btc-perp-bot/structure-lab.html). 5개 후보·70개 조건별 계좌. 채널 후보는 과거4개 연도 플러스였으나 누적+13.42%/36거래로 기준 미달, 실전 채택0개. [전체 보고서](docs/STRUCTURAL_RESULTS.md)

**가격·거래량 후속 조사:** [공개 원칙과 세 가설 검사](https://arcadot.com/btc-perp-bot/price-action.html). 58,440시간 원자료 복구·검증, 거래량 필터의 일관된 우위는 미확인. 계좌 백테스트가 아닌 24시간 사건 연구입니다.

비트코인 무기한 선물 자동매매를 연구하고 검증하는 프로젝트.
첫 거래소 후보는 **Hyperliquid**이며, 거래소와 전략은 아직 최종 확정하지 않았다.

## 목표

**현재 우선순위(2026-09-30 사용자 승인): 실제 거래보다 비용 포함 백테스트·실시간 모의계좌로 전략을 먼저 검증한다. 입금이나 지갑 연결은 필요 없다.**

장기적으로 거래·운영 비용을 제외하고 월 **150,000원**을 남겨 구독료를 충당하는 것이 목표다.
이는 희망 목표이지 예상 수익이나 매월 수익 보장이 아니다.
첫 개발 목표는 수익 금액을 맞추는 것이 아니라, **비용을 반영한 검증에서 유효한 전략인지 확인하는 것**이다.

## 현재 상태 — 2026-10-01

- **[최신 전략 비교 연구소 ↗](https://arcadot.com/btc-perp-bot/strategy-lab.html)** — 13개 전략군 조사·9개 고정 후보·120개 비교 실행. 다중기간 현물 추세는 2022~2025 +52.84% / 낙폭13.56%, 최근2026.01~08 +0.89%. **후속 연구 1순위이지만 사전 기준 미달, 실전 채택0개.** 기존 가격 경로를 사용한 탐색 비교이며 새 미사용 OOS/Hyperliquid 실적이 아니다. [비교·선정 보고서](docs/STRATEGY_COMPARISON.md) · [최신 문헌 검토](docs/STRATEGY_SOURCE_AUDIT.md)
- **[대화형 백테스트 결과 보기 ↗](https://javislab.github.io/btc-perp-bot/)** — GitHub Pages. 기간 선택·자산/낙폭 차트·전략 비교·비용/지연 진단·CSV 다운로드를 제공한다. 정적 연구 스냅샷이며 실시간 거래 화면이 아니다.
- **일봉 추세 사전 고정 검증 완료:** 외부2022~2025 평가의 T1 +6.99%, 관측 낙폭11.97%, 수익 분기7/16. 2026.01~05는−2.81%. **사전 채택 기준 미달·전진 모의운영 미시작.** 외부USDT·HL기존표본USDC는 분리. [전체 해석·자료·재현](docs/LONGITUDINAL_RESULTS.md)
- **전략 재조사:** 일봉 추세와 현물/선물 펀딩 수취 후보의 근거·한계·탈락 기준을 먼저 정리했다. 위 결과는 그 후속 실험이며 캐리는 자료/경제성 단계에서 보류했다. [원래 조사와 계획](docs/STRATEGY_RESEARCH.md)

- **v0.2 검증 환경:** `btc-research`로 공개 데이터 수집, 시간순 개발/평가 분리, 고정 3전략·2비교기준, 거래비용/지연 스트레스, 재개 가능한 가상 계좌, 독립 HTML·JSON·CSV 보고서를 제공한다.
- 최근 120일 BTC 1시간봉·펀딩 기록을 실제 수집해 비교했다. 평가 기간의 추세 −7.96%, 돌파 −6.34%, 평균회귀 +0.96%, 동일 노출 BTC 선물 보유 +3.11%. **선택 후보의 수익성은 입증되지 않았다.** [결과·사용법](docs/RESEARCH.md)
- 새 연구 명령은 지갑/서명/실주문 코드와 분리되어 있다. 이 작업에서는 실제 자금·지갑에 접근하지 않았고 장기 실행 서비스도 등록하지 않았다.

- 저장소·초기 기획 문서를 생성했고, 공개 시세 API와 공식 앱 접속을 직접 확인했다.
- 메인넷·테스트넷의 BTC 정보/호가 HTTP 조회와 WebSocket 호가 수신에 성공했다. [검증 결과](docs/CONNECTIVITY.md)
- 운용 원금, 허용 손실, 전략, 레버리지는 미정이다.
- **v0.1 프로그램 구현:** 암호화 EVM 지갑 생성·로컬 서명 확인, 계좌/포지션 조회, SDK 서명 주문·취소, 모의/테스트넷/사용자 실행용 메인넷 매매 루프.
- 실제 BTC 시세로 모의 진입·청산을 실행했다. 전략은 기능 검증용 1분봉 이동평균이며 수익성을 검증한 전략이 아니다.
- 테스트 전용 지갑을 생성했으나 테스트넷 잔고가 0이어서 거래소의 실제 체결·취소 승인은 미검증이다.
- 에이전트가 실제 자금 입금·거래·송금하거나 상시 매매 서비스를 실행하지 않았다. 사용자의 외부 송금 완료 여부는 확인하지 않았다. 출금 기능은 포함하지 않는다.
- `testnet-smoke` 명령으로 준비 상태 확인과 지정가 주문→취소→IOC 진입→reduce-only 청산→체결 내역 대조를 분리했다. 기본은 조회만 한다. [테스트넷 검증 상태](docs/TESTNET_VALIDATION.md)

## 빠른 실행

Python 3.12 이상, Linux 기준. 시스템 Python 대신 프로젝트 가상환경을 사용한다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q

# 지갑/입금 없이 공개 데이터 수집 → 오프라인 백테스트
.venv/bin/btc-research collect --days 120 --out data/btc-1h.json
.venv/bin/btc-research backtest --data data/btc-1h.json --out runs/first-backtest

# 현재 메인넷의 공개 호가로 가상 거래만 수행; 같은 파일이면 계좌를 이어간다
.venv/bin/btc-research paper --state runs/paper.sqlite --steps 6 --interval 10
.venv/bin/btc-research verify-paper --state runs/paper.sqlite
.venv/bin/btc-research paper-report --state runs/paper.sqlite --out runs/first-paper-report
```

Ubuntu에서 `venv` 생성 시 `ensurepip` 오류가 나면 `python3-venv` 지원이 필요하다.
현재 개발 서버의 `.venv`는 별도로 준비되어 있으며 위 명령의 패키지가 설치되어 있다.

지갑과 프로그램 사용법, 실행 경계, 주문 불확실성 복구는 [운영 가이드](docs/OPERATOR_GUIDE.md)를 따른다.
기능 구현과 실제 거래소 체결 검증의 차이는 [v0.1 검증 결과](docs/IMPLEMENTATION-1402.md)에 기록한다.

## 제안하는 진행 순서

1. 공개 API·거래 화면 접속을 확인한다. **완료.**
2. 지갑/서명/주문/취소 코드를 구현한다. **구현 및 로컬 검증 완료. 테스트넷 자금 확보와 거래소 체결 검증은 미완료.**
3. BTC 데이터를 수집하고 설명 가능한 전략을 비용 포함 백테스트·모의매매로 검증한다. **환경과 첫 비교 완료. 장기 관측과 새로운 기간의 검증은 미완료.**
4. 실제 자금 운용을 검토할 때 원금·손실 한도·성과 기준을 정한다. 당장 수익 목표를 맞추는 최적화는 하지 않는다.
5. 실거래 실행과 자금 이동은 사용자가 직접 관리한다. 현재 수행 범위는 조회·개발·검증이다.

테스트넷은 API 기능 검증용이며, 그 수익률을 메인넷에서의 수익성 증거로 사용하지 않는다.
구독료 목표를 채우기 위해 거래 횟수나 레버리지를 자동으로 늘리지 않는다.

## 문서

- [전략 비교 연구소 — 2026-10-01](https://arcadot.com/btc-perp-bot/strategy-lab.html)
- [9개 후보 비교·선정·재현](docs/STRATEGY_COMPARISON.md)
- [13개 전략군·15개 연구 원문/초록 검토](docs/STRATEGY_SOURCE_AUDIT.md)
- [전략군 비교 사전 명세](docs/EXPERIMENT_1458.md)
- [GitHub Pages 백테스트 탐색](https://javislab.github.io/btc-perp-bot/)
- [일봉 추세 후속 결과·재현 — 2026-10-01](docs/LONGITUDINAL_RESULTS.md)
- [결과 계산 전 고정한 실험 장부](docs/EXPERIMENT_1448.md)
- [전략 조사와 다음 검증 계획 — 2026-09-30](docs/STRATEGY_RESEARCH.md)
- [검증 환경 v0.2: 사용법·첫 결과·한계](docs/RESEARCH.md)
- [결과 확인 전에 고정한 연구 조건](docs/RESEARCH_PLAN.md)
- [첫 백테스트 HTML 보고서](docs/reports/research-1428-backtest.html) — 다운로드 후 브라우저로 열기
- [초기 계획과 수익 목표 계산](docs/PROJECT_BRIEF.md)
- [Hyperliquid 공식 문서 조사](docs/HYPERLIQUID_NOTES.md)
- [실제 접속 검증과 지갑·테스트 자금 조건](docs/CONNECTIVITY.md)

## 개발 방향 제안

Python과 Hyperliquid 공식 Python SDK를 사용한다. 초기에는 BTC 단일 시장의 단순 전략부터 비교한다.
지갑, 시세, 전략, 모의 체결, 거래소 주문 어댑터, 실행 기록을 분리했다.
LLM은 연구·코드·결과 해석을 돕는 용도로 두고, 주문 판단은 재현 가능한 규칙으로 시작한다.
기본 모드는 paper이며, 메인넷 주문은 별도 네트워크용 지갑 파일과 명시적 실행 옵션 없이는 차단된다.

비밀키·시드 문구·개인 계좌 자료는 Git, 채팅, 로그에 남기지 않는다.
