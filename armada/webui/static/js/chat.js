const _mi=document.getElementById('mc-msg');
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
  const h=document.getElementById('mc-cttitle'); if(h)h.textContent=title;
  try{const sel='#mc-threadlist .mc-thread[data-slug="'+(window.CSS&&CSS.escape?CSS.escape(thread):thread)+'"] .mc-thtitle';
    const it=document.querySelector(sel); if(it)it.textContent=title;}catch(e){}
}
if(document.getElementById('mc-turns')){requestAnimationFrame(mcScrollBottom);setTimeout(mcScrollBottom,120);}
// After a reply lands, replace the just-streamed turns with the server's canonical render, so the
// live view matches a reloaded page exactly (Markdown formatting, correct action icons, segments).
// Refetch the right rail (loaded context + capabilities + artifacts) after a reply, so newly created
// output artifacts appear without a manual page reload. No-op if the rail isn't on the page.
async function mcRefreshRail(agent,thread){
  const rail=document.getElementById('mc-rail'); if(!rail)return;
  try{
    const html=await (await fetch('/api/thread-rail?agent='+encodeURIComponent(agent)+'&thread='+encodeURIComponent(thread),{cache:'no-store'})).text();
    if(html&&html.trim()){const st=rail.scrollTop;rail.outerHTML=html;const r2=document.getElementById('mc-rail');if(r2)r2.scrollTop=st;}
  }catch(e){}
}
async function mcRefreshTurns(agent,thread){
  const box=document.getElementById('mc-turns'); if(!box)return;
  try{
    const r=await fetch('/api/thread-turns?agent='+encodeURIComponent(agent)+'&thread='+encodeURIComponent(thread));
    if(!r.ok)return; const html=await r.text();
    if(html&&html.trim()){box.innerHTML=html;mcMarkDone();mcScrollBottom();mcPendingWatch();}
  }catch(e){}
}
// A turn that was already running when this page loaded belongs to a different tab's event
// stream, so nothing here will ever be told it finished. The transcript renders "working on
// it…" server-side; this is what eventually replaces it with the reply.
//
// Polling, not a second SSE connection: two streams for one turn is two things that can
// disagree, and this one only has to notice a file on disk has grown. It stops the moment the
// placeholder is gone, so an idle thread costs nothing.
function mcPendingWatch(){
  const box=document.getElementById('mc-turns'); if(!box)return;
  const live=!!box.querySelector('.mc-pending');
  if(!live){if(window._mcPend){clearTimeout(window._mcPend);window._mcPend=null;}return;}
  if(window._mcPend)return;                       // already watching
  const agent=box.dataset.agent,thread=box.dataset.thread;
  const tick=function(){
    window._mcPend=setTimeout(async function(){
      window._mcPend=null;
      if(document.hidden){mcPendingWatch();return;}   // don't poll a tab nobody is looking at
      const b=document.getElementById('mc-turns');
      if(!b||!b.querySelector('.mc-pending'))return;
      await mcRefreshTurns(agent,thread);
      mcPendingWatch();
    },2500);
  };
  tick();
}
// chat.js is loaded at the end of the body, so DOMContentLoaded may already have fired.
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mcPendingWatch);
else mcPendingWatch();
document.addEventListener('visibilitychange',function(){if(!document.hidden)mcPendingWatch();});
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
  chip.innerHTML='<div class="mc-step-h" style="display:flex;align-items:center;gap:6px;font-size:11.5px;'
   +'color:color-mix(in srgb,var(--color-text) 60%,transparent);'+(detail?'cursor:pointer':'')+'">'
   +'<span style="display:flex">'+icon+'</span><span class="mc-step-l">'+mcEsc(label)+'</span>'
   +(detail?'<span class="mc-step-c" style="margin-left:6px;opacity:.5">▸</span>':'')+'</div>'
   +(detail?'<pre class="mc-step-d" style="display:none;margin:4px 0 2px 20px;background:var(--color-sand-100);border:1px solid var(--color-sand-300);border-radius:var(--r);padding:6px 8px;font-size:11px;line-height:1.45;white-space:pre-wrap;max-height:220px;overflow:auto">'+mcEsc(detail)+'</pre>':'');
  if(detail){const h=chip.querySelector('.mc-step-h');h.onclick=()=>{const d=chip.querySelector('.mc-step-d');const o=d.style.display==='block';d.style.display=o?'none':'block';chip.querySelector('.mc-step-c').textContent=o?'▸':'▾';};}
  steps.appendChild(chip);return chip;}
const MC_ACT={copy:window.mcIcon('copy',14), check:window.mcIcon('check',14),
 restart:window.mcIcon('refresh-cw',14), edit:window.mcIcon('edit',14)};
