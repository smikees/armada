// Claude sign-in banner.
//
// A lapsed Claude Code session stops everything — every agent run fails to authenticate and usage
// goes dark — so this sits under the nav on every page rather than hiding in a corner of Overview.
// The Sign in button starts Claude Code's OWN login in its own window; the owner completes it in
// their browser and Claude Code writes its own credentials. ARMADA never sees a token, it only
// re-asks "are you signed in?" until the answer changes.
(function(){
  const BAR='mc-authbar';
  let polling=null, announced=false;

  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

  function paint(d){
    const el=document.getElementById(BAR); if(!el) return;
    if(!d || d.logged_in){ el.innerHTML=""; return; }
    const cliMissing = d.reason==='cli-missing';
    const msg = cliMissing
      ? "ARMADA can't find the Claude CLI, so agents can't run."
      : "Claude Code is signed out — agents can't run and usage can't be read.";
    const action = cliMissing ? "" :
      '<button class="btn btn-primary" id="mc-authbtn" style="font-size:12.5px;padding:5px 13px;color:#fff" '+
      'onclick="mcAuthLogin(this)">Sign in to Claude</button>';
    el.innerHTML =
      '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:9px 16px;'+
      'background:color-mix(in srgb,var(--status-bad) 12%,var(--color-bg));'+
      'border-bottom:1px solid color-mix(in srgb,var(--status-bad) 35%,transparent)">'+
      '<span style="font-size:12.5px;font-weight:600">'+esc(msg)+'</span>'+
      '<span id="mc-authmsg" style="font-size:11.5px;color:var(--text-muted)"></span>'+
      '<span style="margin-left:auto;display:flex;gap:8px;align-items:center">'+action+'</span></div>';
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
      if(m) m.textContent='complete the sign-in in your browser — this banner clears itself';
      startPolling();
    }catch(e){ if(m) m.textContent='Could not start sign-in: '+e; if(btn) btn.disabled=false; }
  };

  check();
  setInterval(function(){ if(!document.hidden && !polling) check(); }, 60000);
  document.addEventListener('visibilitychange',function(){ if(!document.hidden && !polling) check(); });
})();
