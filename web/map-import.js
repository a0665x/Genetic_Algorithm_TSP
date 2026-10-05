/* Reviewed semantic map import. These controls never infer elevator positions. */
'use strict';
let mapQueue=[], mapTarget=null, mapSession=null, mapCandidate=null, mapReview=null;
let mapStandalone=false, mapScaleAssumed=true, mapApplying=false, mapApplySerial=0;
let mapRevision=0, mapTimer=null, mapReading=false, mapRules=[], mapPicking=false;
let mapHistogramGray=205, mapHistogramStart=null;
const rasterCache=new Map();
const mapDialog=document.createElement('dialog');mapDialog.id='mapImportDialog';
mapDialog.innerHTML=`<div class="dialog-title"><h2 data-i18n="semantic.title"></h2><select id="mapLanguage" data-i18n-aria-label="language.label"><option value="en">English</option><option value="zh-Hant">繁體中文</option></select><button id="closeMapImport" data-i18n-aria-label="common.close">✕</button></div>
<p id="mapFileName" class="hint"></p>
<details id="mapOptions"><summary data-i18n="sheet.import_options"></summary><div class="map-import-fields"><label class="field"><span data-i18n="semantic.floor_id"></span><input id="mapFloorId" maxlength="40" required/></label><label class="field"><span data-i18n="floor.name"></span><input id="mapFloorName" maxlength="40" required/></label><label class="field"><span data-i18n="semantic.source_scale"></span><input id="mapScale" type="number" min=".001" max="2" step=".001" required value="0.1"/></label><label class="field"><span data-i18n="semantic.profile"></span><select id="mapProfile"><option value="auto" data-i18n="semantic.auto"></option><option value="graph" data-i18n="semantic.graph"></option><option value="lidar" data-i18n="semantic.lidar"></option><option value="floorplan" data-i18n="semantic.floorplan"></option><option value="custom" data-i18n="semantic.custom"></option></select></label></div></details>
<div class="map-review-grid"><section><h3 data-i18n="semantic.original"></h3><div class="map-canvas-stack"><canvas id="sourceCanvas" data-i18n-aria-label="semantic.source_pick"></canvas><canvas id="sourceHighlight" aria-hidden="true"></canvas></div></section><section><div class="map-preview-heading"><h3 data-i18n="semantic.preview"></h3><select id="reviewLayer" data-i18n-aria-label="semantic.layer"><option value="class_preview" data-i18n="semantic.classes"></option><option value="map_data" data-i18n="semantic.planning"></option><option value="clearance_preview" data-i18n="semantic.clearance"></option></select></div><canvas id="reviewCanvas" data-i18n-aria-label="semantic.preview"></canvas></section></div>
<p id="mapSimpleSummary" class="map-simple-summary" role="status"></p>
<div class="semantic-legend"><span class="map-class wall" data-i18n="semantic.wall"></span><span class="map-class unknown" data-i18n="semantic.unknown"></span><span class="map-class cost" data-i18n="semantic.cost"></span><span class="map-class free" data-i18n="semantic.free"></span></div>
<p id="mapReviewState" class="map-review-state" role="status"></p><details id="mapDiagnostics"><summary data-i18n="sheet.map_notes"></summary><p id="mapStats" class="hint"></p><div id="mapWarnings" class="map-warnings"></div></details>
<details id="mapAdvanced"><summary data-i18n="semantic.advanced"></summary><div class="map-import-fields"><label class="field"><span data-i18n="semantic.wall_threshold"></span><input id="mapWall" type="number" min="0" max="253" step="1" value="100"/></label><label class="field"><span data-i18n="semantic.free_threshold"></span><input id="mapFree" type="number" min="1" max="255" step="1" value="240"/></label><label class="field"><span data-i18n="semantic.grid_size"></span><select id="mapMaxSide"><option>512</option><option>384</option><option>256</option></select></label><label class="check"><input id="mapInvert" type="checkbox"/><span data-i18n="semantic.invert"></span></label></div>
<p class="hint" data-i18n="semantic.rule_help"></p><section class="color-histogram-panel"><div class="map-preview-heading"><h3 data-i18n="semantic.histogram_title"></h3><span data-i18n="semantic.histogram_axes" class="hint"></span></div><canvas id="colorHistogram" width="768" height="180" tabindex="0" role="img" data-i18n-aria-label="semantic.histogram_aria"></canvas><p id="histogramSelection" class="hint" role="status"></p></section><div class="map-color-controls"><input type="color" id="mapColor" value="#cdcdcd" data-i18n-aria-label="semantic.color"/><select id="mapRuleKind" data-i18n-aria-label="semantic.class"><option value="wall" data-i18n="semantic.wall"></option><option value="unknown" selected data-i18n="semantic.unknown"></option><option value="cost" data-i18n="semantic.cost"></option><option value="free" data-i18n="semantic.free"></option></select><label><span data-i18n="semantic.tolerance"></span><input id="mapTolerance" type="number" min="0" max="64" step="1" value="8"/></label><button id="pickMapColor" data-i18n="semantic.pick"></button><button id="addMapRule" data-i18n="semantic.add_rule"></button></div><div id="mapRules"></div><button id="refreshMapReview" data-i18n="semantic.refresh"></button></details>
<div class="map-import-footer"><label class="check" hidden><input type="checkbox" id="mapReviewed"/><span data-i18n="semantic.confirm"></span></label><button class="primary" id="applyMapImport" disabled data-i18n="semantic.use_map"></button></div>`;
document.body.append(mapDialog);
const importMapButton=document.createElement('button');importMapButton.id='importMapBtn';importMapButton.dataset.i18n='semantic.import';
$('managePortalsBtn').closest('.panel-title').after(importMapButton);
importMapButton.onclick=()=>{if(busy)return;openPortalSettings();$('addFloorBtn').click();};
const layerSelect=document.createElement('select');layerSelect.id='mapLayer';layerSelect.dataset.i18nAriaLabel='semantic.layer';
for(const key of ['planning','original','classes']){const o=document.createElement('option');o.value=key;o.dataset.i18n='semantic.'+key;layerSelect.append(o);}
$('structureBtn').after(layerSelect);layerSelect.onchange=()=>draw();
I18n.apply();

