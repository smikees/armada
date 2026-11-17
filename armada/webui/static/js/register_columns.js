// Register geometry is a local display preference, shared with its promoted section.
(function(){
  'use strict';
  const realm=document.querySelector('meta[name="armada-realm"]')?.content||'';
  const key='armada-register-columns:'+realm,minimum=[140,110,54,48,100,74,120],maximum=800;
  document.querySelectorAll('.mc-register-table').forEach(table=>{
    if(table.dataset.resizable)return;table.dataset.resizable='true';
    const heads=[...table.tHead.rows[0].cells],cols=[...table.querySelectorAll('col')];
    const defaults=heads.map((h,i)=>Math.min(maximum,Math.max(minimum[i],Math.round(h.getBoundingClientRect().width))));
    let widths=[...defaults],drag=null;
    function apply(){
      table.style.tableLayout='fixed';table.style.width=widths.reduce((a,b)=>a+b,0)+'px';
      cols.forEach((col,i)=>{col.style.width=widths[i]+'px';
        heads[i].querySelector('button')?.setAttribute('aria-valuenow',String(widths[i]));});
    }
    function save(){try{localStorage.setItem(key,JSON.stringify(widths));}catch(_){}}
    function change(i,value){widths[i]=Math.max(minimum[i],Math.min(maximum,Math.round(value)));apply();}
    function finish(cancel){if(!drag)return;const old=drag;drag=null;
      if(cancel){widths=old.widths;apply();}else save();
      old.handle.releasePointerCapture?.(old.pointer);
      document.body.style.userSelect=old.selection;old.handle.classList.remove('is-resizing');}
    heads.forEach((head,i)=>{
      const handle=document.createElement('button');handle.type='button';handle.className='mc-column-resize';
      handle.setAttribute('role','separator');handle.setAttribute('aria-orientation','vertical');
      handle.setAttribute('aria-label','Resize '+head.textContent.trim()+' column');
      handle.setAttribute('aria-valuemin',String(minimum[i]));handle.setAttribute('aria-valuemax',String(maximum));
      handle.setAttribute('aria-valuenow',String(widths[i]));
      handle.title='Drag or use arrow keys to resize. Double-click or press Home to reset this column.';
      head.append(handle);
      handle.addEventListener('pointerdown',event=>{
        if(event.button!==0)return;event.preventDefault();event.stopPropagation();
        if(drag)finish(true);
        // First drag preserves the actual automatic layout, including a resized widget.
        if(!table.style.tableLayout)widths=heads.map((h,n)=>Math.max(minimum[n],Math.round(h.getBoundingClientRect().width)));
        drag={i,x:event.clientX,widths:[...widths],handle,pointer:event.pointerId,selection:document.body.style.userSelect};
        handle.setPointerCapture(event.pointerId);handle.classList.add('is-resizing');document.body.style.userSelect='none';
      });
      handle.addEventListener('pointermove',event=>{if(drag?.handle===handle)change(i,drag.widths[i]+event.clientX-drag.x);});
      handle.addEventListener('pointerup',()=>finish(false));
      handle.addEventListener('pointercancel',()=>finish(true));
      handle.addEventListener('lostpointercapture',()=>finish(true));
      handle.addEventListener('click',event=>event.stopPropagation());
      handle.addEventListener('dblclick',event=>{event.preventDefault();change(i,defaults[i]);save();});
      handle.addEventListener('keydown',event=>{
        if(!['ArrowLeft','ArrowRight','Home','Escape'].includes(event.key))return;
        event.preventDefault();event.stopPropagation();
        if(event.key==='Escape'){finish(true);return;}
        change(i,event.key==='Home'?defaults[i]:widths[i]+(event.key==='ArrowRight'?1:-1)*(event.shiftKey?1:10));save();
      });
    });
    try{const saved=JSON.parse(localStorage.getItem(key));
      if(Array.isArray(saved)&&saved.length===heads.length&&saved.every(Number.isFinite)){
        widths=saved.map((v,i)=>Math.max(minimum[i],Math.min(maximum,Math.round(v))));apply();}
    }catch(_){}
    window.addEventListener('pagehide',()=>finish(true));
  });
})();
