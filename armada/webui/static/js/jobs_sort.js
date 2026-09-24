// combined search + status + cadence filter for an agent's Jobs list
function mcAgentJobFilter(){
  const el=document.getElementById('mc-jobsearch');const q=((el&&el.value)||'').toLowerCase();
  const x=document.getElementById('mc-jobsearch-x');if(x)x.style.display=q?'block':'none';
  const gv=id=>{const e=document.getElementById(id);return e?(e.dataset.val||''):'';};
  const s=gv('ajf-status'),c=gv('ajf-cad');
  document.querySelectorAll('#mc-joblist details.mc-job').forEach(d=>{
    const hay=((d.dataset.name||'')+' '+(d.dataset.cadence||'')+' '+d.textContent).toLowerCase();
    d.style.display=(hay.includes(q)&&(!s||d.dataset.jstatus===s)&&(!c||d.dataset.jcad===c))?'':'none';});
  const cl=document.getElementById('ajf-clear');if(cl)cl.style.display=(s||c)?'inline-flex':'none';}
function mcJobSearch(){mcAgentJobFilter();}
function mcJobSearchClear(){const el=document.getElementById('mc-jobsearch');if(el)el.value='';mcAgentJobFilter();if(el)el.focus();}
// Sorts one job list. boxId lets the realm Jobs page and the System pane reuse this — their lists
// have different ids and different columns, but every row carries the same sort keys. .mc-job, not
// details.mc-job: system rows are divs, because there is nothing to expand them into.
function mcSortJobs(el,key,boxId){
  const box=document.getElementById(boxId||'mc-joblist'); if(!box)return;
  const rows=[...box.querySelectorAll('.mc-job')];
  const dir=el._d=(el._d===1?-1:1);
  rows.sort((a,b)=>{const x=a.dataset[key]||'',y=b.dataset[key]||'';return x<y?-dir:x>y?dir:0;});
  rows.forEach(r=>box.appendChild(r));
}
