async function mcRun(agent,job,engine,btn){
  const d=btn.closest('details'); const out=d.querySelector('.mc-out'), msg=d.querySelector('.mc-runmsg');
  out.style.display='block'; out.textContent='running…'; msg.textContent='';
  d.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{ const r=await (await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent,job,engine})})).json();
    out.textContent=r.output||'(no output)'; msg.textContent=r.ok?'done ✓':'finished with errors';
    msg.style.color=r.ok?'var(--status-ok)':'var(--status-bad)';
  }catch(e){ out.textContent='error: '+e; }
  d.querySelectorAll('button').forEach(b=>b.disabled=false);
}

// On/off for one job. Off means the scheduler skips it — the row stays listed, greyed, rather than
// disappearing, because this is a pause and you need to be able to find it again to undo it.
//
// Run now goes with the switch. A button that runs the job, live, next to a switch that says the
// job does not run, is two controls contradicting each other — and the switch is the one that is
// telling the truth about what happens tonight.
async function mcJobEnable(el,agent,job){
  const on=el.checked, d=el.closest('details');
  const lab=el.closest('.mc-toggle');
  el.disabled=true;
  try{
    const r=await (await fetch('/api/job-enable',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent,job,enabled:on})})).json();
    if(r.ok){
      if(d){d.classList.toggle('mc-job-off',!on);mcSetRunBtn(d.querySelector('.btn-primary'),on);}
      if(lab)lab.title=on?'On — click to stop it running on its schedule':'Off — click to let it run again';
      mcJobCount();
    }else{ el.checked=!on; }
  }catch(e){ el.checked=!on; }
  el.disabled=false;
}

// Shared by the user list and the System pane so the two can't drift on what "off" looks like.
function mcSetRunBtn(btn,on){
  if(!btn)return;
  btn.disabled=!on;
  btn.style.opacity=on?'':'.45';
  btn.style.cursor=on?'':'not-allowed';
  btn.title=on?'Run this job now':'This job is switched off — switch it on to run it';
}

// Keep the "Active jobs" figure honest the moment a toggle flips, rather than waiting for a reload.
function mcJobCount(){
  const n=document.querySelectorAll('details.mc-job:not(.mc-job-off)').length;
  document.querySelectorAll('[data-active-jobs]').forEach(el=>{el.textContent=n;});
}

// Delete sits beside Edit inside the expanded job, so the warning goes in the message line that is
// already there next to it. Two presses, and the second names the job — app-native per the house
// rule, and a job is a few hundred words someone wrote rather than a line in a list.
async function mcDeleteJob(el,agent,job,name){
  const d=el.closest('details'), msg=d.querySelector('.mc-runmsg');
  if(el.dataset.armed!=='1'){
    el.dataset.armed='1';
    msg.textContent='Delete “'+name+'”? Press the bin again to confirm — the run history is kept.';
    msg.style.color='var(--status-warn)';
    el._t=setTimeout(()=>{el.dataset.armed='0';msg.textContent='';msg.style.color='';},6000);
    return;
  }
  clearTimeout(el._t);
  msg.textContent='deleting…'; msg.style.color='var(--text-muted)';
  try{
    const r=await (await fetch('/api/delete-job',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent,job})})).json();
    if(r.ok){ d.remove(); mcJobCount(); }
    else{ msg.textContent='error: '+(r.error||'failed'); msg.style.color='var(--status-bad)'; el.dataset.armed='0'; }
  }catch(e){ msg.textContent='error: '+e; msg.style.color='var(--status-bad)'; el.dataset.armed='0'; }
}
