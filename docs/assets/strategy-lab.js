'use strict';
const $=s=>document.querySelector(s),NS='http://www.w3.org/2000/svg';
const colors={primary:'#087b70',spot:'#4669ad',old:'#a4aab6',buyhold:'#c09340',cash:'#7b8590'};
const scenarios={base:'기본',cost_x2:'비용 2배',delay1:'추가 1시간 지연',delay24:'추가 24시간 지연',risk10:'위험 목표 10%',risk30:'위험 목표 30%'};
let index,cache={},period='main',strategy='E_SPOT',scenario='base',mode='equity',hidden=new Set(),chartSeries=[],cursor=null,chartBox,request=0;
const fmt=(n,d=2)=>n==null?'—':Number(n).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(n,d=2)=>n==null?'—':(n<0?'−':n>0?'+':'')+fmt(Math.abs(n),d);
const cls=n=>n<0?'negative':n>0?'positive':'muted';
const date=t=>new Date(t-1).toISOString().slice(0,10);
function element(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function svgel(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e;}
function report(n=strategy,s=scenario){return s==='base'?cache[period].results[n]:cache[period].scenarios[n][s];}
function render(){
 const r=report(),m=r.metrics,info=index.strategies[strategy];
 $('#description').textContent=info.description;
 $('#period-note').textContent=(period==='main'?'2022-01-01 ~ 2025-12-31 · 4년':'2026-01-01 ~ 2026-08-31 · 8개월')+' · Binance / USDT · 각 구간 1,000에서 시작 · '+scenarios[scenario]+' · 탐색 비교';
 const cards=[['누적 수익률',signed(m.return_pct)+'%',cls(m.return_pct),'최종 자산 '+fmt(m.equity)+' USDT'],['연복리 수익률',signed(m.cagr_pct)+'%',cls(m.cagr_pct),period==='recent'?'8개월의 기계적 연환산 · 예측 아님':'4년 누적 성과의 복리 환산'],['최대 관측 낙폭',fmt(m.max_drawdown_pct)+'%','negative','시간별 관측 · 순간 손실 한도 아님'],['샤프 지수',fmt(m.sharpe),'','무위험 수익 0 · 일 수익률 기준']];
 $('#metrics').replaceChildren(...cards.map(([l,v,c,n])=>{const d=element('div',undefined,'metric');d.append(element('span',l,'label'),element('strong',v,c),element('small',n));return d;}));
 $('#attribution').replaceChildren(...[['가격 손익',m.gross_pnl],['펀딩 손익',m.funding],['수수료',-m.fees],['추가 체결비용',-m.impact],['순손익',m.net_pnl]].map(([label,value])=>{const d=element('div',undefined,'row');d.append(element('span',label),element('b',signed(value),cls(value)));return d;}));
 const years=Object.entries(r.periods.yearly),max=Math.max(1,...years.map(([,v])=>Math.abs(v.return_pct)));
 $('#annual').replaceChildren(...years.map(([y,v])=>{const d=element('div',undefined,'annual-row'),svg=svgel('svg',{viewBox:'0 0 100 8',preserveAspectRatio:'none','aria-hidden':true});svg.append(svgel('rect',{x:0,y:0,width:100,height:8,rx:4,fill:'#f1f4f6'}),svgel('rect',{x:0,y:0,width:Math.abs(v.return_pct)/max*100,height:8,rx:4,fill:v.return_pct<0?'#d0767a':'#087b70'}));d.append(element('span',y),svg,element('b',signed(v.return_pct)+'%',cls(v.return_pct)));return d;}));
 $('#csv').href='downloads/search-'+period+'.csv';
 $('#chart-note').textContent=index.strategies[strategy].label+' · '+scenarios[scenario]+' / 비교군은 기본 조건 유지';
 chartSeries=[{key:'primary',id:strategy,label:'선택 전략',curve:r.curve},
  {key:'spot',id:'V_SPOT',label:'위험조절 현물 보유',curve:cache[period].results.V_SPOT.curve},
  {key:'old',id:'T1_OLD',label:'기존 T1',curve:cache[period].results.T1_OLD.curve},
  {key:'buyhold',id:'H_SPOT',label:'현물 100% 보유',curve:cache[period].results.H_SPOT.curve},
  {key:'cash',id:'CASH',label:'현금',curve:cache[period].results.CASH.curve}];
 $('#legend').replaceChildren(...chartSeries.map(s=>{const b=element('button',undefined,'series-'+s.key);b.type='button';b.dataset.series=s.key;b.setAttribute('aria-pressed',String(!hidden.has(s.key)));b.append(element('i'),document.createTextNode(s.label));b.addEventListener('click',()=>{hidden.has(s.key)?hidden.delete(s.key):hidden.add(s.key);b.setAttribute('aria-pressed',String(!hidden.has(s.key)));draw();});return b;}));
 cursor=null;draw();renderTable();renderStress();
}
function draw(){
 if(!chartSeries.length)return;
 const svg=$('#chart'),w=Math.max(240,svg.clientWidth),h=svg.clientHeight||310,pad={l:50,r:12,t:18,b:31};
 const active=chartSeries.filter(s=>!hidden.has(s.key)),all=active.flatMap(s=>s.curve.map(p=>mode==='equity'?p[1]:-p[2]));
 let lo=Math.min(mode==='equity'?1000:0,...all),hi=Math.max(mode==='equity'?1000:0,...all);
 if(hi-lo<1){lo-=mode==='equity'?10:1;hi+=mode==='equity'?10:0;}else{const space=(hi-lo)*.07;lo-=space;hi+=mode==='equity'?space:0;}
 const c=chartSeries[0].curve,n=c.length,x=i=>pad.l+i/(n-1)*(w-pad.l-pad.r),y=v=>pad.t+(hi-v)/(hi-lo)*(h-pad.t-pad.b);
 chartBox={w,h,pad,x,y,n};svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.replaceChildren();
 for(let j=0;j<5;j++){const v=lo+(hi-lo)*j/4,yy=y(v);svg.append(svgel('line',{x1:pad.l,y1:yy,x2:w-pad.r,y2:yy,class:'chart-grid'}),svgel('text',{x:pad.l-9,y:yy+4,'text-anchor':'end',class:'chart-axis'},mode==='equity'?fmt(v,0):fmt(v,1)+'%'));}
 for(let j=0;j<4;j++){const i=Math.round((n-1)*j/3);svg.append(svgel('text',{x:x(i),y:h-7,'text-anchor':j===0?'start':j===3?'end':'middle',class:'chart-axis'},date(c[i][0]).slice(0,7)));}
 for(const s of active){const d=s.curve.map((p,i)=>(i?'L':'M')+x(i).toFixed(2)+','+y(mode==='equity'?p[1]:-p[2]).toFixed(2)).join(' ');svg.append(svgel('path',{d,stroke:colors[s.key],class:'chart-line '+s.key,'data-series':s.key}));}
 $('#chart-title').textContent=mode==='equity'?'가상 자산의 변화':'고점 대비 낙폭';
 svg.setAttribute('aria-label',mode==='equity'?'선택 전략과 비교군의 일별 가상 자산':'선택 전략과 비교군의 일별 고점 대비 낙폭');
 if(cursor!==null)showReadout();else $('#readout').textContent='차트를 터치하거나, 포커스 후 ← → 키로 날짜별 값을 확인하세요.';
}
function showReadout(){
 if(cursor===null||!chartBox)return;cursor=Math.max(0,Math.min(chartBox.n-1,cursor));$('#chart .chart-marker')?.remove();
 $('#chart').append(svgel('line',{x1:chartBox.x(cursor),x2:chartBox.x(cursor),y1:chartBox.pad.t,y2:chartBox.h-chartBox.pad.b,class:'chart-marker'}));
 const strings=chartSeries.filter(s=>!hidden.has(s.key)).map(s=>s.label+' '+(mode==='equity'?fmt(s.curve[cursor][1]):'−'+fmt(s.curve[cursor][2])+'%'));
 $('#readout').textContent=date(chartSeries[0].curve[cursor][0])+' · '+strings.join(' / ');
}
function renderTable(){
 const family=$('#family').value,names=[...index.candidates,...index.benchmarks].filter(n=>family==='all'||family==='candidate'&&index.candidates.includes(n)||index.strategies[n].family===family);
 $('#comparison tbody').replaceChildren(...names.map(n=>{const r=cache[period].results[n],m=r.metrics,ys=Object.values(r.periods.yearly),tr=element('tr',undefined,n===strategy?'selected-row':''),name=element('td'),b=element('button',index.strategies[n].label);b.type='button';b.dataset.strategy=n;b.addEventListener('click',()=>{$('#strategy').value=n;selectStrategy(n);$('#metrics').scrollIntoView({block:'start'});});name.append(b,element('span',n,'row-id'));tr.append(name,element('td',signed(m.return_pct)+'%',cls(m.return_pct)),element('td',signed(m.cagr_pct)+'%',cls(m.cagr_pct)),element('td',fmt(m.max_drawdown_pct)+'%'),element('td',fmt(m.sharpe)),element('td',ys.filter(y=>y.return_pct>0).length+' / '+ys.length));const status=element('td'),gate=index.selection.decisions[n];status.append(element('span',gate?(gate.pass?'통과':'미달 '+Object.values(gate.checks).filter(x=>!x).length+'개'):'비교 기준',gate?'gate-badge':'muted'));tr.append(status);return tr;}));
}
function renderStress(){
 const all={base:cache[period].results[strategy],...(cache[period].scenarios[strategy]||{})};
 $('#stress-table tbody').replaceChildren(...Object.entries(all).map(([k,r])=>{const tr=element('tr'),m=r.metrics;tr.append(element('td',scenarios[k]),element('td',signed(m.return_pct)+'%',cls(m.return_pct)),element('td',fmt(m.max_drawdown_pct)+'%'),element('td',fmt(m.fees)),element('td',signed(m.funding),cls(m.funding)));return tr;}));
}
function selectStrategy(n){strategy=n;const isCandidate=index.candidates.includes(n);$('#scenario').disabled=!isCandidate;if(!isCandidate){scenario='base';$('#scenario').value='base';}render();}
async function selectPeriod(value){
 const token=++request;$('#period').disabled=true;$('#strategy').disabled=true;$('#scenario').disabled=true;
 try{if(!cache[value]){const r=await fetch('assets/search-'+value+'.json?v=1001r2');if(!r.ok)throw Error('구간 자료 HTTP '+r.status);cache[value]=await r.json();}if(token!==request)return;period=value;render();}
 catch(e){$('#error').textContent='자료를 불러오지 못했습니다. 새로고침하거나 텍스트 보고서를 확인하세요. '+e.message;$('#error').classList.remove('hidden');}
 finally{if(token===request){$('#period').disabled=false;$('#strategy').disabled=false;$('#scenario').disabled=!index.candidates.includes(strategy);}}
}
async function init(){
 try{const r=await fetch('assets/search-index.json?v=1001r2');if(!r.ok)throw Error('목록 HTTP '+r.status);index=await r.json();
  const groups=[['후보',index.candidates],['비교 기준',index.benchmarks]];$('#strategy').replaceChildren(...groups.map(([label,keys])=>{const g=element('optgroup');g.label=label;g.append(...keys.map(n=>{const o=element('option',index.strategies[n].label);o.value=n;return o;}));return g;}));$('#strategy').value=strategy;
  const checks=index.selection.decisions.E_SPOT.checks,names={cagr_ge_10:'연복리 수익률 10% 이상',sharpe_ge_08:'샤프 0.8 이상',drawdown_le_25:'최대 관측 낙폭 25% 이하',positive_years_ge_3:'4년 중 3년 이상 수익',cost_x2_positive:'비용 2배에서도 순이익',excluding_best_quarter_positive:'최고 분기를 빼도 누적 양수',margin_ok:'모형 담보 진단 위반 없음'};
  $('#gates').replaceChildren(...Object.entries(names).map(([key,label])=>{const li=element('li',undefined,checks[key]?'':'failed');li.append(element('span',label),element('span',checks[key]?'통과':'미달 · 2 / 4년'));return li;}));
  const u=index.uncertainty.periods.main.E_SPOT[0];$('#confidence').replaceChildren(...[['평균 일간 수익 · 95% 구간',u.mean_daily_pct_ci95,'%'],['위험조절 현물 대비 샤프 차이 · 95%',u.sharpe_difference_ci95,'']].map(([label,values,unit])=>{const d=element('div',label,'confidence-row');d.append(element('b',signed(values[0],3)+unit+' ~ '+signed(values[1],3)+unit));return d;}));
  $('#period').addEventListener('change',e=>selectPeriod(e.target.value));$('#strategy').addEventListener('change',e=>selectStrategy(e.target.value));$('#scenario').addEventListener('change',e=>{scenario=e.target.value;render();});$('#family').addEventListener('change',renderTable);
  document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{mode=b.dataset.mode;document.querySelectorAll('[data-mode]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});draw();}));
  $('#chart').addEventListener('pointermove',e=>{if(!chartBox)return;const box=$('#chart').getBoundingClientRect();cursor=Math.round((e.clientX-box.left-chartBox.pad.l)/(chartBox.w-chartBox.pad.l-chartBox.pad.r)*(chartBox.n-1));showReadout();});
  $('#chart').addEventListener('pointerdown',e=>{if(!chartBox)return;const box=$('#chart').getBoundingClientRect();cursor=Math.round((e.clientX-box.left-chartBox.pad.l)/(chartBox.w-chartBox.pad.l-chartBox.pad.r)*(chartBox.n-1));showReadout();});
  $('#chart').addEventListener('keydown',e=>{if(!chartBox||!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();cursor=e.key==='Home'?0:e.key==='End'?chartBox.n-1:(cursor??chartBox.n-1)+(e.key==='ArrowRight'?1:-1);showReadout();});
  new ResizeObserver(draw).observe($('#chart'));await selectPeriod('main');
 }catch(e){$('#error').textContent='페이지 자료를 불러오지 못했습니다. '+e.message;$('#error').classList.remove('hidden');}
}
init();
