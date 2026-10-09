// Update bar (launch plan 5.4).
//
// An installed ARMADA downloads and checks new versions in the background; the new version goes in
// the next time ARMADA starts. People leave the window open for days, so say under the nav that one
// is waiting, and offer to put it in now. Also says when a release needs the new installer, which
// the in-place updater can't do. A development checkout never shows this (its status says
// installed: false).
(function(){
  const BAR='mc-updbar';
  const DISMISSED='armada-dismissed-update';
  let shownVersion='',dismissed='',lastStatus=null;
  try{dismissed=localStorage.getItem(DISMISSED)||'';}catch(e){}
  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function closeButton(d){
    return d.requested||d.phase==='error'?'':'<button type="button" class="mc-x mc-banner-dismiss" aria-label="Dismiss update notification" title="Dismiss update notification" onclick="mcUpdateDismiss()">'+
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg></button>';
  }

  function paint(d){
    lastStatus=d;shownVersion='';
    const el=document.getElementById(BAR); if(!el) return;
    if(!d || !d.installed){ el.innerHTML=""; return; }
    if(d.phase==='error'&&!d.staged){
      el.innerHTML='<div class="mc-banner mc-banner-info" role="alert"><span>Restart needs attention. '+esc(d.message)+'</span></div>';return;
    }
    // Saved availability belongs to an earlier check, possibly before this installer ran.
    // The server compares the candidate with the running version on every status request.
    if(d.newer!==true){ el.innerHTML=""; return; }
    shownVersion=d.staged||(d.status==='needs-installer'?d.latest:'')||'';
    if(shownVersion&&dismissed===shownVersion&&!d.requested&&d.phase!=='error'){el.innerHTML='';return;}
    if(d.staged){
      el.innerHTML='<div class="mc-banner mc-banner-info" role="status">'+
        '<span class="mc-banner-msg">ARMADA v'+esc(d.staged)+' is ready.</span>'+
        '<span id="mc-updbar-sub" class="mc-banner-sub">'+esc(d.message ||
          (d.requested ? 'Preparing update…' : 'It installs the next time ARMADA starts, or now:'))+'</span>'+
        '<span class="mc-banner-act"><button class="btn btn-sm" id="mc-updbar-btn" '+
        (d.requested?'disabled ':'')+'onclick="mcUpdateNow(this,document.getElementById(\'mc-updbar-sub\'))">'+
        'Restart to update</button>'+(d.requested&&d.phase!=='restarting'?'<button class="btn btn-sm" onclick="mcUpdateCancel(this)">Postpone update</button>':'')+closeButton(d)+'</span></div>';
      return;
    }
    if(d.status==='needs-installer' && d.latest){
      el.innerHTML='<div class="mc-banner mc-banner-info" role="status">'+
        '<span class="mc-banner-msg">ARMADA v'+esc(d.latest)+' is out.</span>'+
        '<span class="mc-banner-sub">This one changes more than the app itself, so it comes as a new installer.</span>'+
        '<span class="mc-banner-act"><a class="btn btn-sm" href="'+esc(d.releases)+'" target="_blank" rel="noopener">Get the installer ↗</a>'+closeButton(d)+'</span></div>';
      return;
    }
    el.innerHTML="";
  }

  async function check(){
    try{ const d=await(await fetch('/api/update-status',{cache:'no-store'})).json(); paint(d); return d; }
    catch(e){ return null; }
  }
  window.mcUpdCheck=check;
  window.mcUpdateDismiss=function(){
    if(!shownVersion||!lastStatus||lastStatus.requested||lastStatus.phase==='error')return;
    dismissed=shownVersion;
    try{localStorage.setItem(DISMISSED,dismissed);}catch(e){}
    paint(lastStatus);
  };
  window.addEventListener('storage',function(e){
    if(e.key===DISMISSED){dismissed=e.newValue||'';paint(lastStatus);}
  });
  window.mcUpdateCancel=async function(btn){
    btn.disabled=true;
    try{const d=await(await fetch('/api/update-cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
      if(!d.ok)throw Error(d.error);await check();
    }catch(e){btn.disabled=false;document.getElementById('mc-updbar-sub').textContent=e.message;}
  };

  // Put the waiting version in place and come back on it. Used by this bar and by Settings.
  // The window and scheduler restart when idle. The stable launcher then replaces the package
  // after every process using the old version has exited. Both
  // end the same way: the server comes back reporting the new version, and the page reloads.
  window.mcUpdateNow=async function(btn,msg){
    const say=function(t){ if(msg) msg.textContent=t; };
    if(btn) btn.disabled=true;
    say('updating…');
    let r;
    try{ r=await(await fetch('/update',{method:'POST'})).json(); }
    catch(e){ say('error: '+e); if(btn) btn.disabled=false; return; }
    if(!r.ok){ say(r.error||r.out||"Couldn't update."); if(btn) btn.disabled=false; return; }
    if((r.restart && !r.waiting) || r.applied || r.out!==undefined){
      say('restarting…');
      try{ await fetch('/restart',{method:'POST'}); }catch(e){}
    }else{
      say(r.message || 'Preparing update…');
    }
    const want=r.version||'';
    const started=Date.now();
    const t=setInterval(async function(){
      try{
        const s=await(await fetch('/api/update-status',{cache:'no-store'})).json();
        if(!want || s.version===want){ clearInterval(t); location.reload(); }
        else { say(s.message || 'Preparing update…'); }
      }catch(e){ /* restarting: the server is briefly away */ }
      if(Date.now()-started>15*60000){ clearInterval(t);
        say('still waiting — it will install when ARMADA next restarts.'); if(btn) btn.disabled=false; }
    },1500);
  };

  check();
  setInterval(function(){ if(!document.hidden) check(); }, 5000);
})();