function mapError(key,params={}){$('mapWarnings').textContent=t('semantic.'+key,params);$('applyMapImport').disabled=true;}
function closeMapImport(){mapRevision++;mapApplySerial++;mapApplying=false;clearTimeout(mapTimer);mapQueue=[];mapSession=null;mapCandidate=null;mapReview=null;mapReading=false;uploadInProgress=false;mapPicking=false;$('applyMapImport').setAttribute('aria-busy','false');mapDialog.close();$('applySettingsBtn').disabled=false;$('addFloorBtn').disabled=false;if(typeof syncWorkbenchState==='function')syncWorkbenchState();}
$('closeMapImport').onclick=closeMapImport;mapDialog.addEventListener('cancel',e=>{e.preventDefault();closeMapImport();});
$('mapLanguage').onchange=e=>I18n.setLanguage(e.target.value);
function invalidateMap(){mapRevision++;mapReview=null;mapPicking=false;$('mapReviewed').checked=false;$('applyMapImport').disabled=true;clearTimeout(mapTimer);mapTimer=setTimeout(computeMapReview,200);}
for(const id of ['mapScale','mapProfile','mapWall','mapFree','mapMaxSide','mapInvert'])$(id).onchange=invalidateMap;
$('mapReviewed').onchange=()=>{$('applyMapImport').disabled=!mapReview||!$('mapReviewed').checked||mapReading||mapReview.stats.walkable===0;};
$('mapFloorId').oninput=()=>{$('mapFloorId').setCustomValidity('');};
$('mapScale').onchange=()=>{mapScaleAssumed=false;invalidateMap();};
$('reviewLayer').value='clearance_preview';
$('reviewLayer').onchange=()=>paintReview();
$('refreshMapReview').onclick=invalidateMap;
$('mapAdvanced').ontoggle=()=>{if($('mapAdvanced').open)drawColorHistogram();};

