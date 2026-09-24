let mcSetIcon='';
function mcSetTab(t){['realm','user','app'].forEach(function(x){
    var p=document.getElementById('st-'+x+'-pane');if(p)p.style.display=(x===t)?'block':'none';
    var b=document.getElementById('st-tab-'+x);if(b)b.style.borderBottomColor=(x===t)?'var(--color-accent)':'transparent';});
  try{localStorage.setItem('mc-settab',t);}catch(e){}}
(function(){try{var t=localStorage.getItem('mc-settab');if(t)mcSetTab(t);}catch(e){}})();
function mcPickSetIcon(el){mcSetIcon=el.dataset.icon;
  document.querySelectorAll('.mc-seticon').forEach(s=>s.style.background=s.dataset.icon===mcSetIcon?'var(--text-12)':'');
  const cur=document.getElementById('st-iconcur');if(cur)cur.innerHTML=el.innerHTML;}
async function mcSaveRealmSettings(){const m=document.getElementById('st-msg');m.textContent='saving…';
  const provs=[...document.querySelectorAll('.st-prov:checked')].map(function(c){return c.value;});
  const p={providers:provs,provider:provs[0]||'claude',
    name:(document.getElementById('st-realmname')||{}).value||'',
    default_model:document.getElementById('st-model').value,
    default_effort:document.getElementById('st-effort').value,
    default_fallback_model:document.getElementById('st-fallback').value,
    default_max_budget_usd:document.getElementById('st-maxbudget').value,icon:mcSetIcon||'',
    timezone:(document.getElementById('st-tz')||{}).value||'',
    default_verbosity:(document.getElementById('st-verbosity')||{}).value||'',
    inbox:mcA2APayload(),
    notifications:mcNotifPayload()};
  try{const r=await(await fetch('/api/save-realm-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
// --- Telegram -----------------------------------------------------------------
// Each step reloads on success: the panel is a state machine (no token → token but no chat →
// connected) and re-rendering it server-side is simpler and less wrong than patching it here.
function mcTgMsg(t,bad){const m=document.getElementById('st-tg-msg');if(!m)return;
  m.textContent=t||'';m.style.color=bad?'var(--status-bad)':'var(--text-muted)';}
async function mcTgPost(url,body,btn,working){
  if(btn)btn.disabled=true; mcTgMsg(working||'working…');
  try{const r=await(await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify(body||{})})).json();
    if(btn)btn.disabled=false;
    if(!r.ok){mcTgMsg(r.error||'That didn\'t work.',true);return null;}
    return r;
  }catch(e){if(btn)btn.disabled=false;mcTgMsg('Could not reach ARMADA: '+e,true);return null;}}
async function mcTgToken(btn){
  const el=document.getElementById('st-tg-token');const v=(el&&el.value||'').trim();
  if(!v){mcTgMsg('Paste the token BotFather gave you.',true);return;}
  const r=await mcTgPost('/api/telegram-token',{token:v},btn,'checking the token with Telegram…');
  if(r){if(el)el.value='';location.reload();}}
async function mcTgEnv(btn){
  const el=document.getElementById('st-tg-env');const v=(el&&el.value||'').trim();
  if(!v){mcTgMsg('Give the path to the file holding the token.',true);return;}
  const r=await mcTgPost('/api/telegram-env',{path:v},btn,'reading that file…');
  if(r)location.reload();}
async function mcTgLink(btn){
  const r=await mcTgPost('/api/telegram-link',{},btn,'looking for your message…');
  if(r)location.reload();}
async function mcTgTest(btn){
  const r=await mcTgPost('/api/notify-test',{channel:'telegram'},btn,'sending…');
  if(r)mcTgMsg('Sent — check Telegram.');}
async function mcTgForget(btn){
  if(!await mcConfirm('Disconnect Telegram?',
      'ARMADA will forget the bot and stop answering messages. Your bot itself is untouched.',
      {confirm:'Disconnect',danger:true}))return;
  const r=await mcTgPost('/api/telegram-forget',{},btn,'disconnecting…');
  if(r)location.reload();}
// --- agent-to-agent defaults -----------------------------------------------
// The realm switch plus the two values every agent inherits when its own setting says "inherit".
// Returns undefined if the section isn't on the page, so an older layout can't clear the settings.
function mcA2APayload(){
  const t=document.getElementById('st-a2a');
  if(!t)return undefined;
  return {enabled:t.checked,
          cadence:(document.getElementById('st-a2a-cadence')||{}).value||'',
          accepts:(document.getElementById('st-a2a-accepts')||{}).value||''};}
// --- desktop notifications -------------------------------------------------
// The event x channel grid. Sent whole so unticking the last box in a row persists as "off"
// instead of falling back to the default and switching itself back on.
function mcNotifPayload(){
  const boxes=document.querySelectorAll('.st-notif');
  if(!boxes.length)return undefined;              // section not rendered
  const m={};
  boxes.forEach(function(c){
    const ev=c.dataset.ev,ch=c.dataset.ch;
    (m[ev]=m[ev]||{})[ch]=c.checked;});
  const x=document.getElementById('st-notif-cross');
  return x?{matrix:m,cross_realm:x.checked}:{matrix:m};}
// Clicking a column heading ticks the whole column, or clears it if it's already full — the usual
// select-all behaviour, without needing a separate control per column.
function mcNotifCol(ch){
  const boxes=[...document.querySelectorAll('.st-notif[data-ch="'+ch+'"]')];
  if(!boxes.length)return;
  const target=!boxes.every(function(c){return c.checked;});
  boxes.forEach(function(c){c.checked=target;});}
async function mcNotifTest(b,ch){const m=document.getElementById('st-notif-msg');
  b.disabled=true;m.style.color='var(--text-muted)';m.textContent='sending…';
  try{const r=await(await fetch('/api/notify-test',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({channel:ch||'desktop'})})).json();
    if(r.ok){m.textContent='sent'+(r.detail?' — '+r.detail:'');
      // ring the bell straight away rather than waiting for its next poll
      if(window.mcBellRefresh)window.mcBellRefresh();}
    else{m.style.color='var(--status-bad)';m.textContent=r.error||'could not send';}}
  catch(e){m.style.color='var(--status-bad)';m.textContent='error: '+e;}
  b.disabled=false;}
// --- realm lifecycle -------------------------------------------------------------------------
function mcRealmSay(t,bad){const m=document.getElementById('st-msg');
  if(!m)return; m.style.color=bad?'var(--status-bad)':'var(--text-muted)'; m.textContent=t;}
async function mcRealmExport(b){
  b.disabled=true;mcRealmSay('building the archive — this can take a moment…');
  try{const r=await(await fetch('/api/realm-export',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
    if(r.ok&&r.skipped_n){const mb=(r.bytes/1048576).toFixed(1);const s=(r.skipped||[]).slice(0,3).join(', ');
      // A partial archive still reports ok — say so plainly rather than let a success message
      // stand in for a backup that is missing files.
      mcRealmSay('exported '+r.files+' files ('+mb+' MB), but '+r.skipped_n+' could not be read and '+
        'are NOT in the archive: '+s+(r.skipped_n>3?', …':'')+' — close anything using them and export again',true);}
    else if(r.ok){const mb=(r.bytes/1048576).toFixed(1);
      const sec=(r.secrets_left_out||[]);
      mcRealmSay('exported '+r.files+' files ('+mb+' MB) — shown in your file manager'+
        (sec.length?'. Left out because they hold keys or passwords: '+sec.slice(0,3).join(', ')+(sec.length>3?', …':''):''));}
    else mcRealmSay(r.error||'export failed',true);}
  catch(e){mcRealmSay('export failed: '+e,true);}
  b.disabled=false;}
async function mcRealmArchive(b,path){
  if(!await mcConfirmBox('Archive this realm?',
      'It disappears from ARMADA\'s realm list. No files are touched — the folder stays exactly '+
      'where it is, and you can add it back later with + New realm.','Archive',false))return;
  b.disabled=true;
  try{const r=await(await fetch('/api/realm-archive',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:path})})).json();
    if(r.ok){mcRealmSay('archived — removed from the list');setTimeout(function(){location.reload();},700);}
    else mcRealmSay(r.error||'could not archive',true);}
  catch(e){mcRealmSay('could not archive: '+e,true);}
  b.disabled=false;}
