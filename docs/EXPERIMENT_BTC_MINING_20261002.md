# BTC 채굴 압박·회복의 조건부 위험 참여 · 사전명세

## 독립 경제 가설과 읽은 범위
Q24 Edwards2019(현재2023-04편집) Hash Ribbons 원문전체·2019~2024저자TradingView변경기록,연결된WillyWoo2019Difficulty Ribbon 원문전체를읽었다. 약한채굴자의운영압박/매도와회복에따른공급압력완화라는기전. 30/60일hash회복을다른가격추세정보와교차해검정. 해시증가는직접매수흐름이아니며장비효율/전력계절성/정책/블록확률도원인이다. 인과신호라고하지않음.
원문5000%는9진입에서사후사이클최고점까지수익이며정의된청산·연속원장아니다. 2015나쁜진입을보고가격filter추가·2019repaint수정·2024공급자중단/전환을확인. 본검정은원문성과복제아니고기존E_SPOT의추세위험에채굴정보가추가가치있는지새로제한한가설이다. WillyWoo는압박중가격안정화자체를매수가능상태로설명하므로경쟁기전도대조한다. 기존BTC계좌의창/임계치검색이아닌새독립입력·경제적게이트. 현재채굴성과는미계산.
출처 https://capriole.com/hash-ribbons-bitcoin-bottoms/ , https://www.tradingview.com/script/kT7jIvqv-Hash-Ribbons/ , https://woobull.com/introducing-the-difficulty-ribbon-the-best-times-to-buy-bitcoin/ . 스크립트본문미확보/외부코드실행없음.

## 자료·단위·가용성 (성과 전에 감사)
Bitcoin-only Blockchain.com 공개chart API `hash-rate`,`difficulty`,`n-transactions`,`n-transactions-per-block`;2020-01~2026-10-01. sampled=false이나2025-11-13~15결측,짧은20일재조회도누락. 원본그대로보존. 3일만공개blocks-day응답437블록의연속높이/해시와first/last헤더6개doubleSHA256·nBits를확인해복원. 세날같은retarget epoch458내여서도중difficulty변화없음,각150/144/143블록. CoinMetrics독립CSV와블록수일치,해시율상대차<4.48e−9. 기존198·새286계좌보존,불필요재실행없음.
BTC HashRate(TH/s)=BlkCnt×일평균Difficulty×2^32/(86400×10^12). 차트의n-transactions/transactions-per-block에서정수블록수복원,공급자hash재계산최대상대차5.36e−15. 직접하드웨어관측/정확순매도량아님. 정상2463일+복원3일=2466행,모두양수·연속. APIBTC자료로ETH등추가하지않음.
CoinMetrics무료BTC CSV는2026-05-24에서정지. API403,공식무료저장소는성공. 전체최근평가를5월로줄이지않음. 비교공급자`provider_cm`조건만CMC가존재하는날은CMC HashRate,이후는원래Blockchain값사용. 자료출처전환을사전에정의하며어느쪽성공을골라기본으로바꾸지않음. CC BY-NC4.0출처·연구용무료자료성격유지,유료서비스없음.
`data/btc-mining-20261002/prepare-audit.json`에14원시파일SHA/normalizedSHA고정. 현재차트스냅샷/블록헤더시각은모든과거최초가용빈티지증명이아니다. UTC d날값은d+2일00UTC부터사용(완료후24h여유);추가7일정보지연민감도도검정. 불완전일/미래소스/공통자료부족은cash,위험가격결측만판단보류. 과거가용성가정으로표시.

## 고정 규칙·모든 비교
매일00UTC t에서가용한가장최근일 d=t−2일의H30=직전30완료일(당일d포함)해시율평균,H60=60일평균. 둘중결측이면모든채굴모형cash. H30≥H60은회복/비압박상태G=1,작으면G=0;임계/창/날짜를성과후최적화하지않음. 단순상태게이트이며원문희소한회복cross한번매수·사후peak청산을복사안함.
가격E_SPOT는기존완료현물20/60/120일수익부호+EMA8/32,16/64,32/128부호의평균score중양수부분P=max(score,0),EMA동일2020-02부터warmup. 방향가중치:
- **HG_REC 기본**: P×G. 양호채굴상태에서만기존BTC현물추세참여,압박재진입시cash.
- HG_STRESS 반대상태대조: P×(1−G). 압박중누적/가격안정화경쟁가설;기본으로승격불가.
- HG_HASH 가격정보제거대조: G. 해시상태만으로롱,역시동일risk상한.
- HG_INV 반증대조: −P×G. 기본허용비중의정확반대perp숏,실제펀딩검산용이기도함.
기존E_SPOT 기본주/최근저장원장참조(새실험으로재실행안함),가격기준대조와CI에사용. 같은정보원으로선택한성공시각·사후청산 없음.

## 계좌·기간·민감도 56개
각1000USDT. t까지완료현물20일logreturn표본std×√365로w=min(1,.20/vol),최종signedtarget=w×direction,명목최대1배. BS현물롱/BPperp숏,동시양다리없음. 기본t+1h시가;현물.00001BTC/min5/fee10bp,perp.001/min50/fee5bp,둘다impact1.5bp,5%p밴드·preflight·종료dust비용. 실제펀딩×raw시간mark시가proxy. 호가/partial/과거규정미복원한계. 실주문/실서비스없음.
4규칙×7조건×2기간=56. main2022~2025/recent2026-01~08 모두이미본개발가격,미사용OOS아님. base,cost_x2,추가체결delay1/delay24,risk10,**source_delay7**(해시자료만추가7일늦음:d=t−9일;가격·risk는현재완료정보유지),**provider_cm**(위정의다른공급자해시). gate신호에거래비용을결과후최적화안함.

## 결과 전 고정한 기각·검증
기본주수익>52.838713%,DD≤13.561952%,최근>4.628391%,DD≤10.450946%,연vol≤13.343621/16.520409%,주Sharpe≥.8,4년중≥3양수,주≥20완료보유구간,담보위반0. base/cost2/체결1·24h/정보7일/비교공급자 모두양기간순손익양수. 낮은risk만통과/반증한구간수익/노출확대로기본채택불가. E_SPOT대비두기간수익이위기준에내포되어있으며,HG_HASH대비추가가치도두기간비교해표시(양기간순수익우위없으면그추가가치주장불가). 모든조건·연도·비용·펀딩·롱숏·노출·정보나이·자료출처민감도보존.
일수익평균/E_SPOT/HG_HASH/HG_STRESS대비차이7/14/28일블록2000회95%구간. 경계검사:해시미래변경/완료·가용지연、공급자교체、자료결측cash、가격/위험미래교란、분리상태和=E_SPOT、반증정확부호、단위scale불변.
별도원시chart비율·Decimal프로토콜식·raw blockheader해시/난이도·CMC교차검산、원시현물에서EMA/모멘텀/vol별도구현、수량/무거래폐형식·Decimal cash/펀딩/hourlyDD、소켓차단전조건바이트재현. raw체결시점거래량>0확인. 모든연구실패보존;불합격시다음원문/공식자료검색으로연속진행. 이실험/게시가전체목표완료아님.
