# BTC 인터넷 근거 감사 · DM1490

## Q1 — Wu & Pinsky (2026-09-06)
- 검색질문: `"On the Performance of Lagged Momentum"`. 실제 Google 조회는 내용부재, Bing은 부적합 검색결과, DuckDuckGo에서 출판사/PDF/RePEc를 찾음(2026-10-02 04:40UTC). Google/Bing 실패를 문헌부재로 해석하지 않음.
- 논문 https://www.mdpi.com/1911-8074/19/9/692 (직접HTML/XML403); 등록초록/저자/날짜 https://api.crossref.org/works/10.3390/jrfm19090692 ; 공식 공개 전문 https://mdpi-res.com/d_attachment/jrfm/jrfm-19-00692/article_deploy/jrfm-19-00692.pdf (200,31쪽,SHA dd22882ce5e89f40c5e10ca7a9814180b1b525f5eed4f8a62a2189cb02c139dd).
- 실제읽음: 초록/서론, 자료·방법(3~4절), BTC 검정·선택·holdout(5~6.3), 결론/자료공개문. PDF 확보=모든 ETH/ETF 표를 감사한 뜻 아님. BTC-only 원칙상 ETH 이식 계산 없음.
- PDF29쪽 Data Availability가 https://github.com/wzf01195010-png/Crypto-day-night-effects 를 직접 연결. 동일논문 저자 코드로 연결 확인. README·btc_eth_backtest.py 전부 읽고 원본 보존(코드SHA70a2d1b4432d6a7e8e2e06bd6bf104d5b2b2ee4b57b240274f4cc1f56e89b219). cutoff_strategy_analysis.py 확보/필요방법부추가감사 대상. 외부 코드는 실행하지 않음. 원본·조회시각·HTTP결과 data/btc-web-20261002/q1-sources.json.
- 같은 종류 전일세션 shift(1), 직전12h가 아님. open_time=k 시간봉 close는 k+1시 직전 가용. bar_ret[k]=close[k]/close[k−1]이므로 k=h…h+11을 곱하면 실제 h~h+12 경계의 close-to-close 수익이 됨. 단순히 close를 open_time로 인덱싱했다는 이유만으로 이 식을 한 시간 미래정보라고 단정하지 않음. 전일동일세션 종료는 현재진입12h 전이라 방향은 사전에 알려짐. 다만 boundary 종가 완벽체결/현재잔고와 수량·최소금액·실제 비용은 재현하지 않음. 자체실험은 완료시각명시+5m실제시가와지연 적용.
- 소스의 turnover는 부호변경에만 기반(반전2), 현금계좌/수량원장 없음; 같은방향 short의 정규화노출 리밸런싱 비용/최종청산 비용이 명시되지 않음. 0/1/2bp는 편도 총비용 가정이 아니라 illustrative friction, funding/borrow/spread/impact 누락.
- 평균 annual MDD는 매년1로재설정한10개MDD평균, 전체연속DD와다름. 코드 full_period_mdd도별도로계산하며 논문Table9는전체MDD라고명시. 전체DD를연간평균으로잘못비교하지않음.
- README 기본파일은7경계×25×2자산×3비용=1050행, 별도완전파일12경계=1800행. 이를 모순이라고하지않음. 원문선택우주BTC300조합. Kraken raw 미포함/빈거래시간처리·출처·재배포검증필요라고README명시. Kraken완전원자료독립재현은아님. PDF의3652calendar days와87672hours는산술상불일치(3653일=87672h);3652는첫/마지막불완전세션제외후cycle수와구분해야함.
- BTC SPA p=.899/.954/.996(0/1/2bp), 선택보정후실패. 2016~20선택은11시Momentum/Long,2021~25수익−29.1% 비용전/보유wealth비.236. 전체선택08시반전은훈련선택과다름. 논문6.3 비용손익분기 대략편도2.1bp라현재5+1.5bp보다낮음. 저자수익을우위증거로승격하지않음.
- 경제기전: 지역참여/유동성공급·수요복귀(인과확인아님). 기존공식BTC1h/5m로별도검증가능. 자체SR00기본/SM00·SL00·SR08비교를결과전에명세. 기각되어도조사종료아님.