async function mcRealmDelete(b,path,name){
  const typed=await mcConfirmBox('Delete this realm?',
    'This deletes the folder and everything in it — every agent\'s memory, every thread, every '+
    'artefact. On Windows it goes to the Recycle Bin, but nothing in ARMADA will bring it back.\n\n'+
    'Export it first if you might want it later.','Delete realm',true,name);
  if(!typed)return;
  b.disabled=true;mcRealmSay('deleting…');
  try{const r=await(await fetch('/api/realm-delete',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:path,confirm:typed})})).json();
    if(r.ok){mcRealmSay(r.recycled?'deleted — it\'s in your Recycle Bin':'deleted');
      setTimeout(function(){location.reload();},900);}
    else mcRealmSay(r.error||'could not delete',true);}
  catch(e){mcRealmSay('could not delete: '+e,true);}
  b.disabled=false;}
// Thin adapter onto the app's shared dialog (confirm.js, loaded on every page) so realm actions
// and everything else use one implementation. With `mustType`, the button stays dead until the
// name is typed back — a mis-click can't reach the destructive path.
function mcConfirmBox(title,detail,okLabel,danger,mustType){
  return window.mcConfirm(title,detail,{ok:okLabel,danger:danger,mustType:mustType});
}
// --- app root ----------------------------------------------------------------------------------
// Saving re-runs the preflight for the realm you're looking at, because moving the root can put
// that realm outside it — better to say so immediately than at 03:00.
async function mcRootSave(b){
  const inp=document.getElementById('st-approot'),m=document.getElementById('st-approot-msg');
  if(!inp||!m)return; b.disabled=true; m.style.color='var(--text-muted)'; m.textContent='saving…';
  try{
    const r=await(await fetch('/api/set-approot',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({root:inp.value.trim()})})).json();
    if(!r.ok){m.style.color='var(--status-bad)';m.textContent=r.error||'could not save';}
    else{
      const pf=r.preflight||{};
      if(!inp.value.trim()){m.style.color='var(--status-warn)';
        m.textContent='Cleared — set a root folder before adding a realm.';}
      else if(pf.held){m.style.color='var(--status-bad)';
        m.textContent='Saved, but this realm can’t run: '+(pf.summary||'');}
      else{m.style.color='var(--text-muted)';m.textContent='Saved. Every realm lives in here.';}
    }
  }catch(e){m.style.color='var(--status-bad)';m.textContent='error: '+e;}
  b.disabled=false;}
