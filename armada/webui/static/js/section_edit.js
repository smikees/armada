let mcSecEdit=false;
const MC_GREY='color-mix(in srgb,var(--color-text) 7%,transparent)';
// app-native confirm modal (defined here too so it's available on every page the sections nav renders)
// the shared app-native dialog is loaded for every page
function _mcSecIdx(el){return parseInt(el.closest('.mc-tab-user').dataset.i,10);}
function _mcSecReindex(){document.querySelectorAll('.mc-tab-user').forEach(function(t,k){t.dataset.i=k;});}
function mcSectionEdit(el){mcSecEdit=!mcSecEdit;
  el.style.color=mcSecEdit?'var(--color-accent)':'var(--text-muted)';
  // Background stays put through the toggle — the button tinting itself made it read as a second,
  // differently-styled control rather than the same one in a different state. The glyph is what
  // changes: a struck-through pencil, which is the thing the next click will do.
  el.style.background=MC_GREY;
  el.title=mcSecEdit?'Done editing sections':'Edit sections';
  const on=el.querySelector('.mc-sec-on'),off=el.querySelector('.mc-sec-off');
  if(on)on.style.display=mcSecEdit?'none':'inline-flex';
  if(off)off.style.display=mcSecEdit?'inline-flex':'none';
  const hint=document.getElementById('mc-sechint');if(hint)hint.style.display=mcSecEdit?'inline':'none';
  document.querySelectorAll('.mc-tab-user').forEach(t=>{
    t.setAttribute('draggable',mcSecEdit?'true':'false');t.style.cursor=mcSecEdit?'grab':'';
    const g=t.querySelector('.mc-secgrip');if(g)g.style.display=mcSecEdit?'inline-flex':'none';
    const x=t.querySelector('.mc-secx');if(x)x.style.display=mcSecEdit?'inline-flex':'none';});}
function mcSecClick(e,el){e.stopPropagation();if(mcSecEdit)return;location.href='/section/'+_mcSecIdx(el);}
function mcSecRename(e,el){if(!mcSecEdit)return;e.stopPropagation();e.preventDefault();mcSecInlineRename(el);}
function mcSecInlineRename(el){if(el.dataset.editing)return;el.dataset.editing='1';var i=_mcSecIdx(el);
  var cur=el.textContent;var inp=document.createElement('input');inp.value=cur;
  inp.style.cssText='font:inherit;font-size:inherit;font-weight:inherit;color:inherit;background:var(--color-bg);border:1px solid var(--color-accent);border-radius:4px;padding:1px 5px;width:10ch;box-sizing:border-box';
  el.textContent='';el.appendChild(inp);inp.focus();inp.select();var done=false;
  function fin(save){if(done)return;done=true;delete el.dataset.editing;var t=inp.value.trim();
    if(!save||!t||t===cur){el.textContent=cur;return;}
    fetch('/api/rename-section',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i,name:t})})
      .then(function(r){return r.json();}).then(function(r){if(r.ok){el.textContent=t;}else{el.textContent=cur;mcAlert('error: '+(r.error||'failed'));}}).catch(function(){el.textContent=cur;});}
  inp.addEventListener('keydown',function(ev){ev.stopPropagation();if(ev.key==='Enter'){ev.preventDefault();fin(true);}else if(ev.key==='Escape'){ev.preventDefault();fin(false);}});
  inp.addEventListener('blur',function(){fin(true);});
  inp.addEventListener('click',function(ev){ev.stopPropagation();});
  inp.addEventListener('dblclick',function(ev){ev.stopPropagation();});}
async function mcSecDelete(e,el){e.stopPropagation();
  var node=el.closest('.mc-tab-user');var nm=node?node.querySelector('.mc-secname').textContent:'';var i=_mcSecIdx(el);
  var ok=await mcConfirm({title:'Remove section?',body:'Remove \u201c'+nm+'\u201d from the menu. This cannot be undone.',confirm:'Remove',danger:true});
  if(!ok)return;
  try{var r=await(await fetch('/api/delete-section',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index:i})})).json();
    if(r.ok){node.remove();_mcSecReindex();}else{mcAlert('error: '+(r.error||'failed'));}}catch(err){mcAlert('error: '+err);}}
(function(){var tabs=document.querySelectorAll('.mc-tab-user');if(!tabs.length)return;var box=tabs[0].parentNode;var drag=null;
 tabs.forEach(function(t){if(t._dnd)return;t._dnd=1;
  t.addEventListener('dragstart',function(e){if(!mcSecEdit){e.preventDefault();return;}drag=t;e.dataTransfer.effectAllowed='move';t.style.opacity='.5';});
  t.addEventListener('dragend',function(){if(drag)drag.style.opacity='';drag=null;});
  t.addEventListener('dragover',function(e){if(!mcSecEdit||!drag||drag===t)return;e.preventDefault();
    var r=t.getBoundingClientRect();var after=(e.clientX-r.left)>r.width/2;box.insertBefore(drag,after?t.nextSibling:t);});
  t.addEventListener('drop',function(e){if(!mcSecEdit)return;e.preventDefault();
    var order=[].slice.call(box.querySelectorAll('.mc-tab-user')).map(function(x){return parseInt(x.dataset.i,10);});
    fetch('/api/reorder-sections',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({order:order})})
      .then(function(r){return r.json();}).then(function(r){if(r.ok){_mcSecReindex();}else{mcAlert('error: '+(r.error||'failed'));}}).catch(function(err){mcAlert('error: '+err);});});});
})();
