'use strict';
(()=>{
const $=id=>document.getElementById(id),fmt=(x,d=2)=>x===null?'—':(x<0?'−':x>0?'+':'')+Math.abs(x).toFixed(d),plain=(x,d=2)=>x===null?'—':Number(x).toFixed(d);
let data,mode='equity',curve=[],values=[],point=0,chartWidth=920;
const ns='http://www.w3.org/2000/svg';
function svg(tag,attrs,text){const e=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);if(text!==undefined)e.textContent=text;return e;}
function row(a,b){return '<div class="value-row"><span>'+a+'</span><b>'+b+'</b></div>';}
function chart(){
 const area=$('chart');area.replaceChildren();let peak=1000;chartWidth=Math.max(280,area.clientWidth);area.setAttribute('viewBox','0 0 '+chartWidth+' 310');
 values=curve.map(x=>{peak=Math.max(peak,x[1]);return mode==='equity'?x[1]:(x[1]/peak-1)*100;});
 const lo=Math.min(mode==='equity'?1000:0,...values),hi=Math.max(mode==='equity'?1000:0,...values),pad=Math.max((hi-lo)*.08,mode==='equity'?1:.1),bottom=lo-pad,top=hi+pad;
 const X=i=>48+i/(values.length-1)*(chartWidth-60),Y=v=>260-(v-bottom)/(top-bottom)*235;
 for(let k=0;k<=4;k++){const v=bottom+(top-bottom)*k/4,y=Y(v);area.append(svg('line',{x1:48,x2:chartWidth-12,y1:y,y2:y,class:'grid-line'}),svg('text',{x:40,y:y+4,'text-anchor':'end',class:'chart-axis'},v.toFixed(mode==='equity'?0:1)));}
 for(const i of chartWidth<500?[0,values.length-1]:[0,Math.floor((values.length-1)/2),values.length-1])area.append(svg('text',{x:X(i),y:294,'text-anchor':i===0?'start':i===values.length-1?'end':'middle',class:'chart-axis'},new Date(curve[i][0]-1).toISOString().slice(0,10)));
 area.append(svg('path',{d:values.map((v,i)=>(i?'L':'M')+X(i).toFixed(2)+','+Y(v).toFixed(2)).join(' '),class:'chart-line'}));
 point=Math.min(point,values.length-1);area.append(svg('line',{id:'focus-line',x1:X(point),x2:X(point),y1:25,y2:260,class:'chart-focus'}));
 $('chart-title').textContent=mode==='equity'?'계좌 자산 · USDT':'일말 고점 대비 낙폭 · %';area.setAttribute('aria-label',$('chart-title').textContent+' · 좌우 키로 탐색');readout();
}
function readout(){if(!curve.length)return;const x=48+point/(values.length-1)*(chartWidth-60);$('focus-line').setAttribute('x1',x);$('focus-line').setAttribute('x2',x);$('chart-readout').textContent=new Date(curve[point][0]-1).toISOString().slice(0,10)+' UTC · '+(mode==='equity'?'자산 '+plain(values[point])+' USDT':'일말 낙폭 '+fmt(values[point])+'%');}
function render(){
 const p=$('period').value,f=$('family').value,c=$('scenario').value,r=data.results[p][f][c],s=r.summary;
 $('status-note').textContent=data.periods[p]+' · '+data.labels[f]+' · '+data.scenarios[c]+' · 탐색 결과 / 사전 채택 기준 미달';
 const metrics=[['누적 수익률',fmt(s.return_pct)+'%'],[p==='main'?'연복리 수익률':'왕복 거래',p==='main'?fmt(s.cagr_pct)+'%':s.trades+'회'],['5분 종가 최대낙폭',plain(s.dd_pct)+'%'],['순손익',fmt(s.net)+' USDT']];
 $('metrics').innerHTML=metrics.map(([label,value])=>'<div class="metric"><span>'+label+'</span><b>'+value+'</b></div>').join('');
 $('years').innerHTML=Object.entries(s.annual).map(([y,v])=>row(y,fmt(v)+'%')).join('');
 $('sides').innerHTML=['long','short'].map(side=>row(side==='long'?'롱':'숏',s.sides[side].trades+'회 · '+fmt(s.sides[side].net)+' USDT')).join('');
 $('comparison').innerHTML=Object.entries(data.labels).map(([id,label])=>{const a=data.results[p][id].base.summary;return '<article class="candidate" data-family="'+id+'"><h4>'+label+'</h4><strong class="'+(a.return_pct<0?'neg':'pos')+'">'+fmt(a.return_pct)+'%</strong><p>낙폭 '+plain(a.dd_pct)+'% · '+a.trades+'회 거래</p><p>'+(p==='main'?'수익 연도 '+a.positive_years+'/4':'최근 8개월 · 연환산 아님')+'</p></article>';}).join('');
 $('stress').innerHTML='<table><thead><tr><th>조건</th><th>누적 수익률</th><th>최대낙폭</th><th>거래수</th><th>순손익 USDT</th></tr></thead><tbody>'+Object.entries(data.scenarios).map(([id,label])=>{const a=data.results[p][f][id].summary;return '<tr data-scenario="'+id+'"><td>'+label+'</td><td>'+fmt(a.return_pct)+'%</td><td>'+plain(a.dd_pct)+'%</td><td>'+a.trades+'</td><td>'+fmt(a.net)+'</td></tr>';}).join('')+'</tbody></table>';
 const d=data.diagnostics[p+'-'+f+'-'+c],baseDiag=data.diagnostics[p+'-'+f+'-base'],ci=data.uncertainty[p][f].find(x=>x.block_days===14);
 $('diagnostics').innerHTML='<p>평균 5분 종가 명목 노출 '+plain(d.mean_fine_close_notional_pct)+'%, 시간상 포지션 보유 '+plain(d.time_in_position_pct)+'%. 낮은 수익에는 적은 거래 기회와 낮은 평균 노출도 작용합니다. 노출만 키운 결과를 새 신호의 우위로 보지는 않습니다.</p><p>가격 손익 '+fmt(d.gross_price_pnl)+' − 수수료 '+plain(s.fees)+' − 가격 충격 '+plain(s.impact)+' + 펀딩 '+fmt(s.funding)+' = 순손익 '+fmt(s.net)+' USDT.</p><p>기본 거래·수량을 그대로 두고 실행비용만 2배로 다시 계산한 귀속 손익: '+fmt(baseDiag.fixed_base_trades_cost2_net)+' USDT. 위 재조정 계좌와 다른 진단입니다.</p><p>기본 조건의 일평균 수익률 14일 블록·5후보 보정 구간: '+ci.ci_bonferroni5.map(x=>fmt(x,4)).join(' ~ ')+'%. 0을 포함하는 불확실성과 반복 탐색의 선택 편향이 남아 있습니다.</p><p>선택 조건의 봉내 극단값 스트레스 낙폭 '+plain(s.adverse_extreme_stress_dd_pct)+'%는 고저 순서를 모르는 보수적 진단이며 실제 경로 낙폭이 아닙니다. 손절·목표 동시 도달 '+s.ambiguous_bars+'봉, 남은 자료 상충 시간의 포지션 노출 '+s.unresolved_archive_exposure_bars+'봉.</p>';
 curve=r.curve;point=curve.length-1;chart();
}
for(const id of ['period','family','scenario'])$(id).addEventListener('change',()=>{if(data)render();});
for(const id of ['equity','drawdown'])$(id).addEventListener('click',()=>{mode=id;for(const v of ['equity','drawdown'])$(v).setAttribute('aria-pressed',String(v===id));if(data)chart();});
$('chart').addEventListener('keydown',e=>{if(!data)return;if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();point=e.key==='Home'?0:e.key==='End'?values.length-1:Math.max(0,Math.min(values.length-1,point+(e.key==='ArrowLeft'?-1:1)));readout();}});
$('chart').addEventListener('pointerdown',e=>{if(!data)return;const r=$('chart').getBoundingClientRect(),x=(e.clientX-r.left)/r.width*chartWidth;point=Math.max(0,Math.min(values.length-1,Math.round((x-48)/(chartWidth-60)*(values.length-1))));readout();});
window.addEventListener('resize',()=>{if(data)chart();});
fetch('assets/structure-data.json?v=1001s1').then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json();}).then(d=>{data=d;render();}).catch(()=>{$('status-note').textContent='결과를 불러오지 못했습니다. 새로고침하거나 아래 CSV를 확인해 주세요.';});
})();