// --- workspace root ---------------------------------------------------------------------------
// The one machine-specific thing a realm carries. Saving it re-runs the preflight server-side, so
// pointing a restored realm at the right folder lifts the scheduler hold in the same click.
async function mcWsSave(b){
  const inp=document.getElementById('st-ws'),m=document.getElementById('st-ws-msg');
  if(!inp||!m)return; b.disabled=true; m.style.color='var(--text-muted)'; m.textContent='saving…';
  try{
    const r=await(await fetch('/api/set-workspace',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({workspace:inp.value.trim()})})).json();
    if(!r.ok){m.style.color='var(--status-bad)';m.textContent=r.error||'could not save';}
    else{
      const pf=r.preflight||{};
      if(!inp.value.trim()) {m.style.color='var(--text-muted)';m.textContent='Cleared.';}
      else if(pf.held){m.style.color='var(--status-bad)';
        m.textContent='Saved, but this realm still can’t run: '+(pf.summary||'');}
      else {m.style.color='var(--text-muted)';
        m.textContent='Saved. '+((pf.warnings&&pf.warnings.length)?pf.summary:'This realm is ready to run.');}
    }
  }catch(e){m.style.color='var(--status-bad)';m.textContent='error: '+e;}
  b.disabled=false;}

// Rewrites the owner's own prompt text across every job, so it previews first and says exactly
// what it would touch. App-native dialog, like every other confirmation.
async function mcWsMigrate(b){
  const m=document.getElementById('st-ws-mig'); b.disabled=true;
  m.style.color='var(--text-muted)'; m.textContent='checking…';
  try{
    const p=await(await fetch('/api/workspace-migrate',{method:'POST',
      headers:{'Content-Type':'application/json'},body:'{}'})).json();
    if(!p.ok){m.style.color='var(--status-bad)';m.textContent=p.error||'nothing to do';b.disabled=false;return;}
    if(!p.refs){m.textContent='Nothing to change — no job uses a full path.';b.disabled=false;return;}
    const top=(p.files||[]).slice(0,8).map(f=>'  • '+f.path+'  ('+f.refs+')').join('\n');
    const more=(p.files||[]).length>8?('\n  …and '+((p.files||[]).length-8)+' more'):'';
    const bad=(p.failed||[]).length?('\n\nSkipped (would not stay valid): '+p.failed.map(f=>f.path).join(', ')):'';
    m.textContent='';
    const go=await window.mcConfirm('Make '+p.refs+' path references portable?',
      'Replaces '+p.root+' with {workspace} in '+p.changed+' job file(s). ARMADA fills the real '+
      'folder in when each job runs, so the jobs keep working here and also work if this realm '+
      'moves to another computer.\n\n'+top+more+bad+
      '\n\nThread history and memory are left exactly as they are.',{ok:'Rewrite '+p.changed+' file(s)'});
    if(!go){b.disabled=false;return;}
    m.textContent='rewriting…';
    const r=await(await fetch('/api/workspace-migrate',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({apply:true,old_root:p.root})})).json();
    m.style.color=r.ok?'var(--text-muted)':'var(--status-bad)';
    m.textContent=r.ok?('Done — '+r.refs+' reference(s) in '+r.changed+' job(s) now use {workspace}.')
                      :(r.error||'failed');
  }catch(e){m.style.color='var(--status-bad)';m.textContent='error: '+e;}
  b.disabled=false;}
