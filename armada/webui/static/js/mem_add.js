async function mcRefreshSystem(btn){var s=btn&&btn.querySelector('svg');
  if(s)s.style.animation='mc-spin .7s linear infinite';if(btn)btn.disabled=true;
  try{var r=await(await fetch('/api/refresh-system',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
    if(r&&r.ok){setTimeout(function(){location.reload();},450);}else{if(s)s.style.animation='';if(btn)btn.disabled=false;mcAlert((r&&r.error)||'refresh failed');}}
  catch(e){if(s)s.style.animation='';if(btn)btn.disabled=false;mcAlert('refresh failed');}}
function mcOpenAddMem(){var o=document.getElementById('mem-add-modal');if(!o)return;
  ['mem-edit','mem-title','mem-text','mem-msg'].forEach(function(id){var e=document.getElementById(id);if(e){if(id==='mem-msg')e.textContent='';else e.value='';}});
  o.style.display='flex';var t=document.getElementById('mem-title');if(t)setTimeout(function(){t.focus();},30);}
function mcCloseAddMem(){var o=document.getElementById('mem-add-modal');if(o)o.style.display='none';}
async function mcAddMemory(scope,agent){
  const t=document.getElementById('mem-title').value, x=document.getElementById('mem-text').value;
  const m=document.getElementById('mem-msg'); if(!mcReq(['mem-text'])){m.textContent='';return;} m.textContent='saving…';
  const name=document.getElementById('mem-edit').value;
  try{const r=await(await fetch('/api/add-memory',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({scope,agent,title:t,text:x,name})})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
function mcEditMem(scope,agent,stem,el){const card=el.closest('.mc-memcard');const body=card.querySelector('template').content.textContent;
  document.getElementById('mem-ed-title').value=card.dataset.title||'';
  document.getElementById('mem-ed-text').value=body;
  document.getElementById('mem-ed-scope').value=scope;document.getElementById('mem-ed-agent').value=agent;document.getElementById('mem-ed-name').value=stem;
  document.getElementById('mem-ed-msg').textContent='';
  document.getElementById('mem-edit-modal').style.display='flex';}
function mcCloseEditMem(){document.getElementById('mem-edit-modal').style.display='none';}
async function mcSaveEditMem(){const m=document.getElementById('mem-ed-msg');
  const x=document.getElementById('mem-ed-text').value;if(!x.trim()){m.textContent='memory cannot be empty';return;}m.textContent='saving…';
  const p={scope:document.getElementById('mem-ed-scope').value,agent:document.getElementById('mem-ed-agent').value,
    title:document.getElementById('mem-ed-title').value,text:x,name:document.getElementById('mem-ed-name').value};
  try{const r=await(await fetch('/api/add-memory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
function mcDelMem(scope,agent,name){document.getElementById('mem-del-scope').value=scope;
  document.getElementById('mem-del-agent').value=agent;document.getElementById('mem-del-name').value=name;
  document.getElementById('mem-del-msg').textContent='';document.getElementById('mem-del-modal').style.display='flex';}
function mcCloseDelMem(){document.getElementById('mem-del-modal').style.display='none';}
async function mcConfirmDelMem(){const m=document.getElementById('mem-del-msg');m.textContent='deleting…';
  const p={scope:document.getElementById('mem-del-scope').value,agent:document.getElementById('mem-del-agent').value,name:document.getElementById('mem-del-name').value};
  try{const r=await(await fetch('/api/delete-memory',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
function mcMemSearch(){const el=document.getElementById('mem-search');const q=(el.value||'').toLowerCase();
  const x=document.getElementById('mem-search-x');if(x)x.style.display=q?'block':'none';
  document.querySelectorAll('.mc-memcard').forEach(c=>{c.style.display=c.textContent.toLowerCase().includes(q)?'':'none';});}
function mcMemSearchClear(){const el=document.getElementById('mem-search');el.value='';mcMemSearch();el.focus();}
