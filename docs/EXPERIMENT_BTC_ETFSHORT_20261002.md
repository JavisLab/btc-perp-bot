# BTC ETF 보고 거래압력의 추가정보 · 성과 전 명세

## 새 경제가설·범위
Q61 Onishchenko(2026)의 BTC ETF 공매도 흐름과 다음2~6거래일 수익 관계, Q60의 ETF/현물 정보발견 차이를 출발점으로 삼는다. 규제시장 참가자·중개자의 거래에는 다른 장소의 BTC 수급/재고 정보가 남을 수 있다. 하지만 FINRA 공매도 표시 거래량은 순숏 포지션·주식대차잔고·순기관매도를 뜻하지 않는다. 중개자의 상쇄 매수·거래소 내 체결은 일부 제외된다. **보고된 short 비중 변화가 BTC 가격과 ETF 거래활동을 통제한 뒤 다음7달력일 BTC 수익에 추가 정보를 주는가**가 우리의 한정된 질문이다.
기본 **EF_INFO**. 유료 Bloomberg 유통주식수·ETF수익·대차료를 사용하는 원논문 복제가 아니다. 우리의 분모는 같은 FINRA 정규시간 보고 거래량이며, 실제 거래는 BTC spot/perp뿐이다. 기존198/273 및 새704계좌 불변. 이미 본 BTC 경로는 개발자료, 미사용OOS 아님. 세 ETF는 원문에서 큰 유동성을 보인 IBIT/FBTC/GBTC로 제한했으므로 현재 알려진 종목선택의 편향도 남는다. 이 명세 전 아래 피처·예측·성과는 계산하지 않았다.

## 고정 자료·정의·가용성
`data/btc-etfshort-20261002/btc-etfshort.json` SHA256 **759c0daec5f061c2a5dfa9c29982faadad3fde971c0c70813fe71c02b1221a23**, 2024-01-11~2026-08-31 공식32월 색인661거래일×3종목. 원문 exact-row subset/전체응답SHA/footer검사/URL·시각과 API응답 보존. 최근229일×3종목=687합계가 API 각 reporting facility합과 Decimal정확일치. API는최근365일만반환하여전체기간으로잘못쓰지않음. ShortVolume은ShortExemptVolume을이미포함, 더하지 않는다. 2026소수수량도절삭안함. 과거 최초발표빈티지·모든수정은복구하지못했으므로현재아카이브제약을남긴다. 추후확보자료를성과에맞춰교체하지않는다.
일 D는 미국 거래일의 달력날짜. 공식파일은 D 18:00 America/New_York까지발표(여름22/겨울23UTC). 기본 가용=A_D=그 UTC시각+24실제시간, 판단은A_D이후첫00UTC. data_delay7은A_D에7×24h추가. 월별transaction 파일·장외시간 자료를같은시각으로소급가용처리하지않는다. T매일00UTC에서A_D≤T인최신보고일하나만선택, T−A_D>7일이면외부피처결측. 7일은해당scenario의가용시각으로측정. 미국조기폐장일도18ET공표상한을사용한다. 서머타임은IANA America/New_York, UTC완료봉시각과구분한다.

## 가격 아닌 정보 측정
각 보고일 D, 각종목 j에 대해 q_jD=ShortVolume/TotalVolume. 그날보다앞선같은종목의20개보고일평균을빼고3종목동일가중평균해 x_D를만든다. 분모양수·필수20이전보고일·3종목완전자료가없으면결측, 미래보충/다른종목대체없음. 거래활동 a_D=3종목평균 ln(TotalVolume_jD / 이전20개보고일 TotalVolume_j 평균). 상대거래활동으로주당BTC수량이서로다른ETF의거래량합산왜곡을피한다.
가격은공식BTC spot1h의완료종가 C_t. r_now(T)=ln(C_T/C_(T−1일)). r_report(D)=ln(C_(D16ET)/C_(D16ET−24h)), D16ET는UTC정수시간이므로완료1h종가로측정. 이는조기폐장일실제ETF마지막체결시각이아니라그날16ET까지알려진BTC가격대조다. 모두A_D전가용이며미래매매가격아님. 필요한봉·완료close_time·양수가격없으면피처결측.
T의가용보고일로 [r_now,r_report,a,x]를만든다. 실제 예측목표 y_T=ln(C_(T+7일)/C_T). 7달력일은원논문의5거래일과동일하지않다. 미래목표는학습label 또는성과후MSE에만사용한다.

