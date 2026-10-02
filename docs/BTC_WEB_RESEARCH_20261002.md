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

## 위험 가설 실행 및 Q11~Q12 확장
- V_SRV 기본/V_HAR·V_RV20 대조는 명세f9cf939 후 30계좌 계산. 주+50.2644068888%·DD11.3478804951%,최근+.8881032876%·DD1.8610122523%;주/최근수익·양수연도·24h지연·주MSE 관문 탈락. 노출감소와 위험감소를 알파로 혼동하지 않음. 기존198계좌 재계산없음. 학습용공식BTC5m21개월만추가,701280봉→2435일을별도RV검산.
- Q10 인용후속 https://arxiv.org/html/1912.05228v3 (Hu/Kuo/Härdle,first2019-12,원고2021-08,v3등록2021-12-09):초록·서론·RV/jump방법읽음.본문은부호점프의예측가치가주로30일에있고1일HAR가오히려우세라고함.단기예측에항상추가이득이라는해석기각.전체부록/모든수치재현아님.
- Q11 실제OpenAlex검색 `bitcoin spot futures order flow information price discovery signed volume` → Alexander/Heck,Price discovery in Bitcoin: the impact of unregulated markets,2020-07-30,10.1016/j.jfs.2020.100776. Sussex공개기관API https://api.figshare.com/v2/articles/23308262 → https://ndownloader.figshare.com/files/41093948 원문36쪽확보(SHA76036eec77cacac5288a2ed5312556ecd720ee7607109c9c59cde1d87ee23be6).초록·자료3절·발견결과4절·지연6절·결론7절읽음;다른자산후속제안은연구확대안함.
- Q11은2019-04~2020-01,coinAPI/Eikon유료1분거래가격과별도OI.파생상품의가격발견이주로선도,현물항상선도라는전제가아님.CME반응4~5분/반대약2분;1h/1d가용지연뒤독립방향알파가남는다고하지않음.논문10%가상충격은당시관측최대1분9%보다큼.2019거래소규제상황을현재사실로옮기지않음.우리BTC현물/선물흐름비교는별도근거필요.
- 후속실제검색 `bitcoin informed trading spot futures order flow predict returns`, `bitcoin return predictability order imbalance spot futures`, `bitcoin liquidity shocks reversal permanent price impact order flow`(OpenAlex,2026-10-02 05:23UTC).기존Q11중복·무관/다른자산·철회논문은새BTC근거로세지않음.
- Q12 Farag/Luo/Yarovaya/Zieba,Returns from liquidity provision in cryptocurrency markets,10.1016/j.jbankfin.2025.107411,등록2025-02-22/권호2025-06.저자Birmingham기관초록직접읽음:단기반전수익과위험/유동성제약관계,횡단면인지BTC시계열인지아직확인필요.공개OA로등록된pure-oai PDF403;Southampton/Dundee와현재Birmingham공개링크를추적.전문확보전단순반전규칙을새증거로포장하지않음.

- Q12 대체원문 확보: Southampton https://eprints.soton.ac.uk/id/eprint/501151/2/1-s2.0-S0378426625000317-main.pdf (18쪽,출판본,SHA76dd5fb7303d9f27e2165ce32b615c91aa45ff32bd22e3bc40b86ba1121a9224).초록·서론·자료/방법2절·예측검정/한계읽음.2017~2022,122생존코인5m,결측최대20%허용후forwardfill,시장평균대비반전포트폴리오/50%margin정규화;BTC1종이면동일수식분모0.실제maker체결원장/우리편도비용후BTC수익증거아님.수식가중치표기에i항의합이남는모호함도있음.유동성충격에대한보상기전은살리되성과이식기각.인용Bianchi/Babiak/Dickerson2022 거래량·유동성논문으로추적.
- 위험검산 보강:3810개재조정수량을12회반복solver와다른폐형식으로검산하고21744개무거래(밴드/최소금액등)를검사.실제spot체결시간원시거래량>0확인.모든30계좌수익변경없음.보강후소켓차단49파일재현은일치했으나기존reproduction.json보호장치가덮어쓰기를거부;기존증명을보존하고reproduction-v2.json으로새검산SHA증명기록(실패가성과오류를의미하지않음).