async function mcUpd(b){const m=document.getElementById("mc-updmsg");m.textContent="pulling…";
  try{const j=await(await fetch("/update",{method:"POST"})).json();m.textContent=(j.ok?"updated — restarting…":(j.out||"no remote")+" — restarting…");
  await fetch("/restart",{method:"POST"});let n=0;const t=setInterval(async()=>{n++;try{await fetch("/api/realm");clearInterval(t);location.reload();}catch(e){if(n>40){clearInterval(t);m.textContent="reload manually";}}},400);}catch(e){m.textContent="error: "+e;}}
// Restart the local server in place (re-exec) so it reloads the current on-disk code. No git pull —
// this is the path for local development / when no update channel is configured.
async function mcRestart(b){const m=document.getElementById("mc-updcheck");if(b)b.disabled=true;m.style.color="var(--text-muted)";m.textContent="restarting…";
  try{await fetch("/restart",{method:"POST"});}catch(e){}
  let n=0;const t=setInterval(async()=>{n++;try{await fetch("/api/realm",{cache:"no-store"});clearInterval(t);location.reload();}catch(e){if(n>50){clearInterval(t);m.textContent="taking longer than expected — reload manually";if(b)b.disabled=false;}}},400);}
function mcChangelog(show){const m=document.getElementById('mc-changelog');if(m)m.style.display=show?'flex':'none';}
async function mcCheckUpd(b){const m=document.getElementById('mc-updcheck');m.textContent='checking…';b.disabled=true;
  try{const j=await(await fetch('/api/check-update')).json();
    if(j.newer){m.textContent='';m.style.color='var(--color-accent)';
      const box=document.getElementById('mc-updbox');box.style.display='block';
      const um=document.getElementById('mc-updmsg');um.textContent=(j.behind?('v'+(j.latest||'?')+' available — '+j.behind+' commit(s) behind'):'a newer version is available');}
    else if(j.error){var e=j.error;var local=/upstream|remote/i.test(e);m.textContent=local?'local build — no update channel (use Restart to load local changes)':('error: '+e);m.style.color='var(--text-muted)';}
    else{m.textContent="you're up to date ✓";m.style.color='var(--text-muted)';}
  }catch(e){m.textContent='error: '+e;}b.disabled=false;}
