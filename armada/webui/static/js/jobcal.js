(function(){
// light tinted backgrounds with dark text; running = the app's theme teal, scheduled = hollow outline
const CLR={missed:'color-mix(in srgb,var(--color-text) 9%,transparent)',
 failed:'color-mix(in srgb,var(--status-bad) 20%,var(--color-bg))',
 warn:'color-mix(in srgb,var(--status-warn) 30%,var(--color-bg))',
 success:'color-mix(in srgb,var(--status-ok) 22%,var(--color-bg))',
 running:'var(--color-accent-2)',
 scheduled:'var(--color-accent-2)'};
const WHITETEXT={running:1};   // running is saturated teal → white text; the light fills use dark text
// saturated dot colours for the day-view list (the pale chip fills would be invisible as a small dot)
const DOT={missed:'var(--status-idle)',failed:'var(--status-bad)',warn:'var(--status-warn)',success:'var(--status-ok)',running:'var(--color-accent-2)',scheduled:'var(--color-accent-2)'};
const DOW=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
const MON=['January','February','March','April','May','June','July','August','September','October','November','December'];
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
function iso(d){return d.getFullYear()+'-'+('0'+(d.getMonth()+1)).slice(-2)+'-'+('0'+d.getDate()).slice(-2);}
function addDays(d,n){const x=new Date(d);x.setDate(x.getDate()+n);return x;}
function monday(d){const x=new Date(d);const wd=(x.getDay()+6)%7;return addDays(x,-wd);}
function fmtLabel(v,a){if(v==='month')return MON[a.getMonth()]+' '+a.getFullYear();
 if(v==='week'){const s=monday(a),e=addDays(s,6);return s.getDate()+' '+MON[s.getMonth()].slice(0,3)+' – '+e.getDate()+' '+MON[e.getMonth()].slice(0,3)+' '+e.getFullYear();}
 return DOW[(a.getDay()+6)%7]+' '+a.getDate()+' '+MON[a.getMonth()].slice(0,3)+' '+a.getFullYear();}
function windowFor(v,a){
 if(v==='month'){const first=new Date(a.getFullYear(),a.getMonth(),1);const last=new Date(a.getFullYear(),a.getMonth()+1,0);return [monday(first),addDays(monday(last),6)];}
 if(v==='week'){const s=monday(a);return [s,addDays(s,6)];}
 const d=new Date(a.getFullYear(),a.getMonth(),a.getDate());return [d,d];}
const JC_CACHE={},JC_TTL=60000;
// scope '' = the realm's agent jobs; 'system' = ARMADA's own upkeep jobs. Cached separately.
async function fetchEvents(a,b,scope){const key=(scope||'')+'|'+iso(a)+'_'+iso(b);const c=JC_CACHE[key];const now=Date.now();
 if(c&&(now-c.t)<JC_TTL)return c.events;
 try{const r=await(await fetch('/api/job-calendar?from='+iso(a)+'&to='+iso(b)+(scope?('&scope='+encodeURIComponent(scope)):''))).json();
  const evs=r.events||[];JC_CACHE[key]={t:now,events:evs};return evs;}
 catch(e){return c?c.events:[];}}
function href(e){return (e.agent==='system')?'/jobs'
 :('/agent/'+encodeURIComponent(e.agent)+'/jobs?job='+encodeURIComponent(e.job));}
function chip(e){const t=e.ts.slice(11,16);const label=t+' · '+e.agent_disp+' · '+e.job_name+' · '+e.status;
 const c=CLR[e.status]||CLR.scheduled;const hollow=(e.status==='scheduled');
 const base='display:block;cursor:pointer;border-radius:4px;font-size:10.5px;line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:3px 4px;';
 const txt=WHITETEXT[e.status]?'#fff':'var(--color-text)';
 const style=hollow?(base+'border:1px solid '+c+';color:'+c+';background:transparent'):(base+'background:'+c+';color:'+txt);
 return '<div class="mc-jc-ev" title="'+esc(label)+'" data-href="'+href(e)+'" style="'+style+'">'+esc(t+' '+e.job_name)+'</div>';}
function byDay(evs){const m={};evs.forEach(e=>{const k=e.ts.slice(0,10);(m[k]=m[k]||[]).push(e);});Object.values(m).forEach(l=>l.sort((x,y)=>x.ts<y.ts?-1:1));return m;}
function drawMonth(body,a,evs){const gs=monday(new Date(a.getFullYear(),a.getMonth(),1));const map=byDay(evs);const tk=iso(new Date());
 let h='<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--color-divider)">';
 DOW.forEach(d=>h+='<div style="background:var(--color-bg);text-align:center;font-size:10px;text-transform:uppercase;letter-spacing:.04em;color:color-mix(in srgb,var(--color-text) 50%,transparent);padding:3px 0">'+d+'</div>');
 for(let i=0;i<42;i++){const d=addDays(gs,i);const inM=d.getMonth()===a.getMonth();const key=iso(d);const evd=map[key]||[];const today=key===tk;
  h+='<div style="background:var(--color-bg);min-height:56px;padding:2px 3px;opacity:'+(inM?'1':'.4')+'">'
   +'<div style="font-size:10.5px;text-align:right;'+(today?'font-weight:700;color:var(--color-accent)':'color:var(--text-muted)')+'">'+d.getDate()+'</div>';
  evd.slice(0,3).forEach(e=>h+='<div style="margin-top:1px">'+chip(e)+'</div>');
  if(evd.length>3)h+='<div class="mc-jc-more" data-day="'+key+'" title="Show all jobs on this day" style="font-size:9.5px;color:var(--text-muted);margin-top:1px;cursor:pointer;text-decoration:underline;text-underline-offset:2px">+'+(evd.length-3)+' more</div>';
  h+='</div>';}
 h+='</div>';body.innerHTML=h;}
function drawWeek(body,a,evs){const s=monday(a);const map=byDay(evs);const tk=iso(new Date());
 let h='<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--color-divider);min-height:100%">';
 for(let i=0;i<7;i++){const d=addDays(s,i);const key=iso(d);const evd=map[key]||[];const today=key===tk;
  h+='<div style="background:var(--color-bg);padding:4px 4px 8px;display:flex;flex-direction:column;gap:2px">'
   +'<div style="font-size:10px;text-align:center;'+(today?'font-weight:700;color:var(--color-accent)':'color:var(--text-muted)')+'">'+DOW[i]+' '+d.getDate()+'</div>';
  evd.forEach(e=>h+=chip(e));h+='</div>';}
 h+='</div>';body.innerHTML=h;}
function drawDay(body,a,evs){const evd=byDay(evs)[iso(a)]||[];
 if(!evd.length){body.innerHTML='<div style="padding:20px;font-size:12.5px;color:var(--text-muted)">No jobs on this day.</div>';return;}
 let h='';evd.forEach(e=>{const c=DOT[e.status]||DOT.scheduled;const hollow=(e.status==='scheduled');
  h+='<div class="mc-jc-ev" title="'+esc(e.ts.slice(11,16)+' · '+e.agent_disp+' · '+e.job_name+' · '+e.status)+'" data-href="'+href(e)+'" style="display:flex;align-items:center;gap:8px;padding:7px 12px;border-bottom:1px solid var(--color-divider);cursor:pointer">'
   +'<span style="font-family:ui-monospace,Menlo,monospace;font-size:11.5px;color:color-mix(in srgb,var(--color-text) 60%,transparent);width:40px">'+e.ts.slice(11,16)+'</span>'
   +'<span style="width:8px;height:8px;border-radius:50%;flex:none;background:'+(hollow?'transparent':c)+';box-shadow:'+(hollow?('inset 0 0 0 1.5px '+c):'none')+'"></span>'
   +'<span style="font-weight:600;font-size:12.5px">'+esc(e.job_name)+'</span>'
   +'<span style="font-size:11.5px;color:var(--text-muted)">'+esc(e.agent_disp)+'</span>'
   +'<span style="margin-left:auto;font-size:10.5px;color:var(--text-muted)">'+esc(e.status)+'</span></div>';});
 body.innerHTML=h;}
// Read the owning pane's filter dropdowns (absent on the dashboard widget → no filtering). The
// widget names its bar's control prefix in data-fpfx, so the User and System calendars each read
// their own filters.
const STATUS_MAP={none:'missed',warning:'warn'};   // filter value -> calendar occurrence status
function applyFilters(evs,pfx){
 if(!pfx)return evs;
 const gv=id=>{const e=document.getElementById(id);return e?(e.dataset.val||''):'';};
 const f1=gv(pfx+'-f1'),cad=gv(pfx+'-cad'),st=gv(pfx+'-status');
 const bar=document.querySelector('.mc-jobsbar[data-pfx="'+pfx+'"]');
 const key=(bar&&bar.dataset.f1key)||'owner';
 const se=document.getElementById(pfx+'-search'),q=((se&&se.value)||'').toLowerCase().trim();
 if(!f1&&!cad&&!st&&!q)return evs;
 const sw=st?(STATUS_MAP[st]||st):'';
 return evs.filter(e=>(!f1||(key==='cost'?e.cost:e.agent)===f1)&&(!cad||e.cad===cad)&&(!sw||e.status===sw)
   &&(!q||((e.job_name||'')+' '+(e.agent_disp||'')).toLowerCase().includes(q)));}
async function render(w){const v=w._view,a=w._anchor;const win=windowFor(v,a);
 const lbl=w.querySelector('.mc-jc-label');if(lbl)lbl.textContent=fmtLabel(v,a);
 w.querySelectorAll('.mc-jc-view').forEach(b=>{const on=b.dataset.jc===v;b.style.background=on?'color-mix(in srgb,var(--color-text) 9%,transparent)':'transparent';b.style.color=on?'var(--color-text)':'var(--text-muted)';});
 const body=w.querySelector('.mc-jc-body');if(body)body.innerHTML='<div style="padding:16px;font-size:12px;color:color-mix(in srgb,var(--color-text) 50%,transparent)">Loading…</div>';
 const evs=applyFilters(await fetchEvents(win[0],win[1],w.dataset.scope||''),w.dataset.fpfx||'');
 if(v==='month')drawMonth(body,a,evs);else if(v==='week')drawWeek(body,a,evs);else drawDay(body,a,evs);}
// let the Jobs page re-draw the calendar when a filter changes
window.mcJobcalRefresh=function(){document.querySelectorAll('.mc-jobcal').forEach(w=>{if(w._jc)render(w);});};
function setup(w){if(w._jc)return;w._jc=1;w._view='week';w._anchor=new Date();
 w.querySelectorAll('.mc-jc-view').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();w._view=b.dataset.jc;render(w);}));
 w.querySelectorAll('.mc-jc-nav').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();const k=b.dataset.jc;
   if(k==='today'){w._anchor=new Date();}
   else{const dir=(k==='next')?1:-1;if(w._view==='month'){w._anchor=new Date(w._anchor.getFullYear(),w._anchor.getMonth()+dir,1);}else{w._anchor=addDays(w._anchor,dir*(w._view==='week'?7:1));}}
   render(w);}));
 w.addEventListener('click',e=>{
   const more=e.target.closest('.mc-jc-more');
   if(more&&more.dataset.day){e.stopPropagation();const p=more.dataset.day.split('-');w._view='day';w._anchor=new Date(+p[0],+p[1]-1,+p[2]);render(w);return;}
   const ev=e.target.closest('.mc-jc-ev');if(ev&&ev.dataset.href)location.href=ev.dataset.href;});
 render(w);}
function init(){document.querySelectorAll('.mc-jobcal').forEach(setup);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
