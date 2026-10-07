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
  function ready(){
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
