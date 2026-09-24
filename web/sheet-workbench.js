/* Sheet-first interaction layer. Sheet order is presentation; IDs are topology.
 * All route changes still go through commit()/preflight. No inferred connections.
 */
'use strict';
let sheetDragKey=null, sheetContextId=null, selectedPortalId=null;
let quickPortalFlow=false, hoveredSheet=null, toastTimer=null;
const previousPortalSettings=openPortalSettings;
const previousStatus=status, previousSegments=activeSegments;
const canvasHandlers={down:$('mapCanvas').onpointerdown,move:$('mapCanvas').onpointermove,
  up:$('mapCanvas').onpointerup,cancel:$('mapCanvas').onpointercancel};

function announce(message,error=false){
  const box=$('actionToast');box.textContent=message;box.classList.toggle('error',error);
  box.hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>box.hidden=true,2800);
  previousStatus(message,error);syncWorkbenchState();
}
status=function(value,error=false){previousStatus(value,error);syncWorkbenchState();};

function syncWorkbenchState(){
  if(!scene||!$('workbenchState'))return;
  const pending=!!portalPick, blocked=!!preview?.error||preview?.preflight?.ok===false;
  let state='ready',key='ready';
  if(busy){state='busy';key='planning';}
  else if(uploadInProgress){state='busy';key='review';}
  else if(pending){state='tool';key='connecting';}
  else if(mode==='add'){state='tool';key='adding';}
  else if(blocked){state='error';key='blocked';}
  else if(previewRunning||previewQueued){state='busy';key='checking';}
  else if(result){state='done';key='done';}
  const badge=$('workbenchState');badge.dataset.state=state;badge.textContent=t('sheet.state_'+key);
  $('addBtn').setAttribute('aria-pressed',String(mode==='add'));
  $('addBtn').classList.toggle('active',mode==='add');
  $('addElevatorBtn').setAttribute('aria-pressed',String(pending));
  $('addElevatorBtn').classList.toggle('active',pending);
  $('addElevatorBtn').disabled=busy||uploadInProgress||scene.portals.length>=12;
  $('addSheetBtn').disabled=busy||uploadInProgress||scene.floors.length>=4;
  $('structureBtn').hidden=scene.floors.length<2;
  $('structureBtn').classList.toggle('active',structure);
  $('structureBtn').setAttribute('aria-pressed',String(structure));
  $('mapCanvas').classList.toggle('add-mode',mode==='add');
  $('mapCanvas').classList.toggle('portal-mode',pending);
  $('toolState').hidden=busy||pending||mode!=='add';
  $('toolState').textContent=t('sheet.add_hint');
  $('planBtn').textContent=busy?t('sheet.running'):t('ga.plan');
  $('planBtn').setAttribute('aria-busy',String(busy));
  const reason=busy?'sheet.running':pending?'sheet.finish_connection':scene.nodes.length<3?'sheet.need_nodes':blocked?'sheet.fix_link':previewRunning||previewQueued?'sheet.checking_route':'sheet.run_tip';
  $('planBtn').title=t(reason);
  $('sawToggle').closest('label').classList.toggle('enabled',!!scene.settings.sower);
  $('evolutionToggle').closest('label').classList.toggle('enabled',$('evolutionToggle').checked);
  $('playBtn').setAttribute('aria-pressed',String(!!replayTimer));
  $('viewOptions').querySelectorAll('input').forEach(e=>e.setAttribute('aria-checked',String(e.checked)));
  $('mapLayer').title=t('sheet.layers');
  $('mapCanvas').closest('.editor-map').classList.toggle('has-tool',mode==='add'||pending);
  $('selectionHint').hidden=selection.size<=1;
  $('nodeForm').previousElementSibling?.classList.toggle('empty-inspector',!current());
  $('endpointControls').hidden=scene.nodes.length<2;
  $('deleteBtn').hidden=!selection.size;
  $('undoBtn').title=t('sheet.undo_tip');
  $('previewMetric').hidden=!scene.nodes.length;
  document.body.classList.toggle('is-planning',busy);
  if(busy)$('observatoryDetails').open=true;
}

