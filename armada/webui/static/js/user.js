function mcUserAvatarModal(show){var m=document.getElementById('us-avatar-modal');if(m)m.style.display=show?'flex':'none';}
async function mcSetUserPreset(preset){var msg=document.getElementById('us-presetmsg');msg.textContent='applying…';
  try{const r=await(await fetch('/api/user-avatar-preset',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({preset})})).json();
    if(r.ok){location.reload();}else{msg.textContent='error: '+(r.error||'failed');}}catch(e){msg.textContent='error: '+e;}}
async function mcRemoveUserAvatar(){var m=document.getElementById('us-avatarmsg');m.textContent='removing…';
  try{const r=await(await fetch('/api/user-avatar-remove',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
async function mcUploadUserAvatar(input){const f=input.files[0];if(!f)return;var m=document.getElementById('us-avatarmsg');m.textContent='processing…';
  try{const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=URL.createObjectURL(f);});
    const S=256,c=document.createElement('canvas');c.width=S;c.height=S;const ctx=c.getContext('2d');ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
    const side=Math.min(img.naturalWidth,img.naturalHeight);ctx.drawImage(img,(img.naturalWidth-side)/2,(img.naturalHeight-side)/2,side,side,0,0,S,S);
    URL.revokeObjectURL(img.src);const data=c.toDataURL('image/png');
    const r=await(await fetch('/api/user-avatar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:'avatar.png',data})})).json();
    if(r.ok){m.textContent='uploaded ✓ — reloading…';location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
async function mcSaveUser(){var m=document.getElementById('us-msg');m.textContent='saving…';
  // No timezone here any more — it's a realm setting, saved from the Realm tab.
  const p={name:document.getElementById('us-name').value,
    gender:document.getElementById('us-gender').value,birthdate:document.getElementById('us-bday').value,
    about:(document.getElementById('us-about')||{}).value||''};
  try{const r=await(await fetch('/api/save-user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){m.textContent='saved ✓';m.style.color='var(--status-ok)';}else{m.textContent='error: '+(r.error||'failed');m.style.color='var(--status-bad)';}}catch(e){m.textContent='error: '+e;}}
// The timezone picker lives in Realm settings now (it's what the scheduler runs this realm's jobs
// against), so this reads st-tz — falling back to the old id so a cached page doesn't break.
function mcTzUpdate(){var sel=document.getElementById('st-tz')||document.getElementById('us-tz'),
  d=document.getElementById('us-tz-time');if(!sel||!d)return;
  var tz=sel.value,now=new Date(),t;
  try{t=tz?new Intl.DateTimeFormat([],{timeZone:tz,hour:'2-digit',minute:'2-digit'}).format(now)
        :now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}
  catch(e){t=now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});}
  d.innerHTML='Time now: <b>'+t+'</b> · Job schedules in this realm will be based on this time.';}
(function(){try{mcTzUpdate();setInterval(mcTzUpdate,30000);}catch(e){}})();
