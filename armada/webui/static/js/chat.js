const _mi=document.getElementById('mc-msg');
const mcDraftKey='armada-draft:'+(document.querySelector?.('meta[name="armada-realm"]')?.content||'')+':'+(window.location?.pathname||'')+(window.location?.search||'');
function mcSaveDraft(){try{if(_mi&&_mi.value)localStorage.setItem(mcDraftKey,_mi.value.slice(0,65536));else localStorage.removeItem(mcDraftKey);}catch(e){}}
if(_mi){try{_mi.value=localStorage.getItem(mcDraftKey)||'';}catch(e){} _mi.addEventListener('input',mcSaveDraft);window.addEventListener('pagehide',mcSaveDraft);}
function mcAutosize(){if(!_mi)return;_mi.style.height='auto';const h=Math.min(260,Math.max(26,_mi.scrollHeight));_mi.style.height=h+'px';_mi.style.overflowY=_mi.scrollHeight>260?'auto':'hidden';}
if(_mi){ mcAutosize();
  _mi.addEventListener('input',()=>{mcAutosize();mcSyncSend();});
  _mi.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();const b=document.getElementById('mc-send');b&&b.click();}});
  _mi.addEventListener('paste',e=>{const items=(e.clipboardData&&e.clipboardData.items)||[];let took=false;
    for(const it of items){if(it.kind!=='file')continue;const f=it.getAsFile();if(!f)continue;took=true;mcAttachFile(f);}
    if(took)e.preventDefault();}); }
async function mcNewThread(agent){
  try{const r=await(await fetch('/api/new-thread',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,name:''})})).json();
    if(r.ok){location.href='/agent/'+agent+'/threads?thread='+encodeURIComponent(r.thread);}else{mcAlert('Could not create thread: '+(r.error||'failed'));}}catch(e){mcAlert('error: '+e);}}
// Icons are rendered from the shared server registry (window.mcIcon), so there's one definition each.
const MC_STEP_ICONS={think:window.mcIcon('think',13), tool:window.mcIcon('terminal',13)};
// green "available / done" indicator shown when a turn completes
const MC_DONE_ICON=window.mcIcon('circle-check-fill',14,'color:var(--status-ok)');
// scroll the transcript to the newest message on load (jump to the bottom of the conversation)
function mcScrollBottom(){const b=document.getElementById('mc-turns');if(b)b.scrollTop=b.scrollHeight;}
// live status dot on this agent's header (matches the server _ACTIVITY_DOT / dash.js MC_ACT_DOT map)
const MC_ACT_DOT={working:['color-mix(in srgb,var(--color-text) 55%,var(--color-bg))',1],input:['var(--status-warn)',0],
  unseen:['var(--color-accent-2)',0],idle:['color-mix(in srgb,var(--color-text) 20%,var(--color-bg))',0]};
// backgroundColor, never the `background` shorthand — the dot's CSS transition is on that property
// and the shorthand would also clear anything else the server set on the element.
function mcPaintDot(d,state){const s=MC_ACT_DOT[state]||MC_ACT_DOT.idle;
  d.style.backgroundColor=s[0];
  d.style.animation=s[1]?'mc-actwork 1.4s ease-in-out infinite':'';
  d.dataset.act=state;}
function mcSetAgentDot(state){document.querySelectorAll('[data-agentdot] .mc-actdot').forEach(d=>mcPaintDot(d,state));}
async function mcRefreshAgentDot(){try{const m=await(await fetch('/api/agent-activity',{cache:'no-store'})).json();
  document.querySelectorAll('[data-agentdot]').forEach(el=>{const st=m[el.dataset.agentdot];const d=el.querySelector('.mc-actdot');if(d&&st)mcPaintDot(d,st);});
  // A reply that arrives while you're on the thread turns the dot teal. You're looking at it, so
  // clear it again — the brief teal-then-fade is the point, not a flicker to avoid.
  if(typeof mcSeenNow==='function')mcSeenNow();}catch(e){}}
