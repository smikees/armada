const MC_RU=10, MC_GAP=14, MC_DEFH=440;                 // grid row unit / gap / default widget height
function mcH2Rows(h){return Math.max(8,Math.round((h+MC_GAP)/(MC_RU+MC_GAP)));}
function mcApplyHeight(cell){const id=cell.dataset.id;
  const h=(window.MC_DASH&&MC_DASH.heights&&MC_DASH.heights[id])||MC_DEFH;
  cell.style.gridRow='span '+mcH2Rows(h);}
function mcSaveLayout(){mcDashSave();}   // order/spans/heights collected + persisted to dashboard.json
function mcApplyLayout(){const g=document.getElementById('mc-grid');if(!g)return;
  const order=(window.MC_DASH&&MC_DASH.order)||[];const spans=(window.MC_DASH&&MC_DASH.spans)||{};
  const byId={};[...g.children].forEach(c=>{if(c.classList&&c.classList.contains('mc-w'))byId[c.dataset.id]=c;});
  // spans + heights (covers widgets not in a saved order too)
  Object.keys(byId).forEach(id=>{if(spans[id]){const s=Math.max(4,Math.min(20,spans[id]));byId[id].dataset.span=s;byId[id].style.gridColumn='span '+s;}mcApplyHeight(byId[id]);});  // enforce 20% min
  order.forEach(id=>{const c=byId[id];if(c)g.appendChild(c);});}
let mcDrag=null;
function mcSpanSet(cell,span){span=Math.max(4,Math.min(20,span));cell.dataset.span=span;cell.style.gridColumn='span '+span;mcSaveLayout();}  // min 4 = 20%
function mcDragLock(on){const g=mcGrid();if(!g)return;[...g.querySelectorAll('iframe')].forEach(f=>f.style.pointerEvents=on?'none':'');}
function mcSetupCell(cell){
  if(cell._mcSetup)return;cell._mcSetup=true;
  const grip=cell.querySelector('.mc-grip');
  if(grip){
    // an inline <svg> isn't reliably draggable — wrap it in a real HTML handle
    let handle=grip.closest('.mc-draghandle');
    if(!handle){handle=document.createElement('span');handle.className='mc-draghandle';
      handle.style.cssText='display:inline-flex;align-items:center;cursor:grab;flex:none';
      grip.parentNode.insertBefore(handle,grip);handle.appendChild(grip);}
    handle.setAttribute('draggable','true');handle.title='Drag to reorder';
    handle.addEventListener('dragstart',e=>{mcDrag=cell;e.dataTransfer.effectAllowed='move';
      try{e.dataTransfer.setData('text/plain','');}catch(x){}cell.style.opacity='.5';mcDragLock(true);});
    handle.addEventListener('dragend',()=>{cell.style.opacity='';mcDrag=null;mcDragLock(false);});}
  cell.addEventListener('dragover',e=>{if(mcDrag){e.preventDefault();e.dataTransfer.dropEffect='move';}});
  cell.addEventListener('drop',e=>{if(!mcDrag||mcDrag===cell){mcDragLock(false);return;}e.preventDefault();const g=mcGrid();
    const r=cell.getBoundingClientRect();const after=(e.clientX-r.left)>r.width/2;
    g.insertBefore(mcDrag,after?cell.nextSibling:cell);mcSaveLayout();mcDragLock(false);});
  // width % is set by dragging the corner handle (below) \u2014 no separate header control
  // resize handle (bottom-right) — drag to set this widget's height; others reflow
  if(cell.style.position!=='relative')cell.style.position='relative';
  mcApplyHeight(cell);
  if(!cell.querySelector('.mc-rz')){
    const rz=document.createElement('div');rz.className='mc-rz';rz.title='Drag to resize (width + height)';
    rz.innerHTML='<svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M11 4 4 11M11 8l-3 3"></path></svg>';
    cell.appendChild(rz);
    rz.addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();
      const sx=e.clientX,sy=e.clientY,r=cell.getBoundingClientRect(),sw=r.width,sh=r.height;
      const g=mcGrid();const colW=g?(g.clientWidth-19*MC_GAP)/20:sw;mcDragLock(true);   // 20 cols = 5% steps
      try{rz.setPointerCapture(e.pointerId);}catch(x){}
      function mv(ev){
        const h=Math.max(160,sh+(ev.clientY-sy));cell.style.gridRow='span '+mcH2Rows(h);
        const w=Math.max(1,sw+(ev.clientX-sx));const span=Math.max(4,Math.min(20,Math.round((w+MC_GAP)/(colW+MC_GAP))));
        if((+cell.dataset.span||10)!==span)mcSpanSet(cell,span);}
      function up(){document.removeEventListener('pointermove',mv);document.removeEventListener('pointerup',up);mcDragLock(false);
        const h=Math.max(160,Math.round(cell.getBoundingClientRect().height));
        window.MC_DASH.heights=window.MC_DASH.heights||{};MC_DASH.heights[cell.dataset.id]=h;mcDashSave();}
      document.addEventListener('pointermove',mv);document.addEventListener('pointerup',up);});}}
function mcInitLayout(){const g=mcGrid();if(!g)return;[...g.children].filter(c=>c.classList.contains('mc-w')).forEach(mcSetupCell);}
mcApplyLayout();mcInitLayout();
