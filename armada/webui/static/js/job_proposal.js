// Uses the shared app-native dialog (window.mcConfirm, loaded for every page). It used to
// carry a private copy with the same name, which shadowed the shared one depending on load
// order and broke callers using the other signature.
async function mcJobProposal(agent,slug,action,btn){
  const box=btn.closest('.mc-prop'); const msg=box?box.querySelector('.mc-propmsg'):null;
  if(action==='reject'){
    const ok=await mcConfirm({title:'Reject job proposal?',
      body:'This permanently deletes the proposed job. It won’t appear on your Jobs page anymore.',
      confirm:'Reject',danger:true});
    if(!ok)return;
  }
  btn.disabled=true; if(msg){msg.style.color='';msg.textContent=action==='approve'?'Approving…':'Rejecting…';}
  try{
    const r=await (await fetch('/api/job-proposal',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent,slug,action})})).json();
    if(r.ok){location.reload();}
    else{if(msg){msg.style.color='var(--status-bad)';msg.textContent=r.error||'failed';}btn.disabled=false;}
  }catch(e){if(msg){msg.style.color='var(--status-bad)';msg.textContent='network error';}btn.disabled=false;}
}
