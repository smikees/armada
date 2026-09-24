function mcThreadMenu(e,btn){e.stopPropagation();const m=btn.parentNode.querySelector('.mc-thmenu');const open=m.style.display==='block';
  document.querySelectorAll('.mc-thmenu').forEach(x=>x.style.display='none');
  if(open){m.style.display='none';return;}
  const r=btn.getBoundingClientRect();m.style.position='fixed';m.style.top=(r.bottom+4)+'px';m.style.left=(r.right-176)+'px';m.style.right='auto';m.style.display='block';}
document.addEventListener('click',()=>document.querySelectorAll('.mc-thmenu').forEach(x=>x.style.display='none'));
async function mcThreadAction(e,agent,slug,action){e.stopPropagation();
  try{const r=await(await fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,thread:slug,action})})).json();
    if(r.ok){location.reload();}else{mcAlert('error: '+(r.error||'failed'));}}catch(err){mcAlert('error: '+err);}}
function mcThreadRename(e,agent,slug,current){e.stopPropagation();document.querySelectorAll('.mc-thmenu').forEach(x=>x.style.display='none');
  document.getElementById('thren-agent').value=agent;document.getElementById('thren-slug').value=slug;
  document.getElementById('thren-title').value=current;document.getElementById('thren-msg').textContent='';
  document.getElementById('mc-thren-modal').style.display='flex';setTimeout(()=>{const t=document.getElementById('thren-title');t.focus();t.select();},50);}
function mcThrenClose(){document.getElementById('mc-thren-modal').style.display='none';}
// delete a thread (permanent) — app-native confirm modal with an option to also wipe artifacts
function mcThreadDelete(e,agent,slug,title){e.stopPropagation();
  document.querySelectorAll('.mc-thmenu').forEach(x=>x.style.display='none');
  var ov=document.createElement('div');
  ov.style.cssText='position:fixed;inset:0;z-index:400;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center';
  ov.innerHTML='<div class="mc-frame" style="background:var(--color-bg);border-radius:var(--r);padding:18px;width:min(440px,92vw);box-shadow:var(--shadow-lg)">'
    +'<div class="mc-h-card" style="margin-bottom:6px">Delete thread?</div>'
    +'<div style="font-size:12.5px;color:var(--text-dim);margin-bottom:12px">Delete “'+String(title==null?'':title).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];})+'”? This permanently removes its messages and cannot be undone.</div>'
    +'<label style="display:flex;align-items:center;gap:8px;font-size:12.5px;cursor:pointer;margin-bottom:14px">'
    +'<input type="checkbox" id="mc-delarts" style="margin:0;flex:none"><span>Also delete this thread’s artifacts from disk</span></label>'
    +'<div style="display:flex;gap:8px;justify-content:flex-end">'
    +'<button class="btn btn-secondary" data-x style="font-size:12.5px;padding:6px 12px">Cancel</button>'
    +'<button class="btn btn-danger" data-ok>Delete</button></div></div>';
  document.body.appendChild(ov);
  function done(){ov.remove();document.removeEventListener("keydown",esc);}
  function esc(ev){if(ev.key==="Escape")done();}
  ov.addEventListener("mousedown",function(ev){if(ev.target===ov)done();});
  ov.querySelector("[data-x]").onclick=done;
  document.addEventListener("keydown",esc);
  ov.querySelector("[data-ok]").onclick=function(){
    var del=!!document.getElementById("mc-delarts").checked;
    fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:agent,thread:slug,action:'delete',delete_artifacts:del})})
      .then(function(r){return r.json();}).then(function(r){if(r.ok){location.href='/agent/'+agent+'/threads';}else{done();mcAlert('error: '+(r.error||'failed'));}}).catch(function(err){done();mcAlert('error: '+err);});};}