function sheetMutation(edit,message){
  // Renaming/reordering sheets is view-only: keep the recorded route and weights.
  if(busy||uploadInProgress||gesture)return;
  undoStack.push(clone(scene));if(undoStack.length>35)undoStack.shift();edit();
  renderEditor();renderTabs();renderPortalSummary();draw();announce(message);
}
function topologySignature(s){
  const x=clone(s);x.floors.sort((a,b)=>a.id.localeCompare(b.id));
  x.floors.forEach(f=>{delete f.name;delete f.starter;});return JSON.stringify(x);
}
function reorderSheet(id,target,after=false){
  if(id===target||!scene.floors.some(f=>f.id===id)||!scene.floors.some(f=>f.id===target))return;
  sheetMutation(()=>{
    const f=scene.floors.find(f=>f.id===id);scene.floors=scene.floors.filter(f=>f.id!==id);
    scene.floors.splice(scene.floors.findIndex(f=>f.id===target)+(after?1:0),0,f);
  },t('sheet.reordered'));
}
function chooseSheet(id){
  if(!scene.floors.some(f=>f.id===id))return;
  floorId=id;structure=false;renderTabs();draw();
}
function renderSheetTabs(){
  if(!scene)return;
  const tabs=$('floorTabs');tabs.replaceChildren();tabs.setAttribute('role','tablist');
  tabs.setAttribute('aria-label',t('sheet.stack_order'));
  for(const [i,f] of scene.floors.entries()){
    const tile=document.createElement('div');tile.className='sheet-tile';tile.dataset.sheet=f.id;
    const active=floorId===f.id;tile.classList.toggle('selected',active);
    const grip=document.createElement('button');grip.className='sheet-grip';grip.draggable=!busy;grip.textContent='⠿';
    grip.setAttribute('aria-label',t('sheet.drag',{name:f.name||f.id}));grip.disabled=busy;
    const tab=document.createElement('button');tab.className='sheet-tab';tab.dataset.floor=f.id;tab.dataset.sheetTab=f.id;
    tab.setAttribute('role','tab');tab.setAttribute('aria-selected',String(active));
    tab.setAttribute('aria-pressed',String(active&&!structure));
    tab.title=t('sheet.layer_tip',{name:f.name||f.id,index:i+1});
    const number=document.createElement('span');number.className='sheet-index';number.textContent=String(i+1);
    const text=document.createElement('span');text.textContent=f.name||f.id;tab.append(number,text);
    tab.onclick=()=>chooseSheet(f.id);
    tab.onkeydown=e=>{if(e.altKey&&['ArrowLeft','ArrowRight'].includes(e.key)){
      e.preventDefault();e.stopPropagation();const j=i+(e.key==='ArrowLeft'?-1:1);
      if(scene.floors[j]){reorderSheet(f.id,scene.floors[j].id,j>i);tabs.querySelector(`[data-sheet-tab="${CSS.escape(f.id)}"]`)?.focus();}
    }};
    tile.oncontextmenu=e=>{e.preventDefault();if(!busy)openSheetMenu(f.id,e.clientX,e.clientY);};
    const more=document.createElement('button');more.className='sheet-more';more.textContent='⋯';more.disabled=busy;
    more.setAttribute('aria-label',t('sheet.options',{name:f.name||f.id}));
    more.onclick=e=>openSheetMenu(f.id,e.clientX,e.clientY);
    grip.ondragstart=e=>{if(busy){e.preventDefault();return;}sheetDragKey=f.id;e.dataTransfer.setData('text/plain',f.id);e.dataTransfer.effectAllowed='move';tile.classList.add('dragging');};
    grip.ondragend=()=>{sheetDragKey=null;clearSheetDrop();};
    tile.ondragover=e=>{if(!sheetDragKey||busy)return;e.preventDefault();clearSheetDrop();tile.classList.add(e.clientX<tile.getBoundingClientRect().left+tile.clientWidth/2?'sheet-before':'sheet-after');};
    tile.ondrop=e=>{e.preventDefault();const id=sheetDragKey;sheetDragKey=null;clearSheetDrop();
      if(id)reorderSheet(id,f.id,e.clientX>=tile.getBoundingClientRect().left+tile.clientWidth/2);};
    tile.append(grip,tab,more);tabs.append(tile);
  }
  $('mapHint').textContent=structure?t('sheet.structure_hint'):t('sheet.edit_hint');
  syncWorkbenchState();
}
function clearSheetDrop(){document.querySelectorAll('.sheet-before,.sheet-after').forEach(e=>e.classList.remove('sheet-before','sheet-after'));}
function openSheetMenu(id,x,y){
  sheetContextId=id;const menu=$('sheetMenu');menu.hidden=false;
  const i=scene.floors.findIndex(f=>f.id===id);
  $('sheetMenuLeft').disabled=busy||i<=0;$('sheetMenuRight').disabled=busy||i===scene.floors.length-1;
  menu.style.left=Math.max(6,Math.min(x,innerWidth-menu.offsetWidth-8))+'px';
  menu.style.top=Math.max(6,Math.min(y,innerHeight-menu.offsetHeight-8))+'px';
}
function openSheetDetails(id){
  sheetContextId=id;$('sheetMenu').hidden=true;const f=scene.floors.find(f=>f.id===id);if(!f)return;
  $('sheetName').value=f.name||f.id;$('sheetRules').hidden=!f.semantics;
  $('sheetIdentity').textContent=t('sheet.id_note',{id:f.id});
  $('sheetRemove').disabled=scene.floors.length===1;$('sheetDialog').showModal();
}
$('sheetMenuRename').onclick=()=>openSheetDetails(sheetContextId);
for(const [button,delta] of [['sheetMenuLeft',-1],['sheetMenuRight',1]])$(button).onclick=()=>{
  const i=scene.floors.findIndex(f=>f.id===sheetContextId),other=scene.floors[i+delta];
  $('sheetMenu').hidden=true;if(other)reorderSheet(sheetContextId,other.id,delta>0);
};
$('closeSheetDialog').onclick=()=>$('sheetDialog').close();
$('sheetForm').onsubmit=e=>{e.preventDefault();const name=$('sheetName').value.trim();if(!name)return;
  sheetMutation(()=>scene.floors.find(f=>f.id===sheetContextId).name=name,t('sheet.renamed'));$('sheetDialog').close();};