function mcInViewport(el){if(!el)return false;const r=el.getBoundingClientRect();return r.bottom>0&&r.top<(window.innerHeight||document.documentElement.clientHeight);}
// Returns the request, so callers can wait for the server to actually clear the flag before asking
// it what the state is — firing and forgetting raced the refresh, and the dot stayed teal until the
// 4-second poller caught up or you navigated away.
function mcMarkThreadRead(agent,thread){
  try{return fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({agent,thread,action:'read'})});}catch(e){return Promise.resolve();}}
// --- "you've seen this" -----------------------------------------------------------------------
// An agent's dot turns teal when it has output you haven't read. The hard part isn't clearing it
// when you open a thread — the server already does that when it renders the page — it's what
// happens when a job finishes WHILE you're sitting on that thread. The reply lands, the poller
// paints the dot teal, and nothing marks it read until you navigate away and back. So this runs on
// load, when the tab becomes visible, on a click inside the thread, and after every poll.
function mcThreadCtx(){
  const b=document.getElementById('mc-turns');
  return (b&&b.dataset.agent)?{agent:b.dataset.agent,thread:b.dataset.thread||'main'}:null;}

let mcSeenAt=0;
function mcSeenNow(force){
  const c=mcThreadCtx(); if(!c)return;
  if(document.hidden)return;                       // a thread in a background tab hasn't been seen
  const now=Date.now();
  if(!force&&now-mcSeenAt<1500)return;             // the poller calls this every 4s; don't spam
  mcSeenAt=now;
  // Fade locally first. You're looking at the output, so "unseen" is already false, and waiting on
  // the round trip makes the change read as a glitch rather than as a response. Deliberately no
  // refresh afterwards: the 4s poller reconciles, and calling it here would re-enter this function.
  document.querySelectorAll('[data-agentdot] .mc-actdot').forEach(d=>{
    if(d.dataset.act==='unseen')mcPaintDot(d,'idle');});
  // Inside the dashboard's thread widget the dot lives on the parent page, out of reach.
  try{if(window.parent!==window)window.parent.postMessage({mcThreadSeen:c.agent},'*');}catch(e){}
  mcMarkThreadRead(c.agent,c.thread);
}
(function(){
  if(!document.getElementById('mc-turns'))return;
  const go=()=>setTimeout(()=>mcSeenNow(true),250);
  if(document.readyState!=='loading')go(); else document.addEventListener('DOMContentLoaded',go);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)mcSeenNow(true);});
  document.addEventListener('click',()=>mcSeenNow(true));   // reading the widget counts as seeing it
})();
// a still-default 'New Chat' thread was auto-named after the first reply: update the header + list in place
function mcSetThreadTitle(thread,title){
  if(!title)return;
  const h=document.getElementById('mc-cttitle'); if(h&&!h.dataset.editing)h.textContent=title;
  if(document.querySelector('meta[name="armada-companion"]'))document.title=(document.getElementById('mc-turns')?.dataset.display||'Thread')+' · '+title+' — ARMADA';
  try{const sel='#mc-threadlist .mc-thread[data-slug="'+(window.CSS&&CSS.escape?CSS.escape(thread):thread)+'"] .mc-thtitle';
    const it=document.querySelector(sel); if(it&&!it.dataset.editing)it.textContent=title;}catch(e){}
}
if(document.getElementById('mc-turns')){requestAnimationFrame(mcScrollBottom);setTimeout(mcScrollBottom,120);}
// Refetch the right rail (loaded context + capabilities + artifacts) after a reply, so newly created
// output artifacts appear without a manual page reload. No-op if the rail isn't on the page.
async function mcRefreshRail(agent,thread){
  const rail=document.getElementById('mc-rail'); if(!rail)return;
  try{
    const html=await (await fetch('/api/thread-rail?agent='+encodeURIComponent(agent)+'&thread='+encodeURIComponent(thread),{cache:'no-store'})).text();
    if(html&&html.trim()){const st=rail.scrollTop;rail.outerHTML=html;const r2=document.getElementById('mc-rail');if(r2)r2.scrollTop=st;}
  }catch(e){}
}
async function mcRefreshMetrics(agent,thread){
  const count=document.getElementById('mc-message-count');if(!count)return;
  try{
    const r=await fetch('/api/thread-metrics?agent='+encodeURIComponent(agent)+'&thread='+encodeURIComponent(thread),{cache:'no-store'});
    if(!r.ok)return;const m=await r.json();
    mcApplyMetrics(m);
  }catch(e){}
}
function mcApplyMetrics(m){
  const count=document.getElementById('mc-message-count');if(count)count.textContent=m.messages;
  const note=document.getElementById('mc-compacted-note');if(note)note.textContent=m.compacted?' · compacted':'';
  const pct=document.getElementById('mc-comp-pct');if(pct)pct.textContent=m.pct;
  const bar=document.getElementById('mc-comp-bar');if(bar){bar.style.width=m.pct+'%';
    bar.style.background=m.pct>=90?'var(--status-bad)':m.pct>=70?'var(--status-warn)':'var(--color-accent-2)';}
  const wrap=document.getElementById('mc-comp-wrap');if(wrap)wrap.title='History uses ~'+Math.floor(m.chars/4).toLocaleString()+' of the model\'s '+Math.floor(m.context_window/1000)+'K-token context window. At 100% the oldest turns are summarised to keep the thread lean.';
}
function mcApplyTurns(box,html){
  const bottom=box.scrollHeight-box.scrollTop-box.clientHeight<90,top=box.scrollTop;
  const open=[...box.querySelectorAll('.mc-step-d')].map((el,i)=>el.style.display==='block'?i:-1).filter(i=>i>=0);
  box.innerHTML=html;
  const details=box.querySelectorAll('.mc-step-d');
  open.forEach(i=>{if(details[i]){details[i].style.display='block';const arrow=details[i].parentNode.querySelector('.mc-step-c');if(arrow)arrow.textContent='▾';}});
  mcMarkDone();if(bottom)mcScrollBottom();else box.scrollTop=top;
}
function mcRefreshTurns(agent,thread){
  const context=mcThreadCtx();
  if(context&&context.agent===agent&&context.thread===thread)return window.mcThreadSync?.();
}
// The shared state observer in thread_sync.js also watches turns started elsewhere.
function mcPendingWatch(){if(window.mcThreadSync)window.mcThreadSync();}
// Right-click menu (Copy / Select All) for thread text. Bound at the DOCUMENT level in the CAPTURE
// phase so it fires first and reliably suppresses any native WebView2 menu, and so it keeps working
// after the transcript's innerHTML is swapped (mcRefreshTurns). Guarded to the transcript only.
function mcCtxInit(){
  if(window._mcCtx)return; window._mcCtx=1;
  const inThread=n=>n&&n.closest&&n.closest('#mc-turns');
  let menu=null;
  const close=()=>{ if(menu){menu.remove();menu=null;} };
  function selectAll(){ const box=document.getElementById('mc-turns'); if(!box)return;
    const r=document.createRange();r.selectNodeContents(box);
    const s=window.getSelection();s.removeAllRanges();s.addRange(r); }
  document.addEventListener('contextmenu',e=>{
    // Editable targets (the composer) get the FULL native menu — spellcheck suggestions, Add to
    // dictionary, Undo/Redo, Cut/Copy/Paste, Select All — which a custom JS menu can't reproduce.
    if(e.target.closest&&e.target.closest('textarea,input,[contenteditable]'))return;
    if(!inThread(e.target))return;                 // let native menus work outside threads
    e.preventDefault(); close();
    const has=(window.getSelection()+'').trim().length>0;
    menu=document.createElement('div'); menu.className='mc-ctx';
    menu.innerHTML='<div class="mc-ctx-i'+(has?'':' mc-ctx-dis')+'" data-a="copy"><span>Copy</span><span class="mc-ctx-k">Ctrl+C</span></div>'
                  +'<div class="mc-ctx-i" data-a="all"><span>Select All</span><span class="mc-ctx-k">Ctrl+A</span></div>';
    document.body.appendChild(menu);
    let x=e.clientX,y=e.clientY; const mw=menu.offsetWidth||176,mh=menu.offsetHeight||74;
    if(x+mw>innerWidth)x=innerWidth-mw-6; if(y+mh>innerHeight)y=innerHeight-mh-6;
    menu.style.left=Math.max(4,x)+'px'; menu.style.top=Math.max(4,y)+'px';
    menu.querySelectorAll('.mc-ctx-i').forEach(it=>{
      it.addEventListener('mousedown',ev=>ev.preventDefault());   // don't clear the selection
      it.addEventListener('click',()=>{
        if(it.dataset.a==='copy'){const t=(window.getSelection()+'');if(t){try{navigator.clipboard.writeText(t);}catch(_){}}}
        else selectAll();
        close();
      });
    });
  },true);
  document.addEventListener('mousedown',ev=>{
    if(menu&&!menu.contains(ev.target)){close();}
    if(ev.button!==0)return;                        // only a normal left-click clears a selection
    // keep the selection only when clicking on an actual message bubble; clicking the empty area
    // below the last message (the transcript's padding) clears it like any other outside click
    if(ev.target.closest&&(ev.target.closest('.mc-turn')||ev.target.closest('.mc-ctx')))return;
    const s=window.getSelection(); if(s&&(''+s).length)s.removeAllRanges();
  });
  document.addEventListener('scroll',close,true);
  window.addEventListener('resize',close);
  document.addEventListener('keydown',ev=>{
    if(ev.key==='Escape'){close();return;}
    if((ev.ctrlKey||ev.metaKey)&&ev.key.toLowerCase()==='a'){
      const ae=document.activeElement;
      if(ae&&(ae.tagName==='TEXTAREA'||ae.tagName==='INPUT'||ae.isContentEditable))return; // let inputs do native
      if(!document.getElementById('mc-turns'))return;
      ev.preventDefault(); selectAll();
    }
  });
}
mcCtxInit();
// Put a green 'Done' marker at the bottom of the newest assistant reply. It stays until the next
// prompt is sent (mcChat clears it). Only one exists at a time.
function mcMarkDone(){
  document.querySelectorAll('#mc-turns .mc-done').forEach(e=>e.remove());
  if(document.querySelector('#mc-turns [data-role="pending"]'))return;
  const ts=[...document.querySelectorAll('#mc-turns .mc-turn[data-role="assistant"]')];
  const t=ts[ts.length-1]; if(!t)return;
  const body=t.querySelector('.mc-body'); const col=body?body.parentNode:t;
  const d=document.createElement('div'); d.className='mc-done';
  d.innerHTML=MC_DONE_ICON+'<span>Done</span>';
  const acts=col.querySelector('.mc-turn-actions');
  if(acts)col.insertBefore(d,acts); else col.appendChild(d);
}
function mcEsc(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}  // quotes too: also used inside attributes
function mcToolLabel(n,i){i=i||{};if(n==='Bash')return 'Running a command';if(n==='Read')return 'Reading '+(i.file_path||i.path||'a file');
 if(n==='Write'||n==='Edit'||n==='MultiEdit')return 'Editing '+(i.file_path||'a file');if(n==='WebSearch')return 'Searching the web';
 if(n==='WebFetch')return 'Fetching a page';if(n==='Glob'||n==='Grep')return 'Searching files';if(n==='Task')return 'Delegating a subtask';return 'Using '+(n||'a tool');}
