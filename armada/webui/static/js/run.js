async function mcRun(agent,job,engine,btn){
  const d=btn.closest('details.mc-job'); const out=d.querySelector('.mc-out'), msg=d.querySelector('.mc-runmsg');
  d.querySelector('.mc-job-output-pane').open=true;
  d.dataset.run=''; d.dataset.starting='1';
  out.textContent='Starting…'; msg.textContent='';
  d.querySelectorAll('button').forEach(b=>b.disabled=true);
  const poll=setInterval(()=>mcLoadJobOutput(d),700);
  try{ const r=await (await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent,job,engine})})).json();
    msg.textContent=r.ok?'done ✓':'finished with errors';
    msg.style.color=r.ok?'var(--status-ok)':'var(--status-bad)';
    if(!r.report)msg.textContent=r.output||'Unable to start the job.';
  }catch(e){ out.textContent='error: '+e; }
  finally{clearInterval(poll);delete d.dataset.starting;await mcLoadJobOutput(d);}
  d.querySelectorAll('button').forEach(b=>b.disabled=false);
  mcSetRunBtn(d.querySelector('.btn-primary'),!d.classList.contains('mc-job-off'));
}

// Output is server-rendered with the same Markdown and activity UI as Threads. Polling
// persisted progress also works for scheduled jobs and after navigating away and back.
async function mcLoadJobOutput(d){
  if(d._loadingOutput)return;
  d._loadingOutput=true;
  const selected=d.dataset.run||'';
  try{
    const q=new URLSearchParams({agent:d.dataset.owner,job:d.dataset.jid,run:selected});
    const response=await fetch('/api/job?'+q);
    if(!response.ok)throw new Error('Unable to load run output');
    const r=await response.json();
    if(selected!==(d.dataset.run||''))return;
    const out=d.querySelector('.mc-out');
    // Preserve expanded activity and scroll position while streaming checkpoints arrive.
    const opened=[...out.querySelectorAll('.mc-step-d')].map((el,i)=>el.style.display==='block'?i:-1);
    if(out._html!==r.html){
      const top=out.scrollTop,atEnd=out.scrollHeight-out.clientHeight-top<40;
      out.innerHTML=r.html;out._html=r.html;
      out.querySelectorAll('.mc-step-d').forEach((el,i)=>{if(opened.includes(i))el.style.display='block';});
      out.scrollTop=d._resetOutputScroll?0:(atEnd&&r.running?out.scrollHeight:top);
      delete d._resetOutputScroll;
    }
    const select=d.querySelector('.mc-job-run-select');
    const options=[{id:'',label:r.running?'Live run':'Latest run'},...r.runs.map(ev=>({id:ev.id,label:(ev.ts||'').replace('T',' · ')+' · '+ev.status}))];
    const key=JSON.stringify(options);
    if(select._key!==key){select.replaceChildren(...options.map(ev=>new Option(ev.label,ev.id)));select._key=key;}
    select.value=selected;
    const hist=d.querySelector('.mc-job-history');
    if(hist && hist._html!==r.history_html){hist.innerHTML=r.history_html;hist._html=r.history_html;}
    const week=d.querySelector('.mc-job-week');if(week)week.innerHTML=r.week_html;
    d.dataset.jstatus=r.jstatus;
    d.dataset.running=r.running?'1':'0';
    const next=d.querySelector('.mc-job-next');
    if(next){next.textContent=r.next_label;next.style.color=r.running?'var(--color-accent-2)':d.classList.contains('mc-job-off')?'var(--text-muted)':'var(--text-strong)';}
    const runBtn=d.querySelector('.btn-primary');
    if(!d.dataset.starting){mcSetRunBtn(runBtn,!d.classList.contains('mc-job-off'));if(r.running)runBtn.disabled=true;}
    d._loadedOutput=true;
  }catch(e){if(!d._loadedOutput)d.querySelector('.mc-out').textContent=e.message;}
  finally{d._loadingOutput=false;}
}
function mcSelectJobRun(el,id){
  const d=el.closest('details.mc-job');if(!d)return;
  d.querySelector('.mc-job-output-pane').open=true;
  d.dataset.run=id;d._resetOutputScroll=true;mcLoadJobOutput(d);
}
document.querySelectorAll('details.mc-job').forEach(d=>{
  d.addEventListener('toggle',e=>{if(e.target===d&&d.open)mcLoadJobOutput(d);});
  if(d.open)mcLoadJobOutput(d);
});
setInterval(()=>document.querySelectorAll('details.mc-job[open]').forEach(d=>{if(!d.dataset.starting)mcLoadJobOutput(d);}),1500);
document.addEventListener('click',e=>{
  const h=e.target.closest('.mc-job-output-pane .mc-step-h');
  if(!h)return;
  const detail=h.parentElement.querySelector('.mc-step-d');
  if(detail)detail.style.display=detail.style.display==='block'?'none':'block';
});

// On/off for one job. Off means the scheduler skips it — the row stays listed, greyed, rather than
// disappearing, because this is a pause and you need to be able to find it again to undo it.
//
// Run now goes with the switch. A button that runs the job, live, next to a switch that says the
// job does not run, is two controls contradicting each other — and the switch is the one that is
// telling the truth about what happens tonight.
async function mcJobEnable(el,agent,job){
  const on=el.checked, d=el.closest('details.mc-job');
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
  const d=el.closest('details.mc-job'), msg=d.querySelector('.mc-runmsg');
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