$('sheetReplace').onclick=()=>{$('sheetDialog').close();requestSheetUpload(sheetContextId);};
$('sheetRules').onclick=()=>{const f=scene.floors.find(f=>f.id===sheetContextId);$('sheetDialog').close();
  beginMapImport([{name:f.semantics.source_name,map_data:f.semantics.source_data,semantics:f.semantics}],f.id,true);};
$('sheetRemove').onclick=()=>{
  if(scene.floors.length<2)return;
  if(!confirm(t('sheet.remove_confirm',{name:floorName(sheetContextId)})))return;
  $('sheetDialog').close();selectedPortalId=null;cancelPortalPick();
  commit(()=>{scene.nodes=scene.nodes.filter(n=>n.floor!==sheetContextId);scene.floors=scene.floors.filter(f=>f.id!==sheetContextId);
    floorId=scene.floors[0].id;if(scene.floors.length===1)structure=false;
    // Keep dangling portal IDs to make incomplete channels visible and repairable.
  },t('sheet.removed'));renderTabs();
};
function requestSheetUpload(target=null){
  if(busy||uploadInProgress)return;uploadTarget=target;$('floorUpload').multiple=!target;$('floorUpload').click();
}
$('floorUpload').onchange=e=>{const files=[...e.target.files],target=uploadTarget;e.target.value='';uploadTarget=null;
  if(files.length)beginMapImport(files,target,!$('settingsDialog').open);
};
$('addSheetBtn').onclick=()=>requestSheetUpload();
$('importMapBtn').onclick=()=>requestSheetUpload(scene.floors.length===1&&scene.floors[0].starter&&!scene.nodes.length&&!scene.portals.length?scene.floors[0].id:null);
$('importMapBtn').dataset.i18n='sheet.upload';$('importMapBtn').textContent=t('sheet.upload');
$('addBtn').after($('addElevatorBtn'));
$('viewOptions').append($('mapLayer'));
$('mapCanvas').before($('toolState'));
$('managePortalsBtn').closest('.portal-sidebar').append(Object.assign(document.createElement('section'),{id:'channelDock'}));

