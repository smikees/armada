(function(){
  let busy=false,queued=false,activityState='';
  window.mcRefreshActivityMonitor=async function(manual=false){
    const boxes=[...document.querySelectorAll('[data-activity-monitor]')];
    if((document.hidden&&!manual)||!boxes.length)return;
    if(busy){queued=true;return;}
    busy=true;
    const buttons=[...document.querySelectorAll('[data-activity-refresh]')];
    let restoreFocus=buttons.includes(document.activeElement)?document.activeElement:null;
    buttons.forEach(button=>{button.disabled=true;button.setAttribute('aria-busy','true');});
    boxes.forEach(box=>box.setAttribute('aria-busy','true'));
    try{
      const response=await fetch('/api/activity-monitor',{cache:'no-store',signal:AbortSignal.timeout(8000)});
      if(!response.ok)throw new Error('Activity refresh failed');
      const data=await response.json();
      if(typeof data.html!=='string')throw new Error('Invalid activity response');
      boxes.forEach(box=>{
        box.removeAttribute('data-stale');box.title='';
        if(box.dataset.activityHtml===data.html)return;
        const scroll=box.scrollTop,active=document.activeElement;
        const focused=box.contains(active),key=active?.closest('[data-activity-key]')?.dataset.activityKey;
        const href=focused?active?.closest('a')?.getAttribute('href'):null;
        box.innerHTML=data.html;box.dataset.activityHtml=data.html;
        if(focused){
          const target=key?[...box.querySelectorAll('[data-activity-key]')].find(el=>el.dataset.activityKey===key):
            [...box.querySelectorAll('a')].find(el=>el.getAttribute('href')===href);
          if(target)target.focus({preventScroll:true});
          else restoreFocus=box.closest('.mc-activity-monitor')?.querySelector('[data-activity-refresh]');
        }
        box.scrollTop=scroll;
      });
      document.querySelectorAll('[data-activity-feedback]').forEach(el=>el.textContent='Activity updated.');
    }catch(error){
      boxes.forEach(box=>{box.dataset.stale='true';box.title='Activity refresh unavailable; showing the last reading.';});
      document.querySelectorAll('[data-activity-feedback]').forEach(el=>el.textContent='Activity could not be refreshed. Try Refresh activity again.');
    }finally{
      busy=false;
      buttons.forEach(button=>{button.disabled=false;button.removeAttribute('aria-busy');});
      boxes.forEach(box=>box.removeAttribute('aria-busy'));
      if(restoreFocus&&document.activeElement===document.body)restoreFocus.focus({preventScroll:true});
      if(queued){queued=false;window.mcRefreshActivityMonitor();}
    }
  };
  document.addEventListener('click',event=>{
    if(!event.target.closest('[data-activity-refresh]'))return;
    event.preventDefault();event.stopPropagation();window.mcRefreshActivityMonitor(true);
  });
  document.addEventListener('mousedown',event=>{
    if(event.target.closest('[data-activity-refresh]'))event.stopPropagation();
  });
  // Reuse the existing lightweight dot poll: completion moves agents between
  // rows promptly, while the complete snapshot refreshes every five minutes.
  window.addEventListener('armada:agent-activity',event=>{
    const state=JSON.stringify(event.detail);
    if(state===activityState)return;
    activityState=state;window.mcRefreshActivityMonitor();
  });
  setInterval(window.mcRefreshActivityMonitor,300000);
  // Queue and system-job transitions need not change an agent's status dot.
  setInterval(window.mcRefreshActivityMonitor,10000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)window.mcRefreshActivityMonitor();});
})();