## Q13 — 거래량 충격과 조건부 반전/지속
- Q12인용에서제목을얻어실제OpenAlex검색 `Trading volume and liquidity provision in cryptocurrency markets`(2026-10-02 05:31UTC). 2018SSRN3239670/2022저널10.1016/j.jbankfin.2022.106547은같은논문계열,독립2건아님.Lancaster PDF/랜딩timeout,Riksbank403,대체 https://www.cerge-ei.cz/pdf/wp/Wp730.pdf 성공(46쪽,2022-06 WP730,SHA c294b4f81a23e8413a8d6b803f73515a8939e2fd102b50616f7386dff84ff588).최종저널과같다고단정안함.초록·서론·자료2.1·방법2.2·비용·회귀4.2읽음,전체부록표재현아님.
- 2017-03~2022-03 CryptoCompare80+거래소 USDpair OHLCV,300+코인;매월직전Amihud100개선택,회귀는전체기간평균유동성100개선택.고정표본/365일생존요건/거래량대시총제거선택을명시.우리BTC/USDTperp와다름.대형·고유동성의반전수익은거의0/유의하지않다는반증중요.
- v=ln(Q_d/mean직전30일Q),return×volume 상호작용은양수라는패널회귀;1일후수익을BTCrolling학습으로별도검사할경제기전.전체기간고정효과는실시간미래시각에쓸수없음.원문의logstd정규화표현/시점표기모호함을우리명세에서해소.본문편도long30/short40bp vsTable5caption20/30bp상충,이종목선택비용을우리순수익증거로사용안함.현재레버리지/비용/신호창최적화없음.

- VI_INT 사전명세1aefe03 후40계좌계산:주−16.9737030311%·DD32.7236830938%,최근−13.2635044261%·DD17.3610809282%.VI_ADD/VI_AR/VI_NEG와비용·지연·risk10모두보존.기본종합기각,VI_NEG 최근+6.8068%만보고승격안함.미래정보/labelclock/비용+SE/반대부호/수익단위5검사통과.원시정규방정식예측5898개·신호12800개·원장이벤트25438개·일말34080개·5m계좌봉9815040개검산,오차2e-11,소켓차단62파일바이트일치.
- 실패후실제OpenAlex검색을BTC고차모멘트/점프/충격감쇠·거시뉴스로확장.계산종료/보고서게시는전체연구완료아님.

