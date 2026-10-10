// The live line under a model picker: what this agent (or job) can still use on the engine the
// chosen model runs on. Asked of the server on every change, because only the server knows the
// grants, the realm default the blank option inherits, and which connections are one engine at a
// time. A late answer for an earlier choice is dropped rather than painted over the current one.
(function(){
  document.querySelectorAll('[data-reach-hint]').forEach(function(hint){
    const select=document.getElementById(hint.dataset.reachFor);
    if(!select)return;
    let generation=0;
    async function update(){
      const mine=++generation;
      const q=new URLSearchParams({agent:hint.dataset.agent||'',model:select.value||''});
      if(hint.dataset.job)q.set('job',hint.dataset.job);
      hint.dataset.state='checking';
      try{
        const r=await (await fetch('/api/engine-impact?'+q,{cache:'no-store'})).json();
        if(mine!==generation)return;
        if(!r.ok){hint.dataset.state='unknown';hint.querySelector('[data-text]').textContent='';return;}
        hint.dataset.state=r.lost.length?'loses':'ok';
        hint.dataset.engine=r.engine;
        hint.querySelector('[data-text]').textContent=r.text;
        const list=hint.querySelector('[data-list]');
        list.replaceChildren(...r.lost.map(function(x){
          const li=document.createElement('li');li.textContent=x.why;return li;}));
        list.hidden=!r.lost.length;
      }catch(e){if(mine===generation)hint.dataset.state='unknown';}
    }
    select.addEventListener('change',update);
  });
})();
