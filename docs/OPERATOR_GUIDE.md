# v0.1 사용 가이드

## 지원 범위

- `wallet create/check`: 암호화 지갑 생성, 복호화 후 로컬 메시지 서명/주소 복구 확인.
- `quote/account/order-status`: BTC 호가, 계좌/포지션, 주문 상태 조회. 지갑 개인키 없이 조회 가능.
- `order/cancel`: 공식 SDK의 실제 서명 주문·취소 경로. 기본 네트워크는 testnet.
- `bot`: 닫힌 1분봉의 3/8 이동평균으로 BTC 목표 방향을 결정하는 실행 루프. 기본은 paper.
- `reconcile`: 타임아웃 등으로 불명확한 요청을 거래소 조회로 확인. 주문을 재전송하지 않는다.

**현재는 실행 기능을 검증하는 프로토타입이지 수익성·장기 운영·메인넷 실행을 검증한 제품이 아니다.**
BTC 기본 perpetual 시장만 지원한다. 다른 자산/오픈 주문이 없는 전용 계좌로 시작하도록 제한한다.
계좌 담보는 `clearinghouseState.marginSummary.accountValue` 양수를 요구한다. 모든 통합 계좌/포트폴리오 마진 모드를 검증하지 않았다.

## 지갑

```bash
.venv/bin/btc-bot wallet create \
  --purpose testnet \
  --keystore ~/.local/share/btc-perp-bot/wallets/testnet.keystore.json

.venv/bin/btc-bot wallet check \
  --keystore ~/.local/share/btc-perp-bot/wallets/testnet.keystore.json
```

암호는 터미널의 비표시 입력으로 받는다. 최소 12자이며 분실 시 복구할 수 없다.
Scrypt 기반 표준 V3 keystore를 쓰고, 출력은 공개 주소와 파일 경로뿐이다. 시드·개인키를 출력하지 않는다.
기존 파일 덮어쓰기, 심볼릭 링크, 다른 사용자에게 공개된 비밀 파일은 거부한다.
저장 폴더는 0700, 지갑 파일은 0600이어야 한다. 파일과 암호를 별도로 안전하게 보관한다.
지갑 생성만으로 거래소 계좌에 잔고가 생기거나 API wallet 승인이 완료되지는 않는다.

무인 테스트에서는 `--password-file /절대경로/암호파일`을 쓸 수 있다. 이 파일도 0600이어야 한다.
암호를 명령행 인수에 직접 넣는 옵션은 없으며 Git·채팅에 올리지 않는다.
**암호 파일과 keystore를 같은 서버에 두면 그 서버를 제어하는 사용자는 둘 다 읽을 수 있다. 암호화가 서버 침해를 막아 주는 것은 아니다.**

`purpose=testnet` 표시는 프로그램의 오작동 방지 장치이지 암호학적 네트워크 격리가 아니다.
동일 EVM 키/주소는 여러 네트워크에서 쓰일 수 있으므로 테스트용 주소에 실제 돈을 보내지 않는다.

## 공개 데이터와 모의매매

```bash
.venv/bin/btc-bot quote --network mainnet
.venv/bin/btc-bot account --network testnet --account 0x사용자공개주소
.venv/bin/btc-bot bot --mode paper --steps 6 --interval 10
```

paper는 지갑을 열지 않고 mainnet `/info`의 공개 데이터만 사용한다. 서명 주문을 보내지 않는다.
기본 가상 잔고 1,000, 목표 거래금액 25 USDC, 수수료 편도 4.5bp, 추가 슬리피지 편도 1bp를 가정한다.
매수는 ask보다 불리하게, 매도는 bid보다 불리하게 가정하므로 스프레드도 반영된다.
매 실행은 새로운 가상 계좌이며, 기존 수익/잔고를 이어받는 프로그램이 아니다.

- 닫힌 봉만 사용하고 캔들 누락과 오래된 호가는 거부한다.
- 같은 방향 신호에는 반복 진입하지 않는다. 반대 신호는 기존 포지션을 닫고 반대쪽에 진입한다.
- `--max-loss`는 시작 자산 대비 평가손실 감지값이다. 급변 시 실제/모의 손실이 이 값을 넘을 수 있다.
- `--max-orders`는 신규 진입 제한에 사용한다. 제한에 도달해도 위험을 줄이는 청산은 허용한다.
- paper는 정상 종료 시 모의 포지션을 닫는다. 오류가 나면 마지막 평가 상태와 오류를 기록한다.
- **펀딩·청산·호가 깊이/시장 충격·지연 체결은 모델링하지 않는다. 수익성 검증용 백테스터가 아니다.**

실행 결과는 `runs/실행ID/`의 tick JSON, `fills.json`, `summary.json`에서 확인한다.
현재 규칙의 계수는 테스트용 출발값이며 검증된 투자 전략이나 추천 거래금액이 아니다.