// Create an elevator with two clicks, not with coordinate forms.
function newChannel(){
  if(busy||uploadInProgress)return;
  if(portalPick){cancelPortalPick();draw();return;}
  if(scene.floors.length<2){$('needSheetDialog').showModal();return;}
  if(scene.portals.length>=12){announce(t('error.max_portals'),true);return;}
  let i=0;while(scene.portals.some(p=>p.id===`E${String.fromCharCode(97+i)}`))i++;
  const id=`E${String.fromCharCode(97+i)}`;
  mode='portal';quickPortalFlow=true;selectedPortalId=id;
  portalPick={id,side:'a',floor:floorId,quick:true};
  commit(()=>scene.portals.push({id,a:{floor:floorId,x:null,y:null},b:{floor:null,x:null,y:null},
    enabled:true,wait:15,reverse_wait:15,door:6,ride:8}),t('sheet.place_first'));
  updatePlacement();renderTabs();draw();
}
$('addElevatorBtn').onclick=newChannel;
$('closeNeedSheet').onclick=()=>$('needSheetDialog').close();
$('uploadSecondSheet').onclick=()=>{$('needSheetDialog').close();requestSheetUpload();};
$('blankSecondSheet').onclick=async()=>{
  $('needSheetDialog').close();if(busy||uploadInProgress||scene.floors.length>=4)return;
  uploadInProgress=true;syncWorkbenchState();
  try{
    const v=await api('/api/editor/start');let i=1;while(scene.floors.some(f=>f.id===`sheet-${i}`))i++;
    commit(()=>{const f={...v.floors[0],id:`sheet-${i}`,name:`Sheet ${i}`,starter:false};scene.floors.push(f);floorId=f.id;},t('sheet.added'));renderTabs();
  }catch(e){announce(e.message,true);}
  finally{uploadInProgress=false;syncWorkbenchState();}
};
updatePlacement=function(){
  if(!portalPick){$('placementBar').hidden=true;syncWorkbenchState();return;}
  const p=scene.portals.find(p=>p.id===portalPick.id);if(!p){portalPick=null;return updatePlacement();}
  $('placementBar').hidden=false;$('placementLabel').textContent=portalPick.quick?
    t(portalPick.side==='a'?'sheet.place_first':'sheet.place_second',{id:p.id}):
    t('sheet.relocate_hint',{id:p.id,side:portalPick.side.toUpperCase()});
  syncWorkbenchState();
};
cancelPortalPick=function(){
  portalPick=null;quickPortalFlow=false;if(mode==='portal')mode='select';
  updatePlacement();renderChannelDock();renderTabs();
};
placePickedPortal=function(point){
  if(!portalPick)return;
  const pick=portalPick,p=scene.portals.find(p=>p.id===pick.id),other=pick.side==='a'?'b':'a';
  if(!p||!point||!validPoint(point)){announce(t('error.add_blocked'),true);return;}
  if(p[other]?.x!=null&&p[other].floor===point.floor){announce(t('sheet.other_sheet'),true);return;}
  const next=pick.quick&&pick.side==='a';
  portalPick=null;
  commit(()=>p[pick.side]={...point},t('portal.saved',{endpoint:`${p.id}_${point.floor}`}));
  selectedPortalId=p.id;
  if(next){
    const otherFloor=scene.floors.find(f=>f.id!==point.floor);
    portalPick={id:p.id,side:'b',floor:otherFloor?.id,quick:true};
    if(!structure&&otherFloor)floorId=otherFloor.id;
    mode='portal';
  }else{mode='select';quickPortalFlow=false;announce(t('sheet.channel_connected',{id:p.id}));}
  updatePlacement();renderTabs();renderChannelDock();draw();
};
function pickEndpoint(id,side){
  if(busy)return;const p=scene.portals.find(p=>p.id===id);if(!p)return;
  selectedPortalId=id;portalPick={id,side,quick:false};mode='portal';
  if(p[side]?.floor&&scene.floors.some(f=>f.id===p[side].floor)&&!structure)floorId=p[side].floor;
  updatePlacement();renderTabs();renderChannelDock();draw();
}
openPortalSettings=function(id=null){
  if(!id){previousPortalSettings();return;}
  if(busy)return;selectedPortalId=id;renderPortalSummary();renderChannelDock();draw();
};
renderPortalSummary=function(){
  if(!scene)return;
  if(portalPick&&!scene.portals.some(p=>p.id===portalPick.id)){portalPick=null;quickPortalFlow=false;if(mode==='portal')mode='select';$('placementBar').hidden=true;}
  const box=$('portalSummary');box.replaceChildren();
  const sidebar=box.closest('.portal-sidebar');sidebar.classList.toggle('no-portals',!scene.portals.length);
  for(const p of scene.portals){
    const state=portalLocalState(p),button=document.createElement('button');button.dataset.portal=p.id;
    button.className=`portal-chip ${state}`;button.classList.toggle('selected',selectedPortalId===p.id);button.disabled=busy;
    button.setAttribute('aria-pressed',String(selectedPortalId===p.id));button.textContent=`${state==='complete'?'✓':state==='disabled'?'○':'!'} ${p.id}`;
    button.title=`${portalEndpointLabel(p,'a')} ↔ ${portalEndpointLabel(p,'b')} · ${t('portal.'+state)}`;
    button.onclick=()=>{selectedPortalId=selectedPortalId===p.id?null:p.id;renderPortalSummary();draw();};box.append(button);
  }
  renderChannelDock();syncWorkbenchState();
};
function renderChannelDock(){
  const dock=$('channelDock');if(!dock||!scene)return;
  const p=scene.portals.find(p=>p.id===selectedPortalId);dock.hidden=!p;dock.replaceChildren();if(!p)return;
  const head=document.createElement('div');head.className='channel-heading';
  const name=document.createElement('input');name.className='channel-name';name.value=p.id;name.maxLength=40;name.disabled=busy;
  name.setAttribute('aria-label',t('portal.id'));
  name.onchange=()=>{const id=name.value.trim();if(!id||scene.portals.some(x=>x!==p&&x.id===id)){name.setCustomValidity(t('error.portal_id'));name.reportValidity();return;}
    commit(()=>{if(portalPick?.id===p.id)portalPick.id=id;p.id=id;selectedPortalId=id;},t('sheet.renamed'));renderPortalSummary();};
  const enabled=document.createElement('button');enabled.textContent=t(p.enabled?'common.enabled':'sheet.disabled');enabled.disabled=busy;
  enabled.setAttribute('aria-pressed',String(p.enabled));enabled.className=p.enabled?'active':'';
  enabled.onclick=()=>commit(()=>p.enabled=!p.enabled,t('portal.updated'));
  head.append(name,enabled);dock.append(head);
  for(const side of ['a','b']){
    const row=document.createElement('div');row.className='channel-end';row.dataset.channelSide=side;
    const label=document.createElement('button');label.className='channel-sheet';label.textContent=p[side]?.floor?floorName(p[side].floor):t('sheet.choose_destination');
    label.disabled=busy;label.title=t('sheet.rebind');label.onclick=()=>pickEndpoint(p.id,side);
    const marker=document.createElement('span');marker.className='channel-letter';marker.textContent=side.toUpperCase();
    const pos=document.createElement('small');pos.className='endpointPosition';pos.textContent=p[side]?.x==null?t('portal.pending'):`${p[side].x}, ${p[side].y}`;
    row.append(marker,label,pos);dock.append(row);
  }
  const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=t('sheet.channel_more');details.append(summary);
  for(const side of ['a','b']){
    const label=document.createElement('label');label.className='field';label.textContent=t('sheet.endpoint_on',{side:side.toUpperCase()});
    const select=document.createElement('select');select.dataset.channelFloor=side;select.disabled=busy;
    select.append(new Option(t('portal.pick_floor'),''));
    scene.floors.forEach(f=>select.append(new Option(f.name||f.id,f.id)));
    if(p[side]?.floor&&!scene.floors.some(f=>f.id===p[side].floor))select.append(new Option(t('floor.missing_option',{floor:p[side].floor}),p[side].floor));
    select.value=p[side]?.floor||'';
    select.onchange=()=>{const fid=select.value;commit(()=>p[side]={floor:fid||null,x:null,y:null},t('portal.updated'));pickEndpoint(p.id,side);};
    label.append(select);details.append(label);
  }
  for(const key of ['wait','reverse_wait','door','ride'])numberControl(details,'portal.'+key,p[key],0,3600,1,v=>commit(()=>p[key]=v,t('portal.updated'))).disabled=busy;
  const remove=document.createElement('button');remove.textContent=t('sheet.delete_channel');remove.className='danger';remove.disabled=busy;
  remove.onclick=()=>{cancelPortalPick();commit(()=>scene.portals=scene.portals.filter(q=>q.id!==p.id),t('sheet.channel_removed'));selectedPortalId=null;renderPortalSummary();};
  details.append(remove);dock.append(details);
}

