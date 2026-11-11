async function mcSaveRunControls(button){
  const box=button.closest('.mc-run-controls'), feedback=box.querySelector('[data-run-feedback]');
  const values={};
  for(const input of box.querySelectorAll('[data-run-control]')){
    const key=input.dataset.runControl.replace(/^rp-(global|agent|realm)-/,'');
    values[key]=input.value===''?'':input.type==='number'?Number(input.value):input.value;
  }
  const payload={values,agent:box.dataset.agent||'',global_provider:box.dataset.global==='true'};
  const key=box.querySelector('[data-api-key]'),clear=box.querySelector('[data-clear-key]');
  if(clear?.checked)payload.api_key='';else if(key?.value)payload.api_key=key.value;
  button.disabled=true;feedback.textContent='Saving…';
  try{
    const response=await fetch('/api/run-controls',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const result=await response.json();
    feedback.textContent=result.ok?'Saved.':result.error||'Could not save run controls.';
    if(result.ok&&key)key.value='';
    if(result.ok&&clear)clear.checked=false;
  }catch(e){feedback.textContent='Could not save run controls. Check the connection and try again.';}
  finally{button.disabled=false;}
}

async function mcWorkerAction(button,action){
  const box=button.closest('.mc-worker-controls'),feedback=box.querySelector('[data-worker-state]');
  const payload={action};
  if(action==='setup')payload.folders=box.querySelector('[data-worker-folders]').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
  button.disabled=true;
  feedback.textContent=action==='setup'?'Waiting for Windows account setup. Accept the Windows administrator prompt to continue.':'Checking the worker…';
  try{
    for(let attempt=0;attempt<120;attempt++){
      const response=await fetch('/api/worker',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(attempt?{action:'status'}:payload)});
      const result=await response.json();
      if(!result.ok)throw Error(result.error||'Worker setup failed.');
      if(!result.pending){feedback.textContent=result.ready?'Worker ready. Provider sign-ins and local connectors use this account.':result.error||'Worker is not set up.';return;}
      await new Promise(resolve=>setTimeout(resolve,2000));
    }
    feedback.textContent='Setup is still pending. Recheck this page after the Windows prompt finishes.';
  }catch(error){feedback.textContent=error.message||'Could not check worker setup.';}
  finally{button.disabled=false;}
}
function mcSetupWorker(button){return mcWorkerAction(button,'setup');}
function mcVerifyWorker(button){return mcWorkerAction(button,'verify');}