## 고정 예측·학습·오차
각T에서훈련판단일U∈[T−372일,T−8일]의365개달력일중유효피처·완료목표를가진행만사용, 최소126행. label완료U+7일≤T−1일이므로추가1일purge. 일별피처의가용성을각scenario대로과거U시점에다시적용한다. 결과보고서기간전체를먼저적합하거나현재T이후y를쓰지않는다.
- INFO: [1,r_now,r_report,a,x]. short압력의음의기전을고정해 x계수≤0인제약최소제곱. 비제약OLS의x계수가양수면 PRICE로재적합하고x계수/공분산행·열을0으로둔다.
- PRICE(가격/활동대조): [1,r_now,r_report,a] OLS.
- RAW(가격·활동통제제거): [1,x], x계수≤0. 양수이면절편평균만재적합.
수치계산은피처센터링SVD OLS, 유효설계rank부족/비유한값이면해당예측결측. 학습창·순위/제약활성·계수·평균·날짜·공분산보존. 세모형은동일유효행과최소126을사용하여MSE비교가달라지지않게한다.
추정평균오차SE는Newey–West sandwich, 7달력일 lag의Bartlett w_l=1−l/8. 잔차score z_u=X_u*e_u, meat=Σz_uz_u' + Σ_(l=1..7)w_l Σ_(u−v=l일)(z_uz_v'+z_vz_u'). bread=(X'X)^−1, covariance=n/(n−k)*bread*meat*bread, SE=sqrt(max(0,X_new covariance X_new')). 결측달력일을인접행으로압축해lag로쓰지않음. 제약활성이면실제자유열의HAC로재계산한다. 한 SE는거래필터이지수익보장/유의성검정의통과선이아니다. 겹친7일수익·반복개발·적은ETF기간제약은남는다.

## 기본과 모든대조의 BTC 포지션
기존 E_SPOT core =max(0,s)*w, s는기존20/60/120일모멘텀·EMA8/32,16/64,32/128의6부호평균. EMA·일종가warmup은기존Market 그대로. w=min(1,target/완료20일spot일로그수익표본std×sqrt365의역수), target기본.20/위험민감도.10, 0vol이면0. core위험결측이면목표보류.
모형예측 μ의양/음방향마다 H=ln(1+.0023) (현물롱), ln(1+.0013) (perp숏). **|μ|>H+SE**여야 override. cost_x2에서도선별/예측은기본비용기준동일,순비용만높여민감도를본다. 이필터는실제미래funding을미리알지못하며 funding은원장에서만실제값반영.
- **EF_INFO 기본**: INFO·PRICE예측이둘다유효, 위필터충족, δ=μ_INFO−μ_PRICE가μ_INFO와같은부호이며 |δ|>1e−12일때방향sign(μ_INFO)*w로override. INFO 제약이활성이면δ=0으로명시하여수치오차로추가정보를만들지않는다. 그외core. 이는두조건부예측의차이지인과효과아님.
- EF_PRICE: PRICE예측만위필터충족하면 sign(μ_PRICE)*w, 그외core.
- EF_RAW: RAW예측만위필터충족하면 sign(μ_RAW)*w, 그외core.
- EF_INV: EF_INFO가override한동일날·동일위험의정확반대방향, 그외core. 반대방향의다른체결비용은실제원장에반영하며기본필터를거꾸로재최적화하지않음.
- EF_TREND: 외부피처미사용core항상. 저장E_SPOT base일별·주요회계정확동일필수.
보고자료없는2022/23 및모형warmup도모든규칙core. 이는그기간ETF정보가있었다는뜻이아니다. 매일재판단(고정7일강제보유아님), flat/방향변경/수량조절은공통원장. 양수는BSspot롱,음수는BPperp숏,동시양다리없음·목표gross≤1. 달력명세/정보·모형·위험·대조를성과후바꾸거나대조를승격하지않는다.

## 60계좌·비용·기간·사전기각
5규칙×6조건×2기간=60계좌. 주2022-01-01~2026-01-01,최근2026-01-01~2026-09-01. base,cost_x2,delay1,delay24,risk10,data_delay7. 실행지연은예측을재계산하지않고기본T+1h시가에추가1/24h,자료지연은과거/현재가용피처와학습모형을재계산한다. 모두1000USDT·현금이자0,spot10/perp5bp+impact각1.5bp·실제funding,비용2배양쪽모두.
BTC-only btc_target_ledger.py불변,5%p밴드/반전·청산예외/12회postcost수량·spot.00001/perp.001절삭·최소5/50USDT(선물감소예외)·atomic전환·최종dust강제청산. 공식시간mark시가proxy·담보5%/시간연속DD포함. 실제호가/부분체결/과거전규정/순간청산·운영위험을완전복원한것아님. 가격SHA9909be60d1d4db6b47f766de26894de9cbb55222530f9c3bbdbc19ef0899faa4·기존329ZIP보존.
기본주수익>52.838713%,DD≤13.561952%,최근수익>4.628391%,DD≤10.450946%,연vol≤13.343621/16.520409%,주Sharpe≥.8,4년중≥3양수,주완료보유구간≥20,양기간담보5%미달0; base/cost_x2/delay1/delay24/data_delay7 양기간순손익>0. 원래주E_SPOT/최근E_LS기준불변.
추가: EF_INFO 순손익이양기간 EF_PRICE·EF_TREND보다높고, DD가양기간 EF_PRICE보다크지않으며, 공통유효예측일의INFO7일목표MSE가PRICE보다양기간모두엄격히낮아야유용성통과. MSE는target완료가평가기간끝이하인공통일만,결측이면추가가치실패. 레버리지확대만의수익을알파로안부름. 사전기준완화/과거실패삭제·승격없음.

## 보존·검사·공개
각모형의일별가용report·age·20이전보고일·훈련/label최후일·rank/제약/HAC·예측·순증분·override/현금/core fallback·고유보고일수보존. 기본·모든비교/실패·연도/최근/비용/실제funding·롱숏손익·노출·무거래·보유구간보존. 모든base평균및EF_PRICE/EF_TREND차이의7/14/28일블록2000회95%구간. 이것으로선택편향·과거수정자료한계를제거했다고주장안함.
구현후성과전: exempt중복금지·소수단위·20일현재제외·미래보고교란·18ET DST/24h가용·추가7일·stale경계·7일목표purge·제약양수zero nested동일·불규칙달력HAC·수수료/펀딩방향/1h체결·core fallback 검사. 별도검산은study/ledger를import하지않고 exact FINRA BTC행·API합계/시계·가격raw ZIP·정규방정식OLS/제약·別HAC計算/모든예측·수량폐형식/무거래·Decimal원장·원시funding/mark·시간DD·노출/margin검산. 새60계좌소켓차단byte재현. 결과후동일규칙구제대신인터넷원문조사계속. 검산결과만기존승인Pages에게시·실제공개확인한다.
