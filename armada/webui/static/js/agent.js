function mcAvatarModal(show){const m=document.getElementById('mc-avatar-modal');if(m)m.style.display=show?'flex':'none';}
async function mcSetPreset(agent,preset){const msg=document.getElementById('mc-presetmsg');msg.textContent='applying…';
  try{const r=await(await fetch('/api/set-avatar-preset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,preset})})).json();
    if(r.ok){location.reload();}else{msg.textContent='error: '+(r.error||'failed');}}catch(e){msg.textContent='error: '+e;}}
async function mcRemoveAvatar(agent){const m=document.getElementById('c-avatarmsg');m.textContent='removing…';
  try{const r=await(await fetch('/api/remove-avatar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent})})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
async function mcSaveAgent(agent){
  if(!mcReq(['c-name'])){return;}
  const payload={agent, display:document.getElementById('c-name').value, role:document.getElementById('c-role').value,
    leader:document.getElementById('c-profile').value, autonomy:document.getElementById('c-autonomy').value,
    inbox:{cadence:document.getElementById('c-freq').value,
           accepts:(document.getElementById('c-accepts')||{}).value||'',
           // master switch: when off, the two fields above are greyed out but keep their values,
           // so switching back on restores the settings rather than resetting them to inherit
           enabled:!document.getElementById('c-a2a')||document.getElementById('c-a2a').checked},
    model:document.getElementById('c-model').value,
    effort:document.getElementById('c-effort').value, color:document.getElementById('c-color').value,
    verbosity:(document.getElementById('c-verbosity')||{}).value||'',
    fallback_model:document.getElementById('c-fallback').value,
    max_budget_usd:document.getElementById('c-maxbudget').value,
    mandate:document.getElementById('c-mandate').value,
    soul:document.getElementById('c-soul').value, tenets:document.getElementById('c-tenets').value};
  const m=document.getElementById('c-savemsg'), btn=document.getElementById('c-save');
  m.style.color='var(--text-muted)'; m.textContent='saving…'; if(btn)btn.disabled=true;
  try{const r=await (await fetch('/api/save-agent',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
    if(r.ok){mcSavedTick(r);}else{m.textContent='error: '+(r.error||'failed'); m.style.color='var(--status-bad)';}
  }catch(e){m.textContent='error: '+e; m.style.color='var(--status-bad)';}
  if(btn)btn.disabled=false;
}
// Saving used to navigate away, which is the wrong answer for a page you edit in several passes:
// you lost your scroll position and had to come back in to make the next change. It now stays put
// and says so. The three document fields drop back to reading mode using HTML rendered by the
// server in the save response — the same _md() the page was built with, so there is still exactly
// one markdown renderer and the confirmation shows you what was actually written.
function mcSavedTick(r){
  const m=document.getElementById('c-savemsg'), tick=document.getElementById('c-saved');
  const html=(r&&r.rendered)||{};
  for(const id in html){
    const v=document.getElementById(id+'-view'), t=document.getElementById(id), d=document.getElementById(id+'-dirty');
    if(v){v.innerHTML=html[id]||'<span style="color:var(--text-ghost)">Nothing yet.</span>';}
    // this text IS the saved text now, so the unsaved marker clears and becomes the new baseline
    if(t){t.setAttribute('data-orig',t.value);}
    if(d){d.style.display='none';}
    if(typeof mcMdEdit==='function'){mcMdEdit(id,false);}
  }
  // A rename shows in the breadcrumb; patch it rather than reload, which is what we just avoided.
  const crumb=document.getElementById('c-crumb-name');
  if(crumb&&r&&r.display){crumb.textContent=r.display;}
  m.textContent='';
  if(tick){tick.style.display='flex'; clearTimeout(mcSavedTick._t);
    mcSavedTick._t=setTimeout(function(){tick.style.display='none';
      m.textContent='writes agent.json + mandate.md + soul.md + tenets.md';},4000);}
}
async function mcUploadAvatar(agent,input){
  const f=input.files[0]; if(!f) return; const m=document.getElementById('c-avatarmsg'); m.textContent='processing…';
  try{
    const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=URL.createObjectURL(f);});
    const S=256, c=document.createElement('canvas'); c.width=S; c.height=S;
    const ctx=c.getContext('2d'); ctx.imageSmoothingEnabled=true; ctx.imageSmoothingQuality='high';
    const side=Math.min(img.naturalWidth,img.naturalHeight);   // center-crop to square, then downscale
    ctx.drawImage(img,(img.naturalWidth-side)/2,(img.naturalHeight-side)/2,side,side,0,0,S,S);
    URL.revokeObjectURL(img.src);
    const data=c.toDataURL('image/png');
    const r=await (await fetch('/api/upload-avatar',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent,filename:'avatar.png',data})})).json();
    if(r.ok){m.textContent='uploaded ✓ — reloading…';location.reload();}else{m.textContent='error: '+(r.error||'failed');}
  }catch(e){m.textContent='error: '+e;}
}

// --- retire / delete an agent -------------------------------------------------------------------
// Two very different actions, so two very different confirmations. Retiring is reversible and the
// dialog says so plainly, because an owner who suspects it might lose a year of an agent's memory
// will use neither button and leave the agent sitting in the realm instead. Deleting makes you type
// the name, the same as deleting a realm.
function mcManageSay(t,bad){const m=document.getElementById('c-manage-msg');if(!m)return;
  m.textContent=t||'';m.style.color=bad?'var(--status-bad)':'var(--text-muted)';}

async function mcAgentRetire(b,agent,name){
  const ok=await window.mcConfirm('Retire '+name+'?',
    name+"'s jobs stop running and they leave the register, goals and delegation.\n\n"+
    'Nothing is deleted. The threads, memories, run history and capability grants all stay exactly '+
    'as they are, and you can bring '+name+' back unchanged from Appoint — Reinstate.',
    {ok:'Retire '+name});
  if(!ok)return;
  b.disabled=true;mcManageSay('retiring…');
  try{const r=await(await fetch('/api/agent-retire',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent:agent})})).json();
    if(r.ok){mcManageSay('retired — returning to the realm…');
      // Back to the register: this agent's page is about to be a page for someone who isn't here.
      setTimeout(function(){location.href='/ministers';},800);}
    else mcManageSay(r.error||'could not retire',true);}
  catch(e){mcManageSay('could not retire: '+e,true);}
  b.disabled=false;}

async function mcAgentDelete(b,agent,name){
  const typed=await window.mcConfirm('Delete '+name+'?',
    'This deletes the folder and everything in it — jobs, threads, memories, run history, grants. '+
    'On Windows it goes to the Recycle Bin, but nothing in ARMADA will bring it back.\n\n'+
    'Retire instead if you might want '+name+' later.',
    {ok:'Delete '+name,danger:true,mustType:name});
  if(!typed)return;
  b.disabled=true;mcManageSay('deleting…');
  try{const r=await(await fetch('/api/agent-delete',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent:agent,display:name,confirm:typed})})).json();
    if(r.ok){mcManageSay(r.recycled?"deleted — it's in your Recycle Bin":'deleted');
      setTimeout(function(){location.href='/ministers';},900);}
    else mcManageSay(r.error||'could not delete',true);}
  catch(e){mcManageSay('could not delete: '+e,true);}
  b.disabled=false;}
