// All views render the same server snapshot, including the window that sent the turn.
(function(){
  const box=document.getElementById('mc-turns');if(!box)return;
  const agent=box.dataset.agent,thread=box.dataset.thread;
  let revision='',timer=null,inflight=false,stopped=false,queued=false,lastStart=0,channel=null;
  function later(){
    if(stopped)return;
    clearTimeout(timer);
    const delay=queued?Math.max(0,250-(Date.now()-lastStart)):(mcGen?750:1500);
    queued=false;timer=setTimeout(tick,delay);
  }
  function wake(){
    if(stopped)return;
    queued=true;if(!inflight)later();
  }
  async function tick(){
    if(stopped)return;
    if(inflight){queued=true;return;}
    inflight=true;lastStart=Date.now();const generation=mcViewGeneration;
    try{
      const response=await fetch('/api/thread-state?'+new URLSearchParams({agent,thread,revision}),{cache:'no-store'});
      const state=await response.json();
      if(generation!==mcViewGeneration)return;
      if(!response.ok){
        if(state.unavailable){
          stopped=true;mcSetGen(true);
          const stop=document.getElementById('mc-stop');if(stop)stop.style.display='none';
        }
        throw new Error(state.error||'Thread updates are unavailable. Retrying…');
      }
      mcTid=state.run_id||mcLocalTid||null;
      mcSetGen(!!mcTid,!!state.stopping||mcStopRequested);
      const status=document.getElementById('mc-chatmsg');
      if(status?.dataset.syncError||status?.dataset.transportError){
        status.textContent='';delete status.dataset.syncError;delete status.dataset.transportError;
      }
      mcSetThreadTitle(thread,state.title);
      if(state.metrics)mcApplyMetrics(state.metrics);
      const selection=window.getSelection();
      const reading=selection&&!selection.isCollapsed&&box.contains(selection.anchorNode);
      if(state.html!==undefined&&!box.querySelector('textarea')&&!reading){
        mcApplyTurns(box,state.html);revision=state.revision;
        mcRefreshRail(agent,thread);mcRefreshAgentDot();
      }
    }catch(error){
      const status=document.getElementById('mc-chatmsg');
      if(status){status.textContent=error.message||'Thread updates are unavailable. Retrying…';status.dataset.syncError='1';}
    }finally{inflight=false;later();}
  }
  // Invalidation speeds up sibling windows; the server remains authoritative.
  // Polling continues when occluded, and also covers browsers without channels.
  try{
    if(typeof BroadcastChannel==='function'){
      const realm=window.mcRealmId||document.querySelector('meta[name="armada-realm"]')?.content||'';
      channel=new BroadcastChannel('armada-thread:'+realm+':'+agent+':'+thread);
      channel.onmessage=wake;
    }
  }catch(error){}
  window.mcThreadSync=tick;
  window.mcThreadChanged=()=>{wake();try{channel?.postMessage('refresh');}catch(error){}};
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)wake();});
  document.addEventListener('selectionchange',()=>{if(window.getSelection()?.isCollapsed)wake();});
  window.addEventListener('focus',wake);
  window.addEventListener('pagehide',()=>{stopped=true;clearTimeout(timer);});
  window.addEventListener('pageshow',()=>{stopped=false;wake();});
  tick();
})();
