// The destination document owns its loading state. Its heading and controls stay put.
(async function(){
  const box=document.getElementById('mc-page-content');if(!box)return;
  try{
    const response=await fetch(box.dataset.endpoint,{cache:'no-store',signal:AbortSignal.timeout(30000)});
    if(!response.ok)throw Error('Could not load this page.');
    box.innerHTML=await response.text();
    // Authenticated first-party markup only, in the same order as a normal page load.
    for(const old of Array.from(box.querySelectorAll('script'))){
      const script=document.createElement('script');
      for(const attr of old.attributes)script.setAttribute(attr.name,attr.value);
      script.textContent=old.textContent;
      const ready=script.src?new Promise((resolve,reject)=>{script.onload=resolve;script.onerror=reject;}):Promise.resolve();
      old.replaceWith(script);await ready;
    }
    document.querySelectorAll('[data-page-controls]').forEach(el=>{if(el.style.visibility!=='hidden')el.inert=false;});
    document.dispatchEvent(new Event('armada:page-ready'));
  }catch(error){
    box.innerHTML='<div class="mc-list-loading" role="alert">Could not load this page. '
      +'<button type="button" class="btn btn-secondary btn-sm" onclick="location.reload()">Try again</button></div>';
  }finally{box.setAttribute('aria-busy','false');}
})();
