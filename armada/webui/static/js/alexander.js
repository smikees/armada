// Alexander's drawer (launch plan 6.2, 6.3, 6.6; armada/alexander/support.py). The button beside
// the gear opens it on every page; "Ask Alexander" on a failed run opens it about that run.
// He proposes; the owner presses a card's button; the app does the work through its own endpoints.
(function(){
  const KEY='mc-alex-conv';
  const I={
    x:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="2" d="M6 6l12 12M18 6L6 18"/></svg>',
    fresh:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M12 20H6l-3 3V6a2 2 0 0 1 2-2h7m5-1v6m-3-3h6"/></svg>',
    send:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19V5m-6 6l6-6l6 6"/></svg>',
    remedy:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18l3 3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.6 2.6l-2.4-.6l-.6-2.4z"/></svg>',
    addon:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linejoin="round" stroke-width="1.8" d="M4 4h7v7H4zm9 0h7v7h-7zM4 13h7v7H4zm12.5 0v7M13 16.5h7"/></svg>',
    report:'<svg width="16" height="16" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M4 6h16v12H4zm0 0l8 7l8-7"/></svg>',
    ok:'<svg width="15" height="15" viewBox="0 0 24 24"><path fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2.4" d="M5 12.5l4.5 4.5L19 7.5"/></svg>'};
  let el=null, busy=false, pending=null;
  const $=s=>el&&el.querySelector(s);
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function conv(){try{return localStorage.getItem(KEY)||'';}catch(e){return '';}}
  function setConv(id){try{localStorage.setItem(KEY,id||'');}catch(e){}}
  async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});return r.json();}

  // [help: jobs#schedules] → a link to the page; [realm: …] and [log: …] → quiet chips.
  function cites(html){
    return html.replace(/\[help:\s*([a-z0-9-]+)(#[a-z0-9-]+)?\]/gi,(m,p,h)=>'<a class="mc-ax-cite" href="/docs/'+p+(h||'')+'" title="Open the help page">Help · '+p.replace(/-/g,' ')+'</a>')
               .replace(/\[(realm|log):\s*([^\]]{1,80})\]/gi,(m,k,v)=>'<span class="mc-ax-cite is-quiet" title="'+(k==='log'?'From ARMADA’s log':'From this realm')+'">'+v+'</span>');}

  function build(){
    el=document.createElement('div');el.className='mc-ax';el.innerHTML=
      '<div class="mc-ax-scrim" data-close></div>'
      +'<aside class="mc-ax-panel" role="dialog" aria-label="Alexander" aria-modal="false">'
      +'<header class="mc-ax-head"><img src="/static/alexander.png" alt="" width="40" height="40">'
      +'<div class="mc-ax-who"><div class="mc-ax-name">Alexander</div><div class="mc-eyebrow">ARMADA’s guide</div></div>'
      +'<button type="button" class="mc-iconbtn" title="New conversation" data-new>'+I.fresh+'</button>'
      +'<button type="button" class="mc-iconbtn" title="Close" data-close>'+I.x+'</button></header>'
      +'<div class="mc-ax-body" aria-live="polite"></div>'
      +'<form class="mc-ax-compose"><textarea rows="1" maxlength="6000" placeholder="Ask about ARMADA, or tell me what’s wrong…"></textarea>'
      +'<button type="submit" class="mc-ax-send" title="Send">'+I.send+'</button></form>'
      +'<footer class="mc-ax-foot"><span>Opus 5.5 · uses your Claude plan, counted as System</span>'
      +'<button type="button" class="btn-link" data-report>Report an issue yourself</button></footer></aside>';
    document.body.appendChild(el);
    el.querySelectorAll('[data-close]').forEach(b=>b.onclick=close);
    $('[data-new]').onclick=()=>{setConv('');paintEmpty();$('textarea').focus();};
    $('[data-report]').onclick=()=>{close();if(window.mcSupportOpen)mcSupportOpen();};
    const ta=$('textarea');
    ta.addEventListener('input',()=>{ta.style.height='auto';ta.style.height=Math.min(160,ta.scrollHeight)+'px';});
    ta.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}});
    $('form').onsubmit=e=>{e.preventDefault();send();};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&el&&el.classList.contains('is-open'))close();});
  }
  function close(){if(el)el.classList.remove('is-open');}
  function scroll(){const b=$('.mc-ax-body');if(b)b.scrollTop=b.scrollHeight;}

  function paintEmpty(){
    const pg=location.pathname;
    const sugg=pg.startsWith('/jobs')||pg.startsWith('/job/')?['Why didn’t my job run?','How do schedules work?','Make a job run every weekday at 8']
      :pg.startsWith('/skills')?['Which capabilities are safe to add?','What does Low risk mean?','Connect my calendar']
      :['What can my team do for me?','Build me a dashboard widget','Is everything working?'];
    $('.mc-ax-body').innerHTML='<div class="mc-ax-empty"><p class="mc-ax-lede">What can I help with?</p>'
      +'<p>I know how ARMADA works and I can see this realm. I can explain things, fix what’s fixable, build you a dashboard widget, or write up a problem for the ARMADA team.</p>'
      +'<div class="mc-ax-sugg">'+sugg.map(s=>'<button type="button" class="mc-ax-chip">'+esc(s)+'</button>').join('')+'</div></div>';
    el.querySelectorAll('.mc-ax-chip').forEach(b=>b.onclick=()=>{$('textarea').value=b.textContent;send();});}

  function bubble(role,html,cards){
    const b=$('.mc-ax-body');const e=b.querySelector('.mc-ax-empty');if(e)e.remove();
    const d=document.createElement('div');d.className='mc-ax-msg is-'+role;
    d.innerHTML=role==='alexander'?'<img src="/static/alexander.png" alt="" width="26" height="26"><div class="mc-ax-text mc-md">'+cites(html)+'</div>'
      :'<div class="mc-ax-text">'+html+'</div>';
    b.appendChild(d);(cards||[]).forEach(c=>d.querySelector('.mc-ax-text').appendChild(card(c)));scroll();return d;}

  function card(c){
    const d=document.createElement('div');d.className='mc-ax-card is-'+c.type;
    d.innerHTML='<div class="mc-ax-cardhead"><span class="mc-ax-cardicon">'+(I[c.type]||'')+'</span>'
      +'<span class="mc-eyebrow">'+({remedy:'A fix',addon:'An add-on',report:'A report'}[c.type]||'')+'</span></div>'
      +'<p class="mc-ax-what">'+esc(c.what)+'</p>'+(c.why?'<p class="mc-ax-why">'+esc(c.why)+'</p>':'')
      +'<div class="mc-ax-cardrow"><button type="button" class="btn btn-primary btn-sm">'+esc(c.button||'Do it')+'</button>'
      +(c.type==='addon'?'<label class="mc-ax-scope"><input type="checkbox"> every realm on this computer</label>':'')
      +'<span class="mc-ax-cardmsg"></span></div>';
    const btn=d.querySelector('button'),msg=d.querySelector('.mc-ax-cardmsg');
    btn.onclick=async()=>{
      if(c.type==='report'){close();if(window.mcSupportOpen)mcSupportOpen({message:c.message});return;}
      if(c.href){location.href=c.href;return;}
      btn.disabled=true;msg.textContent='Working…';msg.className='mc-ax-cardmsg';
      try{let r;
        if(c.type==='addon'){r=await post('/api/alexander-addon',{manifest:c.manifest,scope:d.querySelector('.mc-ax-scope input').checked?'app':'realm'});}
        else if(c.method==='GET'){r=await(await fetch(c.endpoint)).json();}
        else r=await post(c.endpoint,c.body||{});
        const ok=r&&r.ok!==false&&!r.error;
        msg.innerHTML=ok?I.ok+' Done':esc((r&&(r.error||r.output||r.detail))||'That didn’t work.');
        msg.className='mc-ax-cardmsg '+(ok?'is-ok':'is-bad');
        if(ok){btn.remove();if(c.type==='addon'&&location.pathname==='/')setTimeout(()=>location.reload(),900);}
        else btn.disabled=false;}
      catch(e){msg.textContent='That didn’t work: '+e;msg.className='mc-ax-cardmsg is-bad';btn.disabled=false;}};
    return d;}

  async function load(){
    const id=conv();if(!id){paintEmpty();return;}
    try{const r=await post('/api/alexander-history',{id});
      if(!r.ok||!r.messages.length){paintEmpty();return;}
      $('.mc-ax-body').innerHTML='';
      r.messages.forEach(m=>bubble(m.role,m.role==='alexander'?m.html:esc(m.text),m.cards));}
    catch(e){paintEmpty();}}

  async function send(item){
    if(busy)return;const ta=$('textarea');const text=(ta.value||'').trim();if(!text)return;
    busy=true;ta.value='';ta.style.height='auto';
    bubble('owner',esc(text));
    const think=document.createElement('div');think.className='mc-ax-msg is-alexander is-thinking';
    think.innerHTML='<img src="/static/alexander.png" alt="" width="26" height="26"><div class="mc-ax-text"><span class="mc-ax-dots"><i></i><i></i><i></i></span><span class="mc-ax-status">Reading your realm</span></div>';
    $('.mc-ax-body').appendChild(think);scroll();
    const t0=Date.now(),st=think.querySelector('.mc-ax-status');let phase='Reading your realm';
    const tick=setInterval(()=>{st.textContent=phase+' · '+Math.round((Date.now()-t0)/1000)+'s';},1000);
    let done=null,streamed='';
    try{const resp=await fetch('/api/alexander-ask',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({id:conv(),message:text,page:location.pathname+location.search,item:item||pending||null})});
      pending=null;
      const rd=resp.body.getReader(),dec=new TextDecoder();let buf='';
      while(!done){const r=await rd.read();if(r.done)break;buf+=dec.decode(r.value,{stream:true});let i;
        while((i=buf.indexOf('\n\n'))>=0){const ch=buf.slice(0,i).replace(/^data:\s?/,'');buf=buf.slice(i+2);
          let ev;try{ev=JSON.parse(ch);}catch(x){continue;}
          if(ev.kind==='status')phase='Thinking';
          else if(ev.kind==='text'){phase='Writing';streamed+=ev.text;}
          else if(ev.kind==='done')done=ev;}}
      try{rd.cancel();}catch(x){}}
    catch(e){done={ok:false,error:String(e)};}
    clearInterval(tick);think.remove();
    if(done&&done.ok){setConv(done.id);bubble('alexander',done.html||esc(done.text),done.cards);}
    else bubble('alexander','<p class="mc-ax-err">I couldn’t answer that: '+esc((done&&done.error)||'no reply came back')
      +'. If it keeps happening, use “Report an issue yourself” below.</p>');
    busy=false;$('textarea').focus();}

  window.mcAlexOpen=function(){if(!el)build();el.classList.add('is-open');load();setTimeout(()=>$('textarea').focus(),120);};
  // From a failed run: open about it, with the run attached to the first question.
  window.mcAlexAsk=function(item){setConv('');window.mcAlexOpen();pending=item||null;
    const ta=$('textarea');ta.value='This run failed ('+(item&&item.job||'a job')+', '+(item&&item.ts||'')+'). What went wrong, and can you fix it?';
    send(item);};
})();
