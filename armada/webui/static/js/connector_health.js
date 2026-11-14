async function mcHealthSettings(button,url,payload){
  const box=button.closest('dialog'),feedback=box.querySelector('[data-feedback]');
  button.disabled=true;feedback.textContent='Saving…';
  try{
    const result=await (await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
    if(!result.ok)throw Error(result.error||'Could not save.');
    feedback.textContent=result.detail||'Saved.';
    if(result.names)box.querySelector('[data-secret-names]').textContent=result.names.join(', ')||'None';
  }catch(e){feedback.textContent=e.message;}
  finally{button.disabled=false;}
}
function mcCheckHealth(button){
  const ids=[...button.closest('dialog').querySelectorAll('[data-watch]:checked')].map(x=>x.value);
  return mcHealthSettings(button,'/api/connector-health-check',{ids});
}
function mcSaveWatches(button){
  const box=button.closest('dialog'),values={watched:[...box.querySelectorAll('[data-watch]:checked')].map(x=>x.value)};
  box.querySelectorAll('[data-health-setting]').forEach(x=>values[x.dataset.healthSetting]=Number(x.value));
  return mcHealthSettings(button,'/api/connector-watches',{values});
}
function mcSaveCommandSecret(button,remove){
  const box=button.closest('dialog'),name=box.querySelector('#command-secret-name').value.trim(),input=box.querySelector('#command-secret-value');
  const value=remove?'':input.value;
  if(!remove&&!value){box.querySelector('[data-feedback]').textContent='Enter a secret value.';return;}
  input.value='';
  return mcHealthSettings(button,'/api/command-secret',{name,value});
}
async function mcRefreshConnectorHealth(){
  const cards=[...document.querySelectorAll('[data-connector-health]')];
  if(!cards.length||document.hidden)return;
  try{
    const response=await fetch('/api/connector-health');if(!response.ok)return;
    const data=await response.json(),stamp=t=>t?new Date(t*1000).toLocaleString():'never';
    const rows=Object.values(data.connectors||{});
    cards.forEach(card=>{
      card.textContent=rows.filter(r=>r.id===card.dataset.connectorHealth).map(r=>
        r.provider+': '+r.state+(Date.now()/1000-r.checked_at>1800?' (stale)':'')+' · checked '+stamp(r.checked_at)+
        ' · last up '+stamp(r.last_up_at)+' · '+Number(r.uptime_percent||0).toFixed(1)+'% of checks passed in 30 days. '+(r.reason||'')).join('\n')||'No heartbeat recorded.';
    });
  }catch(e){/* Preserve the last displayed reading. */}
}
setInterval(mcRefreshConnectorHealth,30000);
