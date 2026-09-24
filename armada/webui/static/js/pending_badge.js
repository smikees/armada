window.mcPendingRefresh=async function(){try{
  const r=await fetch('/api/proposals-count'); if(!r.ok)return; const d=await r.json();
  const b=document.getElementById('mc-jobsbadge'); if(!b)return;
  const n=(d&&d.count)||0; b.textContent=n; b.style.display=n?'inline-block':'none';
}catch(e){}};
setInterval(window.mcPendingRefresh,10000);
document.addEventListener('visibilitychange',function(){if(!document.hidden)window.mcPendingRefresh();});
