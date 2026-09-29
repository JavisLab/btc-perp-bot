# Hyperliquid 접속 검증 — 2026-09-29

## 결론

**현재 서버에서 공개 API·실시간 호가·공식 웹 화면에 접근할 수 있다.**
이 결과는 지갑 인증, 서명 주문 승인, 주문 체결까지 검증했다는 뜻은 아니다.
현재 미확인 단계는 **지갑 소유·연결 → 테스트 자금 확보 → 테스트넷 주문·취소**다.

## 직접 확인한 결과

2026-09-29 11:44~11:48 UTC, 지갑·API 키 없이 수행했다.

| 항목 | 결과 |
| --- | --- |
| 메인넷 POST /info: metaAndAssetCtxs | HTTP 200, BTC 시장·가격·펀딩 응답 |
| 메인넷 POST /info: BTC l2Book | HTTP 200, 매수/매도 각 20개 호가 레벨 |
| 테스트넷 위 두 조회 | 모두 HTTP 200, BTC 시장·호가 응답 |
| 양 네트워크 WebSocket BTC l2Book | 구독 ACK와 서로 다른 timestamp의 호가 메시지 각 3회 수신 |
| 공식 메인넷 /trade | HTTP 200, 거래 화면 표시 |
| /trade의 Connect 선택창 | 이메일, Default Wallet, WalletConnect, OKX, Coinbase 선택지 표시 |
| 공식 테스트넷 /drip | HTTP 200, 메인넷 입금 이력 조건과 1,000 mock USDC 안내 표시 |
| 공식 메인넷 /API | HTTP 200, 출금 권한 없는 API wallet 설명 표시 |

WebSocket 검사는 Node 기본 클라이언트에서 수행했다. 수신 중 오류는 없었으나,
클라이언트가 종료를 요청한 뒤 양쪽 모두 close code 1006과 오류 이벤트가 관측됐다.
**따라서 호가 수신만 성공으로 기록하며 정상 종료·재연결·장시간 안정성은 검증 완료로 처리하지 않는다.**
초기 단일 메시지 프로브에도 종료 중 오류가 있었고, 별도 3회 수신 프로브에서 수신/종료 결과를 분리했다.

OpenClaw 브라우저 기동 timeout 뒤 독립 Playwright/Chromium으로 웹 화면을 확인했다.
Gateway 설정이나 기존 서비스는 변경하지 않았다. 생성한 검사 브라우저와 WebSocket 연결은 종료했다.
조회 결과의 원본 필드와 브라우저 확인 요약은 [근거 JSON](evidence/2026-09-29-public-connectivity.json)에 보관한다.

## 지갑과 입금은 언제 필요한가

1. **공개 시세 조회·자체 모의매매:** 지갑과 실제 입금 없이 진행 가능. 이번 조회는 이 방식이다.
2. **거래소 테스트넷에서 주문·취소:** 서명용 지갑과 테스트 잔고가 필요하다.
3. **공식 Faucet 조건:** 동일 주소로 메인넷에 입금한 이력이 있어야 1,000 mock USDC를 받을 수 있다고 안내한다.
   신규 무입금 지갑만 생성해서 바로 받을 수 있다고 가정하지 않는다. 확인한 문서·미연결 화면은 최소 입금액을 명시하지 않는다.
4. 기존에 자격을 갖춘 지갑이 있다면 새 실제 입금 없이 수령 가능할 수 있다. 사용자별 자격·수령 가능 여부는 아직 확인하지 않았다.

[공식 Faucet 설명](https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet) ·
[실제 Faucet 화면](https://app.hyperliquid-testnet.xyz/drip)

따라서 **접속 확인을 위해 지금 사용자에게 돈을 보내 달라고 할 필요는 없다.**
테스트넷 자금 조건을 충족하기 위한 메인넷 입금이 필요한지는 사용자 지갑 이력을 확인해야 한다.
입금액·대상 주소·네트워크가 확정되지 않은 상태에서는 송금을 안내하지 않는다.

## 지갑 구성 제안

- 주인이 직접 관리하는 프로젝트 전용 EVM 지갑을 사용한다. 실제 자금용 지갑의 시드·개인키는 주인이 보관하고 채팅이나 저장소에 넣지 않는다.
- 향후 프로그램에는 별도로 승인한 API wallet을 사용하는 구성을 검토한다. 공식 API 화면은 API wallet에 출금 권한이 없다고 명시한다. 출금이 안 된다는 것이 거래 손실까지 방지한다는 뜻은 아니다.
- API wallet은 서명용이며, 계좌 조회에는 원래 사용자 계좌 주소를 쓴다. API wallet 주소를 입금 주소로 혼동하지 않는다.
- 공개 조회·개발·테스트넷 검증과 실제 자금 운용을 분리한다. 실제 자금 이동과 실거래 가동은 사용자가 직접 관리한다.

[공식 API wallet 화면](https://app.hyperliquid.xyz/API) ·
[공식 Nonces and API wallets](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets)

이번에는 지갑 생성·연결, 약관 동의, API wallet 승인, 토큰 수령, 서명 요청, 입금·출금·주문을 하지 않았다.
공개 화면이 열린다는 사실만으로 사용자별 서비스 이용 자격이나 실거래 가능 여부를 확정하지 않는다.
