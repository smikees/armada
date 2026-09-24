// Jobs page filtering / sorting / view switching.
//
// The page has two panes — User jobs and System jobs — that share this code and look the same.
// Nothing here is hard-coded to one of them: each filter bar carries its own control prefix, the
// id of the table it filters, and which row data-attribute its first dropdown matches on
// (data-owner for user jobs, data-cost for system jobs). Views are found by class inside the
// owning pane rather than by a global id, for the same reason.
function mcJobsBars(){return Array.prototype.slice.call(document.querySelectorAll('.mc-jobsbar'));}

function mcJobsFilterOne(bar){
  const p=bar.dataset.pfx||'jf';
  const gv=id=>{const e=document.getElementById(id);return e?(e.dataset.val||''):'';};
  const f1=gv(p+'-f1'),s=gv(p+'-status'),c=gv(p+'-cad');
  const key=bar.dataset.f1key||'owner';
  const se=document.getElementById(p+'-search'),q=((se&&se.value)||'').toLowerCase().trim();
  let shown=0,total=0;
  const tbl=document.getElementById(bar.dataset.table||'mc-jobstable');
  // Both panes are .mc-joblist now. User rows are <details> (expandable); system rows are plain
  // divs (nothing to expand into) — hence .mc-job rather than details.mc-job. Sorting wants the
  // value a column shows, filtering wants the bucket it falls in, so a row carries both: prefer
  // the bucket where it exists.
  const rows=tbl?(tbl.matches('.mc-joblist')?tbl.querySelectorAll('.mc-job')
                                            :tbl.querySelectorAll('tbody tr')):[];
  rows.forEach(r=>{total++;
    const st=r.dataset.jstatus||r.dataset.status||'', cd=r.dataset.jcad||r.dataset.cadence||'';
    const ok=(!f1||r.dataset[key]===f1)&&(!s||st===s)&&(!c||cd===c)
      &&(!q||r.textContent.toLowerCase().includes(q));
    r.style.display=ok?'':'none'; if(ok)shown++;});
  const cnt=document.getElementById(p+'-count'); if(cnt)cnt.textContent=shown+' of '+total;
  const cl=document.getElementById(p+'-clear'); if(cl)cl.style.display=(f1||s||c||q)?'inline-flex':'none';
  const sx=document.getElementById(p+'-search-x'); if(sx)sx.style.display=q?'block':'none';
}
// Called with no arguments by the shared dropdown widget, so it refreshes every bar on the page.
// Only one pane is visible at a time, and each bar only touches its own table, so this is cheap.
function mcJobsFilter(){
  mcJobsBars().forEach(mcJobsFilterOne);
  if(window.mcJobcalRefresh)window.mcJobcalRefresh();   // keep the calendar views in sync
}
function mcJobsBarOf(el){return (el&&el.closest)?el.closest('.mc-jobsbar'):null;}
function mcJobsSearchClear(el){const bar=mcJobsBarOf(el)||mcJobsBars()[0];if(!bar)return;
  const e=document.getElementById((bar.dataset.pfx||'jf')+'-search');if(e)e.value='';
  mcJobsFilter();if(e)e.focus();}
function mcJobsFilterClear(el){const bar=mcJobsBarOf(el)||mcJobsBars()[0];if(!bar)return;
  const p=bar.dataset.pfx||'jf';
  [p+'-f1',p+'-status',p+'-cad'].forEach(id=>{const d=document.getElementById(id);if(!d)return;
    d.dataset.val='';const lbl=d.querySelector('.mc-fdrop-lbl');if(lbl)lbl.textContent=d.dataset.default||'All';
    const sw=d.querySelector('.mc-fdrop-sw');if(sw)sw.style.display='none';d.removeAttribute('open');});
  const se=document.getElementById(p+'-search');if(se)se.value='';mcJobsFilter();}
// Force a status update: re-read run-reports and recompute every job's state (scheduled/missed/…)
// and the 'as of' time. The daemon writes the run data; this just refreshes what the page shows.
function mcJobsRefresh(btn){const s=btn&&btn.querySelector('svg');if(s)s.style.animation='mc-spin .7s linear infinite';
  if(btn)btn.disabled=true;setTimeout(function(){location.reload();},560);}
// List vs calendar view toggle, per pane. The calendar is the same widget as the Overview
// Job-calendar. The choice is remembered (localStorage) so the Jobs page reopens in the last-used
// view — one shared preference, because the two panes should not drift apart visually.
function mcJobsView(v,el,skipSave){
  const pane=(el&&el.closest)?el.closest('.mc-jobspane'):null;
  const panes=pane?[pane]:Array.prototype.slice.call(document.querySelectorAll('.mc-jobspane'));
  panes.forEach(function(pn){
    const L=pn.querySelector('.mc-jobs-list'),C=pn.querySelector('.mc-jobs-cal');
    if(L)L.style.display=(v==='list')?'':'none';
    if(C)C.style.display=(v==='cal')?'':'none';
    pn.querySelectorAll('.mc-jv').forEach(b=>{const on=b.dataset.v===v;
      b.style.background=on?'color-mix(in srgb,var(--color-text) 9%,transparent)':'transparent';
      b.style.color=on?'var(--color-text)':'color-mix(in srgb,var(--color-text) 50%,transparent)';});
  });
  if(v==='cal'&&window.mcJobcalRefresh)window.mcJobcalRefresh();
  if(!skipSave){try{localStorage.setItem('mc-jobs-view',v);}catch(e){}}
}
// restore the last-used view on load (default stays 'list')
(function(){var v='list';try{var s=localStorage.getItem('mc-jobs-view');if(s==='list'||s==='cal')v=s;}catch(e){}
  if(v!=='list'&&document.querySelector('.mc-jobs-cal'))mcJobsView(v,null,true);})();