function mcToolDetail(n,i){if(n==='Bash')return (i&&i.command)||'';try{return JSON.stringify(i||{},null,2);}catch(e){return '';}}
function mcAddChip(steps,icon,label,detail){
  const chip=document.createElement('div');
  chip.className='mc-step';
  chip.innerHTML='<div class="mc-step-h" style="display:flex;align-items:center;gap:6px;font-size:11.5px;'
   +'color:var(--text-dim);'+(detail?'cursor:pointer':'')+'">'
   +'<span style="display:flex">'+icon+'</span><span class="mc-step-l">'+mcEsc(label)+'</span>'
   +(detail?'<span class="mc-step-c" style="margin-left:6px;opacity:.5">▸</span>':'')+'</div>'
   +(detail?'<pre class="mc-step-d" style="display:none;margin:4px 0 2px 20px;background:var(--color-sand-100);border:1px solid var(--color-sand-300);border-radius:var(--r);padding:6px 8px;font-size:11px;line-height:1.45;white-space:pre-wrap;max-height:220px;overflow:auto">'+mcEsc(detail)+'</pre>':'');
  steps.appendChild(chip);return chip;}
document.addEventListener('click',e=>{const h=e.target.closest&&e.target.closest('.mc-step-h');
  if(!h||!h.closest('#mc-turns'))return;const chip=h.closest('.mc-step'),d=chip&&chip.querySelector('.mc-step-d');
  if(!d)return;const open=d.style.display==='block';d.style.display=open?'none':'block';
  const arrow=chip.querySelector('.mc-step-c');if(arrow)arrow.textContent=open?'▸':'▾';});
