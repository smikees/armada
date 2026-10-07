// Closing this view leaves the saved thread and any running turn intact.
(function(){
  const close=document.querySelector('[data-thread-close]');
  if(!close)return;
  close.addEventListener('mousedown',event=>event.stopPropagation());
  close.addEventListener('click',()=>{
    if(window.pywebview?.api?.close_window)window.pywebview.api.close_window();
    else window.close();
  });
})();
