// Uses the shared app-native dialog (window.mcConfirm, loaded for every page). It used to
// carry a private copy with the same name, which shadowed the shared one depending on load
// order and broke callers using the other signature.
function mcJobProposalTools(select){
  const box=select.closest('.mc-prop');
  const value=select.value;
  const error=box.querySelector('.mc-proptoolerror');
  if(error)error.hidden=value==='true'||value==='false';
  box.querySelector('.mc-proptoolstatus').textContent=value==='true'?'Runs WITH tools':
    value==='false'?'Runs WITHOUT tools: it cannot read or write files, use connectors or send inbox messages':
    'Tools setting required before approval';
  box.querySelector('.mc-proptoolwarning').hidden=!(value==='false'&&select.dataset.needsTools==='true');
  const approve=box.querySelector('.mc-propapprove');
  approve.disabled=!(value==='true'||value==='false')||select.dataset.validOther!=='true';
  approve.title=approve.disabled?'Fix the errors above first':'';
}
async function mcJobProposal(agent,slug,action,btn){
  const box=btn.closest('.mc-prop'); const msg=box?box.querySelector('.mc-propmsg'):null;
  const body={agent,slug,action};
  const tools=box?box.querySelector('.mc-proptools'):null;
  if(action==='approve'&&tools){
    if(tools.value!=='true'&&tools.value!=='false')return;
    body.allow_tools=tools.value==='true';
    if(!body.allow_tools&&tools.dataset.needsTools==='true'){
      if(!await mcConfirm({title:'Approve without tools?',
        body:'This job appears to need tools. Without tools it cannot read or write files, use connectors or send inbox messages. Required outputs or destinations will stop it before it runs. You can go back and choose Runs WITH tools.',
        confirm:'Approve without tools',danger:true}))return;
      body.tools_warning_ack=true;
    }
  }
  if(action==='reject'){
    const ok=await mcConfirm({title:'Reject job proposal?',
      body:'This permanently deletes the proposed job. It won’t appear on your Jobs page anymore.',
      confirm:'Reject',danger:true});
    if(!ok)return;
  }
  btn.disabled=true; if(msg){msg.style.color='';msg.textContent=action==='approve'?'Approving…':'Rejecting…';}
  try{
    const r=await (await fetch('/api/job-proposal',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)})).json();
    if(r.ok){location.reload();}
    else{if(msg){msg.style.color='var(--status-bad)';msg.textContent=r.error||'failed';}btn.disabled=false;}
  }catch(e){if(msg){msg.style.color='var(--status-bad)';msg.textContent='network error';}btn.disabled=false;}
}