## 테스트넷 주문 실행

테스트 잔고가 필요하다. 공식 Faucet는 같은 주소의 메인넷 입금 이력을 요구한다.
최소 입금액은 이번 확인 문서에 명시되어 있지 않다. [공식 Faucet 조건](https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet)

원래 지갑 키를 쓰면 해당 주소가 거래 계좌다. 승인된 API wallet 키를 쓰면 반드시 `--account`에 **원래 사용자 계좌 주소**를 전달한다.
프로그램이 API wallet 승인을 대신 생성하거나 자금을 자동 입금하지 않는다.

```bash
# 테스트 잔고 확보 뒤 운영자가 실행하는 테스트넷 예시
.venv/bin/btc-bot bot --mode testnet \
  --keystore ~/.local/share/btc-perp-bot/wallets/testnet.keystore.json \
  --steps 6 --interval 10 --notional 25 --max-loss 5 --flatten-on-exit
```

거래소 모드는 실제 SDK로 서명한 IOC 주문을 보낸다. IOC는 부분 체결되거나 거절될 수 있다.
신규 주문에는 명목금액 상한과 계좌 대비 1배 이하 노출 검사를 적용한다. 슬리피지 기본 한도는 0.1%다.
청산은 reduce-only로 보내며, 완전히 닫히지 않으면 반대쪽에 추가 진입하지 않고 중단한다.
응답 후 포지션이 예상과 다르거나 외부에서 주문/포지션이 변경되면 중단한다.
`--flatten-on-exit`은 **정상 종료** 때만 청산을 요청한다. 장애·강제 종료·타임아웃 시 청산을 보장하지 않으며, 거래소에 상시 손절 주문을 설치하는 기능은 아직 없다.

단일 주문·취소도 가능하다. 다음 숫자는 테스트넷 API 형식 예시일 뿐이며, 현재 호가와 잔고에 맞춰야 한다.

```bash
.venv/bin/btc-bot order --network testnet \
  --keystore ~/.local/share/btc-perp-bot/wallets/testnet.keystore.json \
  --side buy --size 0.0002 --price 70000 --tif Alo --max-notional 25

.venv/bin/btc-bot cancel --network testnet \
  --keystore ~/.local/share/btc-perp-bot/wallets/testnet.keystore.json --id 주문번호
```

가격·수량 정밀도와 BTC 자산 ID는 해당 네트워크 메타데이터로 확인한다. 메인넷의 자산 ID를 테스트넷에 하드코딩하지 않는다.

## 불확실한 주문 결과

서명 요청 전에 주문 의도를 디스크에 저장하고 fsync한다. HTTP 타임아웃은 주문 거절의 증거가 아니므로 자동 재전송하지 않는다.
기록은 `~/.local/share/btc-perp-bot/journals/네트워크-계좌주소.jsonl`에 남는다.
같은 계좌를 쓰는 로컬 프로세스는 파일 잠금으로 중복 실행을 차단한다. 다른 기기/서버의 프로그램까지 잠그는 기능은 아니다.

```bash
.venv/bin/btc-bot order-status --network testnet --account 0x사용자공개주소 --id 0x주문클라이언트ID
.venv/bin/btc-bot reconcile --network testnet --account 0x사용자공개주소 --id 0x주문클라이언트ID
```

조회 결과에서 원래 주문의 존재·결과가 확인되어야 기록을 해제한다. `unknownOid`만으로 미체결이라 단정하지 않는다.
취소 요청의 타임아웃은 journal에 나온 `cancel-...` id로 reconcile한다.
원래 주문이 열려 있으면 취소가 필요할 수 있고, 체결됐다면 포지션 확인이 필요하다. reconcile은 신규 주문을 보내거나 포지션을 닫지 않는다.
미해결 기록을 삭제하고 다시 실행하는 방식으로 중복 주문 방지 장치를 우회하지 않는다.

## 메인넷과 출금

사용자 실행용 메인넷 경로도 코드에 포함되어 있다. `bot --mode live` 또는 `order/cancel --network mainnet`은
`--enable-live-orders`와 `purpose=mainnet` 지갑이 없으면 실행을 거부한다.
이 옵션은 운영자가 직접 가동할 때 쓰는 명시적 설정이다. 에이전트가 이 옵션으로 실자금 주문을 실행하지 않았다.
**실제 메인넷 주문·체결·장애 복구는 미검증**이며 출금/수익금 자동 송금 코드는 제공하지 않는다.

## 출처

- [공식 Python SDK](https://github.com/hyperliquid-dex/hyperliquid-python-sdk)
- [공식 주문 API](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint)
- [계좌와 API wallet의 구분](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets)
- [eth-account 지갑 기능](https://eth-account.readthedocs.io/en/stable/eth_account.html)
