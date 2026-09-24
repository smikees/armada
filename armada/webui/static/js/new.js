async function mcNewAgent(){
  const p={display:document.getElementById('n-name').value,leader:document.getElementById('n-leader').value,
    role:document.getElementById('n-role').value,
    coordinator:document.getElementById('n-coord').checked,autonomy:document.getElementById('n-autonomy').value,
    model:document.getElementById('n-model').value,effort:document.getElementById('n-effort').value,
    color:document.getElementById('n-color').value,
    mandate:document.getElementById('n-mandate').value,soul:document.getElementById('n-soul').value};
  const m=document.getElementById('n-msg'); if(!mcReq(['n-name'])){m.textContent='';return;} m.textContent='creating…';
  try{const r=await (await fetch('/api/new-agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){location.href='/agent/'+r.id;}else{m.textContent='error: '+(r.error||'failed');}
  }catch(e){m.textContent='error: '+e;}
}
async function mcNewJob(){
  const p={agent:document.getElementById('j-agent').value,name:document.getElementById('j-name').value,
    kind:document.getElementById('j-kind').value,thread:document.getElementById('j-thread').value,
    cron:document.getElementById('j-cron').value,prompt:document.getElementById('j-prompt').value};
  const m=document.getElementById('j-msg'); if(!mcReq(['j-name'])){m.textContent='';return;} m.textContent='creating…';
  try{const r=await (await fetch('/api/new-job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){location.href='/agent/'+p.agent+'/jobs';}else{m.textContent='error: '+(r.error||'failed');}
  }catch(e){m.textContent='error: '+e;}
}