const MC_ACT={copy:window.mcIcon('copy',14), check:window.mcIcon('check',14),
 restart:window.mcIcon('refresh-cw',14), edit:window.mcIcon('edit',14)};
// --- attachments + composer + menu ---
let mcAttach=[], mcCtrl=null, mcTid=null, mcLocalTid=null, mcGen=false, mcViewGeneration=0;
let mcStopRequested=false,mcStopBusy=false,mcFocusOnIdle=false,mcServerAdmitted=false;
function mcBuildMessage(text){let m='';for(const f of mcAttach){if(f.text)m+='```'+f.name+'\n'+f.text+'\n```\n\n';}return (m+(text||'')).trim();}
const MC_IMGICON=window.mcIcon('image',13,'opacity:.6');
const MC_FILEICON=window.mcIcon('file',12,'opacity:.6');
const MC_XICON=window.mcIcon('x-bold',9);
// Click an attached image thumbnail → open it in a lightbox modal instead of following its link
// (a data:/thread-file URL, which the WebView2 window can't navigate to — it shows a Windows popup).
function mcLightbox(src){
  const ov=document.createElement('div'); ov.className='mc-lightbox';
  ov.innerHTML='<img src="'+src+'" alt=""><button class="mc-lb-x" title="Close">'+MC_XICON+'</button>';
  document.body.appendChild(ov);
  const close=()=>{ov.remove();document.removeEventListener('keydown',esc);};
  function esc(e){if(e.key==='Escape')close();}
  ov.addEventListener('click',e=>{ if(e.target===ov||(e.target.closest&&e.target.closest('.mc-lb-x')))close(); });
  document.addEventListener('keydown',esc);
}
document.addEventListener('click',e=>{
  const a=e.target.closest&&e.target.closest('.mc-att-img'); if(!a)return;
  e.preventDefault();
  const img=a.querySelector('img'); const src=(img&&img.getAttribute('src'))||a.getAttribute('href');
  if(src)mcLightbox(src);
},true);
// Artifact chips in the right rail: output chips carry data-reveal (open the folder), input image
// chips carry data-lightbox (open the picture). Delegated so it survives rail refreshes.
document.addEventListener('click',e=>{
  const local=e.target.closest&&e.target.closest('a[data-local-file]');
  if(local){e.preventDefault();mcOpenThreadFile(local.dataset.localFile);return;}
  const rv=e.target.closest&&e.target.closest('[data-reveal]');
  if(rv){e.preventDefault();mcRevealFile(rv.getAttribute('data-reveal'));return;}
  const lb=e.target.closest&&e.target.closest('[data-lightbox]');
  if(lb){e.preventDefault();mcLightbox(lb.getAttribute('data-lightbox'));return;}
},true);
// Use the same realm-bound opener as Artefacts; executable files are revealed, never run.
async function mcOpenThreadFile(path){
  const report=message=>{const note=document.getElementById('mc-chatmsg');
    if(note)note.textContent=message;else if(typeof mcAlert==='function')mcAlert(message);};
  try{const r=await(await fetch('/api/open-file',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({path})})).json();
    if(!r.ok||r.error)report(r.error||'Could not open the file.');
  }catch(e){report('Could not open the file: '+e);}
}
// Reveal an OUTPUT artifact in the OS file explorer (the app is local; the file lives on this machine).
async function mcRevealFile(path){
  try{
    const r=await (await fetch('/api/reveal',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({path:path})})).json();
    if(!r||!r.ok){const m=document.getElementById('mc-chatmsg');if(m)m.textContent=(r&&r.error)||'could not open file location';}
  }catch(err){const m=document.getElementById('mc-chatmsg');if(m)m.textContent='could not open file location';}
}
function mcRenderAttach(){const box=document.getElementById('mc-attach');if(!box)return;
  if(!mcAttach.length){box.style.display='none';box.innerHTML='';return;}box.style.display='flex';
  box.innerHTML=mcAttach.map((f,i)=>{
    if(f.image){return '<span class="mc-att-prev"><img src="'+f.image+'" alt="'+mcEsc(f.name)+'"><span class="mc-att-x" title="Remove" onclick="mcDelAttach('+i+')">'+MC_XICON+'</span></span>';}
    return '<span style="display:inline-flex;align-items:center;gap:6px;font-size:11.5px;background:var(--color-sand-100);border:1px solid var(--color-sand-300);border-radius:10px;padding:5px 9px;max-width:200px"><span style="flex:none;display:flex">'+MC_FILEICON+'</span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+mcEsc(f.name)+'</span><span title="Remove" onclick="mcDelAttach('+i+')" style="cursor:pointer;opacity:.5;flex:none;display:flex;color:var(--color-text)">'+MC_XICON+'</span></span>';
  }).join('');}