## Q14~Q19 — 高차모멘트·가격충격·거시정보로 실제검색 확장
- 검색질문: `realized skewness cryptocurrency returns`, `bitcoin price impact decay order flow predictability`, `Bitcoin jumps momentum information discreteness`,이후Bitcoin제목한정FOMC/intraday macroeconomic announcements 검색.무관논문과철회논문은후보근거에서제외.원문/선행큐순환을피해cited-by도조회.
- Q14 Ahmed/Al Mafrachi,Do higher-order realized moments matter for cryptocurrency returns?(10.1016/j.iref.2020.12.009,등록2020-12/권호2021).Crossref/OpenAlex저자(AinShams/HoustonCC)·RePEc초록 https://econpapers.repec.org/RePEc:eee:reveco:v:72:y:2021:i:c:p:483-499 직접읽음.3/5차모멘트의미래수익예측주장,전문미확보.ElsevierAPI200은coredata1836bytes뿐,ScienceDirect403,DDG재검색captcha;전문확보라고하지않음.다른자산계산안함.피인용후속과저자공개판추적.
- Q15 Karagiorgis/Ballis2026-05-28,10.1002/fut.70117, Aston공개13쪽PDF https://publications.aston.ac.uk/id/eprint/49104/1/Journal_of_Futures_Markets_-_2026_-_Karagiorgis_-_Time_Varying_Skewness_Kurtosis_Dynamics_in_Bitcoin_Markets.pdf (SHA52358f5a6ea8ed6eebfca1cd3a70b2f4b7cc6bb374a7180293a570baf83afe52).초록·자료3절·결론읽음:BTC현물/USDTperp1분2020-10~2022-09;시간당50미만관측/zero-volume시간제외,동시skew²→kurtosis관계.미래방향예측아님,예측수익증거로기각.본문17430+17424=34854인데총34859서술불일치;원시미포함으로완전재현주장안함.
- Q17 Donier/Bonart2015,원문 https://arxiv.org/pdf/1412.4503 18쪽(SHAce3cbceeed52c08f760c688dc00710807c23fef6b2e3ec1d79bcbdf4ec4f7c8a),초록·자료·metaorder분리·감쇠5절읽음.MtGox2011~13 고유traderID의anonymous-source데이터(비공개부분)필요;이개인거래자료를확보하지않음.무정보주문선택은[t0,t0+10T]미래시장흐름75%조건으로사후분류;실시간고점에서무정보라고아는신호가아님.공개Binanceaggregate trades는동일traderID가아니며같다고이식불가.집행위험/정보기전참조로만보존.
- Q16 Corbet et al.,The impact of macroeconomic news on Bitcoin returns,10.1080/1351847X.2020.1737168,2020. Dublin저자37쪽원문 https://doras.dcu.ie/25037/1/B27___SC_CL_BL_AM_LY__SUBMITTED_The_impact_of_macroeconomic_news_on_Bitcoin_returns%5B1%5D.pdf (SHA3c417e35ec1202c925276bccf64e4e57b3687c1343f2a28b3dc9a665968185e1).초록·서론·자료/분류3절읽음.LexisNexis3831headline,2010-07~2019-09,당일+다음날기사를사용.뉴스index를발표순간알수있다고백테스트하면미래정보.고용/내구재news는BTC반대반응,CPI/GDP유의하지않음.공식공표시각있는자료로다른별도가설필요;유료자료없음.
- Q18 Pyo/Lee,Do FOMC and macroeconomic announcements affect Bitcoin prices?(2019-12/2020,10.1016/j.frl.2019.101386):RePEc초록만확보,제목은질문이며효과방향/크기가초록에없음.결론을추측하지않음.
- Q19 Ma/Tian/Hsiao/Deng,Monetary policy shocks and Bitcoin prices(2022-06-29,10.1016/j.ribaf.2022.101711), RePEc초록 https://econpapers.repec.org/RePEc:eee:riibaf:v:62:y:2022:i:c:s027553192200099x 직접읽음.FOMC일2년국채예상외수익률+1bp에BTC−.25%,다음며칠효과지속주장.이는식별된충격/회귀효과이며단순공식일별yield변화와같지않음.전체전문미확보.공식FOMC시각·Treasury자료의공표/빈티지감사연결.다른자산매매아님.