// --- attachments + composer + menu ---
let mcAttach=[], mcCtrl=null, mcTid=null, mcGen=false;
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
  const rv=e.target.closest&&e.target.closest('[data-reveal]');
  if(rv){e.preventDefault();mcRevealFile(rv.getAttribute('data-reveal'));return;}
  const lb=e.target.closest&&e.target.closest('[data-lightbox]');
  if(lb){e.preventDefault();mcLightbox(lb.getAttribute('data-lightbox'));return;}
},true);
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
function mcSetGen(on){mcGen=on;const st=document.getElementById('mc-stop'),ta=document.getElementById('mc-msg');
  if(st)st.style.display=on?'inline-flex':'none';if(ta)ta.disabled=on;mcSyncSend();}
async function mcStop(){if(mcTid){try{await fetch('/api/chat-stop?tid='+encodeURIComponent(mcTid));}catch(e){}}if(mcCtrl){try{mcCtrl.abort();}catch(e){}}}
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
  let h='<span style="font-size:10.5px;color:color-mix(in srgb,var(--color-text) 40%,transparent)">'+when+'</span>'+mcActBtn(MC_ACT.copy,'Copy','mcCopyTurn(this)','');
  if(role==='user'){h+=mcActBtn(MC_ACT.restart,'Restart from here','mcRestartTurn(this,\''+agent+'\',\''+thread+'\','+idx+')','');
    if(isLast)h+=mcActBtn(MC_ACT.edit,'Edit','mcEditTurn(this,\''+agent+'\',\''+thread+'\','+idx+')','mc-editbtn');}
  const row=document.createElement('div');row.className='mc-turn-actions';
  row.style.cssText='display:flex;align-items:center;gap:3px;margin-top:3px;justify-content:'+(role==='user'?'flex-end':'flex-start');row.innerHTML=h;
  turn.querySelector('.mc-body').parentNode.appendChild(row);}
