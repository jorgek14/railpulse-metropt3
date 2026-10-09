const $ = id => document.getElementById(id);
const fmt = (v,n=2) => v==null ? '—' : Number(v).toFixed(n).replace('.', ',');
function chart(id, data, key, color, target=null){
 const canvas=$(id), dpr=window.devicePixelRatio||1, w=Math.max(150,canvas.clientWidth), h=Math.max(100,canvas.clientHeight);
 canvas.width=Math.floor(w*dpr); canvas.height=Math.floor(h*dpr);
 const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);
 ctx.clearRect(0,0,w,h);const L=45,R=12,T=17,B=32,pw=w-L-R,ph=h-T-B;
 ctx.font='11px Segoe UI, sans-serif';
 if(!data.length){ctx.fillStyle='#738fa2';ctx.textAlign='center';ctx.fillText('Aguardando fluxo de telemetria…',w/2,h/2);return;}
 const vals=data.map(x=>Number(x[key]));let min=Math.min(...vals),max=Math.max(...vals);
 if(target!==null){min=Math.min(min,target);max=Math.max(max,target)}
 const margin=Math.max(.3,(max-min)*.17); min-=margin;max+=margin;
 const xs=data.map(x=>Date.parse(x.timestamp.replace(' ','T')));
 let minX=Math.min(...xs),maxX=Math.max(...xs);if(minX===maxX)maxX+=1000;
 const fx=x=>L+(x-minX)/(maxX-minX)*pw,fy=y=>T+(max-y)/(max-min)*ph;
 ctx.lineWidth=1;ctx.strokeStyle='#294056';ctx.fillStyle='#89a1b6';ctx.textAlign='right';
 for(let i=0;i<4;i++){let yy=T+ph*i/3;ctx.beginPath();ctx.moveTo(L,yy);ctx.lineTo(w-R,yy);ctx.stroke();ctx.fillText((max-(max-min)*i/3).toFixed(1),L-9,yy+4)}
 if(target!==null){ctx.setLineDash([5,5]);ctx.strokeStyle='#c6a365';ctx.beginPath();ctx.moveTo(L,fy(target));ctx.lineTo(w-R,fy(target));ctx.stroke();ctx.setLineDash([])}
 ctx.strokeStyle=color;ctx.lineWidth=2;ctx.lineJoin='round';ctx.beginPath();
 for(let i=0;i<data.length;i++){const x=fx(xs[i]),y=fy(vals[i]);const gap=i>0 ? (xs[i]-xs[i-1])/1000 : 0;if(i===0||gap>30){ctx.moveTo(x,y)}else{ctx.lineTo(x,y)}}ctx.stroke();
 ctx.fillStyle='#849caf';ctx.textAlign='left';
 const start=data[0].timestamp,end=data[data.length-1].timestamp;
 ctx.fillText(start.slice(11,19),L,h-8);ctx.textAlign='right';ctx.fillText(end.slice(11,19),w-R,h-8);
}
async function fetchJSON(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
function labelMethod(s){return ({'Pressao_nao_recuperada_q99':'Recuperação lenta • TP3','Carga_longa_q99':'Carga prolongada','Somente_carga_mesmo_limiar':'Somente carga • controle'})[s]||s}
async function refresh(){try{
 const [status,samples,alerts]=await Promise.all([fetchJSON('/api/status'),fetchJSON('/api/readings?limit=400'),fetchJSON('/api/alerts?limit=60')]);
 const last=status.last||null;
 $('observedTime').textContent=last?last.timestamp:'Nenhuma leitura';
 $('p-val').textContent=last?fmt(last.tp3,3):'—';$('a-val').textContent=last?fmt(last.motor_current,2):'—';$('t-val').textContent=last?fmt(last.oil_temperature,1):'—';
 $('readingCount').textContent=status.counts.readings.toLocaleString('pt-BR')+' leituras recebidas';
 const state=last ? (last.motor_current>2&&last.dv_eletric>.5?'SOB CARGA':last.motor_current>2?'SEM CARGA':'DESLIGADO'):'AGUARDANDO';
 $('state').textContent=state;$('state').style.color=state==='SOB CARGA'?'#f3bc6a':'#58d9ca';
 $('primaryCount').textContent=status.counts.primary_alerts;$('totalCount').textContent=status.counts.alerts;
 $('cycleCount').textContent=status.cycles;$('gapCount').textContent=status.gaps;
 $('limit').textContent=fmt(status.parameters.recovery_limit_s,0)+' s';$('target').textContent=fmt(status.parameters.pressure_target_bar,1)+' bar';$('gap').textContent=fmt(status.parameters.max_gap_s,0)+' s';
 chart('pressureChart',samples.items,'tp3','#5bdacb',status.parameters.pressure_target_bar);
 chart('currentChart',samples.items,'motor_current','#82b0ff');
 const list=$('alerts');list.replaceChildren();
 if(!alerts.items.length){const empty=document.createElement('div');empty.className='empty';empty.textContent='Nenhum alerta recebido nesta sessão.';list.append(empty)}
 for(const a of alerts.items.slice().reverse().slice(0,20)){
   const row=document.createElement('div');row.className='alertrow '+(a.method==='Pressao_nao_recuperada_q99'?'primary':'');
   const date=document.createElement('span');date.textContent=a.timestamp;
   const meth=document.createElement('strong');meth.textContent=labelMethod(a.method);
   const pres=document.createElement('span');pres.textContent=fmt(a.pressure_bar,2);
   row.append(date,meth,pres);list.append(row);
 }
 $('hint').textContent='';
 }catch(e){$('hint').textContent='Não foi possível obter dados: '+e.message}}
$('reset').addEventListener('click',async()=>{
 if(!confirm('Reiniciar a sessão e apagar as leituras e alertas deste experimento?'))return;
 try{const r=await fetch('/api/reset',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!r.ok)throw Error('HTTP '+r.status);await refresh();$('hint').textContent='Sessão reiniciada com sucesso.'}catch(e){$('hint').textContent=e.message}
});
window.addEventListener('resize',()=>refresh());refresh();setInterval(refresh,1700);