function mcDelAttach(i){mcAttach.splice(i,1);mcRenderAttach();}
function mcClearAttach(){mcAttach=[];mcRenderAttach();}
function mcAttachFile(f){if(!f)return;
  if(/^image\//.test(f.type)){const rd=new FileReader();rd.onload=()=>{mcAttach.push({name:f.name||('image-'+Date.now()+'.png'),image:rd.result});mcRenderAttach();};rd.readAsDataURL(f);return;}
  const rd=new FileReader();rd.onload=()=>{mcAttach.push({name:f.name||'file.txt',text:(rd.result||'').slice(0,20000)});mcRenderAttach();};rd.readAsText(f);}
function mcAddFiles(input){[...input.files].forEach(mcAttachFile);input.value='';}
function mcPlusMenu(e){e.stopPropagation();const m=document.getElementById('mc-plusmenu');if(m)m.style.display=m.style.display==='block'?'none':'block';}
function mcPlusClose(){const m=document.getElementById('mc-plusmenu');if(m)m.style.display='none';}
document.addEventListener('click',(e)=>{const m=document.getElementById('mc-plusmenu');if(m&&!e.target.closest('#mc-plus')&&!e.target.closest('#mc-plusmenu'))m.style.display='none';});
document.addEventListener('keydown',(e)=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='u'){const f=document.getElementById('mc-file');if(f&&document.getElementById('mc-msg')){e.preventDefault();f.click();}}});
function mcSyncSend(){const ta=document.getElementById('mc-msg'),s=document.getElementById('mc-send');
  if(s)s.style.display=(!mcGen&&ta&&ta.value.trim())?'inline-flex':'none';}