async function beginMapImport(files,target=null,standalone=false){
  if(uploadInProgress||busy)return;
  mapStandalone=standalone;
  if(standalone)draft=clone(scene);
  if(!draft)return;
  if(!target&&files.length>4-draft.floors.length){if(typeof announce==='function')announce(t('error.max_floors'),true);$('draftIssues').textContent=t('error.max_floors');return;}
  uploadInProgress=true;mapSession=draft;mapQueue=[...files];mapTarget=target;
  $('applySettingsBtn').disabled=$('addFloorBtn').disabled=true;mapDialog.showModal();$('mapLanguage').value=I18n.language;$('mapOptions').open=false;$('mapDiagnostics').open=false;
  await nextMapCandidate();
}
async function nextMapCandidate(){
  if(!mapQueue.length){const standalone=mapStandalone;closeMapImport();if(!standalone){renderSettings();scheduleDraftCheck();}return;}
  const file=mapQueue.shift(),version=++mapRevision;mapReview=null;mapCandidate=null;mapRules=[];
  $('mapReviewed').checked=false;$('applyMapImport').disabled=true;$('mapAdvanced').open=false;
  try{
    if(file.size>8000000)throw Error(t('semantic.source_size'));
    const url=file.map_data||await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result);r.onerror=()=>reject(Error(t('error.image')));r.readAsDataURL(file);});
    if(version!==mapRevision||!mapDialog.open)return;
    mapCandidate={name:file.name,map_data:url};
    const existing=mapTarget&&draft.floors.find(f=>f.id===mapTarget),old=file.semantics||{},options=old.options||{};
    let k=1;while(draft.floors.some(f=>f.id===`sheet-${k}`))k++;
    $('mapFloorId').value=existing?.id||`sheet-${k}`;$('mapFloorName').value=existing?.name||file.name.replace(/\.[^.]+$/,'');
    $('mapScale').value=existing?existing.resolution/(old.factor||1):.1;mapScaleAssumed=existing?.semantics?!!existing.semantics.scale_assumed:true;
    $('mapProfile').value=options.profile||'auto';$('mapWall').value=options.wall_threshold??100;$('mapFree').value=options.free_threshold??240;
    $('mapMaxSide').value=options.max_side||512;$('mapInvert').checked=options.invert||false;mapRules=clone(options.rules||[]);
    renderMapRules();await computeMapReview();
  }catch(e){if(version===mapRevision){$('mapFileName').textContent=file.name;$('mapWarnings').textContent=e.message;}}
}
function mapRequest(){return {map_data:mapCandidate.map_data,source_resolution:Number($('mapScale').value),settings:clone(draft.settings),options:{profile:$('mapProfile').value,wall_threshold:Number($('mapWall').value),free_threshold:Number($('mapFree').value),max_side:Number($('mapMaxSide').value),invert:$('mapInvert').checked,rules:clone(mapRules)}};}
async function computeMapReview(){
  if(!mapCandidate||!mapDialog.open)return;
  const version=++mapRevision;mapReview=null;mapReading=true;$('applyMapImport').disabled=true;$('mapReviewed').checked=false;
  $('mapWarnings').textContent=t('semantic.analyzing');$('mapReviewState').textContent=t('semantic.analyzing');$('mapSimpleSummary').textContent='';
  try{const v=await api('/api/editor/map-review',mapRequest());if(version!==mapRevision||!mapDialog.open)return;mapReview=v;paintReview();renderMapReview();}
  catch(e){if(version===mapRevision){$('mapWarnings').textContent=e.message;$('mapReviewState').textContent=e.message;$('mapReviewState').classList.add('error');}}
  finally{if(version===mapRevision){mapReading=false;$('applyMapImport').disabled=mapApplying||!mapReview||mapReview.stats.walkable===0;}}
}
function drawReviewImage(id,url){
  const canvas=$(id),version=mapRevision;const image=new Image();image.onload=()=>{if(version!==mapRevision)return;
    canvas.width=image.width;canvas.height=image.height;const g=canvas.getContext('2d');g.imageSmoothingEnabled=false;g.clearRect(0,0,canvas.width,canvas.height);g.drawImage(image,0,0);
    if(id==='sourceCanvas')updateColorHighlight();
  };image.src=url;
}
function paintReview(){if(!mapReview)return;drawReviewImage('sourceCanvas',mapReview.source_preview);drawReviewImage('reviewCanvas',mapReview[$('reviewLayer').value]);drawColorHistogram();}
function renderMapReview(){
  $('mapFileName').textContent=mapCandidate?`${mapCandidate.name}${mapQueue.length?' · '+t('semantic.remaining',{count:mapQueue.length}):''}`:'';
  if(!mapReview)return;const r=mapReview,s=r.stats;
  $('mapSimpleSummary').textContent=t(mapScaleAssumed?'sheet.scale_assumed':'sheet.scale_set',{scale:fmt(r.resolution,3)});
  $('mapReviewState').textContent=s.walkable===0?t('sheet.map_blocked'):t('sheet.map_ready');$('mapReviewState').classList.toggle('error',s.walkable===0);
  $('mapStats').textContent=t('semantic.stats',{source:r.source_size.join(' × '),grid:`${r.width} × ${r.height}`,scale:fmt(r.resolution,3),free:fmt(s.walkable/s.cells*100),components:s.components});
  $('mapWarnings').replaceChildren();for(const code of r.warnings){const p=document.createElement('p');p.textContent=t('semantic.warn_'+code,{factor:r.factor});$('mapWarnings').append(p);}
  renderMapRules();drawColorHistogram();updateColorHighlight();
}
function renderMapRules(){
  $('mapRules').replaceChildren();for(const [i,r] of mapRules.entries()){
    const hit=mapReview?.analysis?.rule_hits?.find(h=>h.index===i);
    const row=document.createElement('div');row.className='map-rule';const label=document.createElement('span');label.textContent=`${r.color} ±${r.tolerance} → ${t('semantic.'+r.kind)}`+(hit?` · ${t('semantic.rule_hits',{matched:hit.matched,applied:hit.applied})}`:'');
    const b=document.createElement('button');b.textContent=t('common.remove');b.onclick=()=>{mapRules.splice(i,1);renderMapRules();invalidateMap();};row.append(label,b);$('mapRules').append(row);
  }
}
$('addMapRule').onclick=()=>{if(mapRules.length>=12){mapError('rule_limit');return;}if(!$('mapTolerance').reportValidity())return;
  mapRules.push({color:$('mapColor').value,kind:$('mapRuleKind').value,tolerance:Number($('mapTolerance').value)});renderMapRules();invalidateMap();};
