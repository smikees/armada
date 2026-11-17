// Switch the menu and visible page together; the browser owns the document request,
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
    if(old.selected){old.selected.removeAttribute('aria-current');
      if(old.busy===null)old.selected.removeAttribute('aria-busy');else old.selected.setAttribute('aria-busy',old.busy);}
    old.current.forEach(el=>el.setAttribute('aria-current','page'));
    old.outgoing.forEach(({el,inert,hidden})=>{
      el.classList.remove('mc-navigation-outgoing');el.inert=inert;
      if(hidden===null)el.removeAttribute('aria-hidden');else el.setAttribute('aria-hidden',hidden);
    });
    panel.hidden=true;
  }
  function place(){
    if(pending)panel.style.top=pending.nav.getBoundingClientRect().bottom+'px';
  }
  function show(value,signal){
    const url=destination(value);if(!url)return;
    const nav=document.querySelector('.mc-mainnav');if(!nav)return;
    reset();
    if(!panel){
      panel=document.createElement('section');panel.className='mc-navigation-loading';panel.hidden=true;
      panel.innerHTML='<h2 class="mc-h-page mc-navigation-title"></h2>'
        +'<div class="mc-navigation-status" role="status" aria-live="polite">'
        +'<span class="mc-loading-spinner" aria-hidden="true"></span><span class="mc-navigation-label"></span></div>'
        +'<div class="mc-navigation-slow" hidden><p>This page is taking longer than usual.</p>'
        +'<button type="button" class="btn btn-secondary btn-sm mc-navigation-stay">Stay on this page</button></div>';
      document.body.append(panel);
      panel.querySelector('button').addEventListener('click',()=>{
        const focus=pending?.focus;window.stop();reset();if(focus?.isConnected)focus.focus({preventScroll:true});
      });
    }
    const part=url.pathname.split('/')[1],links=[...nav.querySelectorAll('a[href]')];
    let selected=links.find(a=>new URL(a.href).pathname===url.pathname);
    if(part==='section')selected=document.querySelector('.mc-tab-user[data-i="'+Number(url.pathname.split('/')[2])+'"]');
    const sub=[...document.querySelectorAll('a.mc-sub[href]')].find(a=>new URL(a.href).pathname===url.pathname);
    selected=sub||selected;
    const title=label(selected,pageNames[part]||'Overview');
    const current=selected?[...(sub?document:nav).querySelectorAll(sub?'.mc-sub[aria-current="page"]':'[aria-current="page"]')]:[];
    const outgoing=[...nav.parentElement.children].filter(el=>
      el!==nav&&el!==panel&&!['SCRIPT','STYLE','TEMPLATE','LINK'].includes(el.tagName)&&
      (nav.compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING));
    const entry={nav,selected,current,outgoing:outgoing.map(el=>({el,inert:el.inert,hidden:el.getAttribute('aria-hidden')})),
      busy:selected?.getAttribute('aria-busy')??null,focus:document.activeElement};
    pending=entry;
    // Keep the original DOM and geometry for cancellation, pagehide persistence
    // and browser Back. Cover the whole page below the menu, including agent chrome.
    entry.outgoing.forEach(({el})=>{el.classList.add('mc-navigation-outgoing');el.inert=true;el.setAttribute('aria-hidden','true');});
    if(selected){current.forEach(el=>el.removeAttribute('aria-current'));
      selected.setAttribute('aria-current','page');selected.setAttribute('aria-busy','true');}
    panel.querySelector('.mc-navigation-title').textContent=title;
    panel.querySelector('.mc-navigation-label').textContent='Loading '+title.toLowerCase()+'…';
    panel.querySelector('.mc-navigation-slow').hidden=true;place();panel.hidden=false;
    entry.timer=setTimeout(()=>{if(pending===entry)panel.querySelector('.mc-navigation-slow').hidden=false;},8000);
    signal?.addEventListener('abort',()=>{if(pending===entry)reset();},{once:true});
  }
  if(window.navigation?.addEventListener){
    navigation.addEventListener('navigate',event=>{
      if(event.defaultPrevented||event.hashChange||event.downloadRequest!=null||event.formData||event.destination.sameDocument)return;
      show(event.destination.url,event.signal);
    });
    navigation.addEventListener('navigateerror',reset);
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
  window.addEventListener('resize',place);
  const nav=document.querySelector('.mc-mainnav');
  if(nav&&window.ResizeObserver)new ResizeObserver(place).observe(nav);
})();