// Affine inverse: screen position -> exact sheet cell. Ambiguous overlap prefers
// the source sheet. The separate bands make drop targets visually unambiguous.
function locateOnSheet(x,y,id){
  const transform=transforms[id],f=floors.find(f=>f.id===id);if(!transform||!f)return null;
  const det=transform.a*transform.d-transform.b*transform.c;if(Math.abs(det)<1e-12)return null;
  const dx=x-transform.e,dy=y-transform.f;
  const px=(transform.d*dx-transform.c*dy)/det,py=(-transform.b*dx+transform.a*dy)/det;
  if(px<0||py<0||px>=f.width||py>=f.height)return null;
  return {floor:id,x:Math.floor(px),y:Math.floor(py)};
}
function pointAt(x,y,preferred=null){
  if(!structure)return locateOnSheet(x,y,floorId);
  if(preferred){const q=locateOnSheet(x,y,preferred);if(q)return q;}
  for(const f of scene.floors){const q=locateOnSheet(x,y,f.id);if(q)return q;}
  return null;
}
function channelLineHit(x,y){
  if(!structure)return null;
  for(const p of [...scene.portals].reverse()){
    if(p.a?.x==null||p.b?.x==null)continue;
    const a=project({...p.a,x:p.a.x+.5,y:p.a.y+.5}),b=project({...p.b,x:p.b.x+.5,y:p.b.y+.5});if(!a||!b)continue;
    const dx=b.x-a.x,dy=b.y-a.y,l2=dx*dx+dy*dy;if(l2<1)continue;
    const k=((x-a.x)*dx+(y-a.y)*dy)/l2;
    if(k>.08&&k<.92&&Math.hypot(x-a.x-k*dx,y-a.y-k*dy)<9)return {id:p.id,side:k<=.5?'a':'b',fromLine:true};
  }
  return null;
}
activeSegments=function(){return gesture?.type==='channel-drag'?[]:previousSegments();};
const oldPortalPoint=portalPoint;
portalPoint=function(p,side){return gesture?.type==='channel-drag'&&gesture.id===p.id&&gesture.side===side?(gesture.point||p[side]):oldPortalPoint(p,side);};
$('mapCanvas').onpointerdown=e=>{
  if(e.button!==0||busy)return;const pos=mouse(e);hideMenu();$('sheetMenu').hidden=true;
  if(portalPick){placePickedPortal(pointAt(pos.x,pos.y));return;}
  const hp=hitPortal(pos.x,pos.y)||channelLineHit(pos.x,pos.y);
  if(hp){
    const p=scene.portals.find(p=>p.id===hp.id);selectedPortalId=p.id;
    gesture={type:'channel-drag',...hp,x:pos.x,y:pos.y,point:{...p[hp.side]},source:{...p[hp.side]},moved:false};
    e.currentTarget.setPointerCapture(e.pointerId);renderPortalSummary();draw();return;
  }
  if(structure){const n=hit(pos.x,pos.y);if(n){selection=new Set([n._key]);renderEditor();draw();}else{selectedPortalId=null;renderPortalSummary();draw();}return;}
  canvasHandlers.down(e);
};
$('mapCanvas').onpointermove=e=>{
  const pos=mouse(e);
  if(gesture?.type==='channel-drag'){
    gesture.moved||=Math.hypot(pos.x-gesture.x,pos.y-gesture.y)>4;
    if(gesture.moved){gesture.point=pointAt(pos.x,pos.y,gesture.source.floor);hoveredSheet=gesture.point?.floor||null;gesture.cursor=pos;}
    draw();
    const p=scene.portals.find(p=>p.id===gesture.id),q=gesture.point;
    const row=$('channelDock').querySelector(`[data-channel-side="${gesture.side}"]`);
    if(row&&q){row.querySelector('.channel-sheet').textContent=floorName(q.floor);row.querySelector('.endpointPosition').textContent=`${q.x}, ${q.y}`;}
    return;
  }
  if(!gesture){$('mapCanvas').style.cursor=portalPick||mode==='add'?'crosshair':hitPortal(pos.x,pos.y)||channelLineHit(pos.x,pos.y)?'grab':'';}
  canvasHandlers.move(e);
};
$('mapCanvas').onpointerup=e=>{
  if(gesture?.type!=='channel-drag'){canvasHandlers.up(e);return;}
  const g=gesture;gesture=null;hoveredSheet=null;
  const p=scene.portals.find(p=>p.id===g.id),other=g.side==='a'?'b':'a';
  if(g.moved){
    if(!g.point||!validPoint(g.point)){announce(t('error.drag_blocked'),true);}
    else if(p[other]?.x!=null&&p[other].floor===g.point.floor){announce(t('sheet.other_sheet'),true);}
    else{commit(()=>{p[g.side]={...g.point};floorId=g.point.floor;},t('portal.updated'));announce(t('sheet.channel_moved'));}
  }
  renderPortalSummary();renderTabs();draw();
};
$('mapCanvas').onpointercancel=()=>{gesture=null;hoveredSheet=null;renderChannelDock();draw();};
$('mapCanvas').addEventListener('lostpointercapture',()=>{if(gesture?.type==='channel-drag'){gesture=null;hoveredSheet=null;renderChannelDock();draw();}});
const oldContext=$('mapCanvas').oncontextmenu;
$('mapCanvas').oncontextmenu=e=>{
  if(busy){e.preventDefault();return;}const pos=mouse(e),channel=hitPortal(pos.x,pos.y)||channelLineHit(pos.x,pos.y);
  if(channel){e.preventDefault();selectedPortalId=channel.id;renderPortalSummary();draw();return;}oldContext(e);
};

