(function(){
  let busy=false;
  window.mcRefreshActivityMonitor=async function(){
    const boxes=[...document.querySelectorAll('[data-activity-monitor]')];
    if(busy||document.hidden||!boxes.length)return;
    busy=true;
    try{
      const response=await fetch('/api/activity-monitor',{cache:'no-store',signal:AbortSignal.timeout(8000)});
      if(!response.ok)throw new Error('Activity refresh failed');
      const data=await response.json();
      if(typeof data.html!=='string')throw new Error('Invalid activity response');
      boxes.forEach(box=>{
        box.removeAttribute('data-stale');box.title='';
        if(box.dataset.activityHtml===data.html)return;
        const scroll=box.scrollTop,open=box.querySelector('details')?.open;
        // Preserve keyboard focus rather than replacing an active link.
        if(box.contains(document.activeElement))return;
        box.innerHTML=data.html;box.dataset.activityHtml=data.html;
        if(open!==undefined&&box.querySelector('details'))box.querySelector('details').open=open;
        box.scrollTop=scroll;box.removeAttribute('data-stale');box.title='';
      });
    }catch(error){boxes.forEach(box=>{box.dataset.stale='true';box.title='Live activity refresh unavailable; showing the last reading.';});}
    finally{busy=false;}
  };
  setInterval(window.mcRefreshActivityMonitor,4000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)window.mcRefreshActivityMonitor();});
})();
