// Every view observes the same saved thread. Polling never starts another agent run.
(function(){
  const box=document.getElementById('mc-turns');
  if(!box)return;
  const agent=box.dataset.agent,thread=box.dataset.thread;
  let revision='',timer=null,inflight=false,stopped=false;
  function later(){if(!stopped){clearTimeout(timer);timer=setTimeout(tick,1500);}}
  async function tick(){
    if(stopped||inflight)return;
    if(document.hidden||mcCtrl){later();return;}
    inflight=true;const generation=mcViewGeneration;
    try{
      const r=await fetch('/api/thread-state?'+new URLSearchParams({agent,thread,revision}),{cache:'no-store'});
      if(!r.ok){
        const result=await r.json();
        if(result.unavailable&&!mcCtrl&&generation===mcViewGeneration){
          stopped=true;mcSetGen(true);
          const stop=document.getElementById('mc-stop');if(stop)stop.style.display='none';
        }
        throw new Error(result.error||'Thread updates are unavailable.');
      }
      const state=await r.json();
      // A local send may have started while this request was in flight.
      if(mcCtrl||generation!==mcViewGeneration)return;
      mcTid=state.run_id||null;mcSetGen(!!mcTid);
      const status=document.getElementById('mc-chatmsg');
      if(status?.dataset.syncError){status.textContent='';delete status.dataset.syncError;}
      mcSetThreadTitle(thread,state.title);
      const selection=window.getSelection();
      const reading=selection&&!selection.isCollapsed&&box.contains(selection.anchorNode);
      if(state.html!==undefined&&!box.querySelector('textarea')&&!reading){
        mcApplyTurns(box,state.html);
        revision=state.revision;
        mcRefreshMetrics(agent,thread);mcRefreshRail(agent,thread);
        mcRefreshAgentDot();
      }
    }catch(error){
      const status=document.getElementById('mc-chatmsg');
      if(status){status.textContent=error.message||'Thread updates are unavailable. Retrying…';status.dataset.syncError='1';}
    }finally{inflight=false;later();}
  }
  window.mcThreadSync=tick;
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)tick();});
  window.addEventListener('focus',tick);
  window.addEventListener('pagehide',()=>{stopped=true;clearTimeout(timer);});
  window.addEventListener('pageshow',()=>{stopped=false;tick();});
  tick();
})();