$('pickMapColor').onclick=()=>{mapPicking=true;$('mapWarnings').textContent=t('semantic.pick_hint');};
$('mapColor').oninput=updateColorSelection;
$('mapTolerance').oninput=()=>{drawColorHistogram();updateColorHighlight();};

function colorChannels(hex){return [1,3,5].map(i=>parseInt(hex.slice(i,i+2),16));}
function nearestHistogramBin(hex){
  if(!mapReview?.analysis?.histogram)return mapHistogramGray;
  const rgb=colorChannels(hex);let best=mapHistogramGray,score=Infinity;
  for(const b of mapReview.analysis.histogram){if(!b.count)continue;const c=colorChannels(b.color),d=c.reduce((sum,v,i)=>sum+(v-rgb[i])**2,0);if(d<score){score=d;best=b.gray;}}
  return best;
}
function updateColorSelection(){mapHistogramGray=nearestHistogramBin($('mapColor').value);drawColorHistogram();updateColorHighlight();}
function selectHistogramRange(a,b){
  if(!mapReview)return;const low=Math.min(a,b),high=Math.max(a,b),center=Math.round((low+high)/2);
  const occupied=mapReview.analysis.histogram.filter(v=>v.count).sort((x,y)=>Math.abs(x.gray-center)-Math.abs(y.gray-center))[0];
  if(!occupied)return;mapHistogramGray=occupied.gray;$('mapColor').value=occupied.color;$('mapTolerance').value=Math.min(64,Math.ceil((high-low)/2));
  drawColorHistogram();updateColorHighlight();
}
function histogramGrayAt(e){const r=$('colorHistogram').getBoundingClientRect();return Math.max(0,Math.min(255,Math.floor((e.clientX-r.left)/r.width*256)));}
$('colorHistogram').onpointerdown=e=>{mapHistogramStart=histogramGrayAt(e);e.currentTarget.setPointerCapture(e.pointerId);selectHistogramRange(mapHistogramStart,mapHistogramStart);};
$('colorHistogram').onpointermove=e=>{if(mapHistogramStart!==null)selectHistogramRange(mapHistogramStart,histogramGrayAt(e));};
$('colorHistogram').onpointerup=e=>{if(mapHistogramStart!==null)selectHistogramRange(mapHistogramStart,histogramGrayAt(e));mapHistogramStart=null;};
$('colorHistogram').onkeydown=e=>{if(!['ArrowLeft','ArrowRight'].includes(e.key))return;e.preventDefault();const step=e.key==='ArrowLeft'?-1:1;if(e.shiftKey)$('mapTolerance').value=Math.max(0,Math.min(64,Number($('mapTolerance').value)+step));else mapHistogramGray=Math.max(0,Math.min(255,mapHistogramGray+step));const occupied=mapReview?.analysis?.histogram.filter(v=>v.count).sort((a,b)=>Math.abs(a.gray-mapHistogramGray)-Math.abs(b.gray-mapHistogramGray))[0];if(occupied){mapHistogramGray=occupied.gray;$('mapColor').value=occupied.color;}drawColorHistogram();updateColorHighlight();};
function drawColorHistogram(){
  const canvas=$('colorHistogram');if(!mapReview||!canvas)return;const g=canvas.getContext('2d'),hist=mapReview.analysis.histogram,max=Math.max(1,...hist.map(v=>v.count));
  g.clearRect(0,0,canvas.width,canvas.height);g.fillStyle='#f7fafb';g.fillRect(0,0,canvas.width,canvas.height);
  const top=12,bottom=28,h=canvas.height-top-bottom,w=canvas.width/256;
  for(const b of hist){if(!b.count)continue;const bh=Math.max(2,Math.log1p(b.count)/Math.log1p(max)*h);g.fillStyle=b.color;g.fillRect(b.gray*w,top+h-bh,Math.ceil(w),bh);}
  const tolerance=Number($('mapTolerance').value)||0,lo=Math.max(0,mapHistogramGray-tolerance),hi=Math.min(255,mapHistogramGray+tolerance);
  g.fillStyle='#087f7526';g.fillRect(lo*w,top,(hi-lo+1)*w,h);g.strokeStyle='#087f75';g.lineWidth=2;g.strokeRect(lo*w+1,top+1,Math.max(2,(hi-lo+1)*w-2),h-2);
  g.fillStyle='#4f6573';g.font='12px sans-serif';for(const x of [0,64,128,192,255])g.fillText(String(x),Math.min(canvas.width-22,x*w),canvas.height-8);
  const count=hist.slice(lo,hi+1).reduce((sum,v)=>sum+v.count,0);$('histogramSelection').textContent=t('semantic.histogram_selection',{low:lo,high:hi,color:$('mapColor').value,count});
}
function updateColorHighlight(){
  const source=$('sourceCanvas'),overlay=$('sourceHighlight');if(!source.width||!source.height)return;
  overlay.width=source.width;overlay.height=source.height;const src=source.getContext('2d').getImageData(0,0,source.width,source.height),ctx=overlay.getContext('2d'),out=ctx.createImageData(source.width,source.height),rgb=colorChannels($('mapColor').value),tol=Number($('mapTolerance').value)||0;let count=0;
  for(let i=0;i<src.data.length;i+=4){if(src.data[i+3]&&Math.max(Math.abs(src.data[i]-rgb[0]),Math.abs(src.data[i+1]-rgb[1]),Math.abs(src.data[i+2]-rgb[2]))<=tol){out.data.set([255,39,110,210],i);count++;}}
  ctx.putImageData(out,0,0);overlay.classList.toggle('active',count>0);
}
$('sourceCanvas').onclick=async e=>{
  if(!mapPicking||!mapReview||!mapCandidate)return;
  const box=e.currentTarget.getBoundingClientRect(),version=mapRevision;
  const ratio=Math.min(box.width/e.currentTarget.width,box.height/e.currentTarget.height),width=e.currentTarget.width*ratio,height=e.currentTarget.height*ratio;
  const rect={left:box.left+(box.width-width)/2,top:box.top+(box.height-height)/2,width,height};
  if(e.clientX<rect.left||e.clientX>rect.left+width||e.clientY<rect.top||e.clientY>rect.top+height)return;
  const sample={x:Math.min(mapReview.source_size[0]-1,Math.max(0,Math.floor((e.clientX-rect.left)/rect.width*mapReview.source_size[0]))),y:Math.min(mapReview.source_size[1]-1,Math.max(0,Math.floor((e.clientY-rect.top)/rect.height*mapReview.source_size[1])))};
  try{const v=await api('/api/editor/map-review',{map_data:mapCandidate.map_data,sample});if(version!==mapRevision)return;$('mapColor').value=v.color;mapPicking=false;updateColorSelection();renderMapReview();}
  catch(e){$('mapWarnings').textContent=e.message;}
};
$('applyMapImport').onclick=async()=>{
  if(mapApplying||!mapDialog.open||!mapReview||mapReading||mapReview.stats.walkable===0||draft!==mapSession||(!mapStandalone&&!$('settingsDialog').open))return;
  // The button itself is explicit confirmation. Stage changes until validation
  // finishes; a second click or closing the dialog cannot add the same map twice.
  for(const id of ['mapFloorId','mapFloorName','mapScale'])if(!$(id).reportValidity())return;
  const id=$('mapFloorId').value.trim(),name=$('mapFloorName').value.trim();
  if(!id||!name||draft.floors.some(f=>f.id===id&&f.id!==mapTarget)){mapError('id_collision');return;}
  if(!mapTarget&&draft.floors.length>=4){mapError('floor_limit');return;}
  const r=mapReview,staged=clone(draft),existing=mapTarget&&staged.floors.find(f=>f.id===mapTarget);
  const floor={id,name,starter:false,resolution:r.resolution,map_data:r.map_data,semantics:{version:1,source_data:mapCandidate.map_data,source_name:mapCandidate.name,scale_assumed:mapScaleAssumed,source_size:r.source_size,source_sha256:r.source_sha256,factor:r.factor,options:r.options,source_preview:r.source_preview,class_preview:r.class_preview}};
  if(existing){
    const geometryChanged=existing.semantics?.source_sha256!==r.source_sha256||existing.semantics?.factor!==r.factor;
    if(geometryChanged){const affected=staged.nodes.some(n=>n.floor===mapTarget)||staged.portals.some(p=>['a','b'].some(side=>p[side].floor===mapTarget&&p[side].x!=null));if(affected&&!confirm(t('semantic.replace_confirm')))return;staged.nodes=staged.nodes.filter(n=>n.floor!==mapTarget);}
    for(const n of staged.nodes)if(n.floor===mapTarget)n.floor=id;
    for(const p of staged.portals)for(const side of ['a','b'])if(p[side].floor===mapTarget)p[side]={floor:id,x:null,y:null};
    Object.assign(existing,floor);delete existing.unknown_value;
  }else staged.floors.push(floor);
  const token=++mapApplySerial,version=mapRevision,session=mapSession;
  mapApplying=true;$('applyMapImport').disabled=true;$('applyMapImport').setAttribute('aria-busy','true');
  try{
    if(mapStandalone)await api('/api/editor/preflight',staged);
    if(token!==mapApplySerial||version!==mapRevision||draft!==session||!mapDialog.open)return;
    draft=staged;mapSession=draft;draftPreflight=null;mapTarget=null;$('mapReviewed').checked=true;
    if(mapStandalone){
      if(typeof cancelPortalPick==='function')cancelPortalPick();
      commit(()=>{scene=clone(staged);floorId=id;selection.clear();structure=false;},t('sheet.added'));
      renderTabs();if(typeof announce==='function')announce(t('sheet.map_added',{name}));
    }
    await nextMapCandidate();
  }catch(e){if(token===mapApplySerial){$('mapReviewState').textContent=e.message;$('mapReviewState').classList.add('error');}}
  finally{if(token===mapApplySerial){mapApplying=false;$('applyMapImport').disabled=!mapReview||mapReading||mapReview.stats.walkable===0;}$('applyMapImport').setAttribute('aria-busy',String(mapApplying));}
};

