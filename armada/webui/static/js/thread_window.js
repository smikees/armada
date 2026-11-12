// Closing this view leaves the saved thread and any running turn intact.
(function(){
  const close=document.querySelector('[data-thread-close]');
  if(!close)return;
  close.addEventListener('mousedown',event=>event.stopPropagation());
  close.addEventListener('click',()=>{
    if(window.pywebview?.api?.close_window)window.pywebview.api.close_window();
    else window.close();
  });
  // Renaming/selecting the title must not start dragging the native frame.
  document.getElementById('mc-cttitle')?.addEventListener('mousedown',event=>event.stopPropagation());
  const resize=document.querySelector('[data-thread-resize]');
  window.mcMarkThreadSeen=()=>{
    const box=document.getElementById('mc-turns');
    if(!box||document.hidden||!document.hasFocus?.())return;
    fetch('/api/thread-read',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent:box.dataset.agent,thread:box.dataset.thread})}).catch(()=>{});
  };
  window.addEventListener('focus',()=>setTimeout(window.mcMarkThreadSeen,800));
  function ready(){
    let frameTimer;
    const refreshFrame=()=>{
      if(frameTimer)return;
      frameTimer=setTimeout(()=>{
        frameTimer=null;
        window.pywebview?.api?.refresh_frame?.();
      },150);
    };
    new MutationObserver(refreshFrame).observe(document.documentElement,{attributes:true,attributeFilter:['class','style','data-theme']});
    const heading=document.querySelector('.mc-chat-heading');
    if(heading)new MutationObserver(refreshFrame).observe(heading,{attributes:true,childList:true,subtree:true});
    document.addEventListener('load',event=>{
      if(event.target.matches?.('.mc-ax-portrait img'))refreshFrame();
    },true);
    refreshFrame();
    setTimeout(window.mcMarkThreadSeen,800);
    if(!resize||!window.pywebview?.api?.resize_window)return;
    resize.hidden=false;
    resize.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;
      event.preventDefault();event.stopPropagation();
      window.pywebview.api.resize_window();
    });
    resize.addEventListener('keydown',event=>{
      const steps={ArrowRight:[20,0],ArrowLeft:[-20,0],ArrowDown:[0,20],ArrowUp:[0,-20]};
      if(!steps[event.key])return;
      event.preventDefault();event.stopPropagation();
      window.pywebview.api.resize_step(...steps[event.key]);
    });
  }
  if(window.pywebview?.api)ready();
  else window.addEventListener('pywebviewready',ready,{once:true});
})();
