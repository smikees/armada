// The setup wizard (launch plan 6.4; webui/setup_wizard.py, setupflow.py). One page per half:
// "welcome" (before the realm: welcome, checks, folder, team) and "realm" (inside it: capabilities,
// first job, tour, done). Alexander's lines come from MC_SU.script, written in advance.
(function(){
  const SU=window.MC_SU||{}; const STEPS=(SU.script&&SU.script.steps||[]).map(s=>s[0]);
  const LINES=(SU.script&&SU.script.lines)||{}; const IC=SU.icons||{};
  const $=id=>document.getElementById(id);
  const vals=Object.assign({},SU.vals||{});
  let cur=null, pendingAdopt='', progress=Promise.resolve(), movingFolder=false;

  function fill(t,v){return String(t||'').replace(/\{(\w+)\}/g,(m,k)=>(v&&v[k]!=null&&v[k]!=='')?v[k]:m);}
  function line(step,key,v){return fill((LINES[step]||{})[key],Object.assign({},vals,v||{}));}
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  function say(id,msg,bad){const m=$(id);if(!m)return;m.textContent=msg||'';m.classList.toggle('is-bad',!!bad);}
  async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});return r.json();}
  function busy(btn,on,label){if(!btn)return;if(on){btn.dataset.label=btn.innerHTML;btn.disabled=true;
      btn.innerHTML='<span class="mc-su-spin" aria-hidden="true"></span>'+esc(label||'Working…');}
    else{btn.disabled=false;if(btn.dataset.label)btn.innerHTML=btn.dataset.label;}}

  // --- moving between steps ---------------------------------------------------------------------
  function paintRail(step){const i=STEPS.indexOf(step);
    document.querySelectorAll('.mc-su-rstep').forEach(li=>{const j=STEPS.indexOf(li.dataset.step);
      const done=j<i;
      li.classList.toggle('is-done',done);li.classList.toggle('is-current',j===i);
      if(j===i)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');});
    const c=$('su-count');if(c)c.textContent='Step '+(i+1)+' of '+STEPS.length;}
  window.mcSuGo=function(step){
    if(movingFolder)return;
    const next=document.querySelector('.mc-su-pane[data-step="'+step+'"]');if(!next)return;
    if(cur&&cur!==next){cur.hidden=true;cur.classList.remove('is-in');}
    next.hidden=false;void next.offsetWidth;next.classList.add('is-in');cur=next;
    document.body.classList.toggle('is-intro',step==='intro');
    if(step==='checks')pendingAdopt='';
    paintRail(step);window.scrollTo({top:0});
    const f=next.querySelector('input:not([type=radio]):not([type=checkbox]):not([disabled]),.mc-su-foot .btn-primary:not([disabled])');
    if(f&&step!=='intro')setTimeout(()=>f.focus({preventScroll:true}),60);
    if(SU.half==='realm')progress=progress.then(()=>post('/api/setup-step',{step})).catch(()=>{});
    if(step==='checks')mcSuCheck();
    if(step==='team'&&window.mcSuPaintTeam)mcSuPaintTeam();
    if(step==='capabilities'){if(capsDone){capsDone=false;document.querySelectorAll('.su-cap').forEach(c=>c.disabled=false);}capCount();}
    if(step==='done')paintSummary();};
  document.addEventListener('keydown',e=>{
    if(e.key!=='Enter'||e.shiftKey||!cur)return;const t=e.target;
    if(t?.closest('dialog'))return;
    if(t&&(t.closest('button,a,summary,select,textarea')||t.matches('input[type=checkbox],input[type=radio]')))return;
    const b=cur.querySelector('.mc-su-foot .btn-primary');if(b&&!b.disabled){e.preventDefault();b.click();}});

  // --- checks -------------------------------------------------------------------------------------
  window.mcSuCheck=async function(manual=false){
    if(!window.mcRefreshProviders)return;
    const b=$('su-recheck');if(manual&&b?.disabled)return;
    if(manual){b.disabled=true;b.classList.add('is-checking');b.setAttribute('aria-busy','true');b.innerHTML=IC.refresh+' Checking…';say('su-check-feedback','Checking installed CLIs and provider sign-ins…');}
    try{const result=await window.mcRefreshProviders(manual);if(manual)say('su-check-feedback',result?'Checked just now.':'Could not complete the check. Try again.',!result);}
    finally{if(manual){b.disabled=false;b.classList.remove('is-checking');b.removeAttribute('aria-busy');b.innerHTML=IC.refresh+' Check again';}}
  };
  window.addEventListener('armada:providers',e=>{
    const connected=Object.values(e.detail.providers).some(p=>p.connected);
    const button=$('su-checks-next');if(button)button.disabled=!connected;
    say('su-checkline',connected?'Connected. You can add or change model providers later in App settings.':'Connect at least one provider to continue.');
  });

  // --- folder and name ----------------------------------------------------------------------------
  window.mcSuPick=async function(){try{const r=await(await fetch('/api/pick-folder')).json();
    if(r.ok&&r.path)$('su-root').value=r.path;else if(r.error)say('su-homemsg',r.error,true);}catch(e){}};
  window.mcSuHome=async function(btn){
    const root=($('su-root').value||'').trim();
    if(SU.half==='realm'){
      movingFolder=true;const back=cur.querySelector('.btn-secondary');if(back)back.disabled=true;
      busy(btn,true,'Saving folder…');say('su-homemsg','');
      try{await progress;const r=await post('/api/setup-folder',{path:root});
        if(!r.ok){say('su-homemsg',r.error,true);return;}
        location.href='/switch?path='+encodeURIComponent(r.path)+'&to=/setup';
      }catch(e){say('su-homemsg','Could not move your realm. Try again.',true);}finally{movingFolder=false;if(back)back.disabled=false;busy(btn,false);}return;
    }
    if(!root){say('su-homemsg','Choose a folder first.',true);$('su-root').focus();return;}
    busy(btn,true,'Checking the folder…');say('su-homemsg','');
    try{const r=await post('/api/set-approot',{root,create:true});
      if(!r.ok){say('su-homemsg',line('home','folder_bad',{reason:(r.error||'it can’t be used').replace(/\.$/,'')}),true);return;}
      SU.haveRoot=true;
      if(pendingAdopt){
        const adopted=await post('/api/new-realm',{mode:'adopt',path:pendingAdopt});
        if(!adopted.ok){say('su-homemsg',adopted.error,true);return;}
        location.href='/switch?path='+encodeURIComponent(adopted.path)+'&to=/';return;
      }
      mcSuGo('naming');}
    catch(e){say('su-homemsg','Couldn’t save the folder: '+e,true);}finally{busy(btn,false);}};

  // --- team ---------------------------------------------------------------------------------------
  window.mcSuNaming=function(){
    for(const [id,label] of [['su-owner','your name'],['su-name','a realm name']]){
      const input=$(id);if(!input.value.trim()){say('su-namingmsg','Enter '+label+' to continue.',true);input.focus();return;}
    }
    say('su-namingmsg','');mcSuGo('team');
  };
  window.mcSuAppoint=async function(btn){
    const chosen=window.mcSuTeamSelection();
    if(!chosen)return;
    busy(btn,true,SU.half==='realm'?'Saving your team…':'Appointing your team…');say('su-teammsg','');
    try{await progress;const r=await post(SU.half==='realm'?'/api/setup-team':'/api/first-realm',{...chosen,wizard:true,check_providers:true});
      if(!r.ok){say('su-teammsg',r.error||'Couldn’t create the realm.',true);return;}
      document.body.classList.add('is-leaving');
      location.href=SU.half==='realm'?'/setup':'/switch?path='+encodeURIComponent(r.path)+'&to=/setup';}
    catch(e){say('su-teammsg','Couldn’t create the realm: '+e,true);}finally{busy(btn,false);}};
  window.mcSuAdopt=async function(btn){btn.disabled=true;say('su-adoptmsg','Choose the realm’s folder…');
    try{const pr=await(await fetch('/api/pick-folder')).json();
      if(!(pr.ok&&pr.path)){say('su-adoptmsg',pr.error||'');return;}
      if(!SU.haveRoot){
        pendingAdopt=pr.path;
        const parts=pr.path.replace(/[\\/]+$/,'').split(/[\\/]/);
        $('su-name').value=parts.pop()||'My realm';
        const parent=parts.join(pr.path.includes('\\')?'\\':'/');
        $('su-root').value=/^[A-Za-z]:$/.test(parent)?parent+'\\':parent||'/';
        mcSuGo('home');
        say('su-homemsg','Confirm the Armada folder containing your existing realm, then continue to open it.');return;
      }
      const r=await post('/api/new-realm',{mode:'adopt',path:pr.path});
      if(!r.ok){say('su-adoptmsg',r.error+(r.suggested_path?' Move it to '+r.suggested_path+' and try again.':''),true);return;}
      location.href='/switch?path='+encodeURIComponent(r.path)+'&to=/';}
    catch(e){say('su-adoptmsg','Couldn’t open it: '+e,true);}finally{btn.disabled=false;}};

  // --- capabilities -------------------------------------------------------------------------------
  let capsDone=false; const added=[];
  function capCount(){const n=document.querySelectorAll('.su-cap:checked').length,b=$('su-caps-add');
    if(b)b.textContent=n?'Add and continue':'Continue without any';}
  document.addEventListener('change',e=>{if(!e.target.matches('.su-cap,.su-cap-enabled'))return;
    const row=e.target.closest('.mc-su-cap-choice'),include=row.querySelector('.su-cap'),toggle=row.querySelector('.su-cap-enabled');
    if(e.target===include){if(!include.checked){toggle.dataset.previous=String(toggle.checked);toggle.checked=false;toggle.disabled=true;}
      else{toggle.disabled=false;toggle.checked=toggle.dataset.previous==='true';}}
    delete row.dataset.savedEnabled;capsDone=false;capCount();
    const group=row.closest('.mc-cap-grp');
    if(group)[...group.querySelectorAll('.mc-su-cap-choice')].sort((a,b)=>Number(b.querySelector('.su-cap-enabled').checked)-Number(a.querySelector('.su-cap-enabled').checked)).forEach(r=>group.appendChild(r));
  });
  window.mcSuCapsSkip=function(){mcSuGo('first-job');};
  window.mcSuCapsAdd=async function(btn){
    if(capsDone){mcSuGo('first-job');return;}
    const rows=[...document.querySelectorAll('.mc-su-cap-choice')].filter(r=>r.querySelector('.su-cap').checked);
    if(!rows.length){say('su-capmsg',line('capabilities','none'));mcSuGo('first-job');return;}
    document.querySelectorAll('.su-cap,.su-cap-enabled').forEach(c=>c.disabled=true);busy(btn,true,'Adding…');let bad=0;
    for(const row of rows){const st=row.querySelector('.mc-su-capst');st.innerHTML='<span class="mc-su-spin"></span>';
      const enabled=row.querySelector('.su-cap-enabled').checked;
      if(row.dataset.savedEnabled===String(enabled)){st.textContent='Added';continue;}
      try{const r=await post('/api/setup-capability',{key:row.dataset.key,enabled});
        if(r.ok){st.textContent=r.pending_setup?'Added · Connection setup required':enabled?'Added and enabled':'Added · Disabled';row.classList.add('is-added');row.dataset.savedEnabled=String(enabled);if(!added.includes(r.name))added.push(r.name);}
        else{bad++;st.innerHTML=IC.bad||'✗';st.title=r.error||'';}}
      catch(e){bad++;st.innerHTML=IC.bad||'✗';}}
    capsDone=!bad;busy(btn,false);btn.textContent=bad?'Retry remaining':'Add and continue';
    document.querySelectorAll('.su-cap').forEach(c=>c.disabled=false);
    document.querySelectorAll('.su-cap-enabled').forEach(c=>c.disabled=!c.closest('.mc-su-cap-choice').querySelector('.su-cap').checked);
    say('su-capmsg',bad?(bad+' didn’t go in. Retry, or choose I’ll do this later to continue.'):'',!!bad);
    if(!bad)mcSuGo('first-job');};

  // --- the first brief ----------------------------------------------------------------------------
  function revealWords(body,html,onFirstWord){
    const source=document.createElement('template');source.innerHTML=html;
    const steps=[];let count=0;
    function queue(node,parent){
      if(node.nodeType===Node.TEXT_NODE){
        const copy=document.createTextNode('');steps.push({word:false,run:()=>parent.append(copy)});
        const tokens=node.textContent.match(/\s*\S+\s*|\s+/g)||[];
        for(const token of tokens){const word=/\S/.test(token);if(word)count++;
          steps.push({word,run:()=>{copy.textContent+=token;}});}
      }else if(node.nodeType===Node.ELEMENT_NODE){
        const copy=node.cloneNode(false);steps.push({word:false,run:()=>parent.append(copy)});
        node.childNodes.forEach(child=>queue(child,copy));
      }
    }
    source.content.childNodes.forEach(node=>queue(node,body));
    if(matchMedia('(prefers-reduced-motion: reduce)').matches){steps.forEach(s=>s.run());onFirstWord();return Promise.resolve();}
    const wordsPerFrame=Math.max(1,Math.ceil(count/300));
    return new Promise(resolve=>{let index=0,revealed=false;
      function frame(){let shown=0;
        while(index<steps.length&&shown<wordsPerFrame){const step=steps[index++];step.run();if(step.word){if(!revealed){onFirstWord();revealed=true;}shown++;}}
        if(index<steps.length)requestAnimationFrame(frame);else resolve();}
      requestAnimationFrame(frame);
    });
  }
  let briefState='idle', t0=0, tick=null;
  function briefBtn(){return $('su-brief-run');}
  window.mcSuBriefSkip=function(){if(briefState==='running')return;if(briefState==='idle')briefState='skipped';say('su-briefmsg',line('first-job','skipped'));mcSuGo('tour');};
  window.mcSuBrief=async function(btn){
    if(briefState==='done'||briefState==='failed'){mcSuGo('tour');return;}
    if(briefState==='running')return;
    briefState='running';busy(btn,true,'Working…');$('su-brief-skip').hidden=true;
    say('su-briefmsg',line('first-job','running'));
    const rep=$('su-reply'),body=$('su-replybody');rep.hidden=true;body.replaceChildren();
    t0=Date.now();tick=setInterval(()=>{const s=Math.round((Date.now()-t0)/1000);$('su-replytime').textContent=s+'s';},500);
    let text='',ok=false,err='',rendered=0,paint=Promise.resolve();
    function queueMarkdown(final=false){
      const boundary=text.lastIndexOf('\n\n');
      const end=final?text.length:(boundary<0?0:boundary+2);
      if(end<=rendered)return;
      const segment=text.slice(rendered,end);rendered=end;
      paint=paint.then(async()=>{const m=await post('/api/render-md',{text:segment});
        if(!m.ok)throw Error('Could not format the reply');
        await revealWords(body,m.html,()=>{rep.hidden=false;});});
    }
    try{let thread=SU.briefThread;
      const nt=await post('/api/new-thread',{agent:SU.coordinator,name:SU.briefTitle});
      if(nt.ok&&nt.thread)thread=nt.thread;
      const resp=await fetch('/api/chat-stream',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({agent:SU.coordinator,thread,message:SU.briefPrompt,tid:'su'+Date.now()})});
      const reader=resp.body.getReader(),dec=new TextDecoder();let buf='';
      // The server keeps the connection open after its 'done' event (it still marks the thread
      // unread, and may rename it), so the turn is over at 'done', not at the end of the stream.
      let over=false;
      while(!over){const r=await reader.read();if(r.done)break;buf+=dec.decode(r.value,{stream:true});let i;
        while((i=buf.indexOf('\n\n'))>=0){const ch=buf.slice(0,i).replace(/^data:\s?/,'');buf=buf.slice(i+2);if(!ch.trim())continue;
          let ev;try{ev=JSON.parse(ch);}catch(x){continue;}
          if(ev.kind==='text'){text+=ev.text;queueMarkdown();}
          else if((ev.kind==='result'||ev.kind==='done')&&ev.output&&!text.trim()){text=ev.output;queueMarkdown();}
          if(ev.kind==='done'){ok=ev.ok!==false&&!!text.trim();if(!ok)err=ev.error||ev.output||'';over=true;}
          else if(ev.kind==='error'){err=ev.error||'failed';over=true;}}}
      try{reader.cancel();}catch(x){}}
    catch(e){err=String(e);}
    clearInterval(tick);
    // A complete Markdown block is formatted before any of its words appear. The final
    // block is flushed at the end, so headings and emphasis never flash as raw syntax.
    if(text.trim()){queueMarkdown(true);try{await paint;}
      catch(e){ok=false;err='Could not format the reply. It is saved in the agent’s thread.';}}
    if(ok){
      briefState='done';say('su-briefmsg',line('first-job','ok'));}
    else{briefState='failed';
      say('su-briefmsg',line('first-job','failed',{reason:(err||'no reply came back').slice(0,160).replace(/\.$/,'')}),true);}
    busy(btn,false);btn.textContent='Continue';};

  // --- done ---------------------------------------------------------------------------------------
  function paintSummary(){const ul=$('su-summary');if(!ul)return;
    const caps=added.length||SU.capsOn||0, brief=briefState==='done'||SU.briefDone;
    const rows=[[true,(vals.realm||'Your realm')+' is set up with '+SU.agents+(SU.agents===1?' agent':' agents')+'.'],
      [caps>0,caps?caps+(caps===1?' capability':' capabilities')+' added.':'No capabilities yet. Add them from Capabilities whenever you like.'],
      [brief,brief?'Your first brief is waiting in '+vals.coordinator+'’s threads.':'The first brief can wait. Run it from '+vals.coordinator+'’s page.'],
      [true,'The scheduler will be running when you open '+(vals.realm||'the realm')+', and it starts with Windows.']];
    ul.innerHTML=rows.map(([on,t])=>'<li class="'+(on?'is-ok':'is-skip')+'"><span>'+(on?(IC.ok||'✓'):(IC.dot||'·'))+'</span>'+esc(t)+'</li>').join('');}
  window.mcSuFinish=async function(btn,destination='/'){busy(btn,true,'Opening…');say('su-donemsg','');
    try{await progress;const r=await post('/api/setup-finish');if(!r.ok)throw Error(r.error||'Could not finish setup.');
      document.body.classList.add('is-leaving');setTimeout(()=>{location.replace(destination);},180);}
    catch(e){say('su-donemsg',e.message||'Could not finish setup. Try again.',true);busy(btn,false);}};

  document.addEventListener('DOMContentLoaded',()=>{
    // Back after a reload with the brief already in its thread: don't run it twice.
    if(SU.half==='realm'&&SU.briefDone&&$('su-brief-run')){briefState='done';$('su-brief-run').textContent='Continue';
      $('su-brief-skip').hidden=true;say('su-briefmsg',line('first-job','ok'));}
    mcSuGo(SU.first||STEPS[0]);
    requestAnimationFrame(()=>document.body.classList.add('is-ready'));});
  window.addEventListener('pageshow',e=>{if(e.persisted)location.reload();});
})();
