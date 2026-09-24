function mcArtGV(id){var e=document.getElementById(id);return e?((e.dataset&&e.dataset.val!==undefined&&e.dataset.val!=='')?e.dataset.val:(e.value||'')):'';}
function mcArtApply(){
  var t=document.getElementById('art-table'); if(!t)return;
  var today=t.dataset.today||'';
  var fe=document.getElementById('art-from'), te=document.getElementById('art-to');
  [fe,te].forEach(function(e){if(e&&today&&e.value&&e.value>today)e.value=today;});   // no future dates
  var q=(mcArtGV('art-q')).toLowerCase();
  var ow=mcArtGV('art-owner'), ty=mcArtGV('art-type');
  var fr=fe?fe.value:'', to=te?te.value:'';
  var n=0, shown=0;
  [...t.tBodies[0].rows].forEach(function(r){
    if(!r.dataset||r.dataset.search===undefined)return;
    n++;
    var ok=(!q||r.dataset.search.indexOf(q)>=0)&&(!ow||r.dataset.owner===ow)&&(!ty||r.dataset.type===ty)
      &&(!fr||r.dataset.ymd>=fr)&&(!to||r.dataset.ymd<=to);
    r.style.display=ok?'':'none'; if(ok)shown++;
  });
  var c=document.getElementById('art-count'); if(c)c.textContent=shown+(shown===1?' artefact':' artefacts')+(shown!==n?(' of '+n):'');
  var active=q||ow||ty||fr||to;
  var cl=document.getElementById('art-clear'); if(cl)cl.style.display=active?'inline-flex':'none';
  var sx=document.getElementById('art-q-x'); if(sx)sx.style.display=q?'block':'none';
}
function mcArtSearchClear(){var e=document.getElementById('art-q');if(e){e.value='';mcArtApply();e.focus();}}
function mcArtClear(ddIds){['art-q','art-from','art-to'].forEach(function(id){var e=document.getElementById(id);if(e)e.value='';});
  if(window.mcFDClear){mcFDClear(ddIds||[],'mcArtApply');}else{mcArtApply();}}
function mcArtSort(th){
  var t=document.getElementById('art-table'); if(!t)return; var col=+th.dataset.col, type=th.dataset.sort||'text';
  var dir=(t.dataset.sortcol==col&&t.dataset.sortdir==='asc')?'desc':'asc'; t.dataset.sortcol=col; t.dataset.sortdir=dir;
  var rows=[...t.tBodies[0].rows].filter(function(r){return r.dataset&&r.dataset.search!==undefined;});
  function key(r){var c=r.cells[col];if(!c)return '';return (c.dataset&&c.dataset.v!==undefined)?c.dataset.v:c.textContent.trim().toLowerCase();}
  rows.sort(function(a,b){var va=key(a),vb=key(b);var cmp=(type==='date')?(va<vb?-1:va>vb?1:0):va.localeCompare(vb,undefined,{numeric:true});return dir==='desc'?-cmp:cmp;});
  var tb=t.tBodies[0]; rows.forEach(function(r){tb.appendChild(r);});
  [...t.tHead.rows[0].cells].forEach(function(h){var a=h.querySelector('.mc-arr');if(a){a.textContent=(h===th)?(dir==='asc'?' ↑':' ↓'):' ↕';a.style.opacity=(h===th)?'0.8':'0.4';}});
}
async function mcRevealFile(path){try{await fetch('/api/reveal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:path})});}catch(e){}}
// Clicking a row opens the artifact in whatever app owns the file type. Anything runnable
// (.exe/.bat/.ps1/…) is revealed in the folder instead — the server decides and tells us why.
async function mcOpenFile(path){
  try{const r=await(await fetch('/api/open-file',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:path})})).json();
    if(!r.ok&&!r.revealed){mcArtToast(r.error||'Could not open the file.');}
    else if(r.revealed&&r.error){mcArtToast(r.error);}}
  catch(e){mcArtToast('Could not open the file: '+e);}}
function mcArtToast(msg){
  let t=document.getElementById('mc-arttoast');
  if(!t){t=document.createElement('div');t.id='mc-arttoast';
    t.style.cssText='position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:500;'+
      'background:var(--color-bg);border:1px solid var(--color-divider);border-radius:var(--r);'+
      'box-shadow:var(--shadow-lg);padding:10px 14px;font-size:12.5px;max-width:520px';
    document.body.appendChild(t);}
  t.textContent=msg;t.style.display='block';
  clearTimeout(t._h);t._h=setTimeout(function(){t.style.display='none';},6000);}
// Adapter onto the app's shared dialog (confirm.js, loaded on every page) — one implementation
// rather than a private copy per feature.
function mcArtConfirm(title,detail,confirmLabel){
  return window.mcConfirm(title,detail,{ok:confirmLabel||'Delete',danger:true});
}
async function mcArtDelete(el,path){
  const name=(path||'').split(/[\\/]/).pop();
  if(!await mcArtConfirm('Delete '+name+'?',
      'This removes the file from disk and cannot be undone. The thread keeps its record of it.',
      'Delete file'))return;
  try{const r=await(await fetch('/api/delete-artefact',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:path})})).json();
    if(!r.ok){mcArtToast(r.error||'Could not delete the file.');return;}
    const tr=el.closest('tr');                       // drop the row; the file is gone
    if(tr){tr.style.transition='opacity .15s';tr.style.opacity='0';setTimeout(function(){tr.remove();},160);}
    mcArtToast('Deleted '+name);}
  catch(e){mcArtToast('Could not delete the file: '+e);}}
// One delegated handler. Paths come from data- attributes, never from inline JS strings.
document.addEventListener('click',function(e){
  if(!e.target.closest)return;
  const go=e.target.closest('.mc-art-go');
  if(go){e.stopPropagation();mcRevealFile(go.getAttribute('data-path'));return;}
  const del=e.target.closest('.mc-art-del');
  if(del){e.stopPropagation();mcArtDelete(del,del.getAttribute('data-path'));return;}
  const rv=e.target.closest('tr[data-open]');
  if(rv&&!e.target.closest('a')){mcOpenFile(rv.getAttribute('data-open'));}},false);
// Arriving with filters in the URL (e.g. from a thread's "Input artifacts" heading) pre-selects
// them, so the page opens showing what the link promised rather than everything.
(function(){
  var q; try{ q=new URLSearchParams(location.search); }catch(e){ return; }
  [['owner','art-owner'],['type','art-type']].forEach(function(pair){
    var val=q.get(pair[0]); if(!val)return;
    var dd=document.getElementById(pair[1]); if(!dd)return;
    // find the menu entry for this value so the pill shows its proper label
    // Match on data-val, not by searching the onclick text: the value is a JSON literal there now
    // (_base._J), and reading code back out of an attribute was always the fragile way round.
    var hit=[...dd.querySelectorAll('.mc-fdrop-menu a')].find(function(a){ return a.dataset.val===val; });
    if(!hit)return;
    dd.dataset.val=val;
    var l=dd.querySelector('.mc-fdrop-lbl'); if(l)l.textContent=hit.textContent.trim();
  });
})();
mcArtApply();
