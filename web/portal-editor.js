/* Paired elevator drafts. The map raster is never painted over to create a link. */
'use strict';
let draftCheckTimer=null, draftVersion=0, draftPreflight=null;
let portalRenderState=[], uploadInProgress=false, settingsSaving=false;

function portalEndpointLabel(p,side){
  if(!p)return '—';
  return `${p.id}_${p[side]?.floor||side.toUpperCase()}`;
}
function portalLocalState(p){
  if(!p.enabled)return 'disabled';
  if(['a','b'].some(s=>!p[s]?.floor||p[s].x==null||p[s].y==null))return 'incomplete';
  if(p.a.floor===p.b.floor||!validPoint(p.a)||!validPoint(p.b))return 'invalid';
  return 'complete';
}
function renderPortalSummary(){
  if(!scene)return;
  const states=new Map((preview?.preflight?.portals||[]).map(p=>[p.id,p.state]));
  const box=$('portalSummary');box.replaceChildren();
  if(!scene.portals.length){box.textContent=t('portal.none');return;}
  for(const p of scene.portals){
    const state=states.get(p.id)||portalLocalState(p),b=document.createElement('button');
    b.className=`portal-chip ${state}`;b.dataset.portal=p.id;b.disabled=busy;
    b.textContent=`${p.id} · ${t('portal.'+state)}`;
    b.title=`${portalEndpointLabel(p,'a')} ↔ ${portalEndpointLabel(p,'b')}`;
    b.onclick=()=>openPortalSettings(p.id);box.append(b);
  }
}
function renderValidation(){
  const issues=preview?.preflight?.issues||[],panel=$('preflightPanel');
  panel.hidden=!issues.length;
  $('preflightIssues').replaceChildren();
  for(const issue of issues){
    const row=document.createElement('div');row.className=`preflight-issue ${issue.severity}`;
    row.dataset.code=issue.code;row.textContent=t(issue.code,issue.params);
    if(issue.params.portal){
      const btn=document.createElement('button');btn.textContent=t('validation.resolve');
      btn.disabled=busy;btn.onclick=()=>openPortalSettings(issue.params.portal);row.append(btn);
    }
    $('preflightIssues').append(row);
  }
  panel.querySelector('strong').textContent=issues.some(i=>i.severity==='error')?t('validation.title'):t('validation.warnings',{count:issues.length});
  $('fixPortalsBtn').disabled=busy;
  renderPortalSummary();availability();
}
function updatePlacement(){
  $('placementBar').hidden=!portalPick;
  if(portalPick){
    const p=scene.portals.find(p=>p.id===portalPick.id);
    $('placementLabel').textContent=t('portal.pick_hint',{floor:floorName(portalPick.floor),endpoint:portalEndpointLabel(p,portalPick.side)});
  }
  $('mapCanvas').classList.toggle('portal-mode',!!portalPick);
  availability();
}
function cancelPortalPick(){
  if(!portalPick)return;
  portalPick=null;mode='select';updatePlacement();renderTabs();
}
function placePickedPortal(point){
  if(!portalPick)return;
  if(!point||point.floor!==portalPick.floor||!validPoint(point)){status(t('error.add_blocked'),true);return;}
  const picked=portalPick,p=scene.portals.find(p=>p.id===picked.id);
  const message=t('portal.saved',{endpoint:portalEndpointLabel(p,picked.side)});
  portalPick=null;mode='select';
  commit(()=>{p[picked.side]={...point};},message);updatePlacement();renderTabs();
}
function portalPoint(p,side){
  return gesture?.type==='portal'&&gesture.id===p.id&&gesture.side===side?gesture.point:p[side];
}
function hitPortal(x,y){
  for(const p of [...(scene?.portals||[])].reverse())for(const side of ['a','b']){
    const q=p[side];if(q?.x==null||q?.y==null)continue;
    const spot=project({...q,x:q.x+.5,y:q.y+.5});
    if(spot&&Math.hypot(spot.x-x,spot.y-y)<10)return {id:p.id,side};
  }
  return null;
}
function drawPortalLinks(ctx,line,center){
  portalRenderState=[];
  if(!structure)return;
  for(const p of scene.portals){
    const a=center(portalPoint(p,'a')),b=center(portalPoint(p,'b'));
    const state=portalLocalState(p),color=!p.enabled?'#aab5bc':state==='complete'?'#a4bac3':'#d27839';
    if(a&&b){line([a,b],color,state==='complete'?1.5:2,[4,5]);portalRenderState.push({id:p.id,kind:'complete',state});continue;}
    const known=a||b;
    if(known){
      const side=a?'b':'a',missing=p[side],source=a?p.a:p.b;
      // Dashed half-link is a visual placeholder only, never a route edge or
      // a stored coordinate. The endpoint stays null in the exported scene.
      const target=missing?.floor&&transforms[missing.floor]?center({...source,floor:missing.floor}):null;
      const half=target?{x:(known.x+target.x)/2,y:(known.y+target.y)/2}:
        {x:known.x+22,y:known.y+(side==='b'?-46:46)};
      line([known,half],color,2.5,[5,4]);
      ctx.fillStyle='#fff8ed';ctx.strokeStyle=color;ctx.lineWidth=1.5;ctx.beginPath();ctx.arc(half.x,half.y,9,0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.font='bold 12px sans-serif';ctx.fillStyle=color;ctx.textAlign='center';ctx.fillText('?',half.x,half.y+4);ctx.textAlign='left';
      ctx.font='11px sans-serif';ctx.fillText(`${portalEndpointLabel(p,side)} · ${t('portal.waiting')}`,half.x+13,half.y+4);
      portalRenderState.push({id:p.id,kind:'half',state,missing:side});
    }else{
      portalRenderState.push({id:p.id,kind:'unplaced',state});
    }
  }
}
function drawPortalPins(ctx,center){
  for(const p of scene.portals)for(const side of ['a','b']){
    const point=portalPoint(p,side),q=center(point);if(!q)continue;
    const good=validPoint(point),color=!p.enabled?'#8b979f':good?'#b1843e':'#ce5949';
    ctx.fillStyle=p.enabled?'#fffaf0':'#e6e9eb';ctx.strokeStyle=color;ctx.lineWidth=2;
    ctx.beginPath();ctx.roundRect(q.x-6,q.y-6,12,12,2);ctx.fill();ctx.stroke();
    if(!good){ctx.beginPath();ctx.moveTo(q.x-4,q.y-4);ctx.lineTo(q.x+4,q.y+4);ctx.moveTo(q.x-4,q.y+4);ctx.lineTo(q.x+4,q.y-4);ctx.stroke();}
    ctx.fillStyle=color;ctx.font='10px sans-serif';ctx.fillText(portalEndpointLabel(p,side),q.x+9,q.y+3);
  }
}
function openPortalSettings(id=null){
  if(busy||uploadInProgress||settingsSaving)return;
  cancelPortalPick();draft=clone(scene);draftPreflight=null;draftVersion++;
  renderSettings();$('dialogLanguageSelect').value=I18n.language;$('settingsDialog').showModal();scheduleDraftCheck();
  if(id){const card=[...$('portalSettings').children].find(c=>c.dataset.portal===id);card?.scrollIntoView({block:'center'});}
}
function labelInput(parent,key,value,onchange){
  const label=document.createElement('label');label.className='field';label.append(document.createTextNode(t(key)));
  const input=document.createElement('input');input.value=value;input.maxLength=40;input.required=true;
  input.onchange=()=>{if(!input.reportValidity())return;onchange(input.value.trim());scheduleDraftCheck();};
  label.append(input);parent.append(label);return input;
}
function renderMapSettings(){
  $('floorSettings').replaceChildren();
  for(const f of draft.floors){
    const card=document.createElement('div');card.className='floor-setting';card.dataset.floor=f.id;
    const heading=document.createElement('div');heading.className='floor-heading';card.append(heading);
    const name=labelInput(heading,'floor.name',f.name||f.id,v=>{f.name=v;});name.dataset.floorName=f.id;
    const id=document.createElement('small');id.className='muted';id.textContent=f.id;heading.append(id);
    numberControl(heading,'m/px',f.resolution,.01,2,.01,v=>{f.resolution=v;scheduleDraftCheck();});
    const replace=document.createElement('button');replace.className='replaceFloor';replace.textContent=t('floor.replace');
    replace.onclick=()=>{uploadTarget=f.id;$('floorUpload').multiple=false;$('floorUpload').click();};heading.append(replace);
    const remove=document.createElement('button');remove.className='removeFloor';remove.textContent=t('common.remove');
    remove.onclick=()=>{
      if(draft.floors.length===1){status(t('error.last_floor'),true);return;}
      if(!confirm(t('portal.confirm_floor',{floor:f.name||f.id})))return;
      draft.floors=draft.floors.filter(x=>x.id!==f.id);draft.nodes=draft.nodes.filter(n=>n.floor!==f.id);
      // Keep dangling portal references for repair instead of silently deleting links.
      draftPreflight=null;renderSettings();scheduleDraftCheck();
    };heading.append(remove);
    const more=document.createElement('details');const summary=document.createElement('summary');summary.textContent=t('setting.unknown');more.append(summary);
    const unknown=document.createElement('input');unknown.type='number';unknown.min=0;unknown.max=254;unknown.step=1;unknown.value=f.unknown_value??'';
    unknown.setAttribute('aria-label',t('setting.unknown'));unknown.placeholder=t('placeholder.unknown');
    unknown.onchange=()=>{if(unknown.value==='')delete f.unknown_value;else if(unknown.reportValidity())f.unknown_value=Number(unknown.value);scheduleDraftCheck();};more.append(unknown);card.append(more);$('floorSettings').append(card);
  }
  $('portalSettings').replaceChildren();
  for(const p of draft.portals){
    const card=document.createElement('div');card.className='portal-setting';card.dataset.portal=p.id;
    const head=document.createElement('div');head.className='portal-heading';card.append(head);
    const id=labelInput(head,'portal.id',p.id,v=>{
      if(!v||draft.portals.some(q=>q!==p&&q.id===v)){fieldError(id,'error.portal_id');id.reportValidity();return;}
      p.id=v;renderSettings();
    });id.className='portalId';
    const enabledLabel=document.createElement('label');enabledLabel.className='check';
    const enabled=document.createElement('input');enabled.type='checkbox';enabled.className='portalEnabled';enabled.checked=p.enabled;
    enabled.setAttribute('aria-label',t('aria.toggle_portal',{portal:p.id}));enabled.onchange=()=>{p.enabled=enabled.checked;scheduleDraftCheck();};
    enabledLabel.append(enabled,document.createTextNode(t('common.enabled')));head.append(enabledLabel);
    const badge=document.createElement('span');badge.className='portal-state';head.append(badge);
    const remove=document.createElement('button');remove.className='removePortal';remove.textContent=t('common.remove');
    remove.onclick=()=>{if(!confirm(t('portal.confirm_remove',{portal:p.id})))return;draft.portals=draft.portals.filter(q=>q!==p);renderSettings();scheduleDraftCheck();};head.append(remove);
    const endpoints=document.createElement('div');endpoints.className='paired-endpoints';card.append(endpoints);
    for(const side of ['a','b']){
      p[side]??={floor:null,x:null,y:null};const q=p[side];
      const row=document.createElement('div');row.className='endpoint-card';row.dataset.side=side;
      const title=document.createElement('strong');title.textContent=portalEndpointLabel(p,side);row.append(title);
      const label=document.createElement('label');label.className='field';label.append(document.createTextNode(t('portal.side_'+side)));
      const select=document.createElement('select');select.className='endpointFloor';
      select.innerHTML=`<option value="">${t('portal.pick_floor')}</option>`+draft.floors.map(f=>`<option value="${esc(f.id)}">${esc(f.name||f.id)}</option>`).join('');
      if(q.floor&&!draft.floors.some(f=>f.id===q.floor)){
        const option=document.createElement('option');option.value=q.floor;option.textContent=t('floor.missing_option',{floor:q.floor});select.append(option);
      }
      select.value=q.floor||'';select.onchange=()=>{p[side]={floor:select.value||null,x:null,y:null};renderSettings();scheduleDraftCheck();};
      label.append(select);row.append(label);
      const coords=document.createElement('span');coords.className='endpoint-coordinates';coords.textContent=q.x==null||q.y==null?t('portal.pending'):`(${q.x}, ${q.y})`;row.append(coords);
      const actions=document.createElement('div');actions.className='endpoint-actions';row.append(actions);
      const place=document.createElement('button');place.className='placeEndpoint';place.textContent=q.x==null||q.y==null?t('portal.place'):t('portal.relocate');
      place.disabled=!draft.floors.some(f=>f.id===q.floor);place.onclick=()=>saveDraft({id:p.id,side,floor:q.floor});actions.append(place);
      const clear=document.createElement('button');clear.className='clearEndpoint';clear.textContent=t('portal.clear');
      clear.disabled=q.x==null&&q.y==null;clear.onclick=()=>{q.x=null;q.y=null;renderSettings();scheduleDraftCheck();};actions.append(clear);
      const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=t('field.coordinates');details.append(summary);
      const inputs=document.createElement('div');inputs.className='field-pair';details.append(inputs);
      for(const axis of ['x','y']){
        const l=document.createElement('label');l.className='field';l.append(document.createTextNode(axis.toUpperCase()));
        const input=document.createElement('input');input.type='number';input.min=0;input.max=511;input.step=1;input.value=q[axis]??'';input.dataset.axis=axis;
        input.onchange=()=>{if(!input.reportValidity())return;q[axis]=input.value===''?null:Number(input.value);coords.textContent=q.x==null||q.y==null?t('portal.pending'):`(${q.x}, ${q.y})`;clear.disabled=q.x==null&&q.y==null;scheduleDraftCheck();};
        l.append(input);inputs.append(l);
      }
      row.append(details);endpoints.append(row);
    }
    const timings=document.createElement('details');const summary=document.createElement('summary');summary.textContent=t('portal.timings');timings.append(summary);
    const controls=document.createElement('div');controls.className='settings-grid';timings.append(controls);
    for(const k of ['wait','reverse_wait','door','ride'])numberControl(controls,'portal.'+k,p[k],0,3600,1,v=>{p[k]=v;scheduleDraftCheck();});
    card.append(timings);$('portalSettings').append(card);
  }
  renderDraftIssues();
}
function scheduleDraftCheck(){
  const version=++draftVersion;clearTimeout(draftCheckTimer);draftPreflight=null;
  $('draftIssues').textContent=t('validation.checking');
  draftCheckTimer=setTimeout(async()=>{
    try{
      const v=await api('/api/editor/preflight',clone(draft));
      if(version!==draftVersion)return;draftPreflight=v;renderDraftIssues();
    }catch(e){if(version===draftVersion)$('draftIssues').textContent=e.message;}
  },160);
}
function renderDraftIssues(){
  const errors=draftPreflight?.issues.filter(i=>i.severity==='error')||[];
  $('draftIssues').textContent=!draftPreflight?t('portal.draft_note'):errors.length?
    errors.map(i=>t(i.code,i.params)).join(' '):t('portal.ready');
  for(const card of $('portalSettings').children){
    const p=draft.portals.find(p=>p.id===card.dataset.portal),state=draftPreflight?.portals.find(p=>p.id===card.dataset.portal)?.state||
      (!p.enabled?'disabled':['a','b'].some(s=>!p[s].floor||p[s].x==null||p[s].y==null)?'incomplete':'checking');
    const el=card.querySelector('.portal-state');el.textContent=state==='checking'?t('validation.checking'):t('portal.'+state);el.className='portal-state '+state;
  }
}
async function saveDraft(pick=null){
  if(settingsSaving||uploadInProgress)return;
  if([...$('settingsDialog').querySelectorAll('input')].some(input=>!input.reportValidity()))return;
  settingsSaving=true;$('settingsDialog').inert=true;$('applySettingsBtn').disabled=true;
  const snapshot=clone(draft),version=draftVersion;
  try{
    await api('/api/editor/preflight',snapshot); // Structural validation, drafts are allowed.
    if(version!==draftVersion)return;
    commit(()=>{scene=snapshot;selection.clear();if(!scene.floors.some(f=>f.id===floorId))floorId=scene.floors[0].id;},t('status.settings'));
    $('settingsDialog').close();draftVersion++;clearTimeout(draftCheckTimer);
    if(pick){portalPick=pick;floorId=pick.floor;structure=false;mode='portal';$('mapCanvas').scrollIntoView({block:'center',behavior:'smooth'});}
    renderTabs();updatePlacement();draw();
  }catch(e){status(e.message,true);$('draftIssues').textContent=e.message;}
  finally{settingsSaving=false;$('settingsDialog').inert=false;$('applySettingsBtn').disabled=false;}
}
function parseSceneJSON(value){try{return JSON.parse(value);}catch(_){throw new Error(t('error.scene_parse'));}}
function fieldError(input,key,params={}){input.dataset.validation=JSON.stringify({code:key,params});input.setCustomValidity(t(key,params));}
document.addEventListener('invalid',e=>{
  const input=e.target;if(!input.setCustomValidity)return;
  if(input.validity.customError)return;
  if(input.validity.valueMissing)fieldError(input,'validation.required');
  else if(input.validity.rangeOverflow||input.validity.rangeUnderflow)fieldError(input,'validation.range',{min:input.min,max:input.max});
  else if(input.validity.stepMismatch)fieldError(input,'validation.integer');
  else fieldError(input,'validation.number');
},true);
document.addEventListener('input',e=>{if(e.target.setCustomValidity){delete e.target.dataset.validation;e.target.setCustomValidity('');}},true);
$('languageSelect').value=I18n.language;
$('languageSelect').onchange=e=>I18n.setLanguage(e.target.value);
$('dialogLanguageSelect').onchange=e=>I18n.setLanguage(e.target.value);
document.addEventListener('languagechange',()=>{
  if(!scene)return;
  $('languageSelect').value=$('dialogLanguageSelect').value=I18n.language;
  // Re-render presentation only. Model, coordinates, order, snapshot and seed stay unchanged.
  const values=[...document.querySelectorAll('#nodeForm input')].map(e=>[e.id,e.value,e.dataset.validation]);
  const world=$('worldSelect').value;
  hideMenu();renderEditor();renderTabs();renderObservation();renderMath();renderValidation();updatePlacement();
  $('worldSelect').innerHTML=`<option value="best">${t('ga.best_world')}</option>`+(meta?Array.from({length:meta.settings.sower?meta.settings.worlds:1},(_,i)=>`<option value="${i}">${t('ga.world',{world:i+1})}</option>`).join(''):'');$('worldSelect').value=world;
  $('playBtn').textContent=replayTimer?t('ga.pause'):t('ga.replay');
  if(draft&&$('settingsDialog').open)renderSettings();
  for(const [id,value,error] of values){$(id).value=value;if(error){const d=JSON.parse(error);fieldError($(id),d.code,d.params);}}
  $('status').textContent=I18n.render(statusValue);
  // Preview labels are dynamic and must not revert to their initial loading text.
  if(!meta){$('previewLabel').textContent=previewRunning||previewQueued?t('preview.updating'):preview?.error?t('preview.no_route'):scene.nodes.length<2?t('preview.two_nodes'):t('preview.ordered');
    $('previewElevators').textContent=preview?.legs.flatMap(l=>l.segments.filter(s=>s.kind==='elevator').map(s=>`${s.id} ${s.start.floor} → ${s.end.floor}`)).join(' / ')||t('route.same_floor');}
});
$('managePortalsBtn').onclick=()=>openPortalSettings();$('fixPortalsBtn').onclick=()=>openPortalSettings();
$('settingsBtn').onclick=()=>openPortalSettings();
$('closeSettings').onclick=()=>{$('settingsDialog').close();draftVersion++;clearTimeout(draftCheckTimer);};
$('settingsDialog').addEventListener('cancel',()=>{draftVersion++;clearTimeout(draftCheckTimer);});
$('applySettingsBtn').onclick=()=>saveDraft();$('cancelPortalPick').onclick=()=>{cancelPortalPick();draw();};
$('addFloorBtn').onclick=()=>{if(draft.floors.length>=4){status(t('error.max_floors'),true);return;}uploadTarget=null;$('floorUpload').multiple=true;$('floorUpload').click();};
$('floorUpload').onchange=async e=>{
  const files=[...e.target.files],target=uploadTarget;e.target.value='';if(!files.length||uploadInProgress)return;
  const uploadDraft=draft;uploadInProgress=true;$('applySettingsBtn').disabled=$('addFloorBtn').disabled=true;
  const failures=[];
  for(const file of files){
    try{
      if(!target&&draft.floors.length>=4)throw Error(t('error.max_floors'));
      if(file.size>2000000)throw Error(t('error.image_size'));
      $('draftIssues').textContent=t('upload.loading',{file:file.name});
      const url=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error(t('error.image')));r.readAsDataURL(file);});
      const v=await api('/api/map-preview',{map_data:url});
      if(draft!==uploadDraft||!$('settingsDialog').open)break;
      if(target){
        const f=draft.floors.find(f=>f.id===target);if(!f)continue;f.map_data=v.data;
        for(const p of draft.portals)for(const side of ['a','b'])if(p[side].floor===target){p[side].x=null;p[side].y=null;}
        status(t('portal.map_replaced'));
      }else{
        let k=1;while(draft.floors.some(f=>f.id===`${k}F`))k++;
        draft.floors.push({id:`${k}F`,name:file.name.replace(/\.[^.]+$/,''),map_data:v.data,resolution:.1});
      }
    }catch(error){failures.push(`${file.name}: ${error.message}`);}
  }
  uploadInProgress=false;$('applySettingsBtn').disabled=$('addFloorBtn').disabled=false;
  if(draft!==uploadDraft||!$('settingsDialog').open)return;
  draftPreflight=null;renderSettings();scheduleDraftCheck();
  if(failures.length)status(t('upload.partial',{file:failures.join('; ')}),true);
};
$('addPortalBtn').onclick=()=>{
  if(draft.floors.length<2){status(t('portal.create_first'),true);return;}
  if(draft.portals.length>=12){status(t('error.max_portals'),true);return;}
  let k=0;while(draft.portals.some(p=>p.id===`E${String.fromCharCode(97+k)}`))k++;
  draft.portals.push({id:`E${String.fromCharCode(97+k)}`,a:{floor:draft.floors[0].id,x:null,y:null},b:{floor:draft.floors[1].id,x:null,y:null},wait:15,reverse_wait:15,door:6,ride:8,enabled:true});
  renderSettings();scheduleDraftCheck();$('portalSettings').lastElementChild.scrollIntoView({block:'nearest'});
};
