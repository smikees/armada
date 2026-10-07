// Recovery belongs to the desktop supervisor, including while hidden in the tray.
// The UI reports only failures that need the owner's action, not normal startup.
(function(){
  const BAR='mc-schedbar';
  let timer=null,busy=false;
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function paint(d){
    const el=document.getElementById(BAR);if(!el)return;
    if(!d||d.running||!d.scheduled||d.action_required===false){el.innerHTML='';return;}
    const n=d.scheduled;
    const prefix=d.recovery==='disabled'?'Automatic scheduler startup is turned off':
      d.recovery==='failed'?"ARMADA couldn't restart the scheduler automatically":"The scheduler isn't running";
    const msg=prefix+' — '+n+' scheduled job'+(n===1?'':'s')+" won't run until it is.";
    el.innerHTML='<div class="mc-banner mc-banner-warn" role="status">'+
      '<span class="mc-banner-msg">'+esc(msg)+'</span>'+
      '<span id="mc-schedmsg" class="mc-banner-sub">'+esc(d.error||'')+'</span>'+
      '<span class="mc-banner-act"><button class="btn btn-sm" id="mc-schedbtn" '+
      'onclick="mcSchedStart(this)">'+(d.recovery==='failed'?'Retry':'Start it')+'</button></span></div>';
  }
  async function check(){
    if(busy)return null;
    busy=true;
    let reading=null;
    try{
      const response=await fetch('/api/scheduler-status',{cache:'no-store'});
      if(!response.ok)throw Error('Scheduler status unavailable.');
      reading=await response.json();paint(reading);
      return reading;
    }catch(e){return null;}
    finally{
      busy=false;clearTimeout(timer);
      const recovering=reading&&!reading.running&&reading.action_required===false&&reading.recovery!=='paused';
      timer=setTimeout(()=>{if(!document.hidden)check();else timer=setTimeout(check,60000);},recovering?2000:60000);
    }
  }
  window.mcSchedCheck=check;
  window.mcSchedStart=async function(btn){
    const message=document.getElementById('mc-schedmsg');
    if(btn)btn.disabled=true;
    if(message)message.textContent='Starting…';
    try{
      const response=await fetch('/api/scheduler-start',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      const result=await response.json();
      if(!response.ok||!result.ok)throw Error(result.error||"Couldn't start the scheduler.");
      await check();
    }catch(error){if(message)message.textContent=error.message;if(btn)btn.disabled=false;}
  };
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)check();});
  check();
})();
