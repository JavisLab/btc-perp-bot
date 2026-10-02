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
