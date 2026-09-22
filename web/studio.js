/* All displayed numbers and routes come from the backend run snapshot. */
'use strict';
const $ = id => document.getElementById(id);
const clone = value => JSON.parse(JSON.stringify(value));
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n,d=1) => Number.isFinite(n) ? n.toFixed(d) : '—';
let scene, defaults, draft, floors=[], images={}, selected=0, floorId='F1', structure=false, mode='select';
let meta=null, history=[], result=null, busy=false, jobId=null, replayTimer=null, selectedEdge=null, uploadTarget=null;
let transforms={}; let matrixKind='weight_matrix';
const coefficients=[['importance','重要性'],['wait','已等待／耐久度'],['risk','損失風險'],['distance','起點距離'],['slow','附近慢速'],['bias','基準偏移']];
const settingsSpec={priority:['等待權重 λ',0,20,.1],risk_penalty:['逾時懲罰 μ · 秒',0,2000,10],distance_penalty:['距離懲罰 ν · 秒/m',0,20,.1],radius:['機器人半徑 · m',0,2,.05],threshold:['障礙灰階上限',0,254,1],gray_cost:['灰階成本 γ',0,10,.1],cruise:['巡航速度 · m/s',.05,3,.05],local_radius:['慢速範圍 · m',0,10,.1],population:['每世界族群',10,200,1],generations:['世代數',1,300,1],worlds:['世界數',1,8,1],interval:['交換間隔',1,100,1],migration:['遷移比例',0,.5,.01],mutation:['突變比例',0,1,.01],seed:['隨機 seed',0,2147483647,1]};
async function api(path,data) {
  const response=await fetch(path,data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const value=await response.json(); if(!response.ok) throw new Error(value.error||`HTTP ${response.status}`); return value;
}
function status(message,error=false) { $('status').textContent=message; $('status').classList.toggle('error',error); }
function floorName(id) { return scene?.floors.find(f=>f.id===id)?.name||id; }
function validPoint(p) { const f=floors.find(f=>f.id===p.floor);return !!f&&p.x>=0&&p.y>=0&&p.x<f.width&&p.y<f.height&&f.blocked_rows[p.y]?.[p.x]==='0'; }
function stopReplay() { clearInterval(replayTimer);replayTimer=null;$('playBtn').textContent='▶ 回放'; }
function record() { const h=history[Number($('generation').value)]; if(!h)return null;const world=$('worldSelect').value;return h.worlds[world==='best'?h.best_world-1:Number(world)]||h.worlds[0]; }
function invalidate(message='輸入已更新，請重新規劃。') {
  stopReplay();meta=null;history=[];result=null;selectedEdge=null;$('generation').value=0;$('generation').max=0;
  $('progress').value=0;$('mathBtn').disabled=true;$('playBtn').disabled=true;$('generation').disabled=true;
  $('priorityPreview').textContent='規劃後顯示實際權重';status(message);renderResults();renderOrders();draw();
}
function lock(value) {
  busy=value;document.body.classList.toggle('busy',value);
  for(const id of ['planBtn','importBtn','settingsBtn','addBtn','deleteBtn','startBtn','moveBtn','selectBtn']) $(id).disabled=value;
  document.querySelectorAll('#orderForm input').forEach(e=>e.disabled=value);
  $('cancelBtn').hidden=!value; if(!value)$('planBtn').disabled=!scene?.orders.length;
}
function renderOrders() {
  $('orderCount').textContent=scene.orders.length;
  $('orderList').innerHTML=scene.orders.map((o,i)=>`<button class="order-item ${i===selected?'selected':''}" data-order="${i}" aria-label="選擇訂單 ${esc(o.id)}"><span class="order-avatar">${esc(o.id.slice(0,2))}</span><span class="order-label"><strong>${esc(o.id)}</strong><small>${esc(floorName(o.floor))} · 已等 ${fmt(o.waited/60)} 分</small></span><span class="urgency">${o.importance>=8?'重要':o.importance<=2?'低':'一般'}</span></button>`).join('');
  $('orderList').querySelectorAll('[data-order]').forEach(b=>b.onclick=()=>{if(busy)return;selectOrder(Number(b.dataset.order));});
  if(!busy)$('planBtn').disabled=!scene.orders.length;
}
function selectOrder(index) { selected=index;const o=scene.orders[index];if(o)floorId=o.floor;selectedEdge=null;renderOrders();renderInspector();renderTabs();draw(); }
function renderInspector() {
  const o=scene.orders[selected];$('orderForm').hidden=!o;$('deleteBtn').disabled=busy||!o;
  $('selectedTitle').textContent=o?`訂單 ${o.id}`:'尚無訂單';$('selectedLocation').textContent=o?`${floorName(o.floor)} · (${o.x}, ${o.y})`:'點地圖新增第一筆訂單';
  if(!o)return;
  $('orderName').value=o.id;for(const k of ['importance','risk','speed','service'])$(k).value=o[k];
  $('importanceValue').textContent=o.importance;$('waited').value=Number((o.waited/60).toFixed(4));$('patience').value=Number((o.patience/60).toFixed(4));$('forbidden').value=(o.forbidden||[]).join(', ');$('forbidden').setCustomValidity('');
  const w=meta?.weights[selected];$('priorityPreview').textContent=w?`實際權重 ${fmt(w.weight,3)} / 10 · z = ${fmt(w.z,3)}`:'規劃後顯示實際權重';
}
function renderTabs() {
  $('floorTabs').innerHTML=scene.floors.map(f=>`<button data-floor="${esc(f.id)}" class="${!structure&&f.id===floorId?'active':''}">${esc(f.name||f.id)}</button>`).join('');
  $('floorTabs').querySelectorAll('button').forEach(b=>b.onclick=()=>{floorId=b.dataset.floor;structure=false;renderTabs();draw();});
  $('structureBtn').setAttribute('aria-pressed',String(structure));
  const f=floors.find(f=>f.id===floorId);$('mapScale').textContent=structure?'結構示意 · 不作像素尋路':f?`${f.width} × ${f.height} · ${f.resolution} m/px`:'';
}
function setMode(next) {
  mode=next;structure=false;renderTabs();
  for(const [id,k] of [['addBtn','add'],['selectBtn','select'],['startBtn','start'],['moveBtn','move']])$(id).classList.toggle('active',mode===k);
  $('editHint').textContent={add:'點擊可通行區域新增訂單。',start:'點擊地圖設定機器人起點。',end:'點擊地圖設定最終終點。',move:'點擊地圖移動目前選取的訂單。',select:'選擇訂單編輯，或點地圖新增。'}[mode];draw();
}
async function preview(candidate) {
  const view=await api('/api/studio/preview',candidate);const loaded={};
  await Promise.all(view.floors.map(f=>new Promise((resolve,reject)=>{const im=new Image();im.onload=()=>{loaded[f.id]=im;resolve();};im.onerror=()=>reject(new Error('地圖影像載入失敗'));im.src=f.image;})));
  return {floors:view.floors,images:loaded};
}
async function applyScene(candidate,message='地圖已就緒。') {
  const view=await preview(candidate);scene=candidate;floors=view.floors;images=view.images;
  if(!scene.floors.some(f=>f.id===floorId))floorId=scene.floors[0].id;
  selected=Math.min(selected,scene.orders.length-1);invalidate(message);renderTabs();renderInspector();
  const invalid=[scene.start,scene.end,...scene.orders,...scene.portals.flatMap(p=>[p.a,p.b])].filter(Boolean).filter(p=>!validPoint(p));
  if(invalid.length)status(`${invalid.length} 個節點不在可行走區域；請移動節點或調整電梯端點。`,true);
}
function project(p) { const t=transforms[p.floor];return t?{x:t.a*p.x+t.c*p.y+t.e,y:t.b*p.x+t.d*p.y+t.f}:null; }
function activeSegments() {
  if(!meta)return [];
  if(selectedEdge)return meta.segments[selectedEdge]||[];
  const r=record();if(!r)return [];
  return r.route.slice(1).flatMap((j,k)=>meta.segments[`${r.route[k]}:${j}`]||[]);
}
function draw() {
  const canvas=$('mapCanvas');const rect=canvas.getBoundingClientRect();if(!rect.width||!rect.height)return;
  const ratio=window.devicePixelRatio||1;canvas.width=Math.round(rect.width*ratio);canvas.height=Math.round(rect.height*ratio);
  const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);const W=rect.width,H=rect.height;ctx.fillStyle='#fbfcfd';ctx.fillRect(0,0,W,H);transforms={};
  if(!floors.length)return;
  const visible=structure?[...floors].reverse():floors.filter(f=>f.id===floorId);
  const maxSum=Math.max(...visible.map(f=>f.width+f.height));const a=structure?Math.min((W-100)/maxSum,(H-80)/(maxSum*.36+(visible.length-1)*maxSum*.32)):0;
  visible.forEach((f,i)=>{
    let t;
    if(structure)t={a,b:a*.36,c:-a,d:a*.36,e:W/2+(f.height-f.width)*a/2,f:30+i*maxSum*a*.32};
    else{const s=Math.min((W-50)/f.width,(H-40)/f.height);t={a:s,b:0,c:0,d:s,e:(W-f.width*s)/2,f:(H-f.height*s)/2};}
    transforms[f.id]=t;ctx.save();ctx.transform(t.a,t.b,t.c,t.d,t.e,t.f);ctx.imageSmoothingEnabled=false;ctx.drawImage(images[f.id],0,0);
    if($('clearanceToggle').checked){ctx.fillStyle='rgba(178,94,45,.20)';for(let y=0;y<f.height;y++)for(let x=0;x<f.width;x++)if(f.blocked_rows[y][x]==='1')ctx.fillRect(x,y,1,1);}
    ctx.restore();
    if(structure){ctx.fillStyle='#506879';ctx.font='600 12px sans-serif';const p=project({floor:f.id,x:0,y:f.height});ctx.fillText(f.name,p.x-3,p.y+20);}
  });
  const floorColors=['#087f8c','#5472c7','#9b69a6','#bc843e'];
  function line(points,color,width=2,dash=[]) {if(!points.length)return;ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();ctx.setLineDash([]);}
  if(structure)for(const p of scene.portals){const from=project(p.a),to=project(p.b);if(from&&to)line([from,to],p.enabled?'#afbec9':'#dde3e7',1,[4,5]);}
  for(const s of activeSegments()){
    if(s.kind==='walk'&&transforms[s.floor])line(s.path.map(p=>project({floor:s.floor,x:p[0]+.5,y:p[1]+.5})),floorColors[floors.findIndex(f=>f.id===s.floor)%4],structure?2:2.8);
    if(s.kind==='elevator'&&structure){const from=project(s.start),to=project(s.end);if(from&&to)line([from,to],'#cf8843',3,[6,4]);}
  }
  for(const p of scene.portals)for(const endpoint of [p.a,p.b]){
    const q=project({...endpoint,x:endpoint.x+.5,y:endpoint.y+.5});if(!q)continue;
    ctx.fillStyle=p.enabled?'#fff':'#e6e6e6';ctx.strokeStyle='#cf8843';ctx.lineWidth=1.6;ctx.fillRect(q.x-5,q.y-5,10,10);ctx.strokeRect(q.x-5,q.y-5,10,10);ctx.fillStyle='#876035';ctx.font='10px sans-serif';ctx.fillText(p.id,q.x+8,q.y+3);
  }
  function node(p,label,fill,radius=9){const q=project({...p,x:p.x+.5,y:p.y+.5});if(!q)return;ctx.beginPath();ctx.arc(q.x,q.y,radius,0,2*Math.PI);ctx.fillStyle=fill;ctx.fill();ctx.lineWidth=2;ctx.strokeStyle='#fff';ctx.stroke();ctx.fillStyle='#fff';ctx.font='600 10px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(label.slice(0,2),q.x,q.y);ctx.textAlign='left';ctx.textBaseline='alphabetic';}
  scene.orders.forEach((o,i)=>node(o,o.id,validPoint(o)?(i===selected?'#087f8c':'#526f86'):'#bb4235',structure?8:i===selected?12:10));
  node(scene.start,'S','#338458',10);if(scene.end)node(scene.end,'G','#b75445',10);
}
function renderResults() {
  const r=record();$('duration').textContent=r?`${fmt(r.duration/60,2)} 分`:'—';$('distance').textContent=r?`${fmt(r.distance)} m`:'—';$('loss').textContent=r?fmt(r.loss,2):'—';
  $('improvement').textContent=r&&result&&result.baseline.loss>0?`${fmt(100*(result.baseline.loss-r.loss)/result.baseline.loss)}%`:'—';
  const h=history[Number($('generation').value)];$('generationLabel').textContent=h?`第 ${h.generation} 代${h.migration?' · 菁英交換 '+h.migration+' 筆':''}`:'尚未規劃';
  $('schedule').innerHTML=r?r.schedule.map(s=>`<div class="stop ${s.late>0?'late':''}"><strong>${s.position}. ${esc(s.id)} · ${esc(floorName(s.floor))}</strong><small>到達 ${fmt(s.arrival/60,2)} 分</small><small>${s.late>0?'逾時 '+fmt(s.late/60,2)+' 分':'等待合計 '+fmt(s.wait_total/60,2)+' 分'}</small></div>`).join(''):'<span class="muted">新增訂單後，開始規劃即可查看到達時間。</span>';
  draw();
}
async function plan() {
  if(busy||!scene.orders.length)return;if(!$('orderForm').reportValidity())return;
  invalidate('檢查地圖與節點…');lock(true);jobId=null;
  try {
    const created=await api('/api/studio/jobs',scene);jobId=created.id;let count=0;
    while(busy&&jobId===created.id){
      const v=await api(`/api/studio/jobs/${created.id}?after=${meta?count:0}`);
      if(!meta)history=v.history;else history.push(...v.history);count=v.count;
      if(v.meta){meta=v.meta;$('mathBtn').disabled=false;renderInspector();
        $('worldSelect').innerHTML='<option value="best">最佳世界</option>'+Array.from({length:meta.settings.sower?meta.settings.worlds:1},(_,i)=>`<option value="${i}">世界 ${i+1}</option>`).join('');}
      $('progress').value=v.progress;status(v.phase);$('generation').max=Math.max(0,history.length-1);$('generation').value=Math.max(0,history.length-1);renderResults();
      if(['done','error','cancelled'].includes(v.status)){
        if(v.status==='done'){result=v.result;status('規劃完成 · 路徑、矩陣與權重已更新。');}
        else status(v.error||v.phase,v.status==='error');break;
      }
      await new Promise(resolve=>setTimeout(resolve,150));
    }
  } catch(error) {status(error.message,true);}
  finally{lock(false);$('generation').disabled=!history.length;$('playBtn').disabled=!history.length;renderResults();}
}
function download(name,value){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function renderMath() {
  if(!meta)return;const table=meta[matrixKind];const unit={weight_matrix:'權重',distance_matrix:'m（水平）',time_matrix:'s'}[matrixKind];
  $('modelVersion').textContent=`${meta.model_version} · 本次規劃快照`;
  $('matrixTable').innerHTML=`<table><thead><tr><th>From / To</th>${meta.labels.map(n=>`<th>${esc(n)}</th>`).join('')}</tr></thead><tbody>${table.map((row,i)=>`<tr><th>${esc(meta.labels[i])}</th>${row.map((x,j)=>`<td><button data-edge="${i}:${j}" class="${selectedEdge===`${i}:${j}`?'chosen':''}" title="${esc(meta.labels[i])} → ${esc(meta.labels[j])}">${fmt(x,2)}</button></td>`).join('')}</tr>`).join('')}</tbody></table>`;
  $('matrixTable').querySelectorAll('button').forEach(b=>b.onclick=()=>{selectedEdge=b.dataset.edge;renderMath();draw();});
  const key=selectedEdge||'0:1';const [i,j]=key.split(':').map(Number);const segments=meta.segments[key]||[];
  const lines=segments.map(s=>s.kind==='walk'?`${s.floor} A*：${fmt(s.distance,3)} m / ${fmt(s.time,3)} s`:`${s.id} ${s.start.floor} → ${s.end.floor}：等待 ${fmt(s.wait)} + 開關門 ${fmt(s.door)} + 移動 ${fmt(s.ride)} = ${fmt(s.time)} s`);
  $('edgeDetail').innerHTML=`<strong>${esc(meta.labels[i])} → ${esc(meta.labels[j])} · ${fmt(table[i]?.[j],4)} ${unit}</strong><br>${lines.map(esc).join('<br>')||'同一節點，無移動路段。'}<br><button id="showEdgeBtn">在地圖顯示這一段</button><p class="hint">D 是所選路徑的水平行走距離，電梯時間獨立加入 T。選擇不同電梯時，D 與 T 都可能不對稱。</p>`;
  $('showEdgeBtn').onclick=()=>{selectedEdge=key;floorId=meta.points[i].floor;structure=meta.points[i].floor!==meta.points[j].floor;$('mathDialog').close();renderTabs();draw();};
  $('formulaList').replaceChildren();for(const [name,equation] of Object.entries(meta.formulas)){const p=document.createElement('pre');p.className='equation';p.textContent=equation;$('formulaList').append(p);}
  $('weightDetails').innerHTML=`<table><thead><tr><th>訂單</th>${coefficients.slice(0,5).map(x=>`<th>${x[1]}貢獻</th>`).join('')}<th>b</th><th>z</th><th>σ(z)</th><th>ω</th></tr></thead><tbody>${meta.weights.map(w=>`<tr><th>${esc(w.id)}</th>${coefficients.slice(0,5).map(([k])=>`<td>${fmt(w.contributions[k],6)}</td>`).join('')}<td>${fmt(w.bias,6)}</td><td>${fmt(w.z,6)}</td><td>${fmt(w.sigmoid,6)}</td><td>${fmt(w.weight,6)}</td></tr>`).join('')}</tbody></table>`;
  const r=record();$('lossDetails').innerHTML=r?Object.entries(r.components).map(([k,v])=>`<span>${{finish:'完成時間',priority:'加權等待',risk:'逾時損失',distance:'距離成本'}[k]} ${fmt(v,4)}</span>`).join('')+`<span>合計 ${fmt(r.loss,4)}</span>`:'規劃進行中。';
}
function numberControl(container,label,value,min,max,step,onchange) {
  const wrapper=document.createElement('label');wrapper.className='field';wrapper.append(document.createTextNode(label));const input=document.createElement('input');input.type='number';input.value=value;input.min=min;input.max=max;input.step=step;input.required=true;
  input.onchange=()=>{if(input.reportValidity())onchange(Number(input.value));};wrapper.append(input);container.append(wrapper);return input;
}
function renderSettings() {
  $('floorSettings').replaceChildren();draft.floors.forEach(f=>{
    const card=document.createElement('div');card.className='floor-setting';card.innerHTML=`<div class="floor-heading"><strong>${esc(f.name||f.id)} · ${esc(f.id)}</strong><button class="replaceFloor">更換網格</button><button class="removeFloor">移除</button></div>`;const header=card.firstChild;
    numberControl(header,'m/px',f.resolution,.01,2,.01,v=>f.resolution=v);
    const label=document.createElement('label');label.className='field';label.append(document.createTextNode('未知灰階 · 留空不指定'));const unknown=document.createElement('input');unknown.type='number';unknown.min=0;unknown.max=254;unknown.placeholder='例如 127';unknown.value=f.unknown_value??'';unknown.onchange=()=>{if(unknown.value==='')delete f.unknown_value;else if(unknown.reportValidity())f.unknown_value=Number(unknown.value);};label.append(unknown);header.append(label);
    card.querySelector('.replaceFloor').onclick=()=>{uploadTarget=f.id;$('floorUpload').click();};
    card.querySelector('.removeFloor').onclick=()=>{if(draft.floors.length===1||draft.start.floor===f.id){status('先將起點移到其他樓層，才能移除此樓層。',true);return;}if(!confirm('移除樓層及該層訂單、電梯連線？'))return;draft.floors=draft.floors.filter(x=>x.id!==f.id);draft.orders=draft.orders.filter(o=>o.floor!==f.id);draft.portals=draft.portals.filter(p=>p.a.floor!==f.id&&p.b.floor!==f.id);if(draft.end?.floor===f.id)draft.end=null;renderSettings();};$('floorSettings').append(card);
  });
  $('portalSettings').replaceChildren();draft.portals.forEach((p,index)=>{
    const card=document.createElement('div');card.className='portal-setting';card.innerHTML=`<div class="portal-heading"><strong>${esc(p.id)} · ${esc(p.a.floor)} ↔ ${esc(p.b.floor)}</strong><label><input class="portalEnabled" type="checkbox" ${p.enabled?'checked':''}>啟用</label><button class="removePortal">移除</button></div><div class="settings-grid timings"></div><details><summary>電梯端點</summary><div class="portal-endpoints"></div></details>`;
    card.querySelector('.portalEnabled').onchange=e=>p.enabled=e.target.checked;card.querySelector('.removePortal').onclick=()=>{draft.portals.splice(index,1);renderSettings();};
    for(const [k,label] of [['wait','去程等待 · 秒'],['reverse_wait','回程等待 · 秒'],['door','開關門 · 秒'],['ride','移動 · 秒']])numberControl(card.querySelector('.timings'),label,p[k],0,3600,1,v=>p[k]=v);
    for(const side of ['a','b']){const row=document.createElement('div');row.className='endpoint';const label=document.createElement('label');label.className='field';label.textContent=side==='a'?'端點 A':'端點 B';const select=document.createElement('select');select.innerHTML=draft.floors.map(f=>`<option value="${esc(f.id)}">${esc(f.name||f.id)}</option>`).join('');select.value=p[side].floor;select.onchange=()=>p[side].floor=select.value;label.append(select);row.append(label);for(const k of ['x','y'])numberControl(row,k,p[side][k],0,511,1,v=>p[side][k]=v);card.querySelector('.portal-endpoints').append(row);}
    $('portalSettings').append(card);
  });
  $('coefficientSettings').replaceChildren();for(const [k,label] of coefficients)numberControl($('coefficientSettings'),label,draft.coefficients[k],k==='bias'?-10:0,10,.1,v=>draft.coefficients[k]=v);
  $('objectiveSettings').replaceChildren();$('engineSettings').replaceChildren();for(const [k,[label,min,max,step]] of Object.entries(settingsSpec))numberControl($(k==='priority'||k.endsWith('penalty')?'objectiveSettings':'engineSettings'),label,draft.settings[k],min,max,step,v=>draft.settings[k]=v);
  $('returnCheck').checked=draft.settings.return_to_start;$('sowerCheck').checked=draft.settings.sower;
}
function normalise(raw) {
  if(!raw||typeof raw!=='object'||Array.isArray(raw))throw new Error('請匯入場景 JSON。');const s=clone(raw);
  if(!Array.isArray(s.floors)||!Array.isArray(s.orders)||!Array.isArray(s.portals))throw new Error('需要 schema_version 2 的 floors / orders / portals。');
  s.settings={...defaults.settings,...s.settings};s.coefficients={...defaults.coefficients,...s.coefficients};
  s.orders=s.orders.map(o=>({importance:5,waited:0,patience:300,risk:.5,speed:.8,service:10,forbidden:[],...o}));
  s.portals=s.portals.map(p=>({wait:15,door:6,ride:8,enabled:true,...p,reverse_wait:p.reverse_wait??p.wait??15}));return s;
}
$('orderForm').onsubmit=e=>e.preventDefault();
for(const [id,key,scale] of [['importance','importance',1],['waited','waited',60],['patience','patience',60],['risk','risk',1],['speed','speed',1],['service','service',1]]){
  $(id).addEventListener(id==='importance'?'input':'change',()=>{if(busy||!scene.orders[selected]||!$(id).reportValidity())return;scene.orders[selected][key]=Number($(id).value)*scale;if(id==='importance')$('importanceValue').textContent=$(id).value;invalidate();});
}
$('orderName').onchange=()=>{const value=$('orderName').value.trim();if(!value||['START','END'].includes(value)||scene.orders.some((o,i)=>i!==selected&&o.id===value)){status('訂單名稱必須唯一，且不可為 START / END。',true);renderInspector();return;}scene.orders[selected].id=value;invalidate();renderInspector();};
$('forbidden').onchange=()=>{const value=$('forbidden').value.trim();const items=value?value.split(',').map(x=>Number(x.trim())):[];if(items.some(x=>!Number.isInteger(x)||x<1||x>scene.orders.length)){$('forbidden').setCustomValidity('禁止順位需為有效整數。');status('禁止順位需為有效整數。',true);return;}$('forbidden').setCustomValidity('');scene.orders[selected].forbidden=items;invalidate();};
$('mapCanvas').onclick=event=>{
  if(busy||structure||!scene)return;const t=transforms[floorId];if(!t)return;const rect=$('mapCanvas').getBoundingClientRect();const p={floor:floorId,x:Math.floor((event.clientX-rect.left-t.e)/t.a),y:Math.floor((event.clientY-rect.top-t.f)/t.d)};
  const nearest=scene.orders.findIndex(o=>o.floor===floorId&&Math.hypot(o.x-p.x,o.y-p.y)*t.a<15);
  if(mode==='select'&&nearest>=0){selectOrder(nearest);return;}
  if(!validPoint(p)){status('此處是障礙或機器人安全區，請選擇通道。',true);return;}
  if(mode==='start'){scene.start=p;setMode('select');}
  else if(mode==='end'){scene.end=p;setMode('select');}
  else if(mode==='move'){if(!scene.orders[selected])return;Object.assign(scene.orders[selected],p);setMode('select');}
  else{if(scene.orders.length>=30){status('最多 30 筆訂單。',true);return;}let n=1;while(scene.orders.some(o=>o.id===`N${n}`))n++;scene.orders.push({id:`N${n}`,...p,importance:5,waited:0,patience:300,risk:.5,speed:.8,service:10,forbidden:[]});selected=scene.orders.length-1;}
  invalidate();renderInspector();
};
$('addBtn').onclick=()=>setMode('add');$('selectBtn').onclick=()=>setMode('select');$('startBtn').onclick=()=>setMode('start');$('moveBtn').onclick=()=>setMode('move');
$('deleteBtn').onclick=()=>{if(!scene.orders[selected])return;scene.orders.splice(selected,1);selected=Math.min(selected,scene.orders.length-1);invalidate();renderInspector();};
$('structureBtn').onclick=()=>{structure=!structure;renderTabs();draw();};$('clearanceToggle').onchange=draw;
$('planBtn').onclick=plan;$('cancelBtn').onclick=async()=>{if(jobId){await api(`/api/studio/jobs/${jobId}/cancel`,{});status('正在停止…');}};
$('generation').oninput=()=>{selectedEdge=null;renderResults();};$('worldSelect').onchange=()=>{selectedEdge=null;renderResults();};
$('playBtn').onclick=()=>{if(replayTimer){stopReplay();return;}if(Number($('generation').value)>=history.length-1)$('generation').value=0;$('playBtn').textContent='Ⅱ 暫停';replayTimer=setInterval(()=>{const next=Number($('generation').value)+1;if(next>=history.length){stopReplay();return;}$('generation').value=next;selectedEdge=null;renderResults();},250);};
$('mathBtn').onclick=()=>{renderMath();$('mathDialog').showModal();};document.querySelectorAll('[data-matrix]').forEach(b=>b.onclick=()=>{matrixKind=b.dataset.matrix;document.querySelectorAll('[data-matrix]').forEach(x=>x.classList.toggle('active',x===b));renderMath();});
$('settingsBtn').onclick=()=>{draft=clone(scene);renderSettings();$('settingsDialog').showModal();};
$('returnCheck').onchange=e=>draft.settings.return_to_start=e.target.checked;$('sowerCheck').onchange=e=>draft.settings.sower=e.target.checked;
$('applySettingsBtn').onclick=async()=>{try{if([...$('settingsDialog').querySelectorAll('input')].some(e=>!e.reportValidity()))return;await applyScene(draft);$('settingsDialog').close();}catch(e){status(e.message,true);alert(e.message);}};
$('endBtn').onclick=()=>{$('settingsDialog').close();setMode('end');};$('clearEndBtn').onclick=()=>{draft.end=null;status('套用設定後會清除終點。');};
$('addPortalBtn').onclick=()=>{if(draft.floors.length<2||draft.portals.length>=12){status('需要至少兩層，最多 12 條電梯連線。',true);return;}let i=1;while(draft.portals.some(p=>p.id===`E${i}`))i++;draft.portals.push({id:`E${i}`,a:{floor:draft.floors[0].id,x:20,y:20},b:{floor:draft.floors[1].id,x:20,y:20},wait:15,reverse_wait:15,door:6,ride:8,enabled:true});renderSettings();};
$('addFloorBtn').onclick=()=>{if(draft.floors.length>=4){status('最多四個樓層。',true);return;}uploadTarget=null;$('floorUpload').click();};
$('floorUpload').onchange=async()=>{const file=$('floorUpload').files[0];if(!file)return;try{if(file.size>2000000)throw new Error('圖片需小於 2 MB。');const data=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=reject;r.readAsDataURL(file);});if(uploadTarget)draft.floors.find(f=>f.id===uploadTarget).map_data=data;else{let k=1;while(draft.floors.some(f=>f.id===`F${k}`))k++;draft.floors.push({id:`F${k}`,name:`${k}F`,resolution:.1,map_data:data});}renderSettings();}catch(e){status(e.message,true);}finally{$('floorUpload').value='';}};
$('exportBtn').onclick=()=>download('dispatch-scene.json',scene);$('exportResultBtn').onclick=()=>download('dispatch-calculation.json',{scene,meta,history,result});
$('importBtn').onclick=()=>$('importFile').click();$('importFile').onchange=async()=>{const file=$('importFile').files[0];if(!file)return;try{if(file.size>12000000)throw new Error('場景檔案需小於 12 MB；請匯入場景而非完整結果。');const value=JSON.parse(await file.text());await applyScene(normalise(value.scene||value),'場景已匯入，請重新規劃。');}catch(e){status(e.message,true);}finally{$('importFile').value='';}};
for(const b of document.querySelectorAll('.closeDialog'))b.onclick=()=>b.closest('dialog').close();
new ResizeObserver(draw).observe($('mapCanvas'));
(async()=>{try{defaults=await api('/api/studio/demo');await applyScene(clone(defaults));}catch(e){status(e.message,true);$('planBtn').disabled=true;}})();