## Q20 및 공식 거시자료 감사
- Q14 피인용검색 OpenAlex cites:W3112679388 → Atance/Serna,Time-varying expected returns, conditional skewness and Bitcoin return predictability(2024-05-28,10.1016/j.qref.2024.101868). 초록은2018~20 skew관계음수/2021~22양수라는 상태의존을 주장. 전체기간 위기분류/계수·비용·가용시각은 아직 감사못함. 기관 https://ebuah.uah.es/dspace/bitstream/10017/63078/3/time_atance_QREF_2024.pdf 는 Python403/웹200 Anubis challenge(원문아님),우회안함. ScienceDirect403,Elsevier view=FULL401(API키요구)로정지;저자공개판/인용연결로다음경로. 초록만으로일별GARCH성과복제했다고하지않음.
- 금리data초기URL resource-center-data-chart-center는잘못된경로404. 공식개발자안내를따라 resource-center/data-chart-center/... XML을찾아2022(249행)/2026(189행)확보. NEW_DATE/BC_2YEAR 이름으로파싱해야하며2022-10/2025-02열추가때문에열번호고정금지. XML updated=2026-10-01은2022당시공개시각아님. 이수집을전략성과로소개안함.
- Treasury 공식방법론 https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology/ (2025-02-18개정) 직접본문읽음:15:30ET입력관측,대개18:00ET공개/지연가능. 예전URL200은meta-refresh페이지뿐;실제canonical본문별도확보. Fed H15 https://www.federalreserve.gov/releases/h15/ 직접읽음:영업일16:15공개/휴일제외,US Treasury출처. 이정시가개별과거수신완료를보장하지않음.
- 공식 https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm 전체직접읽음(2026-09-16갱신),정례8회·3주후minutes. 실제성명 https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm 14:00EDT 확인. Python직접403이어도web_fetch정상내용확보,두경로결과구분.
- ALFRED 공개CSV https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=DGS2&cosd=2022-01-24&coed=2022-01-28&vintage_date=2022-01-27 성공. 같은범위01-26빈티지는25일까지,01-27은26일까지,현재빈티지는28일까지반환됨. 당시원자료가용경계를재현가능;정확한분수신시각은없어전체미국날짜완료후보수지연고정. FRED본문/도움말timeout은CSV빈티지불가라는뜻아님. 세CSV보존. Q19동일제목2021SSRN3947979확인(2022저널과독립2건아님).
- 다음구체가설 M_RATE: 정례FOMC일금리변화와BTC반대방향 지속이d+3UTC부터남는가. 단순일별변화를'예상외충격'으로명명안함;M_INV/M_PRICE/M_CASH·기존E_SPOT대조/비용·위험·지연·37빈티지검산을성과전에명세. Q20왜도전문/후속은병행조사큐,현재끝아님.
- M_RATE 최초원형은성과전자료감사에서36/37:2025-06-18회의의익일06-19는공휴일,빈티지에당일관측없음. 수집파일/코드커밋 보존,계좌성과미계산. 별도MB_RATE가설은d+1~d+7중실제로처음관측되는빈티지v와v+2일00UTC가용지연을사용하도록새명세. 37회완전성/수익·위험기준을낮춘것이아니며공휴일자료수신을결과전에정의한변경이다.

