(function(){
  'use strict';
  function boxOf(element){return element.closest('[data-api-fallback]');}
  function feedback(box,text){box.querySelector('[data-fallback-feedback]').textContent=text;}
  function summary(box,state){
    const label=state.ready?'Critical jobs only':state.managed?'Off':'Not set up';
    document.querySelectorAll('[data-fallback-open="'+box.id+'"]').forEach(button=>{
      button.textContent=state.managed?'Manage API usage fallback':'Set up API usage fallback';
      const entry=button.closest('[data-fallback-entry]');
      if(entry)entry.querySelector('[data-fallback-summary]').textContent=label;
    });
  }
  function source(box){return box.querySelector('[data-fallback-source]')?.value||'engine';}
  function keyStatus(box){
    const own=!!box.dataset.agent,mode=source(box),area=box.querySelector('[data-fallback-key-area]');
    area.hidden=own&&mode!=='agent';
    const saved=own&&mode==='agent'?box._state?.agent_key_saved:box._state?.engine_key_saved;
    area.querySelector('[data-fallback-key-status]').textContent=saved?'A key is saved. Leave this empty to keep it.':'No key saved for this selection.';
    area.querySelector('[data-fallback-remove-row]').hidden=!saved;
    box.querySelector('[data-fallback-test]').hidden=own&&mode==='off';
  }
  function stateOf(box,state,preserveEdits=false){
    box._state=state;
    const enabled=box.querySelector('[data-fallback-enabled]');
    if(enabled&&!preserveEdits)enabled.checked=state.enabled||!state.managed;
    const pick=box.querySelector('[data-fallback-source]');
    if(pick&&!preserveEdits)pick.value=state.key_source;
    keyStatus(box);summary(box,state);
    if(state.error)feedback(box,state.error);
  }
  async function request(box,action,extra={}){
    const response=await fetch('/api/api-fallback',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({provider:box.dataset.provider,agent:box.dataset.agent||'',action,...extra})});
    const result=await response.json();
    if(!response.ok||!result.ok)throw Error(result.error||'Could not update API fallback.');
    return result;
  }
  function busy(box,value){
    box._busy=value;
    for(const button of box.querySelectorAll('[data-fallback-save],[data-fallback-test]'))button.disabled=value;
    box.querySelector('.mc-modal-box').setAttribute('aria-busy',String(value));
  }
  window.mcOpenApiFallback=async function(id){
    const box=document.getElementById(id);if(!box||!box.hidden)return;
    document.body.append(box);
    box.hidden=false;box.style.display='flex';feedback(box,'');
    const generation=box._generation=(box._generation||0)+1;
    box._edited=false;box.oninput=()=>{box._edited=true;};
    box.querySelector('[data-fallback-key]').value='';
    box.querySelector('[data-fallback-remove]').checked=false;
    const dialog=box.querySelector('.mc-modal-box');
    box._releaseFocus=window.mcDialogFocus(dialog,()=>window.mcCloseApiFallback(box),
      dialog.querySelector('h3').textContent,box.querySelector('[data-fallback-source]')||box.querySelector('[data-fallback-key]'));
    busy(box,true);
    try{const result=await request(box,'status');if(generation===box._generation)stateOf(box,result.state,box._edited);}
    catch(error){if(generation===box._generation)feedback(box,error.message||'Could not load API fallback.');}
    finally{if(generation===box._generation)busy(box,false);}
  };
  window.mcCloseApiFallback=function(element){
    const box=boxOf(element);if(!box||box._saving)return;
    box._generation=(box._generation||0)+1;busy(box,false);
    box.querySelector('[data-fallback-key]').value='';
    box.querySelector('[data-fallback-remove]').checked=false;
    box.hidden=true;box.style.display='none';
    box._releaseFocus?.();box._releaseFocus=null;
  };
  window.mcFallbackSource=function(element){
    const box=boxOf(element);
    box._edited=true;
    box.querySelector('[data-fallback-key]').value='';
    box.querySelector('[data-fallback-remove]').checked=false;
    feedback(box,'');keyStatus(box);
  };
  function payload(box){
    const data={key_source:source(box)};
    const key=box.querySelector('[data-fallback-key]');
    if(!key.closest('[hidden]')&&key.value)data.api_key=key.value.trim();
    return data;
  }
  window.mcTestApiFallback=async function(button){
    const box=boxOf(button);if(box._busy)return;
    const generation=box._generation;
    busy(box,true);feedback(box,'Checking the key without starting a model run…');
    try{const result=await request(box,'test',payload(box));if(generation===box._generation)feedback(box,result.message);}
    catch(error){if(generation===box._generation)feedback(box,error.message||'Could not check this API key.');}
    finally{if(generation===box._generation)busy(box,false);}
  };
  window.mcSaveApiFallback=async function(button){
    const box=boxOf(button);if(box._busy)return;
    const data=payload(box),enabled=box.querySelector('[data-fallback-enabled]');
    if(enabled)data.enabled=enabled.checked;
    if(box.querySelector('[data-fallback-remove]').checked){
      delete data.api_key;data.remove_key=true;
      if(enabled&&!box._state?.agent_keys_configured)data.enabled=false;
      if(box.dataset.agent)data.key_source='off';
    }
    box._saving=true;
    box.querySelectorAll('[data-fallback-dismiss]').forEach(button=>{button.disabled=true;});
    busy(box,true);feedback(box,'Saving…');
    try{
      const result=await request(box,'save',data);
      stateOf(box,result.state);
      box.querySelector('[data-fallback-key]').value='';
      box._saving=false;
      if(box.dataset.agent&&!result.state.engine_enabled&&result.state.key_source!=='off'){
        feedback(box,'Saved. Enable Claude API fallback in App Settings to activate it.');
      }else window.mcCloseApiFallback(box);
    }catch(error){feedback(box,error.message||'Could not save API fallback.');}
    finally{box._saving=false;box.querySelectorAll('[data-fallback-dismiss]').forEach(button=>{button.disabled=false;});busy(box,false);}
  };
})();
