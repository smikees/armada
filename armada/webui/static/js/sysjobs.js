// System jobs — running one now and switching one off.
//
// The rows themselves are rendered by the server, in the same list, with the same filters, sorting
// and search as the User jobs list; this file only handles the two actions and patches the row it
// touched so the page doesn't have to reload — throwing away the filters and scroll position to
// show one changed cell is a bad trade.
//
// Cost is shown on every row and never inferred: "free" means deterministic local work, "uses your
// quota" means it invokes agents and spends your Claude subscription. A system job must never
// quietly become a thing that spends money.
(function(){
  function row(id){return document.querySelector('[data-sysjob="'+id+'"]');}

  function msg(id,text,bad){
    const el=document.querySelector('.mc-sysjob-msg[data-for="'+id+'"]');
    if(!el)return;
    el.textContent=text; el.style.color=bad?'var(--status-bad)':'var(--text-muted)';
    el.style.display=text?'block':'none';
  }

  // Repaint the row from /api/system-jobs after an action, so its effect is visible at once.
  //
  // Today's square in the week strip is repainted too: clicking Run now and watching the strip not
  // change says the run didn't count. The square styles come from the server (window.MC_HEALTH) so
  // there is one definition of what a status looks like, not a copy here that drifts from it.
  async function refresh(id){
    let j=null;
    try{
      const r=await(await fetch('/api/system-jobs',{cache:'no-store'})).json();
      j=((r&&r.jobs)||[]).filter(x=>x.id===id)[0]||null;
    }catch(e){ return; }
    const tr=row(id); if(!tr||!j)return;
    tr.style.opacity=j.enabled?'':'.55';
    if(window.mcSetRunBtn)mcSetRunBtn(tr.querySelector('.btn-primary'),j.enabled);
    const nxt=tr.querySelector('[data-next-cell]');
    if(nxt)nxt.textContent=!j.enabled?'off':nextRun(j.next_due,j.due_now);
    const week=tr.querySelector('[data-week]');
    if(week&&window.MC_HEALTH){
      const sq=week.children[week.children.length-4];       // today: 3 days of outlook follow it
      const lbl=!j.enabled?'Not scheduled'
               :(j.status==='error'?'Failed':(j.last_run?'Success':'Scheduled'));
      const st=window.MC_HEALTH[lbl];
      if(sq&&st){
        sq.setAttribute('style','display:inline-block;width:11px;height:11px;border-radius:2px;'
          +'box-sizing:border-box;margin-right:2px;'+st);
        const ti=sq.getAttribute('title')||'';
        const phrase=(window.MC_HEALTH_PHRASE||{})[lbl]||lbl;
        sq.setAttribute('title',ti.split(' \u00b7 ')[0]+' \u00b7 '+phrase);
      }
    }
  }

  // Must match _sysjob_next() server-side, or the cell disagrees with itself the moment an action
  // repaints it. 'Mon 9/21, 20:00' — a wall-clock time you can plan around.
  const DOW=['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  function nextRun(iso,dueNow){
    if(dueNow)return 'any moment';
    if(!iso)return '—';
    const d=new Date(iso); if(isNaN(d.getTime()))return '—';
    const p=n=>String(n).padStart(2,'0');
    // `Thu 24 Sep, 22:30` — the same as datefmt.moment on the server (DESIGN_SYSTEM §9a)
    const MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return DOW[d.getDay()]+' '+d.getDate()+' '+MON[d.getMonth()]+', '+p(d.getHours())+':'+p(d.getMinutes());
  }

  window.mcSysJobRun=async function(btn,id){
    btn.disabled=true; msg(id,'running…',false);
    try{
      const r=await(await fetch('/api/system-job-run',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:id})})).json();
      if(r.skipped){ msg(id,'skipped — '+(r.error||'not available right now'),true); }
      else if(r.ok){ msg(id,'done'+(r.detail?' — '+r.detail:''),false); }
      else { msg(id,r.error||r.detail||'failed',true); }
    }catch(e){ msg(id,'failed: '+e,true); }
    btn.disabled=false;
    await refresh(id);
  };

  window.mcSysJobToggle=async function(el,id){
    const on=el.checked;
    try{
      const r=await(await fetch('/api/system-job-toggle',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:id,on:on})})).json();
      if(!r.ok){ el.checked=!on; msg(id,r.error||'could not change this',true); return; }
      msg(id, on?'switched on':'switched off — it won\'t run on its schedule', false);
    }catch(e){ el.checked=!on; msg(id,'could not change this: '+e,true); return; }
    await refresh(id);
  };
})();
