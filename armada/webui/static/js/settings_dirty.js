// Unsaved settings live only in this document; no form values enter storage.
(function(){
  const groups=[];
  function fields(root){return [...root.querySelectorAll('input,select,textarea,.mc-themecard,.mc-seticon,.mc-day')]
    .filter(el=>el.type!=='file'&&!el.closest('.mc-modal-ov,dialog,[data-api-fallback]'));}
  function value(el){if(el.matches('.mc-themecard'))return el.dataset.selected||'';
    if(el.matches('.mc-seticon'))return el.style.cssText;
    if(el.matches('.mc-day'))return el.dataset.on||'';
    return el.type==='checkbox'||el.type==='radio'?el.checked:el.value;}
  function snapshot(group){return new Map(fields(group.root).map(el=>[el,value(el)]));}
  function changed(a,b){return a.size!==b.size||[...a].some(([el,v])=>b.get(el)!==v);}
  function paint(group){const dirty=changed(snapshot(group),group.base);
    group.button.classList.toggle('mc-save-dirty',dirty);group.button.dataset.unsaved=String(dirty);
    if(dirty)group.button.setAttribute('aria-label','Save unsaved changes');else group.button.removeAttribute('aria-label');}
  window.mcDirtyCapture=function(target){const button=typeof target==='string'?document.querySelector(target):target;
    const group=groups.find(g=>g.button===button);return group?{group,values:snapshot(group)}:null;};
  window.mcDirtySaved=function(token,resets=[]){if(!token)return;
    for(const [el] of token.values)if(resets.includes(el.id))token.values.set(el,value(el));
    token.group.base=token.values;paint(token.group);};
  function init(){
    const selectors=['#st-app-pane .mc-settings-actions .btn-primary','#st-realm-pane .mc-settings-actions .btn-primary',
      '#st-user-pane .mc-settings-actions .btn-primary','#c-save','button[onclick^="mcSaveJob("]','button[onclick^="mcUpdSection("]'];
    for(const selector of selectors){const button=document.querySelector(selector);if(!button)continue;
      const root=button.closest('.mc-settings-pane')||button.closest('[id$="-pane"]')||button.closest('.mc-appscroll');if(!root)continue;
      const group={button,root};group.base=snapshot(group);groups.push(group);}
    const refresh=()=>groups.forEach(paint);
    document.addEventListener('input',refresh);document.addEventListener('change',refresh);
    document.addEventListener('click',()=>queueMicrotask(refresh));
    // Pickers also change hidden/select values programmatically.
    setInterval(refresh,400);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(init,0));else setTimeout(init,0);
})();
