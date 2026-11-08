// Refresh only the sandboxed content frame; keep navigation, focus and page state.
async function mcSnap(index,button,force=true){
  if(button.disabled)return;
  const label=button.innerHTML,status=document.getElementById('mc-snapshot-status');
  button.disabled=true;button.textContent='Refreshing…';
  const controller=new AbortController(),deadline=setTimeout(()=>controller.abort(),30000);
  try{
    let ticket='';
    for(;;){
      const response=await fetch('/api/section-snapshot',{method:'POST',signal:controller.signal,
        headers:{'Content-Type':'application/json'},body:JSON.stringify({index,force,ticket})});
      if(!response.ok)throw Error('The refresh request could not be completed.');
      const result=await response.json();
      if(!result.ok)throw Error(result.error||'The local copy could not be refreshed.');
      if(!result.pending){
        if(result.changed){const frame=document.querySelector('iframe');if(frame){const url=new URL(frame.src);url.searchParams.set('_snapshot',Date.now());frame.src=url.href;}}
        if(status&&result.changed)status.textContent='Local copy updated just now';
        break;
      }
      ticket=result.ticket;
      await new Promise(resolve=>setTimeout(resolve,500));
      if(controller.signal.aborted)throw Error('Refresh is taking longer than expected. Try again to check it.');
    }
  }catch(error){if(status)status.textContent=error.name==='AbortError'?'Refresh is taking longer than expected. Your existing copy is still available.':error.message;}
  finally{clearTimeout(deadline);button.disabled=false;button.innerHTML=label;}
}
const mcSnapshotButton=document.querySelector('[data-snapshot-index]');
if(mcSnapshotButton)mcSnap(Number(mcSnapshotButton.dataset.snapshotIndex),mcSnapshotButton,false);
