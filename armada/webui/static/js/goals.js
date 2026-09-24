function mcOpenAddGoal(){var o=document.getElementById('goal-add-modal');if(!o)return;o.style.display='flex';
  var n=document.getElementById('goal-title');if(n)setTimeout(function(){n.focus();},30);}
function mcCloseAddGoal(){var o=document.getElementById('goal-add-modal');if(o)o.style.display='none';}
async function mcAddGoal(){
  const t=document.getElementById('goal-title').value, m=document.getElementById('goal-msg');
  if(!t.trim()){m.textContent='a title is required';return;} m.textContent='adding…';
  const ow=document.getElementById('goal-owner'); const owner=ow?ow.value.trim():'';
  const p={title:t,status:document.getElementById('goal-status').value,target:document.getElementById('goal-target').value,
    body:document.getElementById('goal-desc').value};
  if(owner){p.agents=[owner];}
  try{const r=await(await fetch('/api/add-goal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
function mcEditGoal(el){const card=el.closest('.mc-goalcard');const tpl=card.querySelector('.mc-goalraw');
  document.getElementById('goal-ed-stem').value=tpl.dataset.stem;
  document.getElementById('goal-ed-title').value=tpl.dataset.title||'';
  document.getElementById('goal-ed-status').value=tpl.dataset.status||'Not started';
  document.getElementById('goal-ed-target').value=tpl.dataset.target||'';
  document.getElementById('goal-ed-desc').value=tpl.content.textContent;
  document.getElementById('goal-ed-msg').textContent='';
  document.getElementById('goal-edit-modal').style.display='flex';}
function mcCloseEditGoal(){document.getElementById('goal-edit-modal').style.display='none';}
async function mcSaveEditGoal(){const m=document.getElementById('goal-ed-msg');
  const t=document.getElementById('goal-ed-title').value;if(!t.trim()){m.textContent='a title is required';return;}m.textContent='saving…';
  const p={stem:document.getElementById('goal-ed-stem').value,title:t,status:document.getElementById('goal-ed-status').value,
    target:document.getElementById('goal-ed-target').value,body:document.getElementById('goal-ed-desc').value};
  try{const r=await(await fetch('/api/add-goal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
function mcDelGoal(stem,title){document.getElementById('goal-del-stem').value=stem;
  document.getElementById('goal-del-name').textContent=title||'this goal';document.getElementById('goal-del-modal').style.display='flex';}
function mcCloseDelGoal(){document.getElementById('goal-del-modal').style.display='none';}
async function mcConfirmDelGoal(){const stem=document.getElementById('goal-del-stem').value;
  try{const r=await(await fetch('/api/delete-goal',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stem})})).json();
    if(r.ok){location.reload();}else{mcAlert('error: '+(r.error||'failed'));}}catch(e){mcAlert('error: '+e);}}
function mcGoalDragStart(e,agent){e.dataTransfer.setData('text/plain',agent);e.dataTransfer.effectAllowed='copy';}
function mcGoalDragOver(e){e.preventDefault();e.dataTransfer.dropEffect='copy';
  const c=e.currentTarget;c.style.outline='2px dashed var(--color-accent-2)';c.style.outlineOffset='2px';}
function mcGoalDragLeave(e){e.currentTarget.style.outline='';}
async function mcGoalDrop(e,stem){e.preventDefault();const c=e.currentTarget;c.style.outline='';
  const agent=e.dataTransfer.getData('text/plain');if(!agent)return;
  try{const r=await(await fetch('/api/set-goal-agents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stem,agent,action:'add'})})).json();
    if(r.ok){location.reload();}else{mcAlert('error: '+(r.error||'failed'));}}catch(err){mcAlert('error: '+err);}}
async function mcGoalRemoveOwner(stem,agent){
  try{const r=await(await fetch('/api/set-goal-agents',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({stem,agent,action:'remove'})})).json();
    if(r.ok){location.reload();}else{mcAlert('error: '+(r.error||'failed'));}}catch(e){mcAlert('error: '+e);}}