const oldDrawLinks=drawPortalLinks;
drawPortalLinks=function(ctx,line,center){
  oldDrawLinks(ctx,line,center);
  if(!structure)return;
  for(const p of scene.portals){
    const a=center(portalPoint(p,'a')),b=center(portalPoint(p,'b'));if(!a||!b)continue;
    const active=selectedPortalId===p.id,color=!p.enabled?'#94a3b8':portalLocalState(p)!=='complete'?'#d46a35':active?'#047eab':'#628eb1';
    if(active)line([a,b],'#3ba8cf26',12);
    line([a,b],color,active?3.5:2,p.enabled?[]:[5,6]);
    if(active){for(const k of [.22,.78]){const x=a.x+(b.x-a.x)*k,y=a.y+(b.y-a.y)*k;
      ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.strokeStyle=color;ctx.lineWidth=2;ctx.stroke();}}
  }
};
drawPortalPins=function(ctx,center){
  for(const p of scene.portals)for(const side of ['a','b']){
    const q=portalPoint(p,side),spot=center(q);if(!spot)continue;
    const active=selectedPortalId===p.id,good=validPoint(q),color=!p.enabled?'#9aa8b3':good?'#087f9f':'#db6439';
    ctx.save();ctx.shadowColor='#0f344b33';ctx.shadowBlur=active?9:4;ctx.shadowOffsetY=2;
    ctx.fillStyle=active?color:'#fff';ctx.strokeStyle=color;ctx.lineWidth=active?3:2;
    ctx.beginPath();ctx.roundRect(spot.x-8,spot.y-8,16,16,4);ctx.fill();ctx.stroke();ctx.shadowBlur=0;ctx.shadowOffsetY=0;
    ctx.strokeStyle=active?'#fff':color;ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(spot.x-3,spot.y+3);ctx.lineTo(spot.x-3,spot.y-3);ctx.lineTo(spot.x+3,spot.y-3);ctx.lineTo(spot.x+3,spot.y+3);ctx.stroke();
    ctx.fillStyle=color;ctx.font=active?'bold 11px sans-serif':'10px sans-serif';
    ctx.fillText(active?portalEndpointLabel(p,side):p.id,spot.x+12,spot.y+3);ctx.restore();
  }
};
function drawSheetOverlay(ctx,W,H){
  if(hoveredSheet&&transforms[hoveredSheet]){
    const f=floors.find(f=>f.id===hoveredSheet),corners=[[0,0],[f.width,0],[f.width,f.height],[0,f.height]].map(([x,y])=>project({floor:f.id,x,y}));
    ctx.beginPath();corners.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.strokeStyle='#168fb7';ctx.lineWidth=3;ctx.stroke();
  }
  if(!scene.nodes.length&&!scene.portals.length&&!structure){
    ctx.save();ctx.font='600 16px sans-serif';ctx.textAlign='center';ctx.fillStyle='#506e88';
    ctx.fillText(t('sheet.canvas_hint'),W/2,H/2);ctx.restore();
  }
}

