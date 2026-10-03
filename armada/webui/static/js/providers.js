// Shared setup/settings connections. Never transport credentials or manufacture OAuth URLs.
(function(){
  let loading=null, latest=null;
  const el=id=>document.getElementById(id);
  const labels={claude:'Claude',codex:'Codex',gemini:'Gemini'};
  const cliLabels={claude:'Claude CLI',codex:'Codex CLI',gemini:'Antigravity CLI'};
  function subscriptionName(provider,value){
    const raw=String(value||'').trim().toLowerCase();
    const plans=provider==='codex'
      ?{free:'Free',go:'Go',plus:'Plus',pro:'Pro',prolite:'Pro',promax:'Pro',team:'Business',business:'Business',enterprise:'Enterprise',edu:'Edu'}
      :{free:'Free',pro:'Pro',max:'Max',team:'Team',business:'Business',enterprise:'Enterprise',edu:'Edu'};
    if(Object.hasOwn(plans,raw))return plans[raw];
    const max=provider==='claude'&&raw.match(/^max[_-]?(5|20)x$/);
    return max?'Max '+max[1]+'×':'';
  }
  function updateModels(data){
    document.querySelectorAll('[data-provider-models]').forEach(select=>{
      const value=select.value;
      const fixed=[...select.options].filter(o=>!o.value||o.value==='auto').map(o=>[o.value,o.textContent]);
      select.replaceChildren();
      [...fixed,...data.models].forEach(([id,label])=>select.add(new Option(label,id)));
      if(value&&![...select.options].some(o=>o.value===value)){
        const missing=new Option(value+' — unavailable',value);missing.disabled=true;select.add(missing);
      }
      select.value=value;
    });
    updateEfforts();
  }
  function updateEfforts(){
    const model=el('alexander-model'), effort=el('alexander-effort');if(!model||!effort||!latest)return;
    const value=effort.value;
    const options=model.value==='auto'?latest.automatic_efforts:(latest.efforts[model.value]||['auto']);
    effort.replaceChildren();options.forEach(e=>effort.add(new Option(e==='auto'?'Automatic':e[0].toUpperCase()+e.slice(1),e)));
    effort.value=options.includes(value)?value:'auto';
  }
  async function refresh(force=false){
    if(loading){await loading;if(!force)return latest;}
    loading=load(force);try{return await loading;}finally{loading=null;}
  }
  async function load(force=false){
    const controller=new AbortController(), deadline=setTimeout(()=>controller.abort(),60000);
    try{
      const response=await fetch('/api/providers'+(force?'?force=1':''),{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error();
      latest=await response.json();
      const runtime=el('su-runtime');
      if(runtime&&latest.runtime){
        const r=latest.runtime;runtime.replaceChildren();
        for(const [name,version,ok,guide] of [
          ['Python',r.python,r.python_available!==false,'https://www.python.org/downloads/windows/'],
          ['WebView2',r.webview2,!!r.webview2,'https://developer.microsoft.com/en-us/microsoft-edge/webview2/']]){
          const li=document.createElement('li'),icon=document.createElement('span');
          icon.className=ok?'mc-su-dep-ok':'mc-su-dep-missing';icon.textContent=ok?'✓':'×';
          icon.setAttribute('aria-label',ok?'Installed':'Missing');li.append(icon,document.createTextNode(name+' · '+(version||'Not available')));
          if(!ok){const a=document.createElement('a');a.href=guide;a.target='_blank';a.rel='noopener';a.textContent='Installation guide';li.append(a);}
          runtime.append(li);
        }
      }
      Object.entries(latest.providers).forEach(([p,s])=>{
        document.querySelectorAll('.mc-provider-card .mc-engine-logo[data-provider="'+p+'"]').forEach(logo=>logo.classList.toggle('is-connected',!!s.connected));
        document.querySelectorAll('.mc-system-provider[data-engine="'+p+'"]').forEach(card=>{
          card.querySelector('.mc-system-provider-version').textContent=s.installed?'CLI '+(s.version?'v'+s.version:'version unavailable'):'CLI not installed';
          const state=card.querySelector('.mc-system-provider-status');
          state.textContent=s.connected?'Signed-in':s.pending?'Waiting for sign-in':!s.enabled?'Disconnected':s.ok===false?'Sign-in check unavailable':'Not signed in';
          state.style.color=s.connected?'var(--status-ok)':'var(--text-muted)';
        });
        const status=el('provider-'+p+'-status');if(!status)return;
        const needsInstall=!s.installed||s.version_ok===false;
        el('provider-'+p+'-installed').textContent=s.installing?'Installing…':s.installed?'CLI installed'+(s.version?' · '+s.version:''):'CLI not installed';
        const plan=el('provider-'+p+'-plan');
        if(plan){
          const subscription=el('provider-'+p+'-subscription');
          const signed=s.installed&&s.ok!==false&&s.logged_in===true;
          const name=(subscription?signed:s.connected)?subscriptionName(p,s.plan):'';
          plan.textContent=name?(plan.dataset.planPrefix?plan.dataset.planPrefix+' ':'')+name:subscription&&signed?'Not reported by CLI':'';
          plan.hidden=!plan.textContent;
          if(subscription)subscription.hidden=!signed;
        }
        const message=s.installing?'Installing '+cliLabels[p]+'. This may take a few minutes.':s.install_error?s.install_error:
          !s.installed?'Install '+cliLabels[p]+' to use '+labels[p]+'.':s.version_ok===false?'Update Claude Code to '+s.min_version+' or newer before signing in.':
          s.connected?'Signed-in':s.pending?(p==='gemini'?'Complete Google sign-in in the CLI window that opened.':s.login_url?'Waiting for sign-in. Open the link below, or copy it into your browser.':'Preparing the sign-in link…'):
          s.login_error?s.login_error:!s.enabled?'Disconnected from Armada.':s.ok===false?'Could not check sign-in. Check the CLI configuration and retry.':'Not signed in';
        if(status.dataset.authPill){
          // Authentication is independent of Armada's enabled flag and CLI version.
          // A failed probe must never masquerade as a confirmed sign-out.
          const signed=s.installed&&s.ok!==false&&s.logged_in===true;
          const auth=signed?'signed-in':s.pending?'Signing in…':!s.installed?'Not available':s.ok===false?'Check unavailable':'not signed in';
          status.innerHTML=(signed?(window.MC_SU?.icons?.ok||''):'')+'<span>'+auth+'</span>';
          status.classList.toggle('mc-provider-signed-in',signed);
          const detail=el('provider-'+p+'-feedback');
          detail.textContent=s.installing||s.install_error||s.login_error||s.pending||s.version_ok===false||s.ok===false?message:'';
          status.title=auth;
        }else{
          status.textContent=message;
          status.classList.toggle('mc-provider-signed-in',!!s.connected);
          status.title=message;
        }
        el('provider-'+p+'-connect').hidden=needsInstall||s.connected||s.pending||s.installing;
        el('provider-'+p+'-connect').disabled=false;
        const signLabel=el('provider-'+p+'-connect').querySelector('[data-signin-label]');
        signLabel.textContent=!s.enabled&&s.logged_in?'Reconnect':signLabel.dataset.defaultLabel;
        el('provider-'+p+'-disconnect').hidden=!s.connected;
        el('provider-'+p+'-install').hidden=!needsInstall&&!s.install_error;
        el('provider-'+p+'-install').disabled=!!s.installing;
        el('provider-'+p+'-install').textContent=(s.installed?'Update ':'Install ')+cliLabels[p];
        el('provider-'+p+'-guide').hidden=!needsInstall&&!s.install_error;
        el('provider-'+p+'-open').hidden=!s.can_open_login||s.connected;
        const link=el('provider-'+p+'-url'), wrap=el('provider-'+p+'-url-wrap');
        const loginUrl=s.pending&&!s.connected?s.login_url||'':'';
        link.textContent=loginUrl;if(loginUrl)link.href=loginUrl;else link.removeAttribute('href');
        wrap.hidden=!loginUrl;
        el('provider-'+p+'-cancel').hidden=!s.pending;
      });
      updateModels(latest);
      window.dispatchEvent(new CustomEvent('armada:providers',{detail:latest}));
      return latest;
    }catch(e){document.querySelectorAll('.mc-system-provider').forEach(card=>{
      card.querySelector('.mc-system-provider-version').textContent='CLI version unavailable';
      card.querySelector('.mc-system-provider-status').textContent='Connection check unavailable';
    });document.querySelectorAll('[data-connection]').forEach(card=>{
      const status=el('provider-'+card.dataset.connection+'-status');
      status.textContent=status.dataset.authPill?'Check unavailable':'Could not check sign-in. Select Recheck to try again.';status.classList.remove('mc-provider-signed-in');
      if(status.dataset.authPill){el('provider-'+card.dataset.connection+'-installed').textContent='Check unavailable';el('provider-'+card.dataset.connection+'-feedback').textContent='Select Recheck to try again.';}
      const plan=el('provider-'+card.dataset.connection+'-plan');if(plan){plan.textContent='';plan.hidden=true;}
      const subscription=el('provider-'+card.dataset.connection+'-subscription');if(subscription)subscription.hidden=true;
    });return null;}finally{clearTimeout(deadline);}
  }
  window.mcRecheckProvider=async function(provider,button){
    const feedback=el('provider-'+provider+'-feedback'), label=button.querySelector('span');
    button.disabled=true;button.setAttribute('aria-busy','true');label.textContent='Checking…';feedback.textContent='';
    try{const data=await refresh(true);feedback.textContent=data?'Checked just now.':'Check failed. Try again.';}
    finally{button.disabled=false;button.removeAttribute('aria-busy');label.textContent='Recheck';}
  };
  window.mcConnection=async function(provider,action,button){
    button.disabled=true;
    try{
      const response=await fetch('/api/provider-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider,action})});
      const r=await response.json();
      if(r.ok){await refresh();}
      else el('provider-'+provider+'-status').textContent=r.error||'Could not update connection.';
    }catch(e){el('provider-'+provider+'-status').textContent='Could not update connection. Try again.';}
    finally{button.disabled=false;}
  };
  window.mcSaveAlexander=async function(button){
    button.disabled=true;
    try{
      const r=await(await fetch('/api/alexander-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:el('alexander-model').value,effort:el('alexander-effort').value,verbosity:el('alexander-verbosity').value})})).json();
      el('alexander-settings-status').textContent=r.ok?'Saved. Applies to Alexander’s next reply.':r.error;
    }catch(e){el('alexander-settings-status').textContent='Could not save. Try again.';}
    finally{button.disabled=false;}
  };
  document.addEventListener('change',e=>{if(e.target.id==='alexander-model')updateEfforts();});
  window.mcRefreshProviders=refresh;
  setTimeout(refresh,0);setInterval(()=>{if(!document.hidden&&latest&&Object.values(latest.providers).some(s=>s.pending||s.installing))refresh();},3000);
  setInterval(()=>{if(!document.hidden)refresh();},60000);
  window.addEventListener('focus',()=>refresh());
})();