## 거시정보 40계좌 결과 및 Q21~Q22 후속
- MB_RATE 새명세9a09aa4 후40계좌:주+52.8825782000%,DD19.2471376516%,vol14.5917982165%;최근+6.3903287728%,DD6.3978987012%. 기본수익/비용·지연양수이나주낙폭/변동성/Sharpe관문실패,가격대조MB_PRICE(+57.2068219365/+7.1357832347%)보다양기간약함.기각,반대/가격대조승격안함.37회38빈티지CSV·raw329ZIP·13632판단·5632폐형식수량·28705무거래·4350펀딩/10002이벤트·34080일말 독립검산오차2e−11,7검사·62파일소켓차단바이트일치.원래d+1고정빈티지의자료실패는보존.
- 실제검색 `bitcoin FOMC information drift monetary surprises`,Bitcoin제목제한 `jumps subsequent returns`, `skewness returns predictability`, `information discreteness`, `intraday momentum informed trading`(OpenAlex).무관암호학/다른자산/기존Q7·Q16중복은새성과근거아님.
- Q21 Predictability of bitcoin returns(2020-11-05,10.1080/1351847X.2020.1835685).NTU저자2020-07원고 https://irep.ntu.ac.uk/id/eprint/41292/1/1374791_Cheah.pdf 50쪽SHA64aa60aafa2c208aeb59d1125f817deb5c64b0db6656fd32ea5c265fbf788513.초록/서론·자료3·회귀/평가·자산배분·비용·Table4읽음.2011-10~2019-01,33예측변수,7/14/21/28일겹친예측,901번째관측부터재귀예측.변수강도선택은전체in-sample결과를먼저씀;반복관문을진정미사용선택으로간주불가.정책/금융불확실성은추가빈티지확인필요.과거거래비용결측을전체표본평균.183%로대체,비용 turnover 가중치차이고실제수량/펀딩아님.비용공식텍스트(bid−ask)는음수인데본문양수.예시.0424−.003×.8=.040은맞음.단순skew는예측추가가치약함(Table4),Q14/Q20의보편적왜도주장을보강하는자료로오인안함.
- Q22 Baur/Smales,Trading behavior in bitcoin futures: Following the smart money(2022-04-27/7월권호,10.1002/fut.22332).UWA저자기관 https://research-repository.uwa.edu.au/en/publications/trading-behavior-in-bitcoin-futures-following-the-smart-money/ 초록직접읽음,leveraged-money숏변화의market timing/후행추종과전략가능성주장.현재Wiley전문403,기관은초록만;전문읽었다고하지않음.공개BTC만CFTC주체별포지션의근거/가용시간확인으로연결.
- CFTC 공식 https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm FAQ직접읽음:화요일포지션→통상금요일15:30ET,휴일변경,**과거공개일전체목록없음/최근13개월만**.분류변경·새진입/탈퇴도수량변화원인,방향투자금으로단정불가.현재공식FAQ는발표후역사자료갱신안함이라고답함;정확과거공개시각/중단기간은별도공식공지감사필요.토큰없이적정API호출가능명시.전역공식ZIP에서다른자산을다운로드하지않고BTC필터API조사예정.
- CFTC공식 TFF Futures Only metadata https://publicreporting.cftc.gov/api/views/gpe5-46if.json 및BTC필터API검토. 일반commodity_name=BITCOIN에는CME5BTC/Micro.1BTC/CoinbaseNano가섞임을최소3행으로확인,본가설은code133741/CME5BTC만사용. 다른자산원시수집없음. 2019-12-03~2026-08-25 BTC352주 JSON SHA707932e8df4ebd9d2035591a5c9b017b485f71d98d7aaefdba0aeb5349b6b34b,중복0,OI양면균형/공식change열차이0,6/7/8일외빈주0. 월요일예외2020-12-21/2023-07-03/2025-11-10,무조건화요일강제하면안됨.
- CFTC HistoricalSpecialAnnouncements https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm 직접읽은범위2017~2025상단(도구19820자로잘림;max확대재요청도같아전체41476자를읽었다고하지않음). 2023 ION중단:01-31보고→02-24공개,02-07→03-03,02-14→03-08,02-21→03-10,02-28→03-14,03-07→03-16,03-14→03-21. 2025정부셧다운10-01~11-12중단·백로그확인. 2025-12-09공식가속공지 https://www.cftc.gov/PressRoom/PressReleases/9147-25 전문은확보/읽음,11-18예전예정표를그대로쓰면틀림.공개주체데이터라하더라도보유일에안다고취급금지.
- 2023-02-16공식 https://www.cftc.gov/PressRoom/PressReleases/8662-23 직접읽음,각재개일은역사공지의실제issued서술로확인. FAQ의역사수정없음과달리역사공지는2019다른상품등정정사례를명시하므로'어떤CFTC자료도절대수정없음'으로일반화안함.BTC352주최초공개바이트와현재API동일성전체입증은아님.
- Q22피인용25건실제조회→Q23 Shen/Li/Luo,Option positions, non-momentum trading, and Bitcoin futures returns(10.1016/j.frl.2026.110300,OpenAlex06-04/출판9월권호).Hull공개OA메타데이터상PDF/record둘다403challenge,우회안함.ElsevierAPI200은1815bytecoredata뿐. RePEc https://econpapers.repec.org/article/eeefinlet/v_3a106_3ay_3a2026_3ai_3ac_3as1544612326008287.htm 초록직접확보:asset-manager **옵션**비모멘텀변화가2주후수익선택예측,미래수익이포지션을선도해인과가격충격아님,하방위험상태효과. 이는leveraged-money선물숏변화와다른별도다음가설,본문정의/기간/비용미확보.표제만보고전문읽음/실행가능알파로부르지않음.
- COT시각범위정밀화:2023공지에는각날실제issuing서술이있으나2025-12-09의표는**개정된예정공개표**다. 개별과거분단위수신완료증거를확보한것이아님. +2일여유와기본10일대기,전체과거배포일목록부재한계를명세에유지한다. 이를완전한point-in-time자료라고승격안함. 연구가능성전체종료사유는아니며새조건성과는개발자료가정하의검증이다.