$('undoBtn').onclick=()=>{
  if(busy||!undoStack.length)return;cancelPortalPick();const previous=undoStack.pop(),same=topologySignature(previous)===topologySignature(scene);
  scene=previous;selection.clear();selectedPortalId=null;
  if(!scene.floors.some(f=>f.id===floorId))floorId=scene.floors[0].id;
  if(same){renderEditor();renderTabs();renderPortalSummary();draw();announce(t('status.undo'));}
  else{changed(t('status.undo'));renderTabs();}
};
$('managePortalsBtn').onclick=()=>{if(scene.portals.length){selectedPortalId=selectedPortalId||scene.portals[0].id;renderChannelDock();}else newChannel();};
$('fixPortalsBtn').onclick=()=>{const bad=scene.portals.find(p=>p.enabled&&portalLocalState(p)!=='complete');if(bad)openPortalSettings(bad.id);else previousPortalSettings();};
// Smaller controls are optional, not silently removed capabilities.
$('importMapBtn').closest('.portal-sidebar').before($('importMapBtn'));
$('importBtn').title=t('sheet.scene_import');$('exportBtn').title=t('sheet.scene_export');
$('settingsBtn').onclick=()=>{previousPortalSettings();document.querySelectorAll('#settingsDialog > details').forEach(d=>d.open=false);};
document.addEventListener('pointerdown',e=>{if(!$('sheetMenu').contains(e.target))$('sheetMenu').hidden=true;});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){$('sheetMenu').hidden=true;hoveredSheet=null;quickPortalFlow=false;syncWorkbenchState();}});
document.addEventListener('languagechange',()=>{renderTabs();renderChannelDock();syncWorkbenchState();$('actionToast').hidden=true;});
document.addEventListener('click',e=>{const b=e.target.closest('button');if(b&&!b.disabled){b.classList.remove('tap-feedback');void b.offsetWidth;b.classList.add('tap-feedback');setTimeout(()=>b.classList.remove('tap-feedback'),500);}syncWorkbenchState();});
$('clearanceToggle').addEventListener('change',syncWorkbenchState);
$('observatoryDetails').addEventListener('toggle',()=>{drawChart();});
I18n.apply();