## 인용연결 — Q2, Q7
- Q1 Crossref30개참고문헌에서Q2 Wen(2022)와Shen/Urquhart/Wang `Bitcoin intraday time series momentum`(2022,10.1111/fire.12290)를확인. Q1과Q2는독립중복성과로개수를부풀리지않음.
- 실제검색 `Wen 2022 intraday return predictability cryptocurrency momentum reversal pdf`: 출판사/SSRN4080253/ResearchGate두중복레코드/공개학생동아리PDF https://www.cuats.co.uk/wp-content/uploads/2026/02/ssrn-4080253.pdf 발견;후자직접403,전문확보아님. 다음은출판사preview/저자·기관경로.
- 실제검색 `Bitcoin intraday time series momentum 2022 Elaut Zhang Gao pdf`: 검색어의저자추정은틀렸고실제저자는Shen,Urquhart,Wang. University of Reading 원문 https://centaur.reading.ac.uk/100181/3/21Sep2021Bitcoin%20Intraday%20Time-Series%20Momentum.R2.pdf 200/41쪽/SHA299f51695b1071b16166138b0643d43b30c527e684b39e872f3a7bba06eec803. 확보후읽기진행,수익기전검증완료아님. 초록은거래량으로첫거래세션을정의하고첫30분→마지막30분예측을주장;시간대전체표본선택/비용먼저감사할것.

## Q1 실행/검산 이력
- 기본40계좌계산완료. 첫synthetic 최소금액검사는1%목표가비용후수량0으로내림되는데minimum event를기대한테스트오류(IndexError). 테스트를3%목표(양의수량이지만50USDT미달)로고치고0수량은무거래로별도해석. 연구규칙/계좌성과변경없음. 최초셸이테스트실패후실험을계속한이력도보존;이후검사는실패즉시중지형으로실행.
- 첫독립검산은40계좌의수량/원장/DD숫자가통과했으나12정산의mark원시월자료없음에서정지. 기존공식daily복구4일을검산기에서빠뜨린것을확인,기존파일만연결하여원시검증재시도(원본가격/성과수정없음).

## Q3 — 가격통제 주문흐름 (2026 출판 / 2025 학위논문)
- 실제검색 `"Order flow and cryptocurrency returns" Anastasopoulos pdf` → EFMA2025발표PDF,SSRN5020002,Guelph학위논문,RePEc. EFMA TLS issuer오류(검증끄지않음),ScienceDirect403/API429. RePEc에서 DOI10.1016/j.finmar.2026.101047과5저자·초록확인.
- 대체저자원문 https://atrium.lib.uoguelph.ca/server/api/core/bitstreams/bae607b2-3fff-401a-8412-c34569fd5f98/content (200,120쪽,SHAfbc12baa484ceba15c1a233f9ea008fb551be9d8f45c09a841eb5ef66758f908), Alexia Anastasopoulos,2025-12. 최종저널판과같다고단정하지않음. 실제읽기:자료1.2,가격통제1.3,학습2.4,잔차포트폴리오2.5,BTC/횡단면차이3.3.
- CMC700+거래소가격과CryptoCompare300+거래소11통화signedvolume,2018~2022 균형84코인.전기간생존/양의거래조건,일표본은주말·미국공휴일제외. Binance단일BTCperp에그대로대입불가. Log buy/sell,30일std(현재완료일포함),당일가격통제잔차는확장OLS.초기훈련/검증각1년·월간롤링. OF자체daily t=.62→가격통제후2.58,일잔차포트폴리오alpha t1.65로headline ML3.63Sharpe와다름.누적세계흐름의BTC예측/동시효과구분필수.
- 새기전:동시가격반영분을제외한비정상체결압력이후속BTC방향을예측하는가. Q3자체OF_RES/OF_RAW/PF_REV/OF_NEG 사전명세후검증;다른코인·유료데이터를추가하지않음.

