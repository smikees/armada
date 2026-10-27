// Navigate immediately; slow local inventory rendering never holds the old page open.
async function mcLoadCapabilities(){
  const box=document.getElementById('cap-content');
  try{
    const response=await fetch('/api/capabilities-content',{cache:'no-store',signal:AbortSignal.timeout(30000)});
    if(!response.ok)throw Error('Could not load capabilities.');
    box.innerHTML=await response.text();
    // Only first-party server markup is accepted here; preserve normal script order.
    for(const old of Array.from(box.querySelectorAll('script'))){
      const script=document.createElement('script');
      for(const attr of old.attributes)script.setAttribute(attr.name,attr.value);
      script.textContent=old.textContent;
      const ready=script.src?new Promise((resolve,reject)=>{script.onload=resolve;script.onerror=reject;}):Promise.resolve();
      old.replaceWith(script);await ready;
    }
  }catch(error){
    box.innerHTML='<div class="mc-cap-loading" role="alert"><p>Could not load capabilities.</p><button class="btn btn-secondary" onclick="location.reload()">Try again</button></div>';
  }
}
mcLoadCapabilities();