function mcChat(agent,thread,forceText){
  const ta=document.getElementById('mc-msg'); const typed=(ta.value||'').trim();
  const text=(forceText!==undefined)?forceText:typed; if(!text&&!mcAttach.length) return;
  const box=document.getElementById('mc-turns'); if(!box) return;
  const disp=box.dataset.display||'Agent';
  document.querySelectorAll('.mc-editbtn').forEach(b=>b.remove());
  document.querySelectorAll('.mc-done').forEach(b=>b.remove());   // clear the previous 'Done' marker
  const msg=mcBuildMessage(text);
  const imgs=mcAttach.filter(f=>f.image).map(f=>({name:f.name,data:f.image}));
  const files=mcAttach.filter(f=>!f.image).map(f=>f.name);
  const attHtml=mcAttach.map(f=>f.image
    ?('<a href="'+f.image+'" target="_blank" class="mc-att-img"><img src="'+f.image+'"></a>')
    :('<span class="mc-att-file">'+MC_FILEICON+'<span>'+mcEsc(f.name)+'</span></span>')).join('');
  const attRow=attHtml?('<div class="mc-att-row">'+attHtml+'</div>'):'';
  const u=document.createElement('div');u.className='mc-turn';u.dataset.role='user';u.style.marginBottom='12px';
  const _uav=document.querySelector('.mc-userav');const uav=(_uav&&_uav.innerHTML.trim())||'';
  const ubub=uav?('<div style="width:28px;height:28px;border-radius:50%;overflow:hidden;flex:none;border:1px solid var(--color-divider)">'+uav+'</div>')
    :'<div style="width:28px;height:28px;border-radius:50%;background:var(--color-accent);color:#fff;display:grid;place-items:center;font-size:11px;flex:none">You</div>';
  u.innerHTML='<div style="display:flex;flex-direction:row-reverse;gap:10px">'+ubub
   +'<div style="max-width:72%">'+attRow+'<div class="mc-body" style="background:var(--color-sand-100);border-radius:var(--r);padding:8px 10px;font-size:13px;line-height:1.5;white-space:pre-wrap">'+mcEsc(text||'(files)')+'</div></div></div><template class="mc-raw">'+mcEsc(text||'')+'</template>';
  box.appendChild(u);
  // The whole portrait out of the <template class="mc-av">, colour crescent and all — not the
  // avatar's innerHTML dropped into a 28px overflow:hidden box, which threw the crescent away and
  // left the streaming turn's avatar looking different from every finished turn above it. Selecting
  // the template explicitly also matters: '.mc-av' matches the inner circle of the header portrait
  // first, which is a different size.
  const _avt=document.querySelector('template.mc-av');
  const av=(_avt&&_avt.innerHTML)||'<span style="display:inline-block;width:28px;height:28px;border-radius:50%;overflow:hidden"><svg width=28 height=28 viewBox="2 0.8 21 21" style="background:var(--color-accent-100)"><path fill="color-mix(in srgb,var(--color-accent) 75%,transparent)" d="M7.5 6.5C7.5 8.981 9.519 11 12 11s4.5-2.019 4.5-4.5S14.481 2 12 2S7.5 4.019 7.5 6.5M20 21h1v-1c0-3.859-3.141-7-7-7h-4c-3.86 0-7 3.141-7 7v1z"/></svg></span>';
  const a=document.createElement('div');a.className='mc-turn';a.dataset.role='assistant';a.style.marginBottom='12px';
  a.innerHTML='<div style="display:flex;gap:10px"><div style="display:flex;flex:none">'+av+'</div>'
   +'<div style="flex:1;min-width:0"><div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">'+mcEsc(disp)+'</div>'
   +'<div class="mc-steps" style="display:flex;flex-direction:column;gap:4px;margin-bottom:6px"></div>'
   +'<div class="mc-answer mc-body" style="font-size:13px;line-height:1.55;white-space:pre-wrap"></div>'
   +'<div class="mc-work" style="display:flex;flex-direction:column;gap:4px;margin-top:6px"></div></div></div>';
  box.appendChild(a);
  const steps=a.querySelector('.mc-steps'), answer=a.querySelector('.mc-answer'), work=a.querySelector('.mc-work');
  // the "working…" gif trails the output — it sits BELOW the streamed reply as the agent thinks
  const working=mcAddChip(work,'<img src="/static/working.gif" width="34" height="34" style="display:block" alt="">',disp+' is working…','');
  working.querySelector('.mc-step-l').style.animation='mc-pulse 1.4s ease-in-out infinite';
  ta.value=''; mcAutosize(); mcClearAttach(); mcSyncSend(); box.scrollTop=box.scrollHeight;
  mcSetAgentDot('working');                              // this agent's header dot pulses while it replies
  const tools={}; mcTid='t'+Date.now()+Math.random().toString(36).slice(2,7); mcCtrl=new AbortController(); mcSetGen(true);
  let done=false;
  function finish(ok){if(done)return;done=true;ok=(ok!==false);
    // the animated "working…" gif shows for the whole turn; then it's removed and (on success) the
    // canonical render swap adds a green 'Done' marker at the BOTTOM of the reply (see mcMarkDone).
    if(working.parentNode)working.remove();
    mcSetGen(false);mcTid=null;mcCtrl=null;
    mcAddActions(a,'assistant',agent,thread,false);
    const us=[...document.querySelectorAll('#mc-turns .mc-turn[data-role="user"]')];if(us.length)mcAddActions(us[us.length-1],'user',agent,thread,true);
    const t=document.getElementById('mc-msg');if(t)t.focus();
    if(ok){mcRefreshTurns(agent,thread);   // swap streamed turns for the canonical server render
      mcRefreshRail(agent,thread);         // new output artifacts / caps appear without a reload
      if(window.mcPendingRefresh)window.mcPendingRefresh();}   // reply may have proposed a job → bump the nav badge
    mcRefreshAgentDot();                    // reply done → dot returns to its real state…
    setTimeout(mcRefreshAgentDot, 900);     // …and again once the server has settled unread + cleared the run marker
    if(ok)setTimeout(()=>mcSeenNow(true),1100);   // your own reply is seen; let the server settle first
  }
  function handle(ev){
    if(ev.kind==='thinking'){mcAddChip(steps,MC_STEP_ICONS.think,'Thought for a moment',ev.text);}
    else if(ev.kind==='tool'){const c=mcAddChip(steps,MC_STEP_ICONS.tool,mcToolLabel(ev.name,ev.input),mcToolDetail(ev.name,ev.input));if(ev.id)tools[ev.id]=c;}
    else if(ev.kind==='tool_result'){const c=tools[ev.id];if(c){const pre=c.querySelector('.mc-step-d');if(pre)pre.textContent=pre.textContent+'\n— result —\n'+ev.content;c.querySelector('.mc-step-l').textContent+=(ev.is_error?' · failed':' · done');}}
    else if(ev.kind==='text'){answer.textContent+=ev.text;}
    else if(ev.kind==='result'){if(ev.output&&!answer.textContent.trim())answer.textContent=ev.output;}
    else if(ev.kind==='rename'){if(ev.thread_title)mcSetThreadTitle(thread,ev.thread_title);}
    else if(ev.kind==='done'){if(ev.output&&!answer.textContent.trim())answer.textContent=ev.output;
      if(ev.thread_title)mcSetThreadTitle(thread,ev.thread_title);finish();}
    else if(ev.kind==='error'){answer.textContent=(answer.textContent||'')+'\n[error: '+(ev.error||'failed')+']';finish(false);}
    box.scrollTop=box.scrollHeight;}
  (async()=>{try{
    const resp=await fetch('/api/chat-stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,thread,message:msg,images:imgs,files:files,tid:mcTid}),signal:mcCtrl.signal});
    const reader=resp.body.getReader();const dec=new TextDecoder();let buf='';
    while(true){const r=await reader.read();if(r.done)break;buf+=dec.decode(r.value,{stream:true});
      let i;while((i=buf.indexOf('\n\n'))>=0){const chunk=buf.slice(0,i);buf=buf.slice(i+2);const line=chunk.replace(/^data:\s?/,'');if(!line.trim())continue;let ev;try{ev=JSON.parse(line);}catch(x){continue;}handle(ev);}}
    finish();
  }catch(e){if(e.name==='AbortError'){answer.textContent=(answer.textContent||'').trim()+' — stopped';}else{answer.textContent=(answer.textContent||'')+'\n[error: '+e+']';}finish(false);}})();
}
