'use strict';
const $=s=>document.querySelector(s);
const colors={T1:'#244fc9',T2:'#a28441',T3:'#8c6fb3',T4:'#be825d',T5:'#b85c70',vol_long:'#178475',perp_hold:'#8d7ab8',spot_hold:'#77869b',cash:'#acb5c5'};
const order=['T1','vol_long','spot_hold','perp_hold','cash','T2','T3','T4','T5'];
const state={index:null,run:null,id:'evaluation',mode:'equity',visible:new Set(['T1','vol_long','spot_hold']),cache:new Map(),generation:0,hover:0};
const num=(x,d=2)=>x===null||x===undefined?'—':Number(x).toLocaleString('ko-KR',{minimumFractionDigits:d,maximumFractionDigits:d});
const signed=(x,d=2)=>(x>0?'+':x<0?'−':'')+num(Math.abs(x),d);
const cls=x=>x>0?'positive':x<0?'negative':'neutral';
const date=t=>new Date(t).toISOString().slice(0,10);
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function getStudy(id){if(!state.cache.has(id)){const response=await fetch(`assets/${id}.json`);if(!response.ok)throw new Error(`결과 요청 실패 (${response.status})`);state.cache.set(id,await response.json());}return state.cache.get(id);}
function showError(e){$('#error').textContent='결과를 불러오지 못했습니다. 새로고침하거나 하단 GitHub 텍스트 보고서를 확인해 주세요. '+e.message;$('#error').classList.remove('hidden');}
async function chooseStudy(id){
  const generation=++state.generation;$('#study-note').textContent='선택한 결과를 불러오는 중…';
  try{const run=await getStudy(id);if(generation!==state.generation)return;state.run=run;state.id=id;state.hover=0;
    const available=order.filter(k=>run.results[k]);state.visible=new Set([...state.visible].filter(k=>available.includes(k)));if(!state.visible.size)state.visible.add('T1');
    $('#error').classList.add('hidden');render();
  }catch(e){if(generation===state.generation)showError(e);}
}
function render(){
  const r=state.run,m=r.results.T1.metrics,q=r.quote;
  $('#study-note').textContent=`${r.note} · ${date(Date.parse(r.start))} ~ ${date(Date.parse(r.end)-1)} · 가상 1,000 ${q} · 실거래 아님`;
  const cards=[['T1 순수익률',signed(m.return_pct)+'%',`${signed(m.net_pnl)} ${q} · 종료 ${num(m.equity)} ${q}`,cls(m.return_pct)],
    ['최대 관측 낙폭','−'+num(m.max_drawdown_pct)+'%','시간별 관측 · 순간 최악값 아님','negative'],
    ['연환산 수익률',signed(m.cagr_pct)+'%','CAGR · 매년 같은 수익이라는 뜻 아님',cls(m.cagr_pct)],
    ['수익 난 분기',`${r.gate1.positive_quarters} / ${r.gate1.total_quarters}`,'부분 분기 포함 · 아래 상세 참조','neutral']];
  $('#metrics').innerHTML=cards.map(c=>`<div class="metric"><span>${c[0]}</span><strong class="${c[3]}">${c[1]}</strong><small>${c[2]}</small></div>`).join('');
  $('#chart-subtitle').textContent=`가상 시작금 1,000 ${q} · 기본 비용 조건 · 최종 정리 비용 포함`;
  $('#legend').innerHTML=order.filter(k=>r.results[k]).map(k=>`<button data-key="${k}" aria-pressed="${state.visible.has(k)}"><span class="swatch ${k}"></span>${escape(r.results[k].name)}</button>`).join('');
  $('#legend').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{const k=b.dataset.key;state.visible.has(k)?state.visible.delete(k):state.visible.add(k);b.setAttribute('aria-pressed',state.visible.has(k));$('#tooltip').classList.add('hidden');drawChart();}));
  const costs=[['기준가격 손익',m.gross_pnl],['수수료',-m.fees],['스프레드 · 슬리피지',-m.impact],['펀딩 수취 / 지급',m.funding],['최종 순손익',m.net_pnl]];
  $('#waterfall').innerHTML=costs.map((c,i)=>`<div class="cost-row ${i===4?'total':''}"><span>${c[0]}</span><b class="${cls(c[1])}">${signed(c[1])} <small>${q}</small></b></div>`).join('');
  $('#comparison tbody').innerHTML=order.filter(k=>r.results[k]).map(k=>{const x=r.results[k].metrics;return `<tr class="${k==='T1'?'primary':''}"><td><span class="strategy-id">${k.startsWith('T')?k:'·'}</span>${escape(r.results[k].name)}</td><td class="${cls(x.return_pct)}">${signed(x.return_pct)}%</td><td>−${num(x.max_drawdown_pct)}%</td><td>${num(x.sharpe)}</td><td>${num(x.mean_exposure*100,1)}%</td><td>${x.fills}</td></tr>`;}).join('');
  const quarters=r.results.T1.periods.quarterly;
  $('#quarters-summary').textContent=`양수 ${r.gate1.positive_quarters}개 · 최고 분기 제외 수익 ${signed(r.gate1.excluding_best_quarter_return_pct)}%`;
  const firstMonth=Number(r.start.slice(5,7)),firstDay=Number(r.start.slice(8,10)),lastDate=new Date(Date.parse(r.end));
  const firstPartial=(firstMonth-1)%3!==0||firstDay!==1;const lastPartial=lastDate.getUTCDate()!==1||lastDate.getUTCMonth()%3!==0;
  const qentries=Object.entries(quarters);
  $('#quarters').innerHTML=qentries.map(([key,v],i)=>`<div class="quarter ${v.return_pct>=0?'up':'down'}"><span>${key.replace('-Q',' Q')}${(i===0&&firstPartial)||(i===qentries.length-1&&lastPartial)?' (일부)':''}</span><b class="${cls(v.return_pct)}">${signed(v.return_pct)}%</b></div>`).join('');
  const more=[['최악 1일',signed(m.worst_1d_pct)+'%'],['최악 7일',signed(m.worst_7d_pct)+'%'],['최악 30일',signed(m.worst_30d_pct)+'%'],['일간 하위5% 평균',signed(m.cvar_5pct_daily_pct)+'%'],['실현 연변동성',num(m.realized_vol_pct)+'%'],['최대 관측 노출',num(m.max_exposure*100,1)+'%'],['회복 전 최장 경과',num(m.longest_underwater_days,1)+'일'],['종료 시 회복 여부',m.underwater_at_end?'미회복':'회복'],['포지션 보유 시간',num(m.active_hours_pct,1)+'%'],['완료 왕복 거래',m.round_trips+'회'],['롱 귀속 순손익',signed(m.directional_pnl.long)+' '+q],['숏 귀속 순손익',signed(m.directional_pnl.short)+' '+q],['거래 회전율',num(m.turnover_initial_multiple)+'× 초기자본'],['미체결·자료 공백 기록',m.skipped+'건'],['평가 기준',q==='USDC'?'기존 표본 회귀 확인':'외부 역사 모형']];
  $('#extra-metrics').innerHTML=more.map(([label,value])=>`<div><span>${label}</span><strong>${escape(value)}</strong></div>`).join('');
  $('#csv-link').href=`downloads/${state.id}.csv`;$('#json-link').href=`downloads/${state.id}.json.gz`;
  $('#stress').value='base';renderStress();drawChart();
}
function renderStress(){
  if(!state.run)return;const key=$('#stress').value,base=state.run.results.T1.metrics,m=key==='base'?base:state.run.stress[key].metrics;
  $('#stress-result').innerHTML=`<div><span>T1 순수익률</span><strong class="${cls(m.return_pct)}">${signed(m.return_pct)}%</strong><small>기본 대비 ${signed(m.return_pct-base.return_pct)}%p</small></div><div><span>최대 관측 낙폭</span><strong class="negative">−${num(m.max_drawdown_pct)}%</strong><small>가상 최종 자산 ${num(m.equity)}</small></div>`;
}
const NS='http://www.w3.org/2000/svg';
function element(tag,attrs,text){const node=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs||{}))node.setAttribute(k,v);if(text!==undefined)node.textContent=text;return node;}
function chartSeries(){return order.filter(k=>state.visible.has(k)&&state.run.results[k]).map(k=>({key:k,name:state.run.results[k].name,color:colors[k],points:[[Date.parse(state.run.start),1000,0],...state.run.results[k].curve]}));}
function drawChart(){
  if(!state.run)return;const svg=$('#chart'),w=svg.clientWidth,h=svg.clientHeight;svg.replaceChildren();svg.setAttribute('viewBox',`0 0 ${w} ${h}`);
  svg.setAttribute('aria-label',state.mode==='equity'?'전략별 날짜에 따른 가상 자산 비교':'전략별 날짜에 따른 관측 고점 대비 낙폭');
  const series=chartSeries(),left=48,right=12,top=14,bottom=30,pw=w-left-right,ph=h-top-bottom;
  const from=Date.parse(state.run.start),to=Date.parse(state.run.end);const value=p=>state.mode==='equity'?p[1]:-p[2];
  let min=state.mode==='equity'?1000:0,max=min;
  for(const s of series)for(const p of s.points){min=Math.min(min,value(p));max=Math.max(max,value(p));}
  const gap=Math.max((max-min)*.1,state.mode==='equity'?5:.5);min-=gap;max+=gap;
  const x=t=>left+(t-from)/(to-from)*pw,y=v=>top+(max-v)/(max-min)*ph;
  for(let i=0;i<5;i++){const v=min+(max-min)*i/4,yy=y(v);svg.append(element('line',{x1:left,x2:w-right,y1:yy,y2:yy,stroke:'#e9edf3','stroke-width':1}));svg.append(element('text',{x:left-8,y:yy+3,fill:'#8490a2','font-size':10,'text-anchor':'end'},state.mode==='equity'?num(v,0):num(v,1)+'%'));}
  const ticks=w<500?2:4;
  for(let i=0;i<=ticks;i++){const t=from+(to-from)*i/ticks;svg.append(element('text',{x:x(t),y:h-5,fill:'#8490a2','font-size':10,'text-anchor':i===0?'start':i===ticks?'end':'middle'},date(i===ticks?t-1:t).slice(0,7)));}
  const base=state.mode==='equity'?1000:0;svg.append(element('line',{x1:left,x2:w-right,y1:y(base),y2:y(base),stroke:'#bbc6d9','stroke-dasharray':'3 4'}));
  for(const s of series){const path=s.points.map((p,i)=>(i?'L':'M')+x(p[0]).toFixed(2)+' '+y(value(p)).toFixed(2)).join(' ');svg.append(element('path',{d:path,fill:'none',stroke:s.color,'stroke-width':s.key==='T1'?2.3:1.5,'stroke-linejoin':'round','stroke-linecap':'round','data-series':s.key}));}
  if(!series.length)svg.append(element('text',{x:w/2,y:h/2,fill:'#667187','font-size':12,'text-anchor':'middle'},'범례에서 비교할 전략을 선택하세요.'));
  svg.append(element('line',{id:'crosshair',x1:0,x2:0,y1:top,y2:h-bottom,stroke:'#7f8ca4','stroke-dasharray':'2 3',visibility:'hidden'}));
  state.chart={left,pw,from,to,w,series,x};
}
function hoverChart(index){
  if(!state.chart||!state.chart.series.length)return;const c=state.chart,points=c.series[0].points,i=Math.max(0,Math.min(points.length-1,index));state.hover=i;
  const t=points[i][0],cross=$('#crosshair');cross.setAttribute('x1',c.x(t));cross.setAttribute('x2',c.x(t));cross.setAttribute('visibility','visible');
  const tip=$('#tooltip');tip.replaceChildren();const title=document.createElement('b');title.textContent=date(i===0?t:t-1)+' UTC';tip.append(title);
  for(const s of c.series){const p=s.points[i];if(!p)continue;const span=document.createElement('span');span.textContent=`${s.name}  ${state.mode==='equity'?num(p[1])+' '+state.run.quote:'−'+num(p[2])+'%'}`;tip.append(span);}
  tip.classList.remove('hidden');
}
function pointerChart(e){if(!state.chart)return;const c=state.chart,rect=$('#chart').getBoundingClientRect(),fraction=Math.max(0,Math.min(1,(e.clientX-rect.left-c.left)/c.pw));const length=c.series[0]?.points.length||0;hoverChart(Math.round(fraction*(length-1)));}
function renderVerdict(report,index){
  const c=report.gate1.checks,m=report.results.T1.metrics,b=report.results.vol_long.metrics;
  const rows=[['기본·비용 2배 모두 순이익',c.base_and_double_cost_positive],['수익 분기 ≥ 11 / 16개',c.two_thirds_positive_quarters],['기본 최대 관측 낙폭 ≤ 12%',c.drawdown_at_most_12pct],['42일·84일 모두 손실인 상황 아님',c.neighbors_not_both_losing],['위험조절 보유보다 높은 샤프',c.sharpe_above_risk_matched_hold],['보수적 담보완충 검사 위반 없음',c.no_margin_buffer_breach]];
  $('#gates').innerHTML=rows.map(([label,pass])=>`<li><span>${label}</span><b class="${pass?'pass':'fail'}">${pass?'통과':'미달'}</b></li>`).join('');
  const bs=report.bootstrap.find(x=>x.block_days===14);
  $('#confidence').innerHTML=`<div><span>평균 일간 수익 · 95% 구간</span><code>${signed(bs.mean_daily_pct_ci95[0],4)} ~ ${signed(bs.mean_daily_pct_ci95[1],4)}%</code></div><div><span>샤프 차이 · 95% 구간</span><code>${signed(bs.sharpe_difference_ci95[0],3)} ~ ${signed(bs.sharpe_difference_ci95[1],3)}</code></div><div><span>샤프 점추정 · T1 / 위험조절 보유</span><code>${num(m.sharpe,3)} / ${num(b.sharpe,3)}</code></div>`;
  $('#carry-shocks').innerHTML='<table><thead><tr><th>BTC 상승 충격</th><th>선물 담보 잔액¹</th><th>5% 예시 완충금</th></tr></thead><tbody>'+index.carry.shock_rows.map(r=>`<tr><td>+${r.btc_change_pct}%</td><td>${num(r.short_collateral_before_costs,0)} USDC</td><td>${num(r.illustrative_5pct_buffer,0)} USDC</td></tr>`).join('')+'</tbody></table><p class="fine">¹ 펀딩·수수료·담보 이동 없음 가정. 실제 청산 가격 계산이 아닙니다.</p>';
}
$('#stress').addEventListener('change',renderStress);
$('#study').addEventListener('change',e=>chooseStudy(e.target.value));
document.querySelectorAll('[data-chart]').forEach(b=>b.addEventListener('click',()=>{state.mode=b.dataset.chart;document.querySelectorAll('[data-chart]').forEach(el=>{const active=el===b;el.classList.toggle('active',active);el.setAttribute('aria-pressed',active);});$('#chart-title').textContent=state.mode==='equity'?'가상 자산의 변화':'관측 고점 대비 낙폭';$('#tooltip').classList.add('hidden');drawChart();}));
$('#chart').addEventListener('pointermove',pointerChart);$('#chart').addEventListener('pointerdown',pointerChart);$('#chart').addEventListener('pointerleave',()=>{$('#tooltip').classList.add('hidden');$('#crosshair')?.setAttribute('visibility','hidden');});
$('#chart').addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();hoverChart(state.hover+(e.key==='ArrowLeft'?-1:1));}});
new ResizeObserver(()=>{drawChart();$('#tooltip').classList.add('hidden');}).observe($('#chart'));
(async()=>{try{const response=await fetch('assets/index.json');if(!response.ok)throw new Error('목록을 읽을 수 없습니다.');state.index=await response.json();$('#study').innerHTML=state.index.studies.map(s=>`<option value="${s.id}">${escape(s.label)}</option>`).join('');$('#study').disabled=false;const evaluation=await getStudy('evaluation');renderVerdict(evaluation,state.index);await chooseStudy('evaluation');}catch(e){showError(e);}})();