// archived-threads modal
function mcArchOpen(){var m=document.getElementById('mc-tharch-modal');if(m)m.style.display='flex';}
function mcArchClose(){var m=document.getElementById('mc-tharch-modal');if(m)m.style.display='none';}
async function mcThrenSave(){const m=document.getElementById('thren-msg');const title=document.getElementById('thren-title').value.trim();
  if(!title){m.textContent='name required';return;}m.textContent='saving…';
  const p={agent:document.getElementById('thren-agent').value,thread:document.getElementById('thren-slug').value,action:'rename',title};
  try{const r=await(await fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
   if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
// double-click a thread name (left list or chat header) to rename it in place
var _mcThNav=null;
function mcThTitleClick(e,el,agent,slug){e.stopPropagation();clearTimeout(_mcThNav);
  _mcThNav=setTimeout(function(){location.href='/agent/'+agent+'/threads?thread='+encodeURIComponent(slug);},220);}
function mcThTitleDbl(e,el,agent,slug){e.stopPropagation();e.preventDefault();clearTimeout(_mcThNav);mcThreadInlineRename(el,agent,slug);}
function mcThreadInlineRename(el,agent,slug){if(el.dataset.editing)return;el.dataset.editing='1';
  var cur=el.textContent;var inp=document.createElement('input');inp.value=cur;
  inp.style.cssText='font:inherit;font-size:inherit;font-weight:inherit;color:inherit;background:var(--color-bg);border:1px solid var(--color-accent);border-radius:4px;padding:1px 5px;width:100%;box-sizing:border-box';
  el.textContent='';el.appendChild(inp);inp.focus();inp.select();var done=false;
  function fin(save){if(done)return;done=true;delete el.dataset.editing;var t=inp.value.trim();
    if(!save||!t||t===cur){el.textContent=cur;return;}
    fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:agent,thread:slug,action:'rename',title:t})})
      .then(function(r){return r.json();}).then(function(r){if(r.ok){location.reload();}else{el.textContent=cur;mcAlert('error: '+(r.error||'failed'));}}).catch(function(){el.textContent=cur;});}
  inp.addEventListener('keydown',function(ev){ev.stopPropagation();if(ev.key==='Enter'){ev.preventDefault();fin(true);}else if(ev.key==='Escape'){ev.preventDefault();fin(false);}});
  inp.addEventListener('blur',function(){fin(true);});
  inp.addEventListener('click',function(ev){ev.stopPropagation();});
  inp.addEventListener('dblclick',function(ev){ev.stopPropagation();});}
// keyboard shortcuts while a menu is open
document.addEventListener('keydown',(e)=>{const m=[...document.querySelectorAll('.mc-thmenu')].find(x=>x.style.display==='block');if(!m)return;
  const row=m.closest('.mc-thread');if(!row)return;const k=e.key.toLowerCase();const a=row.querySelectorAll('.mc-thmenu a');
  const hit=(t)=>{const x=[...a].find(el=>el.textContent.includes(t));if(x)x.click();};
  if(k==='p'&&row.dataset.slug!=='main'){a[0].click();}else if(k==='u'){hit('Mark as');}
  else if(k==='r'){hit('Rename');}else if(k==='a'&&row.dataset.slug!=='main'){hit('Archive');}});
// drag to reorder
(function(){const box=document.getElementById('mc-threadlist');if(!box||box._dnd)return;box._dnd=1;let drag=null;
 box.querySelectorAll('.mc-thread[draggable="true"]').forEach(row=>{
  row.addEventListener('dragstart',e=>{drag=row;e.dataTransfer.effectAllowed='move';row.style.opacity='.5';});
  row.addEventListener('dragend',()=>{if(drag)drag.style.opacity='';drag=null;});
  row.addEventListener('dragover',e=>{e.preventDefault();});
  row.addEventListener('drop',e=>{e.preventDefault();if(!drag||drag===row)return;
    const rows=[...box.querySelectorAll('.mc-thread')];const main=rows.find(r=>r.dataset.slug==='main');
    const tgt=row;box.insertBefore(drag,tgt);
    if(main&&box.firstElementChild!==main){box.insertBefore(main,box.firstElementChild);} // keep main on top
    const order=[...box.querySelectorAll('.mc-thread')].map(r=>r.dataset.slug).filter(s=>s!=='main');
    fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:box.dataset.agent,action:'reorder',order})});});});
})();
// mark the opened thread as read
(function(){const box=document.getElementById('mc-threadlist');if(!box||!box.dataset.selunread)return;
 fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:box.dataset.agent,thread:box.dataset.selected,action:'read'})});})();
