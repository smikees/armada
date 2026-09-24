// First-run page (5.3). Step 1 sets ARMADA's folder; step 2 creates or opens a realm, then
// /switch moves the server into it and the normal app takes over.
(function(){
  function $(id){return document.getElementById(id);}
  function say(id,msg,bad){const m=$(id); if(!m) return; m.textContent=msg||''; m.classList.toggle('is-bad',!!bad);}
  async function post(url,body){
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    return r.json();
  }
  function step2(on){const s=$('w-step2'); if(s){ if(on) s.removeAttribute('aria-disabled'); else s.setAttribute('aria-disabled','true'); }}
  function open(path){ location.href='/switch?path='+encodeURIComponent(path)+'&to=/'; }

  window.mcWelcomePick=async function(inputId){
    try{
      const r=await(await fetch('/api/pick-folder')).json();
      if(r.ok && r.path){ $(inputId).value=r.path; return r.path; }
      if(r.error) say('w-rootmsg',r.error,true);
    }catch(e){ say('w-rootmsg','Type the folder instead.',true); }
    return '';
  };

  window.mcWelcomeEditRoot=function(){ const f=$('w-rootform'); if(f) f.hidden=false; $('w-root').focus(); };

  window.mcWelcomeSetRoot=async function(btn){
    const root=($('w-root').value||'').trim();
    if(!root){ say('w-rootmsg','Choose a folder first.',true); return; }
    btn.disabled=true; say('w-rootmsg','…');
    try{
      const r=await post('/api/set-approot',{root:root,create:true});
      if(!r.ok){ say('w-rootmsg',r.error||'That folder can’t be used.',true); return; }
      say('w-rootmsg','✓ Using '+r.root);
      $('w-rootform').hidden=true; step2(true); $('w-name').focus();
    }catch(e){ say('w-rootmsg','Couldn’t save: '+e,true); }
    finally{ btn.disabled=false; }
  };

  window.mcWelcomeCreate=async function(btn){
    if($('w-step2').getAttribute('aria-disabled')){ say('w-createmsg','Choose ARMADA’s folder first (step 1).',true); return; }
    const name=($('w-name').value||'').trim();
    if(!name){ say('w-createmsg','Give it a name.',true); $('w-name').focus(); return; }
    const t=document.querySelector('input[name="w-tpl"]:checked');
    btn.disabled=true; say('w-createmsg','Creating…');
    try{
      const r=await post('/api/first-realm',{name:name,template:t?t.value:'scratch'});
      if(!r.ok){ say('w-createmsg',r.error||'Couldn’t create it.',true); btn.disabled=false; return; }
      open(r.path);
    }catch(e){ say('w-createmsg','Couldn’t create it: '+e,true); btn.disabled=false; }
  };

  window.mcWelcomeAdopt=async function(btn){
    if($('w-step2').getAttribute('aria-disabled')){ say('w-adoptmsg','Choose ARMADA’s folder first (step 1).',true); return; }
    btn.disabled=true; say('w-adoptmsg','Choose the realm’s folder…');
    try{
      const pr=await(await fetch('/api/pick-folder')).json();
      if(!(pr.ok && pr.path)){ say('w-adoptmsg',pr.error||''); return; }
      const r=await post('/api/new-realm',{mode:'adopt',path:pr.path});
      if(!r.ok){ say('w-adoptmsg',r.error+(r.suggested_path?' Move it to '+r.suggested_path+' and try again.':''),true); return; }
      open(r.path);
    }catch(e){ say('w-adoptmsg','Couldn’t open it: '+e,true); }
    finally{ btn.disabled=false; }
  };
})();
