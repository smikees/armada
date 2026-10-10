function mcCronHelp(show){const m=document.getElementById('mc-cronhelp');if(m)m.style.display=show?'flex':'none';}
function mcSelDays(){return [...document.querySelectorAll('.mc-day')].filter(d=>d.dataset.on==='1').map(d=>+d.dataset.dow);}
function mcTglDay(el){el.dataset.on=el.dataset.on==='1'?'0':'1';
  el.style.background=el.dataset.on==='1'?'var(--color-accent-100)':''; el.style.borderColor=el.dataset.on==='1'?'var(--color-accent-300)':'var(--color-divider)';
  el.style.color=el.dataset.on==='1'?'var(--color-accent-800)':''; mcCron();}
// init day .on from server-rendered style
document.querySelectorAll('.mc-day').forEach(d=>{d.dataset.on=d.style.background.includes('accent')?'1':'0';});
function mcCron(){
  const t=(document.getElementById('j-time').value||'09:00').split(':'); const mm=+t[1],hh=+t[0];
  const days=mcSelDays(); const dom1=document.getElementById('j-dom1').checked;
  const dom=dom1?'1':'*'; const dow=days.length?days.sort().join(','):'*';
  const cron=`${mm} ${hh} ${dom} * ${dow}`;
  document.getElementById('j-cron').value=cron; mcNext(cron);
}
function mcCronManual(){ mcNext(document.getElementById('j-cron').value); }
function mcPreset(p){
  const days={daily:[],weekdays:[1,2,3,4,5],weekly:[1],monthly:[]};
  document.querySelectorAll('.mc-day').forEach(d=>{const on=(days[p]||[]).includes(+d.dataset.dow)?'1':'0';d.dataset.on=on;
    d.style.background=on==='1'?'var(--color-accent-100)':'';d.style.borderColor=on==='1'?'var(--color-accent-300)':'var(--color-divider)';d.style.color=on==='1'?'var(--color-accent-800)':'';});
  document.getElementById('j-dom1').checked=(p==='monthly');
  if(p==='on demand'){document.getElementById('j-cron').value='';mcNext('');return;}
  mcCron();
}
function mcNext(cron){document.getElementById('j-next').textContent=cron?('cron: '+cron):'on demand (manual only)';}
async function mcSaveJob(agent,job){
  const skills=[...document.querySelectorAll('.mc-skill:checked')].map(c=>c.value);
  const cron=document.getElementById('j-cron').value.trim();
  const payload={agent,job,name:document.getElementById('j-name').value,
    summary:(document.getElementById('j-summary')||{}).value||'',
    prompt:document.getElementById('j-prompt').value,kind:document.getElementById('j-kind').value,
    thread:document.getElementById('j-thread').value,model:document.getElementById('j-model').value,
    effort:document.getElementById('j-effort').value,verbosity:document.getElementById('j-verbosity').value,cron:cron,allowed_skills:skills,
    retries:Number(document.getElementById('j-onfail').value),budget:document.getElementById('j-budget').value,
    capture_tools:document.getElementById('j-capture-tools').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean),
    capture_dir:document.getElementById('j-capture-dir').value,
    capture_keep_days:Number(document.getElementById('j-capture-keep').value),
    require_capture:document.getElementById('j-require-capture').checked,
    dry_run_keep_days:Number(document.getElementById('j-dry-keep').value),
    inspector:document.getElementById('j-inspector').checked,
    dry_run_inputs:document.getElementById('j-dry-inputs').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean),
    dry_run_scripts:document.getElementById('j-dry-scripts').value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean),
    approve_dry_run_scripts:document.getElementById('j-dry-approve').checked,
    dry_run_command:document.getElementById('j-dry-command').value.trim()};
  const m=document.getElementById('j-savemsg'); m.textContent='saving…';
  try{let r=await (await fetch('/api/save-job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
    if(r.connector_warning){
      if(!await mcConfirm('Review connector access',r.connector_warning,{ok:'Save model choice'})){m.textContent='Model change not saved.';return;}
      payload.confirm_connector_change=true;
      r=await (await fetch('/api/save-job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
    }
    m.textContent=r.ok?'saved ✓ · '+(r.path||''):'error: '+(r.error||'failed'); m.style.color=r.ok?'var(--status-ok)':'var(--status-bad)';
    if(r.ok)document.getElementById('j-dry-approve').checked=false;
  }catch(e){m.textContent='error: '+e;}
}
// Delete from the job's own page. Same two-press confirm as the list, but on success there is no
// row left to stand on, so it returns to the agent's Jobs tab.
async function mcDeleteJobPage(btn,agent,job,name){
  const m=document.getElementById('j-savemsg');
  if(btn.dataset.armed!=='1'){
    btn.dataset.armed='1';
    m.textContent='Delete “'+name+'”? Press again to confirm — the run history is kept.';
    m.style.color='var(--status-warn)';
    btn._t=setTimeout(()=>{btn.dataset.armed='0';m.textContent='';m.style.color='';},6000);
    return;
  }
  clearTimeout(btn._t); btn.disabled=true;
  m.textContent='deleting…'; m.style.color='var(--text-muted)';
  try{
    const r=await (await fetch('/api/delete-job',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent,job})})).json();
    if(r.ok){ location.href='/agent/'+agent+'/jobs'; }
    else{ m.textContent='error: '+(r.error||'failed'); m.style.color='var(--status-bad)';
      btn.disabled=false; btn.dataset.armed='0'; }
  }catch(e){ m.textContent='error: '+e; m.style.color='var(--status-bad)';
    btn.disabled=false; btn.dataset.armed='0'; }
}
mcNext(document.getElementById('j-cron')?document.getElementById('j-cron').value:'');