function mcSetGen(on,stopping=false){mcGen=on;const st=document.getElementById('mc-stop'),ta=document.getElementById('mc-msg');
  if(!on)mcStopRequested=false;
  if(st){st.style.display=on?'inline-flex':'none';st.disabled=!!stopping;
    st.title=stopping?'Stopping conversation…':'Stop conversation';
    if(st.lastChild?.nodeType===3)st.lastChild.textContent=stopping?'Stopping…':'Stop';}
  if(ta)ta.disabled=on;mcSyncSend();
  if(!on&&mcFocusOnIdle){mcFocusOnIdle=false;if(!document.hidden)ta?.focus();}}
async function mcStop(){
  const context=mcThreadCtx();if(!context||mcStopBusy||!mcGen)return;
  const note=document.getElementById('mc-chatmsg');
  if(note?.dataset.stopError){note.textContent='';delete note.dataset.stopError;}
  mcStopBusy=true;mcStopRequested=true;mcSetGen(true,true);
  try{
    const response=await fetch('/api/chat-stop?'+new URLSearchParams({
      agent:context.agent,thread:context.thread,tid:mcLocalTid||mcTid||''}),{cache:'no-store'});
    const result=await response.json();
    if(!response.ok||!result.ok)throw new Error(result.error||'Could not stop the conversation. Try again.');
    // Stop can beat admission of a just-sent request. Keep its transport alive,
    // and retry the cancellation once the server owns it.
    if(!result.stopped&&mcLocalTid)setTimeout(()=>{if(mcStopRequested&&mcLocalTid)mcStop();},200);
  }catch(error){
    mcStopRequested=false;mcSetGen(mcGen);
    if(note){note.textContent=error.message||'Could not stop the conversation. Try again.';note.dataset.stopError='1';}
  }finally{
    mcStopBusy=false;window.mcThreadChanged?.();
  }
}
// --- turn actions ---
function mcRawText(turn){const t=turn.querySelector('template.mc-raw');if(t)return t.content.textContent;const b=turn.querySelector('.mc-body');return b?b.textContent:'';}
function mcCopyTurn(btn){const txt=mcRawText(btn.closest('.mc-turn'));try{navigator.clipboard.writeText(txt);}catch(e){}
  const old=btn.innerHTML;btn.innerHTML=MC_ACT.check;btn.style.color='var(--status-ok)';setTimeout(()=>{btn.innerHTML=old;btn.style.color='';},1200);}
