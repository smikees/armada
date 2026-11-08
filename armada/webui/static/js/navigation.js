// Paint the destination immediately; the browser still owns the document request,
// authentication, history, redirects and cancellation. No HTML fetch/reinjection.
(function(){
  'use strict';
  let pending=null,panel=null;
  const pageNames={ministers:'Agents',goals:'Goals',jobs:'Jobs',inbox:'Inbox',memory:'Memory',
    skills:'Capabilities',artefacts:'Artefacts',docs:'Documentation',settings:'Settings',agent:'Agent',job:'Job',section:'Section'};
  function destination(value){
    let url;try{url=new URL(value,location.href);}catch(_){return null;}
    if(url.origin!==location.origin||!/^https?:$/.test(url.protocol))return null;
    const part=url.pathname.split('/')[1];
    if(url.pathname!=='/'&&!Object.hasOwn(pageNames,part))return null;
    return url;
  }
  function label(link,fallback){
    if(!link)return fallback;
    const copy=link.cloneNode(true);copy.querySelectorAll('.mc-count').forEach(n=>n.remove());
    return link.getAttribute('title')||copy.textContent.trim()||fallback;
  }
  function reset(){
    const old=pending;if(!old)return;pending=null;clearTimeout(old.timer);
    old.styles.forEach(([name,value,priority])=>{if(value)old.content.style.setProperty(name,value,priority);else old.content.style.removeProperty(name);});
    old.content.inert=old.inert;
    if(old.busy===null)old.content.removeAttribute('aria-busy');else old.content.setAttribute('aria-busy',old.busy);
    document.querySelectorAll('.mc-mainnav [aria-current],.mc-navigation-target').forEach(n=>{
      n.removeAttribute('aria-current');n.classList.remove('mc-navigation-target');
    });
    old.current.forEach(([node,value])=>node.setAttribute('aria-current',value));
    panel.hidden=true;
  }
  function show(value,signal){
    const url=destination(value);if(!url)return;
    const content=document.querySelector('.mc-appscroll');
    if(!content||!document.querySelector('.mc-mainnav'))return;
    reset();
    if(!panel){
      panel=document.createElement('section');panel.className='mc-navigation-loading';panel.hidden=true;
      panel.innerHTML='<h1 class="mc-navigation-title"></h1><p role="status" aria-live="polite">'
        +'<span class="mc-navigation-spinner" aria-hidden="true"></span>Loading page…</p>'
        +'<div class="mc-navigation-slow" hidden><p>This page is taking longer than usual.</p>'
        +'<button type="button" class="mc-btn mc-navigation-stay">Stay on this page</button></div>';
      content.after(panel);
      panel.querySelector('button').addEventListener('click',()=>{
        const focus=pending?.focus;window.stop();reset();if(focus?.isConnected)focus.focus({preventScroll:true});
      });
    }
    const part=url.pathname.split('/')[1],links=[...document.querySelectorAll('.mc-mainnav a.mc-tab[href],.mc-mainnav a.mc-nav-action[href]')];
    let selected=links.find(a=>new URL(a.href).pathname===url.pathname);
    if(part==='section')selected=document.querySelector('.mc-tab-user[data-i="'+Number(url.pathname.split('/')[2])+'"]');
    const sub=[...document.querySelectorAll('a.mc-sub[href]')].find(a=>new URL(a.href).pathname===url.pathname);
    const title=label(sub||selected,pageNames[part]||'Overview');
    if(!selected&&['agent','job'].includes(part))selected=links.find(a=>new URL(a.href).pathname==='/ministers');
    const rect=content.getBoundingClientRect(),properties=['visibility','position','top','left','width','height','box-sizing'];
    const entry={content,styles:properties.map(name=>[name,content.style.getPropertyValue(name),content.style.getPropertyPriority(name)]),inert:content.inert,busy:content.getAttribute('aria-busy'),
      current:[...document.querySelectorAll('.mc-mainnav [aria-current]')].map(n=>[n,n.getAttribute('aria-current')]),focus:document.activeElement};
    pending=entry;
    entry.current.forEach(([n])=>n.removeAttribute('aria-current'));
    if(selected){selected.setAttribute('aria-current','page');selected.classList.add('mc-navigation-target');}
    // Retain the old DOM at its existing size, outside flex layout. Its scroll,
    // filters, fields and iframes survive; the loading sibling fills the available
    // space in normal layout, including when the menu wraps during a resize.
    Object.assign(content.style,{visibility:'hidden',position:'fixed',top:rect.top+'px',left:rect.left+'px',
      width:rect.width+'px',height:rect.height+'px',boxSizing:'border-box'});
    content.inert=true;content.setAttribute('aria-busy','true');
    panel.querySelector('h1').textContent=title;
    panel.querySelector('.mc-navigation-slow').hidden=true;panel.hidden=false;
    entry.timer=setTimeout(()=>{if(pending===entry)panel.querySelector('.mc-navigation-slow').hidden=false;},8000);
    signal?.addEventListener('abort',()=>{if(pending===entry)reset();},{once:true});
  }
  if(window.navigation?.addEventListener){
    navigation.addEventListener('navigate',event=>{
      if(event.defaultPrevented||event.hashChange||event.downloadRequest!=null||event.formData||event.destination.sameDocument)return;
      show(event.destination.url,event.signal);
    });
  }else{
    // Older browser fallback: observe only ordinary same-window page links after
    // app handlers have had a chance to cancel or decorate them.
    window.addEventListener('click',event=>{
      if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.altKey||event.shiftKey)return;
      const link=event.target.closest?.('a[href]');if(!link||link.hasAttribute('download')||(link.target&&link.target!=='_self'))return;
      const url=destination(link.href);
      if(!url||(url.hash&&url.pathname===location.pathname&&url.search===location.search))return;
      show(url.href);
    });
  }
  // Custom section menus use location.href rather than anchors.
  window.mcNavigationPending=value=>{if(!window.navigation?.addEventListener)show(value);};
  window.addEventListener('pagehide',reset);
  window.addEventListener('pageshow',reset);
})();
