// Notification centre — the in-app archive behind the bell.
//
// Everything ARMADA announces lands here, including the events that also raise a Windows
// notification: the desktop toast is the interruption, this is the record you can come back to.
// Some kinds (a capability update being available) only ever appear here, because they're worth
// knowing about but not worth pulling you out of what you're doing.
(function(){
  // Colour carries the meaning: red needs fixing, amber needs a decision, blue is the app telling
  // you it did something, green is an offer you can take or leave.
  const ICONS={
    job_started:   {g:'▶', c:'var(--text-muted)'},
    job_finished:  {g:'✓', c:'var(--color-accent-2)'},
    job_failed:    {g:'!', c:'var(--status-bad)'},
    approval_needed:{g:'?', c:'var(--status-warn)'},
    update_available:{g:'↑', c:'color-mix(in srgb,var(--status-ok) 62%,white)'},
    capability_found:{g:'+', c:'color-mix(in srgb,var(--status-ok) 62%,white)'},
    signed_out:    {g:'!', c:'var(--status-bad)'},
    // app machinery rather than your agents' work — a failure worth seeing, softer than a red alarm
    system_job_failed:{g:'⚙', c:'color-mix(in srgb,var(--status-bad) 62%,var(--text-muted))'},
    inbox_task:    {g:'→', c:'var(--color-accent-2)'},
    inbox_failed:  {g:'!', c:'var(--status-bad)'},
    test:          {g:'✓', c:'var(--color-accent-2)'}   // from "Send a test notification"
  };
  let open=false, items=[], unread=0, lastRead='';

  function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}

  // "3m", "2h", "4d" — compact enough for a dense list.
  function ago(ts){
    const t=Date.parse(ts); if(isNaN(t))return '';
    const s=Math.max(0,(Date.now()-t)/1000);
    if(s<60)return 'just now';
    if(s<3600)return Math.floor(s/60)+'m ago';
    if(s<86400)return Math.floor(s/3600)+'h ago';
    return Math.floor(s/86400)+'d ago';
  }

  function badge(){
    const d=document.getElementById('mc-belldot');
    if(d){
      d.style.display=unread?'block':'none';
      d.title=unread?(unread+' new notification'+(unread===1?'':'s')):'';
    }
    const bell=document.getElementById('mc-bell');
    if(bell)bell.title=unread?(unread+' new notification'+(unread===1?'':'s')):'Notifications';
  }

  // Ring once when something NEW lands. Keyed on the newest timestamp rather than the count, so
  // it still fires when one arrives and another is marked read in the same poll — and so a test
  // notification rings exactly like a real one.
  let lastSeenTs=null;
  function ringIfNew(){
    const newest=items.length?String(items[0].ts||''):'';
    if(lastSeenTs!==null && newest && newest>lastSeenTs){
      const bell=document.getElementById('mc-bell');
      if(bell){ bell.classList.remove('mc-bell-ring'); void bell.offsetWidth; bell.classList.add('mc-bell-ring'); }
    }
    lastSeenTs=newest;
  }

  // Only same-origin paths are followed. The server already filters these, but the panel renders
  // agent-authored text so it re-checks rather than trusting what it was handed.
  function safeHref(h){ h=String(h||''); return (h.startsWith('/')&&!h.startsWith('//'))?h:''; }

  // Collapse a run of identical notifications into one row with a count. Eight "Warren finished a
  // task" entries in a row are one fact, not eight — and stacked separately they push the thing you
  // actually need to see off the bottom of the panel. Only CONSECUTIVE repeats merge, so the list
  // stays in true chronological order.
  function group(list){
    const out=[];
    for(const it of list){
      const prev=out[out.length-1];
      if(prev && prev.event===it.event && prev.title===it.title){
        prev.count++;
        if(String(it.ts||'')>prev.lastRead_ts)prev.lastRead_ts=it.ts;
        continue;
      }
      out.push(Object.assign({},it,{count:1,lastRead_ts:it.ts}));
    }
    return out;
  }

  function rowHTML(it){
    const m=ICONS[it.event]||{g:'•',c:'var(--text-muted)'};
    const isNew=String(it.ts||'')>lastRead;
    const href=safeHref(it.href);
    const tag=href?'a':'div';
    const attrs=href
      ? ' href="'+esc(href)+'" class="mc-notifrow" style="text-decoration:none;color:inherit;cursor:pointer;'
      : ' style="';
    return '<'+tag+attrs+'display:flex;gap:9px;padding:9px 12px;border-bottom:1px solid var(--color-divider);'+
      (isNew?'background:color-mix(in srgb,var(--color-accent) 7%,transparent);':'')+'">'+
      '<span style="flex:none;width:17px;height:17px;border-radius:50%;margin-top:1px;font-size:10px;'+
      'font-weight:700;line-height:17px;text-align:center;color:#fff;background:'+m.c+'">'+m.g+'</span>'+
      '<div style="min-width:0;flex:1">'+
      '<div style="font-size:12.5px;font-weight:600;line-height:1.35">'+esc(it.title)+
      ((it.count>1)?'<span style="margin-left:6px;font-size:10px;font-weight:700;padding:1px 6px;'+
        'border-radius:999px;background:color-mix(in srgb,var(--color-text) 11%,transparent);'+
        'color:var(--text-muted)">×'+it.count+'</span>':'')+'</div>'+
      (it.body?'<div style="font-size:11.5px;color:var(--text-muted);line-height:1.4;margin-top:1px;'+
        'overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;'+
        '-webkit-box-orient:vertical">'+esc(it.body)+'</div>':'')+
      // No "open" affordance: a linked row highlights on hover, which is enough of a hint.
      '<div style="font-size:10.5px;color:var(--text-muted);margin-top:2px">'+esc(ago(it.ts))+'</div>'+
      '</div></'+tag+'>';
  }

  function panelHTML(){
    const head='<div style="display:flex;align-items:center;gap:8px;padding:10px 12px;'+
      'border-bottom:1px solid var(--color-divider)">'+
      '<span style="font-family:var(--font-heading);font-weight:600;font-size:13.5px">Notifications</span>'+
      (unread?'<span style="font-size:11px;color:var(--text-muted)">'+unread+' new</span>':'')+
      '<a onclick="mcBellRead()" style="margin-left:auto;font-size:11.5px;cursor:pointer;'+
      'color:var(--color-accent)">Mark all read</a></div>';
    const body=items.length
      ? group(items).map(rowHTML).join('')
      : '<div style="padding:20px 14px;font-size:12px;color:var(--text-muted);text-align:center">'+
        'Nothing yet. Job runs, approvals and capability updates show up here.</div>';
    return head+'<div style="max-height:min(60vh,420px);overflow:auto">'+body+'</div>';
  }

  function paint(){
    const p=document.getElementById('mc-bellpanel'); if(!p)return;
    p.innerHTML=panelHTML();
    p.style.cssText='position:absolute;top:26px;right:-6px;z-index:300;width:344px;'+
      'background:var(--color-bg);border:1px solid var(--color-divider);border-radius:var(--r);'+
      'box-shadow:var(--shadow-lg);overflow:hidden;display:'+(open?'block':'none');
  }

  async function load(){
    try{
      const r=await(await fetch('/api/notifications',{cache:'no-store'})).json();
      items=(r&&r.items)||[]; unread=(r&&r.unread)||0; lastRead=(r&&r.last_read)||'';
      badge(); ringIfNew(); if(open)paint();
    }catch(e){}
  }

  // Opening the panel counts as seeing it: the badge clears, but the "new" tint stays for this
  // viewing (it's painted from the lastRead captured before the mark), so you can still tell at a
  // glance which ones arrived since you last looked.
  async function openPanel(){
    await load();
    paint();
    if(unread){
      try{ await fetch('/api/notifications-read',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }
      catch(e){}
      unread=0; badge();
    }
  }

  // Let the rest of the app say "something just happened, look now" instead of waiting out the
  // poll — that's what makes a test notification ring immediately, like a real one.
  window.mcBellRefresh=load;

  window.mcBellToggle=function(ev){
    if(ev){ev.preventDefault();ev.stopPropagation();}
    open=!open;
    paint();
    if(open) openPanel();
  };
  window.mcBellRead=async function(){
    try{ await fetch('/api/notifications-read',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); }
    catch(e){}
    await load(); paint();
  };

  document.addEventListener('click',function(e){
    if(!open)return;
    if(e.target.closest&&e.target.closest('.mc-notifrow'))return;   // let the link navigate
    const w=document.getElementById('mc-bellwrap');
    if(w&&!w.contains(e.target)){open=false;paint();}
  });
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&open){open=false;paint();}});

  load();
  setInterval(function(){if(!document.hidden)load();},30000);
  document.addEventListener('visibilitychange',function(){if(!document.hidden)load();});
})();
