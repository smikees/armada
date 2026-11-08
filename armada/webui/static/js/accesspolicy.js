(() => {
  const root=document.querySelector('.mc-access-policy');if(!root)return;
  const lines=el=>el.value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  const status=root.querySelector('[data-policy-status]'),preview=root.querySelector('[data-policy-preview]');
  const receipt='mc-policy-result:'+document.querySelector('meta[name="armada-realm"]')?.content+':'+root.dataset.agent;
  function say(message,state='working'){status.textContent=message;status.dataset.state=state;}
  try{const saved=sessionStorage.getItem(receipt);if(saved){say(saved,'saved');sessionStorage.removeItem(receipt);}}catch(_){}
  function payload(realm){
    const tools={};
    if(realm){
      root.querySelectorAll('[data-default-connector]').forEach(row=>{
        const deny=lines(row);if(deny.length)tools[row.dataset.defaultConnector]={deny};
      });
      return {tool_policy:tools,read_only:lines(root.querySelector('[data-read-only]')),
        policy_builder:root.querySelector('[data-policy-builder]').value.trim()};
    }
    root.querySelectorAll('[data-tool-connector]').forEach(row=>{
      if(row.querySelector('[data-limit-tools]').checked)tools[row.dataset.toolConnector]={
        allow:lines(row.querySelector('[data-allow]')),deny:lines(row.querySelector('[data-deny]'))};
    });
    return {tool_policy:tools,write_scope:root.querySelector('[data-limit-writes]').checked?lines(root.querySelector('[data-write-scope]')):null};
  }
  let busy=false;
  async function send(button,url,body,{read=false,message='Changes saved. They apply to new runs.'}={}){
    if(busy)return;busy=true;root.setAttribute('aria-busy','true');
    const controls=[...root.querySelectorAll('input,textarea,button')].map(el=>[el,el.disabled]);
    controls.forEach(([el])=>{el.disabled=true;});
    say(read?'Preparing preview…':url.includes('refresh')?'Refreshing tool names…':'Saving…');
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000);
    let answered=false;
    try{
      const response=await fetch(url,{method:'POST',signal:controller.signal,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const result=await response.json();answered=true;
      if(!response.ok||!result.ok)throw Error(result.error||'The request was refused.');
      if(read){paint(result);say('Preview ready. Nothing has been saved.','ready');}
      else{say(message,'saved');try{sessionStorage.setItem(receipt,message);}catch(_){}location.reload();}
    }catch(error){say(answered?error.message:read?'Preview unavailable. Check the connection and try again.':
      'Could not confirm whether the change was saved. Reload to check before trying again.','error');}
    finally{clearTimeout(timer);busy=false;controls.forEach(([el,disabled])=>{el.disabled=disabled;});root.removeAttribute('aria-busy');
      if(document.activeElement===document.body)button.focus();}
  }
  function paint(result){
    preview.replaceChildren();preview.hidden=false;
    function add(tag,text,parent=preview){const node=document.createElement(tag);node.textContent=text;parent.append(node);return node;}
    add('h4','Unsaved access for '+result.agent);add('p',result.notice);
    for(const connector of result.connectors){
      const group=add('details','');add('summary',connector.name,group);
      add('p','Can call: '+(connector.can_call.join(', ')||'No recorded tools'),group);
      add('p','Cannot call: '+(connector.cannot_call.join(', ')||'None of the recorded tools'),group);
      if(connector.reason)add('p',connector.reason,group);
      if(connector.literal_names.length)add('p','Explicit names not yet recorded: '+connector.literal_names.join(', '),group);
      if(!connector.inventory_known)add('p','Tool names are not recorded; this is not a complete tool inventory.',group);
      if(connector.newly_allowed.length)add('p','Newly permitted: '+connector.newly_allowed.join(', '),group);
      if(connector.newly_denied.length)add('p','Newly blocked: '+connector.newly_denied.join(', '),group);
    }
    add('p',result.builder?'Builder: realm file restrictions do not apply.':result.write_scope===null?
      'No per-agent write scope is set.':'May write only: '+(result.write_scope.join(', ')||'nowhere'));
    add('p','Realm read-only paths: '+(result.read_only.join(', ')||'none')+(result.builder?' (builder exempt)':''));
    if(result.scoped)add('p','Shell and native file writes are disabled. Guarded writes still protect control records and validate notes and proposals.');
  }
  root.addEventListener('input',()=>{if(!preview.hidden){preview.hidden=true;say('Preview is out of date. Preview again to review these edits.');}});
  root.querySelectorAll('[data-preview-policy]').forEach(button=>button.addEventListener('click',()=>{
    const realm=button.dataset.previewPolicy==='realm';
    send(button,'/api/preview-access-policy',{agent:root.dataset.agent,provider:root.dataset.provider,
      realm_defaults:realm,policy:payload(realm)},{read:true});
  }));
  root.querySelector('[data-save-agent-policy]').addEventListener('click',event=>
    send(event.currentTarget,'/api/save-access-policy',{agent:root.dataset.agent,policy:payload(false)}));
  root.querySelector('[data-save-realm-policy]').addEventListener('click',event=>
    send(event.currentTarget,'/api/save-access-policy',{policy:payload(true)}));
  root.querySelectorAll('[data-save-tool-names]').forEach(button=>button.addEventListener('click',()=>{
    const row=button.closest('[data-inventory-connector]');
    send(button,'/api/save-tool-inventory',{connector:row.dataset.inventoryConnector,names:lines(row.querySelector('[data-tool-names]'))},
      {message:'Tool names saved. Access rules still apply.'});
  }));
  root.querySelector('[data-refresh-tools]').addEventListener('click',event=>
    send(event.currentTarget,'/api/refresh-tool-inventory',{agent:root.dataset.agent,provider:root.dataset.provider},
      {message:'Tool names refreshed. Access rules still apply.'}));
})();
