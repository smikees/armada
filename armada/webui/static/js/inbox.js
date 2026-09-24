
// Filters are client-side: the whole exchange is already on the page, so narrowing it should be
// instant rather than a round-trip. The archive search only applies inside the archive.
function mcInboxFilter(){
  // the filters are the app's dropdowns (a <details> carrying data-val); the archive search is an input
  const v=function(id){const e=document.getElementById(id);if(!e)return '';return e.tagName==='DETAILS'?(e.dataset.val||''):e.value;};
  const f=v('ib-from'),t=v('ib-to'),s=v('ib-status'),q=v('ib-arch-q').toLowerCase().trim();
  const arch=document.getElementById('ib-archive');
  document.querySelectorAll('.mc-inbox-msg').forEach(function(c){
    let ok=(!f||c.dataset.from===f)&&(!t||c.dataset.to===t)&&(!s||c.dataset.status===s);
    if(ok&&q&&arch&&arch.contains(c))ok=(c.dataset.search||'').indexOf(q)>=0;
    c.style.display=ok?'':'none';});
  // A section whose every card is hidden says so, instead of looking broken
  document.querySelectorAll('.mc-inbox-sec').forEach(function(sec){
    const cards=sec.querySelectorAll('.mc-inbox-msg');
    if(!cards.length)return;
    const any=[...cards].some(function(c){return c.style.display!=='none';});
    const none=sec.querySelector('.mc-inbox-none');
    if(none)none.style.display=any?'none':'block';});
}
function mcInboxClear(){
  const q=document.getElementById('ib-arch-q');if(q)q.value='';
  if(window.mcFDClear)mcFDClear(['ib-from','ib-to','ib-status'],'mcInboxFilter');else mcInboxFilter();
}
document.addEventListener('click',async function(e){
  const el=e.target.closest&&e.target.closest('[data-act]');
  if(!el)return;
  e.preventDefault(); e.stopPropagation();          // don't toggle the card open
  const act=el.dataset.act,agent=el.dataset.agent,id=el.dataset.id;
  const card=el.closest('.mc-inbox-msg');
  const ask=card?(card.dataset.search||'').slice(0,120):'';
  if(act==='delete'){
    const yes=await window.mcConfirm('Delete this message?',
      (ask?'"'+ask+'…"\n\n':'')+'It disappears from the inbox for good. This does not undo anything '+
      'the agent already did.',{ok:'Delete',danger:true});
    if(!yes)return;
  }
  el.style.pointerEvents='none';
  const ep={unread:'/api/inbox-unread',delete:'/api/inbox-delete',process:'/api/inbox-process'}[act];
  try{
    const r=await(await fetch(ep,{method:'POST',headers:{'Content-Type':'application/json'},
       body:JSON.stringify({agent:agent,id:id})})).json();
    if(!r.ok){await window.mcConfirm('That didn\'t work',r.error||'Could not do that.',{ok:'OK'});
      el.style.pointerEvents='';return;}
    if(act==='process'){
      // The agent runs in the background; reload shortly so the card shows Running, then Done.
      el.innerHTML='';el.title='processing…';
      setTimeout(function(){location.reload();},1400);
      return;
    }
    if(card){card.style.transition='opacity .15s';card.style.opacity='0';
      setTimeout(function(){location.reload();},180);}
  }catch(err){
    await window.mcConfirm('That didn\'t work',String(err),{ok:'OK'});
    el.style.pointerEvents='';}
});
