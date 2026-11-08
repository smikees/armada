// Presentation only: never store settings, passwords, permissions or form submissions.
(function(){
  'use strict';
  const dialogs=new WeakMap();
  window.mcPrepareDialog=function(id,show){
    const dialog=document.getElementById(id);if(!dialog)return;
    if(show)dialog.querySelectorAll('template[data-lazy-dialog]').forEach(t=>{
      t.replaceWith(t.content.cloneNode(true));
    });
    dialog.style.display=show?'flex':'none';
    if(show&&!dialogs.has(dialog)){
      const title=dialog.getAttribute('aria-label')||dialog.querySelector('h1,h2,h3,.mc-h-card')?.textContent?.trim()||'Dialog';
      dialogs.set(dialog,mcDialogFocus(dialog,()=>mcPrepareDialog(id,false),title));
    }else if(!show){dialogs.get(dialog)?.();dialogs.delete(dialog);}
  };
  const realm=document.querySelector('meta[name="armada-realm"]')?.content;
  if(!realm)return;
  const query=new URLSearchParams(location.search);query.delete('_realm');query.sort();
  const bucket='armada-view-state',key=realm+':'+location.pathname+'?'+query.toString();
  let lastFocus='';
  document.addEventListener('focusin',event=>{if(event.target.id)lastFocus=event.target.id;});
  const selectors=['.mc-appscroll','#mc-turns','#mc-threadlist','#mc-rail'];
  function read(){try{const value=JSON.parse(sessionStorage.getItem(bucket)||'[]');return Array.isArray(value)?value.filter(s=>s&&typeof s.key==='string'):[];}catch(_){return [];}}
  function save(){
    const scroll=selectors.map(s=>[s,document.querySelector(s)?.scrollTop||0]);
    const filters=[...document.querySelectorAll('.mc-jobsbar')].map(bar=>{
      const prefix=bar.dataset.pfx||'jf';
      return {prefix,search:document.getElementById(prefix+'-search')?.value?.slice(0,256)||'',
        choices:['f1','status','cad'].map(n=>[n,document.getElementById(prefix+'-'+n)?.dataset.val||''])};
    });
    const state={key,time:Date.now(),scroll,filters,focus:lastFocus||document.activeElement?.id||''};
    try{sessionStorage.setItem(bucket,JSON.stringify([state,...read().filter(s=>s.key!==key)].slice(0,32)));}catch(_){}
  }
  let touched=false;
  for(const name of ['pointerdown','keydown','wheel'])document.addEventListener(name,()=>{touched=true;},{once:true,passive:true});
  function restore(){
    const state=read().find(s=>s.key===key&&Date.now()-s.time<7200000);
    if(!state||touched||location.hash)return;
    const prefixes=[...document.querySelectorAll('.mc-jobsbar')].map(b=>b.dataset.pfx||'jf');
    for(const filter of Array.isArray(state.filters)?state.filters:[]){
      if(!filter||!prefixes.includes(filter.prefix)||typeof filter.search!=='string')continue;
      const search=document.getElementById(filter.prefix+'-search');if(search)search.value=filter.search;
      for(const choice of Array.isArray(filter.choices)?filter.choices:[]){
        if(!Array.isArray(choice))continue;
        const [name,value]=choice;if(!['f1','status','cad'].includes(name)||typeof value!=='string')continue;
        const control=document.getElementById(filter.prefix+'-'+name);
        const row=[...(control?.querySelectorAll('[data-val]')||[])].find(r=>r.dataset.val===value);
        if(row&&window.mcFDPick)mcFDPick(row,control.id,value,row.textContent.trim());
      }
    }
    if(window.mcJobsFilter)mcJobsFilter();
    let restored=false;
    function place(){
      if(restored)return;restored=true;
      if(touched)return;
      for(const entry of Array.isArray(state.scroll)?state.scroll:[]){
        if(!Array.isArray(entry))continue;
        const [selector,y]=entry;
        if(!selectors.includes(selector)||!Number.isFinite(y))continue;
        const el=document.querySelector(selector);if(el)el.scrollTop=y;
      }
      const focus=document.getElementById(state.focus);
      if(focus?.getClientRects().length)focus.focus({preventScroll:true});
    }
    requestAnimationFrame(()=>requestAnimationFrame(place));
    // WebView2 pauses animation frames in a hidden/occluded window. Keep its
    // presentation state ready for the next tray restore as well.
    setTimeout(place,250);
  }
  window.addEventListener('pagehide',save);
  if(document.readyState==='complete')restore();else window.addEventListener('load',restore,{once:true});
})();
