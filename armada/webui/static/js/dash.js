const MC_LBL='font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin:0 0 4px;display:block';
const MC_FIELD='display:block;width:100%;padding:6px 8px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text);font:inherit;font-size:13px';
const MC_SINGLE=[{id:'register',label:'Register',desc:'Your agents with autonomy, status and latest activity.'},
                 {id:'usage',label:'Usage',desc:'Token usage — overall, per agent and per model.'},
                 {id:'jobcal',label:'Job calendar',desc:'Scheduled jobs by month / week / day, colour-coded by run status.'}];
(window.MC_ADDON_W||[]).forEach(w=>MC_SINGLE.push(w));   // add-on widgets (ADR-012) hide and show the same way
function mcEscH(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function mcEscA(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function mcGrid(){return document.getElementById('mc-grid');}
// --- dashboard state (persisted in the realm's dashboard.json, portable/versioned) ---
window.MC_DASH=window.MC_DASH||{single:{},order:[],spans:{},heights:{},threads:[]};
if(!MC_DASH.heights)MC_DASH.heights={};
let _mcSaveT=null;
function mcDashSave(){
  const g=mcGrid();if(g){const order=[],spans={};
    [...g.children].filter(c=>c.classList.contains('mc-w')).forEach(c=>{order.push(c.dataset.id);spans[c.dataset.id]=+c.dataset.span||10;});
    MC_DASH.order=order;MC_DASH.spans=spans;}
  clearTimeout(_mcSaveT);
  _mcSaveT=setTimeout(()=>{fetch('/api/save-dashboard',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(MC_DASH)}).catch(()=>{});},250);}
// --- thread widgets (multi-instance) ---
function mcTWLoad(){return MC_DASH.threads||(MC_DASH.threads=[]);}
function mcTWSave(l){MC_DASH.threads=l;mcDashSave();}
function mcTWId(w){return 'thread:'+w.agent+':'+w.thread;}
// Icons come from the shared server registry (window.mcIcon) — single source, no drift.
const MC_DOTS=window.mcIcon('dots',18);
const MC_MI={
 user:window.mcIcon('user',16,'flex:none'), mail:window.mcIcon('mail',16,'flex:none'),
 mailopen:window.mcIcon('mail-open',16,'flex:none'), pen:window.mcIcon('square-pen',16,'flex:none'),
 plus:window.mcIcon('plus',16,'flex:none'), trash:window.mcIcon('trash',16,'flex:none')};
function mcMenuItem(act,label,icon){const bad=(act==='remove');
  return '<a data-act="'+act+'" onclick="event.stopPropagation();mcTWMenuClick(this)" style="display:flex;align-items:center;gap:9px;padding:7px 10px;font-size:12.5px;cursor:pointer;color:'+(bad?'var(--status-bad)':'inherit')+';text-decoration:none;border-radius:var(--r)">'
   +'<span class="mc-mi-ic" style="display:flex;color:'+(bad?'var(--status-bad)':'var(--text-dim)')+'">'+icon+'</span><span class="mc-mi-l" style="flex:1">'+label+'</span></a>';}
function mcTWEl(w){
  const id=mcTWId(w);const span=w.span||10;const unread=!!w.unread;
  const cell=document.createElement('div');cell.className='mc-w';cell.dataset.id=id;cell.dataset.span=String(span);
  cell.dataset.agent=w.agent;cell.dataset.thread=w.thread;
  cell.style.cssText='grid-column:span '+span+';grid-row:span 19;min-height:0;position:relative';
  const title=(w.agentDisp||w.agent)+' · '+(w.threadTitle||w.thread);
  const src='/embed/thread?agent='+encodeURIComponent(w.agent)+'&thread='+encodeURIComponent(w.thread);
  const ag=(window.MC_AGENTS||[]).find(a=>a.id===w.agent);const ava=(ag&&ag.icon)||'';
  cell.innerHTML=
   '<div class="mc-widget mc-tw'+(unread?' mc-tw-unread':'')+'" style="height:100%;display:flex;flex-direction:column;overflow:hidden">'
   +'<div class="mc-tw-head" style="display:flex;align-items:center;gap:8px;padding:8px 12px;border-bottom:1px solid var(--color-divider);position:relative">'
   +'<span style="display:inline-flex;align-items:center">'+(window.MC_GRIP||'')+'</span>'
   // the avatar carries its own status dot (server-rendered into MC_AGENTS[].icon), so there is no
   // longer a separate dot beside the title
   +'<span class="mc-tw-ava" data-agentdot="'+mcEscA(w.agent)+'" style="display:flex;flex:none;align-items:center;justify-content:center">'+ava+'</span>'
   +'<span class="mc-tw-title" title="'+mcEscA(title)+'" style="font-family:var(--font-heading);font-weight:600;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:none;max-width:40%">'+mcEscH(title)+'</span>'
   +'<span style="display:inline-flex;align-items:center;gap:6px;font-size:11px;color:var(--text-muted);white-space:nowrap;overflow:hidden"><span class="mc-tw-count">…</span><span style="opacity:.5">·</span><span class="mc-tw-comp" style="display:inline-flex;align-items:center;gap:6px"></span></span>'
   +'<div style="margin-left:auto;position:relative">'
   +'<button class="mc-tw-dots" title="Options" onclick="mcTWMenu(event,this)" style="border:0;background:transparent;cursor:pointer;padding:3px;border-radius:var(--r);display:inline-flex;color:var(--text-65)">'+MC_DOTS+'</button>'
   +'<div class="mc-tw-menu" style="display:none;min-width:180px;background:var(--color-bg);border:1px solid var(--color-divider);border-radius:var(--r);box-shadow:var(--shadow-md);padding:4px">'
   +mcMenuItem('goto','Go to agent',MC_MI.user)
   +mcMenuItem('section','Add as section',MC_MI.plus)
   +mcMenuItem('unread',unread?'Mark read':'Mark unread',unread?MC_MI.mailopen:MC_MI.mail)
   +mcMenuItem('rename','Rename',MC_MI.pen)
   +mcMenuItem('remove','Remove widget',MC_MI.trash)
   +'</div></div>'
   +'</div>'
   +'<iframe src="'+src+'" onload="mcTWCount(this)" style="flex:1;border:0;width:100%;background:var(--color-bg)"></iframe>'
   +'</div>';
  return cell;}
// live activity dot — matches the server _ACTIVITY_DOT map (idle grey, unseen teal, input orange, working pulsing grey)
const MC_ACT_DOT={working:['color-mix(in srgb,var(--color-text) 55%,var(--color-bg))',1,'Working…'],
  input:['var(--status-warn)',0,'Needs input'],unseen:['var(--color-accent-2)',0,'Unseen output'],
  idle:['color-mix(in srgb,var(--color-text) 20%,var(--color-bg))',0,'Idle']};
// A thread widget is an iframe, so the thread you're reading and the dot that describes it live in
// different documents. The embed posts up when it's been seen; we fade that agent's dots here, and
// remember it so the next poll doesn't paint them teal again before the server has caught up.
const mcSeenWidgets=new Set();
function mcFadeAgentDots(agent){
  document.querySelectorAll('[data-agentdot="'+CSS.escape(agent)+'"] .mc-actdot').forEach(d=>{
    if(d.dataset.act==='unseen')mcApplyActDot(d,'idle');});}
window.addEventListener('message',e=>{
  const a=e.data&&e.data.mcThreadSeen; if(!a)return;
  mcSeenWidgets.add(a); mcFadeAgentDots(a);
  setTimeout(()=>mcSeenWidgets.delete(a),6000);      // long enough for one poll to come back clean
});
// backgroundColor, never the `background` shorthand — the dot's CSS transition is on that property
// and the shorthand would also clear anything else the server set on the element.
function mcApplyActDot(dot,state){const s=MC_ACT_DOT[state]||MC_ACT_DOT.idle;
  dot.style.backgroundColor=s[0];
  dot.style.animation=s[1]?'mc-actwork 1.4s ease-in-out infinite':'';dot.title=s[2];
  dot.dataset.act=state;}
function mcTWCount(ifr){try{const d=ifr.contentDocument;if(!d)return;const box=d.getElementById('mc-turns');
  const wid=ifr.closest('.mc-widget');const meta=wid&&wid.querySelector('.mc-tw-count');const comp=wid&&wid.querySelector('.mc-tw-comp');
  const dot=wid&&wid.querySelector('.mc-actdot');if(dot&&box&&box.dataset.activity)mcApplyActDot(dot,box.dataset.activity);
  if(!meta)return;
  const upd=()=>{const n=box?box.querySelectorAll('.mc-turn').length:0;meta.textContent=n+' message'+(n===1?'':'s');
    if(comp){const p=box?(+box.dataset.compPct||0):0;
      const col=p>=90?'var(--status-bad)':(p>=70?'var(--status-warn)':'var(--color-accent-2)');
      comp.title="History fills the model's context window; at 100% the oldest turns are summarised to keep the thread lean.";
      comp.innerHTML=p+'% to compaction <span style="display:inline-block;width:74px;height:8px;border-radius:4px;background:var(--color-bg);border:1px solid var(--color-divider);box-sizing:border-box;overflow:hidden;vertical-align:middle"><span style="display:block;width:'+p+'%;height:100%;background:'+col+'"></span></span>';}};
  upd();if(box&&!box._mcObs){box._mcObs=new MutationObserver(upd);box._mcObs.observe(box,{childList:true});}
}catch(e){}}
function mcHydrateTW(){const g=mcGrid();if(!g)return;
  mcTWLoad().forEach(w=>{const id=mcTWId(w);if(!g.querySelector('.mc-w[data-id="'+CSS.escape(id)+'"]'))g.appendChild(mcTWEl(w));});}
function mcTWMenu(e,btn){e.stopPropagation();const m=btn.parentNode.querySelector('.mc-tw-menu');const open=m.style.display==='block';
  document.querySelectorAll('.mc-tw-menu').forEach(x=>x.style.display='none');
  if(open){m.style.display='none';return;}
  const r=btn.getBoundingClientRect();m.style.position='fixed';m.style.top=(r.bottom+4)+'px';m.style.left=(r.right-180)+'px';m.style.right='auto';m.style.zIndex='90';m.style.display='block';}
document.addEventListener('click',()=>document.querySelectorAll('.mc-tw-menu,.mc-wmenu').forEach(x=>x.style.display='none'));
// ⋮ menu on single-instance widgets (Register / Usage / Job calendar). Uses fixed positioning like the
// thread-widget menu because the widget clips overflow, and removes the widget via the visibility state.
function mcWidgetMenu(e,btn){e.stopPropagation();const m=btn.parentNode.querySelector('.mc-wmenu');if(!m)return;const open=m.style.display==='block';
  document.querySelectorAll('.mc-tw-menu,.mc-wmenu').forEach(x=>x.style.display='none');
  if(open){m.style.display='none';return;}
  const r=btn.getBoundingClientRect();m.style.position='fixed';m.style.top=(r.bottom+4)+'px';m.style.left=(r.right-168)+'px';m.style.right='auto';m.style.zIndex='90';m.style.display='block';}
function mcWidgetRemove(id){document.querySelectorAll('.mc-wmenu').forEach(x=>x.style.display='none');if(window.mcSetSingle)mcSetSingle(id,false);}
// Promote a widget to its own nav page. Default title derived here; server de-dupes one section per widget.
function mcWidgetTitle(wid){
  if(wid==='register')return 'Register'; if(wid==='usage')return 'Usage'; if(wid==='jobcal')return 'Job calendar';
  if(wid.indexOf('thread:')===0){const p=wid.split(':');const ag=(window.MC_AGENTS||[]).find(a=>a.id===p[1]);
    return (ag?ag.display+' · ':'')+((p[2]==='main')?'Main':p[2]);}
  return 'Section';}
function mcWidgetAddSection(wid,title){
  document.querySelectorAll('.mc-wmenu,.mc-tw-menu').forEach(x=>x.style.display='none');
  const name=(title||mcWidgetTitle(wid)).trim();
  fetch('/api/add-widget-section',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({widget:wid,name:name})})
    .then(r=>r.json()).then(r=>{if(r&&r.ok&&typeof r.index==='number'){location.href='/section/'+r.index;}
      else{mcAlert('Could not add section'+(r&&r.error?': '+r.error:''));}}).catch(e=>mcAlert('error: '+e));}