// --- scroll preservation across the reloads that apply a theme / colour mode ----------------
// Applying a theme re-renders the whole page, which otherwise drops you back at the top — with
// the theme picker near the bottom of Settings, that means losing your place on every click.
function mcScroller(){
  const d=document.scrollingElement||document.documentElement;
  if(d&&d.scrollHeight>d.clientHeight+2)return d;
  let best=null;                       // otherwise find the real scrolling container
  document.querySelectorAll('div').forEach(function(el){
    const o=getComputedStyle(el).overflowY;
    if((o==='auto'||o==='scroll')&&el.scrollHeight>el.clientHeight+2&&
       (!best||el.scrollHeight>best.scrollHeight))best=el;});
  return best||d;}
function mcKeepScroll(){try{sessionStorage.setItem('mc-setscroll',String(mcScroller().scrollTop));}catch(e){}}
(function(){try{
  const v=sessionStorage.getItem('mc-setscroll');
  if(v===null)return;
  sessionStorage.removeItem('mc-setscroll');
  const y=parseInt(v,10)||0;
  // wait two frames so fonts/layout have settled, or we'd scroll a page that's still growing
  const go=function(){requestAnimationFrame(function(){requestAnimationFrame(function(){
    const s=mcScroller();if(s)s.scrollTop=y;});});};
  if(document.readyState==='complete')go();else window.addEventListener('load',go);
}catch(e){}})();
async function mcSetTheme(id){
  mcKeepScroll();
  try{const r=await(await fetch('/api/save-appearance',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme:id})})).json();
    if(r.ok){location.reload();}else{mcAlert('error: '+(r.error||'failed'));}}catch(e){mcAlert('error: '+e);}}
// The mode is saved on the server, next to the theme — it used to be written to localStorage and
// never read back, so it applied to the page this navigated to and was lost on the next click.
// 'system' is resolved in the browser by a boot script in the page head, so there's no ?dark flag
// and no flash.
async function mcSetMode(v){
  mcKeepScroll();
  try{const r=await(await fetch('/api/save-appearance',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:v})})).json();
    if(!r.ok){mcAlert('error: '+(r.error||'failed'));return;}
  }catch(e){mcAlert('error: '+e);return;}
  location.href=location.pathname;}
// --- notification channels (per machine) ----------------------------------------------------
async function mcSaveChannels(){
  const m=document.getElementById('st-ch-msg');
  const p={};
  ['inapp','desktop','telegram'].forEach(function(c){
    const el=document.getElementById('st-ch-'+c);
    if(el)p['notify_'+c]=!!el.checked;});
  if(m){m.style.color='var(--text-muted)';m.textContent='saving…';}
  try{const r=await(await fetch('/api/save-channels',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(m)m.textContent=r.ok?'saved ✓':('error: '+(r.error||'failed'));}
  catch(e){if(m){m.style.color='var(--status-bad)';m.textContent='error: '+e;}}}
