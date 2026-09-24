// Update bar (launch plan 5.4).
//
// An installed ARMADA downloads and checks new versions in the background; the new version goes in
// the next time ARMADA starts. People leave the window open for days, so say under the nav that one
// is waiting, and offer to put it in now. Also says when a release needs the new installer, which
// the in-place updater can't do. A development checkout never shows this (its status says
// installed: false).
(function(){
  const BAR='mc-updbar';
  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

  function paint(d){
    const el=document.getElementById(BAR); if(!el) return;
    if(!d || !d.installed){ el.innerHTML=""; return; }
    if(d.staged){
      el.innerHTML='<div class="mc-banner mc-banner-info" role="status">'+
        '<span class="mc-banner-msg">ARMADA v'+esc(d.staged)+' is ready.</span>'+
        '<span id="mc-updbar-sub" class="mc-banner-sub">'+(d.requested
          ?'Installing as soon as the running jobs finish…'
          :'It installs the next time ARMADA starts, or now:')+'</span>'+
        '<span class="mc-banner-act"><button class="btn btn-sm" id="mc-updbar-btn" '+
        (d.requested?'disabled ':'')+'onclick="mcUpdateNow(this,document.getElementById(\'mc-updbar-sub\'))">'+
        'Restart to update</button></span></div>';
      return;
    }
    if(d.status==='needs-installer' && d.latest){
      el.innerHTML='<div class="mc-banner mc-banner-info" role="status">'+
        '<span class="mc-banner-msg">ARMADA v'+esc(d.latest)+' is out.</span>'+
        '<span class="mc-banner-sub">This one changes more than the app itself, so it comes as a new installer.</span>'+
        '<span class="mc-banner-act"><a class="btn btn-sm" href="'+esc(d.releases)+'" target="_blank" rel="noopener">Get the installer ↗</a></span></div>';
      return;
    }
    el.innerHTML="";
  }

  async function check(){
    try{ const d=await(await fetch('/api/update-status',{cache:'no-store'})).json(); paint(d); return d; }
    catch(e){ return null; }
  }
  window.mcUpdCheck=check;

  // Put the waiting version in place and come back on it. Used by this bar and by Settings.
  // Either this window's server swaps the folder itself (then restarts), or — when the scheduler is
  // running — the scheduler does it at its next quiet moment and restarts the window after. Both
  // end the same way: the server comes back reporting the new version, and the page reloads.
  window.mcUpdateNow=async function(btn,msg){
    const say=function(t){ if(msg) msg.textContent=t; };
    if(btn) btn.disabled=true;
    say('updating…');
    let r;
    try{ r=await(await fetch('/update',{method:'POST'})).json(); }
    catch(e){ say('error: '+e); if(btn) btn.disabled=false; return; }
    if(!r.ok){ say(r.error||r.out||"Couldn't update."); if(btn) btn.disabled=false; return; }
    if(r.applied || r.out!==undefined){             // swapped here (or a git pull): restart now
      say('restarting…');
      try{ await fetch('/restart',{method:'POST'}); }catch(e){}
    }else{
      say('installing as soon as the running jobs finish…');
    }
    const want=r.version||'';
    const started=Date.now();
    const t=setInterval(async function(){
      try{
        const s=await(await fetch('/api/update-status',{cache:'no-store'})).json();
        if(!want || s.version===want){ clearInterval(t); location.reload(); }
      }catch(e){ /* restarting: the server is briefly away */ }
      if(Date.now()-started>15*60000){ clearInterval(t);
        say('still waiting — it will install when ARMADA next restarts.'); if(btn) btn.disabled=false; }
    },1500);
  };

  check();
  setInterval(function(){ if(!document.hidden) check(); }, 10*60000);
})();