## Q2/Q4/Q5/Q6 상태 갱신
- Q2 Wen DOI등록:2022-11,저자Zhuzhu Wen/Elie Bouri/Yahua Xu/Yang Zhao. 직접출판사403;Crossref text-miningURL은200이지만`full-text-retrieval-response`이름과달리coredata만있고전문없음.기존초록/서론preview와현재전문미확보를구분.30분창최적화전재현가능규칙필요,관련Q7저자기관전문은확보됨.
- Q4 실제검색정확제목으로Wiley/UNIVPM기관/RePEc발견.Wiley·기관403,RePEc초록확인(2022,42(3),492–524):perpetual의여러u-shape·계절성·분기선물spillover;cash-and-carry는시장불균형때주로존재.이는perp방향수익보장이아니며이미실패한확정funding규칙의재실행근거아님.다음인용7건/기관공개판검토.
- Q5 Crossref공식등록초록 https://api.crossref.org/works/10.2139/ssrn.6697060 (Boon Chuan Lim,2026)를직접확인.18개월5코인pooled RV예측은있으나 **BTC계수는essentially zero**, 강한HAR-RV기준에는OOS개선없음.기존큐의'BTCbasis예측정보'전제가과도했음을정정.방향전략근거로기각,이논문만을위한대량premium수집안함.다른BTCbasis가설가능성을전체부정하는것아님.
- Q6 Crossref검색으로2021SSRN3910202와2023-10저널10.1016/j.irfa.2023.102712가동일제목/저자Zehua Zhang,Ran Zhao임을확인(별도독립근거2개아님).현재전문미확보;횡단면소트는BTC단일방향수익증거아님.저자/기관·인용문헌을통해semivariance의실제BTC위험예측추가가치근거탐색.
- 검색장애:DDG일부후속요청은captcha,Google빈결과/Bing무관결과/Yahoo500.이들은해당검색경로실패일뿐전체웹조사중단사유아님.공식Crossref/저자기관/RePEc경로로계속확보.
- Q7 Shen/Urquhart/Wang(2022) Reading수록2021-09원고:거래량최대구간으로세션시작선택,CME17ET종료;첫정보세션+끝직전30m반전.3.7은무레버리지손익분기3/7/10bp로Bitstamp25bp비용에미달한다고인정.10배레버리지로29/64/96bp가되어수익가능하다는서술은명목비례수수료도함께증가하는단위문제를해결하지못함.기존레버리지금지원칙에따라그부분기각.지역시각/정보흡수기전은별도검증가능하나시각최적값/레버리지결론을채택하지않음.

## Q8~Q10 — 큐 이후 BTC 위험 예측으로 조사 확장
- 실제학술검색 `bitcoin realized semivariance downside upside volatility forecasting`(OpenAlex search):Q8 Regime-Dependent Good and Bad Volatility of Bitcoin(2020-12-07,10.3390/jrfm13120312),Q9 Forecasting realized volatility of bitcoin returns: tail events and asymmetric loss(2021-04-02,10.1080/1351847X.2021.1906728),Q10 Cryptocurrency volatility forecasting: What can we learn from the first wave of the COVID-19 outbreak?(2021-06-16,10.1007/s10479-021-04116-x)확보.다른자산거래확장없음.
- Q8 MDPI CDN403,OpenAlex는EconStor handle10419/239398과UWA기관경로를반환.대체원문추적중,전문읽음아님.
- Q9 Pretoria저자원문 https://repository.up.ac.za/bitstream/2263/84189/1/Gkillas_Forecasting_2021.pdf 확보(SHA5cfdec1209097ccd5d2a161ed234242bf363bb193e75a1ec40e9f1f2294637dd).2020-11원고/2021출판구분.초록·HAR-RV방법·평가/결론읽기:tail추가효과는과소예측을더벌주는비대칭손실/특정창·짧은중간horizon에서주로발생.보편적방향알파아님,많은창중최적값복사안함.
- Q10 PMC공개전문 https://pmc.ncbi.nlm.nih.gov/articles/PMC8207820/ 확보/초록·방법·자료·BTC예측결과읽음.원본은Bloomberg5m/2018.4~2020.6,주식식5/22기간HAR와WLS·MCS;공개Binance2022~26에서새독립검증필요.초록의'분산부호모델best'를BTC전체결과라고오인하지않음:본문전체표본BTC1일/5일best는Model5(부호점프),1개월은Model2.모형/기간에따라결론이다름.
- 경제기전:같은총변동성이라도하락/상승의분해가미래위험의지속성이다를수있음.수익신호와위험예측을분리하며,단순노출/레버리지확대를수익예측알파로명명하지않음.후속HAR/부호위험규칙을성과전에고정할예정.
- Q2/OpenAlex 공개PDF없음, Q4 Wollongong/figshare27809493도메타데이터만(files=[]),Q6공개PDF없음.접근한범위명시·유료/권한우회없음.
