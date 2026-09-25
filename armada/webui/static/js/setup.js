// The setup wizard (launch plan 6.4; webui/setup_wizard.py, setupflow.py). One page per half:
// "welcome" (before the realm: welcome, checks, folder, team) and "realm" (inside it: capabilities,
// first job, tour, done). Alexander's lines come from MC_SU.script, written in advance.
(function(){
  const SU=window.MC_SU||{}; const STEPS=(SU.script&&SU.script.steps||[]).map(s=>s[0]);
  const LINES=(SU.script&&SU.script.lines)||{}; const IC=SU.icons||{};
  const $=id=>document.getElementById(id);
  const vals=Object.assign({},SU.vals||{});
  let cur=null, pollT=null;

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
      const done=(SU.half==='realm'&&j<4)||j<i;
      li.classList.toggle('is-done',done);li.classList.toggle('is-current',j===i);
      if(j===i)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');});
    const c=$('su-count');if(c)c.textContent='Step '+(i+1)+' of '+STEPS.length;}
  window.mcSuGo=function(step){
    const next=document.querySelector('.mc-su-pane[data-step="'+step+'"]');if(!next)return;
    if(cur&&cur!==next){cur.hidden=true;cur.classList.remove('is-in');}
    next.hidden=false;void next.offsetWidth;next.classList.add('is-in');cur=next;
    paintRail(step);window.scrollTo({top:0});
    const f=next.querySelector('input:not([type=radio]):not([type=checkbox]):not([disabled]),.mc-su-foot .btn-primary:not([disabled])');
    if(f)setTimeout(()=>f.focus({preventScroll:true}),60);
    if(SU.half==='realm')post('/api/setup-step',{step}).catch(()=>{});
    if(step==='checks')mcSuCheck(true);else stopPoll();
    if(step==='team')paintTeam();
    if(step==='capabilities')capCount();
    if(step==='done')paintSummary();};
  document.addEventListener('keydown',e=>{
    if(e.key!=='Enter'||e.shiftKey||!cur)return;const t=e.target;
    if(t&&(t.tagName==='TEXTAREA'||t.tagName==='BUTTON'||t.tagName==='A'))return;
    const b=cur.querySelector('.mc-su-foot .btn-primary');if(b&&!b.disabled){e.preventDefault();b.click();}});

  // --- checks -------------------------------------------------------------------------------------
  function mark(id,state,detail){const li=$(id);if(!li)return;
    li.classList.remove('is-ok','is-bad','is-wait','is-warn');li.classList.add('is-'+state);
    li.querySelector('.mc-su-ckicon').innerHTML=state==='wait'?'<span class="mc-su-spin"></span>':(IC[state]||'');
    const d=$(id+'-d');if(d)d.textContent=detail;}
  function stopPoll(){if(pollT){clearInterval(pollT);pollT=null;}}
  function startPoll(){if(!pollT)pollT=setInterval(()=>mcSuCheck(true,true),4000);}
  const PLANS={pro:'Pro',max:'Max',team:'Team',enterprise:'Enterprise'};
  window.mcSuCheck=async function(force,quiet){
    if(!quiet){mark('su-ck-cli','wait','Checking…');mark('su-ck-auth','wait','Checking…');}
    let d=null;try{d=await(await fetch('/api/auth-status'+(force?'?force=1':''),{cache:'no-store'})).json();}catch(e){}
    if(!d){mark('su-ck-cli','bad','Couldn’t check. Try again.');return;}
    const cli=d.reason!=='cli-missing', inn=!!d.logged_in, plan=String(d.plan||'').toLowerCase();
    const old=cli&&d.version_ok===false;
    mark('su-ck-cli',!cli?'bad':old?'warn':'ok',!cli?'Not installed':
      old?('Version '+d.version+'. ARMADA needs '+d.min_version+' or newer.'):('Installed'+(d.version?' · '+d.version:'')));
    $('su-ck-cli-a').hidden=cli&&!old; if(cli)$('su-install').hidden=true;
    const ib=$('su-ck-cli-a').querySelector('button');if(ib){ib.textContent=old?'Update Claude Code':'Install Claude Code';ib.dataset.update=old?'1':'';}
    if(!cli)mark('su-ck-auth','wait','Waiting for Claude Code');
    else if(inn){const p=PLANS[plan];const unsure=d.method==='claude.ai'&&!p;
      mark('su-ck-auth',unsure?'warn':'ok','Signed in'+(p?' · '+p+' plan':''));}
    else mark('su-ck-auth','bad','Signed out');
    $('su-ck-auth-a').hidden=!(cli&&!inn);
    const unsure=inn&&d.method==='claude.ai'&&!PLANS[plan];
    const key=!cli?'no_claude':old?'old_claude':!inn?'signed_out':unsure?'no_plan':'all_ok';
    const l=$('su-checkline');if(l){l.textContent=line('checks',key);l.parentNode.classList.toggle('is-ok',key==='all_ok');}
    const ok=cli&&inn&&!old; $('su-checks-next').disabled=!ok;
    if(ok)stopPoll();else startPoll();};
  window.mcSuInstall=async function(btn){const upd=!!btn.dataset.update;busy(btn,true,upd?'Opening the update…':'Opening the installer…');
    try{const r=await post('/api/install-claude',{update:upd});if(!upd)$('su-install').hidden=false;
      if(!r.ok)say('su-checkline',r.error||'Couldn’t start the installer.',true);}catch(e){}
    busy(btn,false);startPoll();};
  window.mcSuCopy=async function(btn){try{await navigator.clipboard.writeText($('su-cmd').textContent);
    btn.classList.add('is-copied');setTimeout(()=>btn.classList.remove('is-copied'),1400);}catch(e){}};
  window.mcSuSignIn=async function(btn){busy(btn,true,'Opening sign-in…');
    try{const r=await post('/api/auth-login');
      mark('su-ck-auth','wait',r.ok?'Finish signing in in the window that opened. I’ll notice when you’re done.':(r.error||'Couldn’t start sign-in.'));}catch(e){}
    busy(btn,false);startPoll();};

  // --- folder and name ----------------------------------------------------------------------------
  window.mcSuPick=async function(){try{const r=await(await fetch('/api/pick-folder')).json();
    if(r.ok&&r.path)$('su-root').value=r.path;else if(r.error)say('su-homemsg',r.error,true);}catch(e){}};
  window.mcSuHome=async function(btn){
    const root=($('su-root').value||'').trim(), name=($('su-name').value||'').trim();
    if(!root){say('su-homemsg','Choose a folder first.',true);$('su-root').focus();return;}
    if(!name){say('su-homemsg','Give your realm a name.',true);$('su-name').focus();return;}
    busy(btn,true,'Checking the folder…');say('su-homemsg','');
    try{const r=await post('/api/set-approot',{root,create:true});
      if(!r.ok){say('su-homemsg',line('home','folder_bad',{reason:(r.error||'it can’t be used').replace(/\.$/,'')}),true);return;}
      vals.owner=($('su-owner').value||'').trim();vals.realm=name;mcSuGo('team');}
    catch(e){say('su-homemsg','Couldn’t save the folder: '+e,true);}finally{busy(btn,false);}};

  // --- team ---------------------------------------------------------------------------------------
  function tpl(){const r=document.querySelector('input[name="su-tpl"]:checked');return r?r.value:'scratch';}
  function extraRow(){const d=document.createElement('div');d.className='mc-su-extra';
    d.innerHTML='<input class="mc-field su-x-name" maxlength="40" placeholder="Name"><input class="mc-field su-x-role" maxlength="60" placeholder="Role (optional)">'
      +'<button type="button" class="mc-iconbtn" title="Remove" onclick="this.parentNode.remove();mcSuPicked()">'+(IC.x||'×')+'</button>';
    d.querySelector('.su-x-name').addEventListener('input',()=>mcSuPicked());return d;}
  function paintTeam(){const k=tpl(), p=(SU.presets||{})[k]||{agents:[]};
    vals.collective=p.collective;vals.coordinator=p.coordinator;
    const tl=$('su-tplline');if(tl)tl.textContent=line('team',k);
    $('su-teamlabel').textContent='Your '+(p.collective||'team').toLowerCase();
    const box=$('su-team');box.innerHTML=p.agents.map(a=>
      '<label class="mc-su-member'+(a.coordinator?' is-coord':'')+'"><input type="checkbox" class="su-keep" value="'+esc(a.id)+'" checked'+(a.coordinator?' disabled':'')+'>'
      +'<span class="mc-su-mname">'+esc(a.display)+'</span><span class="mc-su-mrole">'+esc(a.role||'')+'</span>'
      +(a.coordinator?'<span class="mc-su-laurel" title="Leads the team">'+(IC.laurel||'')+'</span>':'')+'</label>').join('');
    box.querySelectorAll('.su-keep').forEach(c=>c.addEventListener('change',mcSuPicked));
    if(!p.agents.length)box.appendChild(extraRow());
    mcSuPicked();}
  window.mcSuPicked=function(){const k=tpl(),p=(SU.presets||{})[k]||{agents:[]};
    const n=document.querySelectorAll('.su-keep:checked').length
      +[...document.querySelectorAll('.su-x-name')].filter(i=>i.value.trim()).length;
    const pl=$('su-pickedline');
    if(!n)pl.textContent=line('team','blank_needs_one');
    else if(p.agents.length)pl.textContent=line('team','picked',{count:n,collective:p.collective,coordinator:'the '+p.coordinator});
    else pl.textContent=n+(n===1?' agent':' agents')+'. The first leads the team.';
    $('su-appoint').disabled=!n;};
  window.mcSuAddAgent=function(){const r=extraRow();$('su-team').appendChild(r);r.querySelector('input').focus();mcSuPicked();};
  document.addEventListener('change',e=>{if(e.target&&e.target.name==='su-tpl')paintTeam();});
  window.mcSuAppoint=async function(btn){
    const keep=[...document.querySelectorAll('.su-keep')].filter(c=>c.checked).map(c=>c.value);
    const extra=[...document.querySelectorAll('.mc-su-extra')].map(d=>({display:d.querySelector('.su-x-name').value.trim(),
      role:d.querySelector('.su-x-role').value.trim()})).filter(x=>x.display);
    busy(btn,true,'Appointing your team…');say('su-teammsg','');
    try{const r=await post('/api/first-realm',{name:vals.realm,owner:vals.owner||'',template:tpl(),keep,extra,wizard:true});
      if(!r.ok){say('su-teammsg',r.error||'Couldn’t create the realm.',true);busy(btn,false);return;}
      document.body.classList.add('is-leaving');
      setTimeout(()=>{location.href='/switch?path='+encodeURIComponent(r.path)+'&to=/setup';},180);}
    catch(e){say('su-teammsg','Couldn’t create the realm: '+e,true);busy(btn,false);}};
  window.mcSuAdopt=async function(btn){btn.disabled=true;say('su-adoptmsg','Choose the realm’s folder…');
    try{const pr=await(await fetch('/api/pick-folder')).json();
      if(!(pr.ok&&pr.path)){say('su-adoptmsg',pr.error||'');return;}
      if(!SU.haveRoot){say('su-adoptmsg','First I need ARMADA’s folder. Carry on to the folder step, then open it from there.',true);return;}
      const r=await post('/api/new-realm',{mode:'adopt',path:pr.path});
      if(!r.ok){say('su-adoptmsg',r.error+(r.suggested_path?' Move it to '+r.suggested_path+' and try again.':''),true);return;}
      location.href='/switch?path='+encodeURIComponent(r.path)+'&to=/';}
    catch(e){say('su-adoptmsg','Couldn’t open it: '+e,true);}finally{btn.disabled=false;}};

  // --- capabilities -------------------------------------------------------------------------------
  let capsDone=false; const added=[];
  function capCount(){if(capsDone)return;const n=document.querySelectorAll('.su-cap:checked').length,b=$('su-caps-add');
    if(b)b.textContent=n?('Add '+n+' capabilit'+(n===1?'y':'ies')):'Continue without any';}
  document.addEventListener('change',e=>{if(e.target&&e.target.classList.contains('su-cap'))capCount();});
  window.mcSuCapsSkip=function(){mcSuGo('first-job');};
  window.mcSuCapsAdd=async function(btn){
    if(capsDone){mcSuGo('first-job');return;}
    const rows=[...document.querySelectorAll('.mc-su-cap')].filter(r=>r.querySelector('.su-cap').checked);
    if(!rows.length){say('su-capmsg',line('capabilities','none'));mcSuGo('first-job');return;}
    document.querySelectorAll('.su-cap').forEach(c=>c.disabled=true);busy(btn,true,'Adding…');let bad=0;
    for(const row of rows){const st=row.querySelector('.mc-su-capst');st.innerHTML='<span class="mc-su-spin"></span>';
      try{const r=await post('/api/setup-capability',{key:row.dataset.key});
        if(r.ok){st.innerHTML=IC.ok||'✓';row.classList.add('is-added');added.push(r.name);}
        else{bad++;st.innerHTML=IC.bad||'✗';st.title=r.error||'';}}
      catch(e){bad++;st.innerHTML=IC.bad||'✗';}}
    capsDone=true;busy(btn,false);btn.textContent='Continue';
    say('su-capmsg',bad?(bad+' didn’t go in. You can add '+(bad===1?'it':'them')+' later from Capabilities.'):
      (added.length+' added and switched on.'),!!bad);};

  // --- the first brief ----------------------------------------------------------------------------
  let briefState='idle', t0=0, tick=null;
  function briefBtn(){return $('su-brief-run');}
  window.mcSuBriefSkip=function(){briefState='skipped';say('su-briefmsg',line('first-job','skipped'));mcSuGo('tour');};
  window.mcSuBrief=async function(btn){
    if(briefState==='done'||briefState==='failed'){mcSuGo('tour');return;}
    if(briefState==='running')return;
    briefState='running';busy(btn,true,'Working…');$('su-brief-skip').hidden=true;
    say('su-briefmsg',line('first-job','running'));
    const rep=$('su-reply'),body=$('su-replybody');rep.hidden=false;body.innerHTML='<span class="mc-su-caret"></span>';
    t0=Date.now();tick=setInterval(()=>{const s=Math.round((Date.now()-t0)/1000);$('su-replytime').textContent=s+'s';},500);
    let text='',ok=false,err='';
    try{let thread=SU.briefThread;
      const nt=await post('/api/new-thread',{agent:SU.coordinator,name:SU.briefTitle});
      if(nt.ok&&nt.thread)thread=nt.thread;
      const resp=await fetch('/api/chat-stream',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({agent:SU.coordinator,thread,message:$('su-brief-prompt').textContent,tid:'su'+Date.now()})});
      const reader=resp.body.getReader(),dec=new TextDecoder();let buf='';
      const show=()=>{body.textContent=text;const c=document.createElement('span');c.className='mc-su-caret';body.appendChild(c);};
      // The server keeps the connection open after its 'done' event (it still marks the thread
      // unread, and may rename it), so the turn is over at 'done', not at the end of the stream.
      let over=false;
      while(!over){const r=await reader.read();if(r.done)break;buf+=dec.decode(r.value,{stream:true});let i;
        while((i=buf.indexOf('\n\n'))>=0){const ch=buf.slice(0,i).replace(/^data:\s?/,'');buf=buf.slice(i+2);if(!ch.trim())continue;
          let ev;try{ev=JSON.parse(ch);}catch(x){continue;}
          if(ev.kind==='text'){text+=ev.text;show();}
          else if((ev.kind==='result'||ev.kind==='done')&&ev.output&&!text.trim()){text=ev.output;show();}
          if(ev.kind==='done'){ok=ev.ok!==false&&!!text.trim();if(!ok)err=ev.error||ev.output||'';over=true;}
          else if(ev.kind==='error'){err=ev.error||'failed';over=true;}}}
      try{reader.cancel();}catch(x){}}
    catch(e){err=String(e);}
    clearInterval(tick);
    if(ok){try{const m=await post('/api/render-md',{text});body.innerHTML=m.ok?m.html:esc(text);}catch(e){body.textContent=text;}
      briefState='done';say('su-briefmsg',line('first-job','ok'));}
    else{briefState='failed';body.textContent=text||'';if(!text)rep.hidden=true;
      say('su-briefmsg',line('first-job','failed',{reason:(err||'no reply came back').slice(0,160).replace(/\.$/,'')}),true);}
    busy(btn,false);btn.textContent='Continue';};

  // --- done ---------------------------------------------------------------------------------------
  function paintSummary(){const ul=$('su-summary');if(!ul)return;
    const caps=added.length||SU.capsOn||0, brief=briefState==='done'||SU.briefDone;
    const rows=[[true,(vals.realm||'Your realm')+' is set up with '+SU.agents+(SU.agents===1?' agent':' agents')+'.'],
      [caps>0,caps?caps+(caps===1?' capability':' capabilities')+' switched on.':'No capabilities yet. Add them from Capabilities whenever you like.'],
      [brief,brief?'Your first brief is waiting in '+vals.coordinator+'’s threads.':'The first brief can wait. Run it from '+vals.coordinator+'’s page.'],
      [true,'The scheduler will be running when you open '+(vals.realm||'the realm')+', and it starts with Windows.']];
    ul.innerHTML=rows.map(([on,t])=>'<li class="'+(on?'is-ok':'is-skip')+'"><span>'+(on?(IC.ok||'✓'):(IC.dot||'·'))+'</span>'+esc(t)+'</li>').join('');}
  window.mcSuFinish=async function(btn){busy(btn,true,'Opening…');
    try{await post('/api/setup-finish');}catch(e){}
    document.body.classList.add('is-leaving');setTimeout(()=>{location.href='/';},180);};

  document.addEventListener('DOMContentLoaded',()=>{
    // Back after a reload with the brief already in its thread: don't run it twice.
    if(SU.half==='realm'&&SU.briefDone&&$('su-brief-run')){briefState='done';$('su-brief-run').textContent='Continue';
      $('su-brief-skip').hidden=true;say('su-briefmsg',line('first-job','ok'));}
    mcSuGo(SU.first||STEPS[0]);
    requestAnimationFrame(()=>document.body.classList.add('is-ready'));});
})();
