// Engine reach on the Capabilities page (docs/dev/CAPABILITIES_UPGRADE.md).
//
// The switcher above the sections shows one reach at a time (Any engine, Claude, Codex, Gemini) or
// all of them. It hides whole sections only, so it composes with the filter bar, which hides cards.
// The choice survives a reload within the session: grant an agent, the page reloads, you are still
// looking at the section you were working in.
const MC_REACH_LABEL={claude:'Claude',codex:'Codex',gemini:'Gemini',any:'Any engine'};
function mcReachPick(button){
  const want=button.dataset.reach||'';
  document.querySelectorAll('.mc-reach-pill').forEach(p=>p.setAttribute('aria-pressed',String(p===button)));
  document.querySelectorAll('.mc-reach-sec').forEach(s=>{s.hidden=!!want&&s.dataset.reachSec!==want;});
  try{sessionStorage.setItem('armada.cap.reach',want);}catch(e){}
}
(function(){
  let saved='';
  try{saved=sessionStorage.getItem('armada.cap.reach')||'';}catch(e){}
  if(!saved)return;
  const pill=Array.from(document.querySelectorAll('.mc-reach-pill')).find(p=>p.dataset.reach===saved);
  if(pill)mcReachPick(pill);
})();
// Arrow keys move between pills, as in any segmented control.
document.querySelector('.mc-reach-switch')?.addEventListener('keydown',function(event){
  if(!['ArrowLeft','ArrowRight'].includes(event.key))return;
  const pills=Array.from(this.querySelectorAll('.mc-reach-pill'));
  const i=pills.indexOf(document.activeElement);if(i<0)return;
  const next=pills[(i+(event.key==='ArrowRight'?1:pills.length-1))%pills.length];
  event.preventDefault();next.focus();mcReachPick(next);
});

// Moving a one-engine-at-a-time capability. The preview names who gains and who loses before
// anything is saved; ARMADA never signs in or out for the owner, so the confirmation says what is
// still theirs to do.
async function mcReachMove(button,cap,engine){
  const post=async body=>(await fetch('/api/capability-move',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})).json();
  button.disabled=true;
  try{
    const preview=await post({capability:cap,engine,preview:true});
    if(!preview.ok){await mcAlert(preview.error,'Can’t move it');return;}
    const to=MC_REACH_LABEL[preview.to],from=MC_REACH_LABEL[preview.from];
    const lines=['From '+from+' to '+to+'.',''];
    if(preview.loses.length)lines.push('Stops working for: '+preview.loses.map(a=>a.name+' (on '+MC_REACH_LABEL[a.engine]+')').join(', ')+'.');
    if(preview.gains.length)lines.push('Starts working for: '+preview.gains.map(a=>a.name).join(', ')+'.');
    if(!preview.loses.length&&!preview.gains.length)lines.push('No agent that can use it changes.');
    lines.push('',preview.note);
    if(!await mcConfirm('Move '+preview.name+' to '+to+'?',lines.join('\n'),{ok:'Move to '+to,primary:true}))return;
    const saved=await post({capability:cap,engine});
    if(!saved.ok){await mcAlert(saved.error,'Can’t move it');return;}
    try{sessionStorage.setItem('armada.connector.focus',cap);}catch(e){}
    location.reload();
  }catch(error){await mcAlert(String(error),'Can’t move it');}
  finally{button.disabled=false;}
}

// One engine at a time, set by the owner for a service ARMADA doesn't know about.
async function mcReachExclusive(input,cap){
  input.disabled=true;
  try{
    const r=await (await fetch('/api/capability-exclusive',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({capability:cap,exclusive:input.checked})})).json();
    if(!r.ok){input.checked=!input.checked;await mcAlert(r.error,'Not saved');return;}
    try{sessionStorage.setItem('armada.connector.focus',cap);}catch(e){}
    location.reload();
  }catch(error){input.checked=!input.checked;await mcAlert(String(error),'Not saved');}
  finally{input.disabled=false;}
}
