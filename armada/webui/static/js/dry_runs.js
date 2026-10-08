// One independent draft history per job; a production run never changes this selection.
if(!window.mcDryInstalled){
window.mcDryInstalled=true;
window.mcDryLoad=async function(panel){
  if(panel._dryLoading)return;
  panel._dryLoading=true;
  const selected=panel.dataset.dryRun||'';
  try{
    const q=new URLSearchParams({agent:panel.dataset.dryAgent,job:panel.dataset.dryJob,run_id:selected});
    const response=await fetch('/api/dry-runs?'+q),r=await response.json();
    if(!response.ok||!r.ok)throw new Error(r.error||'Unable to load dry runs.');
    if(selected!==(panel.dataset.dryRun||''))return;
    const picker=panel.querySelector('.mc-dry-model');
    if(picker){
      const value=picker.value,key=JSON.stringify(r.models);
      if(picker._key!==key){picker.replaceChildren(new Option('Choose a model…',''),...r.models.map(m=>new Option(m.label,m.id)));picker._key=key;picker.value=value;}
    }
    const history=panel.querySelector('.mc-dry-history'),key=JSON.stringify(r.runs.map(run=>[run.run_id,run.status]));
    if(history._key!==key){
      history.replaceChildren(new Option('Latest dry run',''),...r.runs.map(run=>new Option(run.started.replace('T',' · ').slice(0,24)+' · '+(run.actual_model||run.model||'Command')+' · '+run.status,run.run_id)));
      history._key=key;
    }
    history.value=selected;
    const output=panel.querySelector('.mc-dry-output');
    if(output._html!==r.html){output.innerHTML=r.html;output._html=r.html;}
    panel._dryActive=r.runs.find(run=>['queued','running'].includes(run.status));
    const stop=panel.querySelector('.mc-dry-stop');
    stop.hidden=!panel._dryActive;stop.style.display=panel._dryActive?'':'none';
    panel.querySelector('.mc-dry-start').disabled=!!panel._dryActive||!!panel._dryStarting||!!(picker&&!r.models.length);
    if(picker&&!r.models.length)panel.querySelector('.mc-dry-message').textContent='No models available. Connect a provider in Settings → App.';
    panel._dryLoaded=true;
  }catch(e){panel.querySelector('.mc-dry-message').textContent=e.message;}
  finally{panel._dryLoading=false;}
};
window.mcDryStart=async function(button){
  const panel=button.closest('.mc-dry-runs'),message=panel.querySelector('.mc-dry-message');
  const picker=panel.querySelector('.mc-dry-model');
  if(picker&&!picker.value){message.textContent='Choose a model first.';picker.focus();return;}
  panel._dryStarting=true;button.disabled=true;message.textContent='Starting dry run…';
  try{
    const response=await fetch('/api/dry-run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:panel.dataset.dryAgent,job:panel.dataset.dryJob,model:picker?picker.value:''})});
    const r=await response.json();if(!response.ok||!r.ok)throw new Error(r.error||'Could not start the dry run.');
    panel.dataset.dryRun=r.run.run_id;message.textContent='Dry run started.';
  }catch(e){message.textContent=e.message;}
  finally{panel._dryStarting=false;button.disabled=false;await mcDryLoad(panel);}
};
window.mcDryStop=async function(button){
  const panel=button.closest('.mc-dry-runs'),run=panel._dryActive;
  if(!run)return;
  button.disabled=true;
  try{
    const r=await(await fetch('/api/dry-run-stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:panel.dataset.dryAgent,job:panel.dataset.dryJob,run_id:run.run_id})})).json();
    if(!r.ok)throw new Error(r.error||'Could not stop the dry run.');
    panel.querySelector('.mc-dry-message').textContent='Stopping…';
  }catch(e){panel.querySelector('.mc-dry-message').textContent=e.message;}
  finally{button.disabled=false;await mcDryLoad(panel);}
};
window.mcDrySelect=function(select){const panel=select.closest('.mc-dry-runs');panel.dataset.dryRun=select.value;mcDryLoad(panel);};
document.querySelectorAll('.mc-dry-runs').forEach(panel=>{
  panel.addEventListener('toggle',e=>{if(e.target===panel&&panel.open)mcDryLoad(panel);});
  if(panel.open)mcDryLoad(panel);
});
setInterval(()=>document.querySelectorAll('.mc-dry-runs[open]').forEach(panel=>{
  const parent=panel.closest('.mc-job');if(!parent||parent.open)mcDryLoad(panel);
}),1800);
}