function mcDropFrom(turn){let n=turn;const rm=[];while(n){if(n.classList&&n.classList.contains('mc-turn'))rm.push(n);n=n.nextElementSibling;}rm.forEach(x=>x.remove());}
async function mcRestartTurn(btn,agent,thread,idx){const turn=btn.closest('.mc-turn');const txt=mcRawText(turn);
  await fetch('/api/thread-truncate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,thread,keep:idx})});
  mcDropFrom(turn);mcChat(agent,thread,txt);}
function mcEditTurn(btn,agent,thread,idx){const turn=btn.closest('.mc-turn');const body=turn.querySelector('.mc-body');const txt=mcRawText(turn);
  const ta=document.createElement('textarea');ta.value=txt;ta.style.cssText='width:100%;min-height:60px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);padding:8px 10px;font:inherit;font-size:13px;resize:vertical';
  const acts=turn.querySelector('.mc-turn-actions');if(acts)acts.style.display='none';
  const bar=document.createElement('div');bar.style.cssText='display:flex;gap:6px;align-items:center;justify-content:flex-end;margin-top:6px;width:100%';
  const info=document.createElement('span');info.className='mc-tip';info.setAttribute('data-tip','Saving restarts the conversation from here.');
  info.style.cssText='display:inline-flex;align-items:center;color:#6b7280;margin-right:auto;cursor:help';
  info.innerHTML=window.mcIcon('info',17);
  const cancel=document.createElement('button');cancel.className='btn btn-secondary';cancel.style.cssText='font-size:12px;padding:4px 10px';cancel.textContent='Cancel';
  const send=document.createElement('button');send.className='btn btn-primary';send.style.cssText='color:#fff;font-size:12px;padding:4px 10px';send.textContent='Save';
  function syncSave(){const changed=ta.value.trim()&&ta.value.trim()!==txt.trim();send.disabled=!changed;send.style.opacity=changed?'1':'.5';send.style.cursor=changed?'pointer':'not-allowed';}
  syncSave();ta.addEventListener('input',syncSave);
  bar.appendChild(info);bar.appendChild(cancel);bar.appendChild(send);body.replaceWith(ta);ta.parentNode.appendChild(bar);ta.focus();
  cancel.onclick=()=>location.reload();
  send.onclick=async()=>{const nt=ta.value.trim();if(!nt||nt===txt.trim())return;await fetch('/api/thread-truncate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,thread,keep:idx})});mcDropFrom(turn);mcChat(agent,thread,nt);};}
function mcActBtn(icon,title,onclick,cls){return '<button class="mc-iconbtn mc-act '+(cls||'')+'" title="'+title+'" onclick="'+onclick+'">'+icon+'</button>';}
function mcAddActions(turn,role,agent,thread,isLast){if(turn.querySelector('.mc-turn-actions'))return;
  const idx=[...document.querySelectorAll('#mc-turns .mc-turn')].indexOf(turn);const d=new Date();
  const when=('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2);
  let h='<span style="font-size:10.5px;color:var(--text-ghost)">'+when+'</span>'+mcActBtn(MC_ACT.copy,'Copy','mcCopyTurn(this)','');
  if(role==='user'){h+=mcActBtn(MC_ACT.restart,'Restart from here','mcRestartTurn(this,\''+agent+'\',\''+thread+'\','+idx+')','');
    if(isLast)h+=mcActBtn(MC_ACT.edit,'Edit','mcEditTurn(this,\''+agent+'\',\''+thread+'\','+idx+')','mc-editbtn');}
  const row=document.createElement('div');row.className='mc-turn-actions';
  row.style.cssText='display:flex;align-items:center;gap:3px;margin-top:3px;justify-content:'+(role==='user'?'flex-end':'flex-start');row.innerHTML=h;
  turn.querySelector('.mc-body').parentNode.appendChild(row);}
function mcChat(agent,thread,forceText){
  if(mcGen)return;
  const ta=document.getElementById('mc-msg'),box=document.getElementById('mc-turns');
  if(!ta||!box)return;
  const text=forceText!==undefined?forceText:(ta.value||'').trim();
  if(!text&&!mcAttach.length)return;
  const message=mcBuildMessage(text);
  const images=mcAttach.filter(f=>f.image).map(f=>({name:f.name,data:f.image}));
  const files=mcAttach.filter(f=>!f.image).map(f=>f.name);
  const tid='t'+Date.now()+Math.random().toString(36).slice(2,7),ctrl=new AbortController();
  mcViewGeneration++;mcLocalTid=mcTid=tid;mcCtrl=ctrl;mcServerAdmitted=false;
  mcStopRequested=false;mcFocusOnIdle=true;mcSetGen(true);
  ta.value='';mcSaveDraft();mcAutosize();mcClearAttach();
  const note=document.getElementById('mc-chatmsg');if(note)note.textContent='';
  let finished=false,connected=false;
  function finish(){
    if(finished)return;finished=true;
    if(mcCtrl===ctrl){mcCtrl=null;mcLocalTid=null;mcServerAdmitted=false;}
    // The transport is only an observer. It never writes a second transcript,
    // nor declares the engine stopped just because a connection closed.
    window.mcThreadChanged?.();
    mcRefreshRail(agent,thread);mcRefreshAgentDot();
    if(window.mcPendingRefresh)window.mcPendingRefresh();
  }
  function handle(event){
    if(event.kind==='rename'&&event.thread_title)mcSetThreadTitle(thread,event.thread_title);
    if(event.kind==='error'&&note)note.textContent=event.error||'The turn failed.';
    window.mcThreadChanged?.();
    if(event.kind==='done'||event.kind==='error'){finish();return true;}
    return false;
  }
  (async()=>{
    try{
      const response=await fetch('/api/chat-stream',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({agent,thread,message,images,files,tid}),signal:ctrl.signal});
      if(!response.ok){
        const result=await response.json();
        throw new Error(result.error||result.output||'Could not send the message.');
      }
      connected=true;
      // The server admits RunSession before sending these headers. Discard polls
      // predating that admission; thereafter only the server decides busy/idle.
      if(mcCtrl===ctrl){mcServerAdmitted=true;mcViewGeneration++;window.mcThreadChanged?.();}
      if(!response.body)throw new Error('The live connection is unavailable.');
      const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
      while(true){
        const chunk=await reader.read();if(chunk.done)break;
        buffer+=decoder.decode(chunk.value,{stream:true});
        let split;
        while((split=buffer.indexOf('\n\n'))>=0){
          const line=buffer.slice(0,split).replace(/^data:\s?/,'');buffer=buffer.slice(split+2);
          let event;try{event=JSON.parse(line);}catch(error){continue;}
          if(handle(event)){
            // Release the keep-alive stream after a terminal event; subsequent
            // renames and other changes arrive through the canonical observer.
            try{await reader.cancel();}catch(error){}
            return;
          }
        }
      }
    }catch(error){
      if(note){
        note.textContent=error.name==='AbortError'
          ?'Live connection interrupted. Reconnecting to the saved conversation…'
          :(error.message||'Live connection interrupted. The saved conversation will keep updating.');
        if(connected||error.name==='AbortError'||error.name==='TypeError')note.dataset.transportError='1';
      }
    }finally{finish();}
  })();
}