function mcTWMenuClick(a){const act=a.getAttribute('data-act');const cell=a.closest('.mc-w');if(!cell)return;
  const id=cell.dataset.id,agent=cell.dataset.agent,thread=cell.dataset.thread;
  document.querySelectorAll('.mc-tw-menu').forEach(m=>m.style.display='none');
  if(act==='goto'){location.href='/agent/'+encodeURIComponent(agent)+'/threads?thread='+encodeURIComponent(thread);}
  else if(act==='unread'){mcTWToggleUnread(id);}
  else if(act==='rename'){mcTWRename(id,agent,thread);}
  else if(act==='section'){const t=cell.querySelector('.mc-tw-title');mcWidgetAddSection('thread:'+agent+':'+thread,(t&&t.textContent)||'');}
  else if(act==='remove'){mcTWConfirmRemove(id);}}
function mcTWToggleUnread(id){const l=mcTWLoad();const i=l.findIndex(w=>mcTWId(w)===id);if(i<0)return;
  const on=!l[i].unread;l[i].unread=on;mcTWSave(l);mcTWApplyUnread(id,on);}
function mcTWApplyUnread(id,on){const cell=mcGrid().querySelector('.mc-w[data-id="'+CSS.escape(id)+'"]');if(!cell)return;
  const wid=cell.querySelector('.mc-widget');if(wid)wid.classList.toggle('mc-tw-unread',on);
  // Unread is shown by the .mc-tw-unread class on the widget. It used to also repaint the header
  // dot, which was pointless — the activity poller overwrote it seconds later — and now that the
  // dot lives on the avatar and means "what is this agent doing", it would be actively wrong.
  const mi=cell.querySelector('.mc-tw-menu a[data-act="unread"]');
  if(mi){mi.querySelector('.mc-mi-l').textContent=on?'Mark read':'Mark unread';mi.querySelector('.mc-mi-ic').innerHTML=on?MC_MI.mailopen:MC_MI.mail;}}
