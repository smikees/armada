// Draft profiles stay in memory until Appoint the team succeeds.
(function(){
  const SU=window.MC_SU||{}, $=id=>document.getElementById(id);
  if(!$('su-team-builder'))return;
  const drafts=new Map();let dragId='',dialogReturn=null;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const template=()=>document.querySelector('input[name="su-tpl"]:checked')?.value||'scratch';
  const owner=()=>$('su-owner').value.trim();
  const ready=()=>!!(owner()&&$('su-name').value.trim());
  function draft(){const key=template();if(!drafts.has(key))drafts.set(key,{keep:new Set(),extra:[]});return drafts.get(key);}
  const profiles=()=>SU.presets[template()]?.agents||[];
  const all=()=>profiles().concat(draft().extra.map((a,i)=>({...a,id:'custom-'+i})));
  const chosen=()=>{const selected=all().filter(a=>draft().keep.has(a.id));const leader=selected.find(a=>a.coordinator&&a.id.startsWith('custom-'))||selected.find(a=>a.coordinator)||selected[0];return selected.map(a=>({...a,coordinator:a.id===leader?.id}));};
  const personal=s=>String(s||'').replaceAll('{owner}',owner()||'the owner');
  const portrait=a=>a.avatar_url||a.avatar_data||'/static/avatars/'+(a.avatar||'a20.png');
  const coordinatorTip='Can assign work to all other agents and is assigned to all goals.';
  const info='<span class="mc-su-info" tabindex="0" role="img" aria-label="'+coordinatorTip+'" title="'+coordinatorTip+'">'+SU.icons.info+'</span>';
  const coordinator='<span class="mc-su-coordinator" tabindex="0" role="img" aria-label="Coordinator agent. '+coordinatorTip+'" title="'+coordinatorTip+'">'+SU.icons.laurel+'</span>';
  function card(a,selected){
    const wiki=a.wikipedia?'<a class="mc-su-wikipedia" href="'+esc(a.wikipedia)+'" target="_blank" rel="noopener noreferrer">Wikipedia '+SU.icons.external+'</a>':'';
    const custom=a.id.startsWith('custom-');
    return '<article class="mc-su-profile" data-agent="'+esc(a.id)+'" draggable="'+ready()+'">'
      +'<span class="mc-su-grip" aria-hidden="true">⠿</span><img src="'+esc(portrait(a))+'" width="42" height="42" alt="">'
      +'<div><div class="mc-su-profile-title"><h3>'+esc(a.display)+'</h3><span class="mc-su-profile-role">'+esc(a.role||'Agent')+'</span>'+(a.coordinator?coordinator:'')+wiki+'</div>'
      +'<p class="mc-su-profile-summary">'+esc(personal(a.leader||a.mandate||'A profile you create for your realm.'))+'</p>'
      +'<div class="mc-su-profile-actions"><button type="button" class="btn-link" data-team-action="view" data-id="'+esc(a.id)+'">See profile</button>'
      +'<span class="mc-su-grow"></span><button type="button" class="btn btn-secondary btn-sm" data-team-action="'+(selected?'remove':'add')+'" data-id="'+esc(a.id)+'" aria-label="'+(selected?'Remove ':'Add ')+esc(a.display)+'">'+(selected?'Remove':'Add')+'</button>'
      +(custom?'<button type="button" class="btn btn-secondary btn-sm is-danger" data-team-action="delete" data-id="'+esc(a.id)+'" aria-label="Delete '+esc(a.display)+'">Delete</button>':'')+'</div></div></article>';
  }
  window.mcSuPaintTeam=function(){
    const d=draft(), selected=chosen(), available=all().filter(a=>!d.keep.has(a.id)), n=selected.length;
    $('su-tplline').textContent=template()==='state'?'The Cabinet profiles include their full mission, soul and tenets.':template()==='scratch'?'Start with your own agent profiles.':'These starter profiles include their full mission, soul and tenets.';
    const collective=template()==='company'?'Company':template()==='scratch'?'Realm':(SU.presets[template()]?.collective||'Realm');
    $('su-teamlabel').textContent='Your '+collective+' ('+n+(n===1?' member)':' members)');
    $('su-roster').innerHTML=available.map(a=>card(a,false)).join('')||'<p class="mc-su-drop-hint">'+(all().length?'Drag profiles back here to remove them from your team.':'Create your first agent on the right.')+'</p>';
    $('su-team').innerHTML=selected.map(a=>card(a,true)).join('')||'<p class="mc-su-drop-hint">Drop profiles here to build your team.</p>';
    const leader=selected.find(a=>a.coordinator)||selected[0];
    $('su-pickedline').textContent=n?leader.display+' coordinates your team.':'Choose at least one agent. You can add more later.';
    $('su-appoint').disabled=!ready()||!n;
    $('su-addagent').disabled=d.extra.length>=12;
  };
  window.mcSuTeamSelection=function(){
    const d=draft();if(!ready()||!chosen().length)return null;
    return {name:$('su-name').value.trim(),owner:owner(),template:template(),keep:profiles().filter(a=>d.keep.has(a.id)).map(a=>a.id),extra:d.extra.filter((a,i)=>d.keep.has('custom-'+i))};
  };
  function close(){ $('su-profile-dialog').close();dialogReturn?.focus(); }
  function show(a,edit){
    dialogReturn=document.activeElement;let avatar=a.avatar||'a20.png',avatarData='';
    const field=(key,label,max,placeholder='')=>'<label class="mc-label">'+label+'<input class="mc-field" name="'+key+'" maxlength="'+max+'" value="'+esc(personal(a[key]))+'" placeholder="'+esc(placeholder)+'"'+(key==='display'?' required':'')+'></label>';
    const section=(key,label)=>'<section class="mc-su-profile-section"><h3>'+label+'</h3><div class="mc-md">'+(a.html?.[key]?a.html[key].replaceAll('{owner}',esc(owner()||'the owner')):'<p>'+esc(personal(a[key]||'Not specified.')).replaceAll('\n','<br>')+'</p>')+'</div></section>';
    const avatarForm='<div class="mc-su-avatar-form"><img id="su-profile-avatar" src="'+esc(portrait(a))+'" width="64" height="64" alt="Selected avatar"><div><div class="mc-label">Avatar (optional)</div><button type="button" class="btn btn-secondary btn-sm" data-avatar-upload>Choose file…</button> <button type="button" class="btn btn-secondary btn-sm" data-avatar-set>Pick from set</button><input type="file" id="su-avatar-file" accept="image/*" hidden><p class="mc-hint" id="su-avatar-message">Upload a portrait, or pick one from the set. Images are cropped square &amp; optimized.</p></div></div>'
      +'<div id="su-avatar-set" class="mc-su-avatar-set" hidden>'+Array.from({length:20},(_,i)=>'<button type="button" data-avatar="a'+(i+1)+'.png" aria-label="Portrait '+(i+1)+'"><img src="/static/avatars/a'+(i+1)+'.png" width="56" height="56" alt=""></button>').join('')+'</div>';
    $('su-profile-content').innerHTML='<form id="su-profile-form"><p class="mc-hint">You will be able to edit '+(edit?'these and other profile fields':'all profile fields')+" from the agent's config page, after completing the setup.</p>"
      +'<header>'+(edit?'':'<img src="'+esc(portrait(a))+'" width="64" height="64" alt="">')+'<h2 id="su-profile-title">'+(edit?'Create an agent':esc(a.display))+'</h2><button type="button" class="btn btn-secondary" data-close-profile>Close</button></header>'
      +(edit?avatarForm+'<div class="mc-su-two">'+field('display','Name',40,'e.g. Warren')+field('role','Role (optional)',60,'E.g. Finance Minister')+'</div>'+field('leader','Profile (optional)',500,'E.g. after Warren Buffett — value discipline, margin of safety…')+'<label class="mc-su-coordinator-choice"><input type="checkbox" name="coordinator"> Is coordinator '+info+'</label>'
      :'<p class="mc-su-profile-subtitle">'+esc(a.role||'Agent')+'</p>'+(a.coordinator?coordinator:'')+'<p>'+esc(personal(a.leader))+'</p>'+section('mandate','Role and Mission')+section('voice','Soul — character, voice and traits')+section('tenets','Tenets')+'<section class="mc-su-profile-section"><h3>Configuration</h3><dl class="mc-su-config"><dt>Model and effort</dt><dd>Inherit realm default</dd><dt>Autonomy</dt><dd>Propose</dd><dt>Verbosity</dt><dd>Inherit realm default</dd><dt>Agent-to-agent messages</dt><dd>Enabled</dd><dt>Fallback and budget</dt><dd>Inherit realm default</dd></dl></section>')
      +(edit?'<button type="submit" class="btn btn-primary">Add to team</button>':'')+'</form>';
    $('su-profile-form').addEventListener('submit',e=>{e.preventDefault();if(!edit)return;const data=Object.fromEntries(new FormData(e.currentTarget));if(!data.display.trim())return;const d=draft();d.keep.add('custom-'+d.extra.length);if(data.coordinator)d.extra.forEach(a=>a.coordinator=false);d.extra.push({...data,coordinator:!!data.coordinator,avatar,avatar_data:avatarData});mcSuPaintTeam();close();});
    $('su-profile-content').querySelector('[data-close-profile]').addEventListener('click',close);
    if(edit){
      const toggleSet=()=>{const set=$('su-avatar-set');set.getAnimations().forEach(a=>a.cancel());
        if(!set.hidden){set.hidden=true;return;}set.hidden=false;
        if(!matchMedia('(prefers-reduced-motion: reduce)').matches)set.animate([{height:'0px',opacity:0,paddingTop:0,paddingBottom:0},{height:set.getBoundingClientRect().height+'px',opacity:1,paddingTop:'16px',paddingBottom:'16px'}],{duration:280,easing:'ease-out'});
      };
      $('su-profile-content').querySelector('[data-avatar-set]').onclick=toggleSet;
      $('su-profile-content').querySelector('[data-avatar-upload]').onclick=()=>$('su-avatar-file').click();
      $('su-avatar-set').onclick=e=>{const b=e.target.closest('[data-avatar]');if(!b)return;avatar=b.dataset.avatar;avatarData='';$('su-profile-avatar').src='/static/avatars/'+avatar;$('su-avatar-set').hidden=true;};
      $('su-avatar-file').onchange=async e=>{
        const file=e.target.files[0];if(!file)return;const msg=$('su-avatar-message'),save=$('su-profile-form').querySelector('[type=submit]');save.disabled=true;
        const url=URL.createObjectURL(file);
        try{const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=url;});
          const c=document.createElement('canvas');c.width=c.height=256;const side=Math.min(img.naturalWidth,img.naturalHeight),ctx=c.getContext('2d');ctx.imageSmoothingQuality='high';
          ctx.drawImage(img,(img.naturalWidth-side)/2,(img.naturalHeight-side)/2,side,side,0,0,256,256);
          avatarData=c.toDataURL('image/png');$('su-profile-avatar').src=avatarData;msg.textContent='Portrait ready.';
        }catch{msg.textContent='Could not read this image. Choose another file.';}finally{URL.revokeObjectURL(url);save.disabled=false;}
      };
    }
    $('su-profile-dialog').showModal();
  }
  $('su-profile-dialog').addEventListener('click',e=>{if(e.target!==e.currentTarget)return;const r=e.currentTarget.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)close();});
  window.mcSuCovenant=function(key){
    const preset=SU.presets[key];if(!preset)return;dialogReturn=document.activeElement;
    $('su-profile-content').innerHTML='<p class="mc-hint">The same for all realm types. You will be able to edit this document in the Realm config page, after completing the setup.</p><header><h2 id="su-profile-title" class="mc-su-document-title">'+SU.icons.agreement+' '+esc(preset.covenantTitle)+'</h2><button type="button" class="btn btn-secondary" data-close-profile>Close</button></header><div class="mc-md">'+preset.covenantHTML+'</div>';
    $('su-profile-content').querySelector('[data-close-profile]').onclick=close;$('su-profile-dialog').showModal();
  };
  window.mcSuAddAgent=()=>{if(ready()&&draft().extra.length<12)show({avatar:'a20.png'},true);};
  $('su-team-builder').addEventListener('click',e=>{
    const b=e.target.closest('[data-team-action]');if(!b||!ready())return;
    const id=b.dataset.id,d=draft(),a=all().find(a=>a.id===id);if(!a)return;
    if(b.dataset.teamAction==='view'){show(a,false);return;}
    if(b.dataset.teamAction==='delete'){
      const index=Number(id.slice('custom-'.length));if(!Number.isInteger(index)||index<0||index>=d.extra.length)return;
      d.extra.splice(index,1);
      d.keep=new Set([...d.keep].filter(k=>k!==id).map(k=>{
        if(!k.startsWith('custom-'))return k;
        const n=Number(k.slice('custom-'.length));return n>index?'custom-'+(n-1):k;
      }));mcSuPaintTeam();return;
    }
    if(b.dataset.teamAction==='add')d.keep.add(id);else d.keep.delete(id);
    mcSuPaintTeam();document.querySelector('[data-agent="'+id+'"] button')?.focus();
  });
  $('su-team-builder').addEventListener('dragstart',e=>{const row=e.target.closest('[data-agent]');if(!ready()||!row){e.preventDefault();return;}dragId=row.dataset.agent;e.dataTransfer.setData('text/plain',dragId);e.dataTransfer.effectAllowed='move';});
  for(const target of ['su-roster','su-team-drop']){
    $(target).addEventListener('dragover',e=>{if(ready()&&dragId){e.preventDefault();e.currentTarget.classList.add('is-dragover');}});
    $(target).addEventListener('dragleave',e=>{if(!e.currentTarget.contains(e.relatedTarget))e.currentTarget.classList.remove('is-dragover');});
    $(target).addEventListener('drop',e=>{e.preventDefault();e.currentTarget.classList.remove('is-dragover');if(ready()&&all().some(a=>a.id===dragId)){if(target==='su-team-drop')draft().keep.add(dragId);else draft().keep.delete(dragId);}dragId='';mcSuPaintTeam();});
  }
  document.addEventListener('dragend',()=>{dragId='';for(const id of ['su-team-drop','su-roster'])$(id).classList.remove('is-dragover');});
  document.addEventListener('change',e=>{if(e.target.name==='su-tpl')mcSuPaintTeam();});
  for(const id of ['su-owner','su-name'])$(id).addEventListener('input',mcSuPaintTeam);
  if(SU.savedTeam){
    const saved=SU.savedTeam;
    $('su-owner').value=saved.owner||'';$('su-name').value=saved.name||'';
    const radio=document.querySelector('input[name="su-tpl"][value="'+saved.template+'"]');if(radio)radio.checked=true;
    drafts.set(saved.template,{keep:new Set([...(saved.keep||[]),...(saved.extra||[]).map((a,i)=>'custom-'+i)]),extra:saved.extra||[]});
    $('su-appoint').textContent='Save team and continue';
  }
  mcSuPaintTeam();
})();
