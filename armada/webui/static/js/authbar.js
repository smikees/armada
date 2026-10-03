// Claude sign-in notification: show once per Armada session, with an explicit dismiss action.
// The server's session ID changes on app restart. Remembering it across page loads means polling,
// navigation and realm switches cannot bring back an already-seen notice. Sign-in remains in Settings.
// The Sign in button starts Claude Code's own flow; ARMADA only asks about the result.
(function(){
  const BAR='mc-authbar', SEEN='mc_claude_auth_notice_seen';
  let polling=null, announced=false, shownSession=null, visibleSession=null;

  function wasShown(d){
    const session=d.app_session||'browser-session';
    if(shownSession===session)return true;
    try{return (d.app_session?localStorage:sessionStorage).getItem(SEEN)===session;}catch(e){return false;}
  }
  function remember(d){
    shownSession=d.app_session||'browser-session';
    try{(d.app_session?localStorage:sessionStorage).setItem(SEEN,shownSession);}catch(e){}
  }

  window.mcAuthDismiss=function(){
    const el=document.getElementById(BAR);if(el)el.innerHTML='';
    visibleSession=null;
  };

  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

  function paint(d){
    const el=document.getElementById(BAR); if(!el) return;
    if(!d)return;
    if(d.logged_in||d.enabled===false||d.notice_enabled===false){window.mcAuthDismiss();return;}
    const session=d.app_session||'browser-session';
    // Keep an open notice (and any login progress) intact while polling. Once closed, stay quiet.
    if(wasShown(d)){
      if(visibleSession!==session)window.mcAuthDismiss();
      return;
    }
    remember(d);visibleSession=session;
    const cliMissing = d.reason==='cli-missing';
    const title=cliMissing ? 'Claude CLI is unavailable' : 'Claude Code is signed out';
    const msg=cliMissing ? "ARMADA can't find the Claude CLI, so Claude agents can't run."
      : "Claude agents can't run and Claude usage can't be read. You can sign in now or later in Settings.";
    const action = cliMissing ? "" :
      '<button class="btn btn-primary" id="mc-authbtn" style="font-size:12.5px;padding:5px 13px;color:#fff" '+
      'onclick="mcAuthLogin(this)">Sign in to Claude</button>';
    el.innerHTML =
      '<div class="mc-auth-notice" role="status" aria-live="polite">'+
      '<div class="mc-auth-notice-head"><span>'+esc(title)+'</span>'+
      '<button type="button" class="mc-iconbtn" aria-label="Dismiss Claude sign-in notification" '+
      'title="Dismiss for this app session" onclick="mcAuthDismiss()">×</button></div>'+
      '<p>'+esc(msg)+'</p><div class="mc-auth-notice-actions">'+action+
      '<span id="mc-authmsg" class="mc-banner-sub"></span></div></div>';
  }

  async function check(force){
    try{
      const r=await(await fetch('/api/auth-status'+(force?'?force=1':''),{cache:'no-store'})).json();
      paint(r);
      return r;
    }catch(e){ return null; }
  }
  window.mcAuthCheck=check;

  // After launching the flow, poll until the CLI reports signed in. The owner may take a while in
  // the browser, so poll for a few minutes and then stop rather than hammering forever.
  function startPolling(){
    if(polling) clearInterval(polling);
    const started=Date.now();
    polling=setInterval(async function(){
      const r=await check(true);
      const m=document.getElementById('mc-authmsg');
      if(r && r.logged_in){
        clearInterval(polling); polling=null;
        if(!announced){announced=true;location.reload();}   // repaint the app with usage restored
        return;
      }
      if(Date.now()-started>4*60*1000){ clearInterval(polling); polling=null;
        if(m) m.textContent='Still signed out — finish in the window that opened, then click Sign in again.'; }
    },3000);
  }

  window.mcAuthLogin=async function(btn){
    const m=document.getElementById('mc-authmsg');
    if(btn) btn.disabled=true;
    if(m) m.textContent='opening the Claude sign-in window…';
    try{
      const r=await(await fetch('/api/auth-login',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
      if(!r.ok){ if(m) m.textContent=r.error||'Could not start sign-in.'; if(btn) btn.disabled=false; return; }
      if(m) m.textContent='complete the sign-in in your browser — this notice clears itself';
      startPolling();
    }catch(e){ if(m) m.textContent='Could not start sign-in: '+e; if(btn) btn.disabled=false; }
  };

  check();
  setInterval(function(){ if(!document.hidden && !polling) check(); }, 60000);
  document.addEventListener('visibilitychange',function(){ if(!document.hidden && !polling) check(); });
})();
