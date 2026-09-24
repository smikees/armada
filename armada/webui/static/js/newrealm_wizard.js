// The new-realm wizard on the realm-setup page (was _core._WIZ_JS; UI audit L1). Expects
// MC_PRESETS (the templates' presets) to be defined inline by the page before this loads.
let mcTpl='state', mcIcon='';
function mcPickTpl(el){mcTpl=el.dataset.tpl;document.querySelectorAll('.mc-tplcard').forEach(c=>c.style.outline='');
  el.style.outline='2px solid var(--color-accent)';mcIcon=MC_PRESETS[mcTpl].icon;mcMarkIcon();}
function mcPickIcon(el){mcIcon=el.dataset.icon;window.mcIconData='';document.getElementById('r-iconprev').innerHTML='';mcMarkIcon();}
async function mcWizIcon(input){const f=input.files[0];if(!f)return;
  const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=URL.createObjectURL(f);});
  const S=128,c=document.createElement('canvas');c.width=S;c.height=S;const x=c.getContext('2d');x.imageSmoothingQuality='high';
  const side=Math.min(img.naturalWidth,img.naturalHeight);
  x.drawImage(img,(img.naturalWidth-side)/2,(img.naturalHeight-side)/2,side,side,0,0,S,S);URL.revokeObjectURL(img.src);
  window.mcIconData=c.toDataURL('image/png');
  document.getElementById('r-iconprev').innerHTML='<img src="'+window.mcIconData+'" width=22 height=22 style="border-radius:3px;vertical-align:middle">';
  document.querySelectorAll('.mc-iconpick').forEach(s=>s.style.background='');}
function mcMarkIcon(){document.querySelectorAll('.mc-iconpick').forEach(s=>s.style.background=s.dataset.icon===mcIcon?'var(--text-12)':'');}
function mcWizStep(n){document.querySelectorAll('#wiz-steps .wiz-step').forEach(function(el){var on=(+el.dataset.s===n);
  el.style.background=on?'var(--color-accent-100)':'var(--text-6)';
  el.style.color=on?'var(--color-accent-700)':'var(--text-muted)';});}
function mcWizCancel(){if(window.parent!==window&&window.parent.mcNewRealmClose){window.parent.mcNewRealmClose();}else{location.href='/settings';}}
function mcWizStepClick(n){var onStep2=document.getElementById('wiz-2').style.display!=='none';
  if(n===2&&!onStep2)mcNext();else if(n===1&&onStep2)mcBack();}
function mcReportH(){try{if(window.parent!==window)window.parent.postMessage({mcRealmH:document.body.scrollHeight},'*');}catch(e){}}
function mcMode(){const c=document.getElementById('r-mode').value==='create';document.getElementById('r-createonly').style.display=c?'block':'none';}
async function mcBrowse(){const m=document.getElementById('r-msg');m.textContent='opening picker…';
  try{const r=await(await fetch('/api/pick-folder')).json();if(r.ok&&r.path){document.getElementById('r-path').value=r.path;m.textContent='';}else{m.textContent=r.error||'pick a folder manually';}}catch(e){m.textContent='type the path manually';}}
function mcNext(){const m=document.getElementById('r-msg');const path=document.getElementById('r-path').value.trim();
  if(!mcReq(['r-name','r-path'])){m.textContent='';return;}
  if(document.getElementById('r-mode').value==='adopt'){mcFinish();return;}
  const p=MC_PRESETS[mcTpl];document.getElementById('r-agents-intro').textContent='Choose who staffs your '+p.collective+'. At least one is required, including the '+p.coordinator+'.';
  const box=document.getElementById('r-agents');box.innerHTML=p.agents.map((a,i)=>
    `<label class="mc-frame" style="display:flex;gap:10px;align-items:center;padding:8px 10px;border-radius:var(--r);margin-bottom:6px">
      <input type="checkbox" class="mc-preset" data-i="${i}" checked>
      <span style="font-family:var(--font-heading);font-weight:600;font-size:14px">${a.display}</span>
      <span style="font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--color-accent-700)">${a.role||''}</span>
      ${a.coordinator?'<span title="Coordinator agent" style="display:inline-flex;margin-left:auto;color:var(--color-accent-2)">'+window.mcIcon('laurel',16)+'</span>':''}</label>`).join('')
    ||'<div style="font-size:12px;color:var(--text-muted)">Blank template — add at least one agent below (the first becomes the coordinator).</div>';
  document.getElementById('wiz-1').style.display='none';document.getElementById('wiz-2').style.display='block';mcWizStep(2);mcReportH();}
function mcBack(){document.getElementById('wiz-2').style.display='none';document.getElementById('wiz-1').style.display='block';mcWizStep(1);mcReportH();}
function mcAddAgentRow(){const box=document.getElementById('r-agents');const d=document.createElement('div');
  d.className='mc-customagent';d.style.cssText='display:flex;gap:6px;margin-bottom:6px';
  d.innerHTML=`<input class="ca-name" placeholder="Name" style="flex:1;padding:5px 7px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text)">
    <input class="ca-role" placeholder="Role" style="flex:1;padding:5px 7px;border:1px solid var(--color-divider);border-radius:var(--r);background:var(--color-bg);color:var(--color-text)">
    <label style="font-size:11px;display:flex;align-items:center;gap:4px"><input type="checkbox" class="ca-coord">coord</label>`;
  box.appendChild(d);}
async function mcFinish(){const m=document.getElementById('r-msg2')||document.getElementById('r-msg');
  const mode=document.getElementById('r-mode').value;
  const payload={mode,name:document.getElementById('r-name').value,template:mcTpl,icon:mcIcon,
    iconData:window.mcIconData||'',path:document.getElementById('r-path').value};
  if(mode==='create'){const p=MC_PRESETS[mcTpl];const agents=[];
    document.querySelectorAll('.mc-preset:checked').forEach(c=>agents.push(p.agents[+c.dataset.i]));
    document.querySelectorAll('.mc-customagent').forEach(d=>{const n=d.querySelector('.ca-name').value.trim();
      if(n)agents.push({display:n,role:d.querySelector('.ca-role').value,coordinator:d.querySelector('.ca-coord').checked});});
    if(!agents.length){m.textContent='add at least one agent';return;}
    if(!agents.some(a=>a.coordinator))agents[0].coordinator=true;
    payload.agents=agents;}
  m.textContent='working…';
  try{const r=await(await fetch('/api/new-realm',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})).json();
    if(r.ok){const t=window.top||window;
      if(r.format_warning&&t.mcAlert)await t.mcAlert(r.format_warning,'Saved by a newer ARMADA');
      if(r.review&&t.mcAlert){const nc=(r.review.command_jobs||[]).length,na=r.review.agent_jobs||0;
        await t.mcAlert('It came with '+nc+' command job'+(nc===1?'':'s')+' and '+na+' agent job'+(na===1?'':'s')+
          '. They\u2019re paused until you\u2019ve looked at them \u2014 the Jobs page lists every command and lets you allow them.',
          'This realm\u2019s jobs are paused');}
      t.location.href='/switch?path='+encodeURIComponent(r.path);}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
document.addEventListener('DOMContentLoaded',()=>{const c=document.querySelector('.mc-tplcard[data-tpl="state"]');if(c)mcPickTpl(c);mcWizStep(1);mcReportH();});
window.addEventListener('load',mcReportH);