function mcTWRename(id,agent,thread){const l=mcTWLoad();const w=l.find(x=>mcTWId(x)===id);const cur=(w&&w.threadTitle)||thread;
  document.getElementById('twren-id').value=id;document.getElementById('twren-agent').value=agent;document.getElementById('twren-thread').value=thread;
  document.getElementById('twren-title').value=cur;document.getElementById('twren-msg').textContent='';
  document.getElementById('mc-twren-modal').style.display='flex';setTimeout(()=>{const t=document.getElementById('twren-title');t.focus();t.select();},50);}
function mcTWRenClose(){document.getElementById('mc-twren-modal').style.display='none';}
async function mcTWRenSave(){const m=document.getElementById('twren-msg');const title=document.getElementById('twren-title').value.trim();
  if(!title){m.textContent='name required';return;}m.textContent='saving…';
  const id=document.getElementById('twren-id').value,agent=document.getElementById('twren-agent').value,thread=document.getElementById('twren-thread').value;
  try{const r=await(await fetch('/api/thread-action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent,thread,action:'rename',title})})).json();
    if(!r.ok){m.textContent='error: '+(r.error||'failed');return;}
    const l=mcTWLoad();const w=l.find(x=>mcTWId(x)===id);if(w){w.threadTitle=title;mcTWSave(l);}
    const cell=mcGrid().querySelector('.mc-w[data-id="'+CSS.escape(id)+'"]');
    if(cell){const t=cell.querySelector('.mc-tw-title');const disp=(w&&w.agentDisp)||agent;const full=disp+' · '+title;if(t){t.textContent=full;t.title=full;}}
    mcTWRenClose();
  }catch(e){m.textContent='error: '+e;}}
function mcTWConfirmRemove(id){const l=mcTWLoad();const w=l.find(x=>mcTWId(x)===id);
  const name=w?((w.agentDisp||w.agent)+' · '+(w.threadTitle||w.thread)):'this widget';
  document.getElementById('twdel-id').value=id;document.getElementById('twdel-name').textContent=name;
  document.getElementById('mc-twdel-modal').style.display='flex';}
function mcTWDelClose(){document.getElementById('mc-twdel-modal').style.display='none';}
function mcTWDelConfirm(){const id=document.getElementById('twdel-id').value;
  const cell=mcGrid().querySelector('.mc-w[data-id="'+CSS.escape(id)+'"]');if(cell)cell.remove();
  mcTWSave(mcTWLoad().filter(w=>mcTWId(w)!==id));mcTWDelClose();if(mcModalOpen())mcModalRender();}
function mcRemoveWidgetById(id){const g=mcGrid();const c=g&&g.querySelector('.mc-w[data-id="'+CSS.escape(id)+'"]');if(c)c.remove();
  mcTWSave(mcTWLoad().filter(w=>mcTWId(w)!==id));mcModalRender();}
// --- single-instance widget visibility ---
function mcSingleOn(id){return MC_DASH.single[id]!==false;}
function mcApplyVis(){const g=mcGrid();if(!g)return;MC_SINGLE.forEach(w=>{const c=g.querySelector('.mc-w[data-id="'+CSS.escape(w.id)+'"]');if(c)c.style.display=mcSingleOn(w.id)?'':'none';});}
function mcSetSingle(id,on){MC_DASH.single[id]=on;
  const g=mcGrid();const c=g&&g.querySelector('.mc-w[data-id="'+CSS.escape(id)+'"]');if(c)c.style.display=on?'':'none';mcDashSave();mcModalRender();}
// --- widget manager modal ---
let mcModalAgent='';
function mcModalOpen(){const m=document.getElementById('mc-wmodal');return m&&m.style.display==='flex';}
function mcAddWidget(){document.getElementById('mc-wmodal').style.display='flex';mcModalRender();}
function mcWModalClose(){document.getElementById('mc-wmodal').style.display='none';}
function mcSecHead(t){return '<div style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--text-soft);margin:2px 0 8px">'+t+'</div>';}
function mcSingleRow(w,on){
  return '<label style="display:block;padding:7px 11px;border:1px solid var(--color-divider);border-radius:10px;margin-bottom:7px;cursor:pointer">'
   +'<span style="display:flex;align-items:center;gap:9px">'
   +'<input type="checkbox" '+(on?'checked':'')+' onchange="mcSetSingle(\''+w.id+'\',this.checked)" style="margin:0;flex:none">'
   +'<span style="font-weight:600;font-size:13px">'+mcEscH(w.label)+'</span></span>'
   +'<span style="display:block;font-size:11.5px;color:var(--text-muted);margin:1px 0 0 25px">'+mcEscH(w.desc)+'</span></label>';}
function mcThreadRow(w){
  const ag=(window.MC_AGENTS||[]).find(a=>a.id===w.agent);const ava=(ag&&ag.icon)||'';
  return '<div style="display:flex;align-items:center;gap:10px;padding:9px 11px;border:1px solid var(--color-divider);border-radius:10px;margin-bottom:8px">'
   +'<span style="display:flex;flex:none;align-items:center">'+ava+'</span>'
   +'<span style="flex:1;font-size:13px"><b>Thread</b> · '+mcEscH((w.agentDisp||w.agent)+' / '+(w.threadTitle||w.thread))+'</span>'
   +'<button onclick="mcRemoveWidgetById('+mcEscA(JSON.stringify(mcTWId(w)))+')" style="border:0;background:transparent;cursor:pointer;display:inline-flex;align-items:center;gap:6px;font-size:12px;padding:3px 6px;border-radius:8px;color:var(--status-bad)"><span style="display:flex">'+MC_MI.trash+'</span>Remove</button></div>';}
function mcThreadForm(){
  const ags=(window.MC_AGENTS||[]).map(a=>'<option value="'+mcEscA(a.id)+'"'+(a.id===mcModalAgent?' selected':'')+'>'+mcEscH(a.display)+'</option>').join('');
  return '<div style="border:1px dashed var(--color-divider);border-radius:10px;padding:12px">'
   +'<div style="font-weight:600;font-size:13px;margin-bottom:2px">Thread conversation</div>'
   +'<div style="font-size:11.5px;color:var(--text-muted);margin-bottom:10px">A live conversation — same chat as the Threads tab. Add as many as you like.</div>'
   +'<div style="display:flex;gap:8px;align-items:flex-end">'
   +'<div style="flex:1"><label style="'+MC_LBL+'">Agent</label><select id="mc-w-agent" style="'+MC_FIELD+'" onchange="mcModalAgent=this.value;mcWLoadThreads()">'+ags+'</select></div>'
   +'<div style="flex:1"><label style="'+MC_LBL+'">Thread</label><select id="mc-w-thread" style="'+MC_FIELD+'"></select></div>'
   +'<button class="btn btn-primary" onclick="mcWAdd()">Add</button></div></div>';}
function mcModalRender(){
  const body=document.getElementById('mc-wmodal-body');if(!body)return;
  if(!mcModalAgent&&window.MC_AGENTS&&MC_AGENTS.length)mcModalAgent=MC_AGENTS[0].id;
  let ex='';MC_SINGLE.forEach(w=>{if(mcSingleOn(w.id))ex+=mcSingleRow(w,true);});
  mcTWLoad().forEach(w=>ex+=mcThreadRow(w));
  if(!ex)ex='<div style="font-size:12px;color:var(--text-soft);margin-bottom:8px">Nothing on the dashboard yet.</div>';
  let other='';MC_SINGLE.forEach(w=>{if(!mcSingleOn(w.id))other+=mcSingleRow(w,false);});
  other+=mcThreadForm();
  body.innerHTML=mcSecHead('On your dashboard')+ex+'<div style="height:12px"></div>'+mcSecHead('Add widgets')+other;
  mcWLoadThreads();}
async function mcWLoadThreads(){const ag=document.getElementById('mc-w-agent'),th=document.getElementById('mc-w-thread');
  if(!ag||!th)return; if(!ag.value){th.innerHTML='<option value="main">Main</option>';return;}
  th.innerHTML='<option>…</option>';
  try{const r=await(await fetch('/api/threads?agent='+encodeURIComponent(ag.value))).json();
    th.innerHTML=(r.threads||[]).map(t=>'<option value="'+mcEscA(t.slug)+'">'+mcEscH(t.title)+'</option>').join('')||'<option value="main">Main</option>';
  }catch(e){th.innerHTML='<option value="main">Main</option>';}}
function mcWAdd(){const ag=document.getElementById('mc-w-agent'),th=document.getElementById('mc-w-thread');
  if(!ag.value||!th.value)return;
  const w={agent:ag.value,agentDisp:ag.options[ag.selectedIndex].text,thread:th.value,threadTitle:th.options[th.selectedIndex].text,span:10};
  const l=mcTWLoad();if(l.some(x=>mcTWId(x)===mcTWId(w)))return;
  l.push(w);mcTWSave(l);const cell=mcTWEl(w);mcGrid().appendChild(cell);
  if(window.mcSetupCell)mcSetupCell(cell);mcModalRender();}
mcHydrateTW();mcApplyVis();
// Overview header casts its shadow only once the grid is scrolled (so it reads as lifting off content).
(function mcOvShadow(){const g=document.getElementById('mc-grid'),h=document.getElementById('mc-ovh');if(!g||!h)return;
  const on='0 8px 10px -8px rgba(0,0,0,.22)';
  const upd=()=>{h.style.boxShadow=(g.scrollTop>2)?on:'none';};
  g.addEventListener('scroll',upd,{passive:true});upd();})();
// Poll live agent activity and recolour every status dot — register rows and thread-widget headers —
// so a dot changes (idle→working→unseen…) without a page reload.
(function mcActPoll(){
  async function tick(){
    if(document.hidden)return;
    let m;try{m=await(await fetch('/api/agent-activity',{cache:'no-store'})).json();}catch(e){return;}
    if(!m)return;
    // One selector now: every dot lives inside a [data-agentdot] avatar, thread widgets included.
    document.querySelectorAll('[data-agentdot]').forEach(el=>{const st=m[el.dataset.agentdot];
      const d=el.querySelector('.mc-actdot');if(d&&st)mcApplyActDot(d,st);});
    mcSeenWidgets.forEach(a=>mcFadeAgentDots(a));   // re-clear anything a read widget already saw
  }
  tick();setInterval(tick,4000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
})();