function renameFloor(oldId,newId){
  newId=newId.trim();if(!newId||draft.floors.some(f=>f.id===newId&&f.id!==oldId))return false;
  draft.floors.find(f=>f.id===oldId).id=newId;
  for(const n of draft.nodes)if(n.floor===oldId)n.floor=newId;
  for(const p of draft.portals)for(const side of ['a','b'])if(p[side].floor===oldId)p[side].floor=newId;
  return true;
}
function enhanceMapSettings(){
  for(const card of $('floorSettings').children){
    const f=draft.floors.find(f=>f.id===card.dataset.floor),head=card.querySelector('.floor-heading');
    const id=labelInput(head,'semantic.floor_id',f.id,v=>{if(renameFloor(f.id,v)){renderSettings();scheduleDraftCheck();}else{id.setCustomValidity(t('semantic.id_collision'));id.reportValidity();}});id.className='floor-id-input';
    if(f.semantics){
      const b=document.createElement('button');b.className='editSemantics';b.textContent=t('semantic.edit');
      b.onclick=()=>beginMapImport([{name:f.semantics.source_name,map_data:f.semantics.source_data,semantics:f.semantics}],f.id);head.append(b);
    }
  }
  if(!$('referenceMapControls')){
    const box=document.createElement('div');box.id='referenceMapControls';box.className='reference-map-controls';
    box.innerHTML='<select id="referenceMapSelect" data-i18n-aria-label="semantic.references"></select><button id="loadReferenceMap" data-i18n="semantic.load_reference"></button>';
    $('addFloorBtn').after(box);
    api('/api/editor/reference-maps').then(rows=>{for(const row of rows){const o=document.createElement('option');o.value=row.id;o.textContent=row.filename;$('referenceMapSelect').append(o);}}).catch(e=>status(e.message,true));
    $('loadReferenceMap').onclick=async()=>{if(uploadInProgress||draft.floors.length>=4){$('draftIssues').textContent=t('error.max_floors');return;}
      try{const v=await api('/api/editor/reference-maps/'+encodeURIComponent($('referenceMapSelect').value));await beginMapImport([{name:v.filename,map_data:v.map_data}]);}catch(e){$('draftIssues').textContent=e.message;}
    };
  }
  I18n.apply($('referenceMapControls'));
}
function drawFloorRaster(ctx,f,fallback){
  const semantic=scene.floors.find(x=>x.id===f.id)?.semantics,kind=$('mapLayer').value;
  const url=semantic&&(kind==='original'?semantic.source_preview:kind==='classes'?semantic.class_preview:null);
  if(!url){if(fallback)ctx.drawImage(fallback,0,0);return;}
  if(!rasterCache.has(url)){const im=new Image();im.onload=()=>draw();im.src=url;rasterCache.set(url,im);if(rasterCache.size>16)rasterCache.delete(rasterCache.keys().next().value);}
  const im=rasterCache.get(url);if(!im?.complete||!im.naturalWidth){if(fallback)ctx.drawImage(fallback,0,0);return;}
  const width=kind==='original'?semantic.source_size[0]/semantic.factor:f.width,height=kind==='original'?semantic.source_size[1]/semantic.factor:f.height;
  ctx.drawImage(im,0,0,width,height);
}
document.addEventListener('languagechange',()=>{if(mapDialog.open){$('mapLanguage').value=I18n.language;renderMapRules();renderMapReview();}});
