// Scheduler banner (launch plan 5.5).
//
// Scheduled jobs are fired by a separate background process, so the window being open says nothing
// about whether they'll run. When that process isn't running and this realm has jobs on a schedule,
// say so under the nav on every page — the failure it prevents is "my jobs silently stopped".
// Nothing to say when the realm has no scheduled jobs: a bar about nothing teaches people to ignore
// bars.
(function(){
  const BAR='mc-schedbar';
  let polling=null;

  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

  function paint(d){
    const el=document.getElementById(BAR); if(!el) return;
    if(!d || d.running || !d.scheduled){ el.innerHTML=""; return; }
    const n=d.scheduled;
    const msg="The scheduler isn't running — "+n+" scheduled job"+(n===1?"":"s")+" won't run until it is.";
    el.innerHTML =
      '<div class="mc-banner mc-banner-warn" role="status">'+
      '<span class="mc-banner-msg">'+esc(msg)+'</span>'+
      '<span id="mc-schedmsg" class="mc-banner-sub"></span>'+
      '<span class="mc-banner-act"><button class="btn btn-sm" id="mc-schedbtn" '+
      'onclick="mcSchedStart(this)">Start it</button></span></div>';
  }

  async function check(){
    try{
      const r=await(await fetch('/api/scheduler-status',{cache:'no-store'})).json();
      paint(r);
      return r;
    }catch(e){ return null; }
  }
  window.mcSchedCheck=check;

  window.mcSchedStart=async function(btn){
    const m=document.getElementById('mc-schedmsg');
    if(btn) btn.disabled=true;
    if(m) m.textContent='starting…';
    try{
      const r=await(await fetch('/api/scheduler-start',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
      if(!r.ok){ if(m) m.textContent=r.error||"Couldn't start the scheduler."; if(btn) btn.disabled=false; return; }
      // A new scheduler takes a moment to claim its realms; poll briefly until it has.
      const started=Date.now();
      if(polling) clearInterval(polling);
      polling=setInterval(async function(){
        const s=await check();
        if(s && s.running){ clearInterval(polling); polling=null; return; }
        if(Date.now()-started>30000){ clearInterval(polling); polling=null;
          const mm=document.getElementById('mc-schedmsg'), b=document.getElementById('mc-schedbtn');
          if(mm) mm.textContent="It didn't start. See Help → Troubleshooting.";
          if(b) b.disabled=false; }
      },2000);
    }catch(e){ if(m) m.textContent="Couldn't start the scheduler: "+e; if(btn) btn.disabled=false; }
  };

  check();
  setInterval(function(){ if(!document.hidden && !polling) check(); }, 60000);
  document.addEventListener('visibilitychange',function(){ if(!document.hidden && !polling) check(); });
})();
