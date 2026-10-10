let mcConnectorTarget="",mcConnectorListGeneration=0,mcConnectorFocus=null;
const mcConnectorCatalog=JSON.parse(document.getElementById('mc-conn-catalog')?.textContent||'[]');
function mcConnClose(){++mcConnectorListGeneration;document.getElementById("mc-conn-modal").style.display="none";if(mcConnectorFocus)mcConnectorFocus.focus();}
function mcConnectorSelect(id){
  const service=mcConnectorCatalog.find(s=>s.id===id);if(!service)return;
  document.getElementById('mc-conn-service').value=id;
  document.querySelectorAll('.mc-conn-service').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.service===id)));
  const panel=document.getElementById('mc-conn-service-detail');panel.replaceChildren();
  const title=document.createElement('strong');title.textContent=service.name;panel.append(title);
  const summary=document.createElement('p');summary.textContent=service.description;panel.append(summary);
  Object.entries(service.engines).forEach(([engine,note])=>{
    const row=document.createElement('p'),label=document.createElement('b');
    label.textContent=engine.charAt(0).toUpperCase()+engine.slice(1)+': ';row.append(label,document.createTextNode(note));panel.append(row);
  });
  document.getElementById('mc-conn-add-submit').disabled=false;
}
function mcConnectorSearch(){
  const query=document.getElementById('mc-conn-search').value.trim().toLowerCase();
  const category=document.getElementById('mc-conn-category').value,engine=document.getElementById('mc-conn-filter-engine').value;
  const visible=[];
  document.querySelectorAll('.mc-conn-service').forEach(b=>{
    b.hidden=!(query.split(/\s+/).every(word=>b.dataset.search.includes(word))&&(!category||category===b.dataset.category)&&
      (!engine||b.dataset.engines.split(' ').includes(engine))&&(!mcConnectorTarget||b.dataset.service!=='notion'));
    if(!b.hidden)visible.push(b.dataset.service);
  });
  document.getElementById('mc-conn-empty').hidden=!!visible.length;
  document.getElementById('mc-conn-service-detail').hidden=!visible.length;
  document.getElementById('mc-conn-add-submit').disabled=!visible.length;
  if(visible.length&&!visible.includes(document.getElementById('mc-conn-service').value))mcConnectorSelect(visible[0]);
}
function mcConnectorAdd(){
  mcConnectorFocus=document.activeElement;
  mcConnectorTarget="";
  document.getElementById("mc-conn-mode").disabled=false;
  document.getElementById("mc-conn-mode").value="native";
  document.getElementById("mc-conn-engine").disabled=false;
  document.getElementById("mc-conn-name-row").hidden=false;
  document.getElementById("mc-conn-name").value="";
  document.getElementById("mc-conn-url").value="";
  document.getElementById('mc-conn-account').value='';
  ['mc-conn-search','mc-conn-category','mc-conn-filter-engine'].forEach(id=>document.getElementById(id).value='');
  mcConnectorSelect('google-drive');mcConnectorSearch();
  document.getElementById("mc-conn-preset").value="";mcConnectorPreset();
  document.getElementById("mc-conn-add-submit").textContent="Add connector";
  document.getElementById("mc-conn-modal").style.display="flex";mcConnectorMode();
  document.getElementById('mc-conn-search').focus();
}
function mcConnectorMode(){
  const existing=document.getElementById("mc-conn-mode").value==="existing";
  const native=document.getElementById("mc-conn-mode").value==="native";
  ++mcConnectorListGeneration;
  document.getElementById("mc-conn-existing").hidden=!existing;
  document.getElementById("mc-conn-remote").hidden=existing||native;
  document.getElementById("mc-conn-native").hidden=!native;
  document.getElementById("mc-conn-name-row").hidden=native||!!mcConnectorTarget;
  document.getElementById("mc-conn-add-status").textContent="";
  document.getElementById('mc-conn-add-submit').disabled=false;
  if(native)mcConnectorSearch();
  if(existing)mcConnectorRegistrations();
}
async function mcConnectorAction(payload){
  const response=await fetch('/api/connector-action',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(payload),signal:AbortSignal.timeout(65000)});
  const data=await response.json();
  if(!response.ok||!data.ok)throw new Error(data.error||'Connector action failed.');
  return data;
}
async function mcConnectorRegistrations(){
  const generation=++mcConnectorListGeneration, provider=document.getElementById("mc-conn-engine").value;
  const select=document.getElementById("mc-conn-registration"),status=document.getElementById("mc-conn-add-status");
  select.replaceChildren(new Option("Loading connections…",""));select.disabled=true;
  try{
    const data=await mcConnectorAction({action:'inventory',provider});
    if(generation!==mcConnectorListGeneration)return;
    select.replaceChildren(new Option("Choose a connection…",""));
    data.registrations.forEach(row=>select.add(new Option(row.label||row.server_name,row.server_name)));
    status.textContent=data.registrations.length?'':'No connections found in this engine. Connect the service there, then refresh this list.';
  }catch(error){if(generation===mcConnectorListGeneration)status.textContent=error.message;}
  finally{if(generation===mcConnectorListGeneration)select.disabled=false;}
}
function mcConnectorLink(button){
  const row=button.closest('.mc-conn-detail');mcConnectorAdd();
  mcConnectorTarget=row.dataset.cap;
  document.getElementById('mc-conn-mode').value='existing';document.getElementById('mc-conn-mode').disabled=true;
  document.getElementById('mc-conn-engine').value=row.dataset.provider;document.getElementById('mc-conn-engine').disabled=true;
  document.getElementById('mc-conn-name-row').hidden=true;
  document.getElementById('mc-conn-add-submit').textContent='Link connection';mcConnectorMode();
}
function mcConnectorNative(button){
  const row=button.closest('.mc-conn-detail');mcConnectorAdd();mcConnectorTarget=row.dataset.cap;
  document.getElementById('mc-conn-mode').disabled=true;
  document.getElementById('mc-conn-add-submit').textContent='Link native app';mcConnectorMode();
}
async function mcConnectorSave(button){
  const existing=document.getElementById('mc-conn-mode').value==='existing';
  button.disabled=true;
  try{
    const data=await mcConnectorAction({action:mcConnectorTarget?'bind':'add',capability:mcConnectorTarget,
      account_label:document.getElementById('mc-conn-account').value,
      service:document.getElementById('mc-conn-mode').value==='native'?document.getElementById('mc-conn-service').value:'',
      name:document.getElementById('mc-conn-name').value,url:existing?'':document.getElementById('mc-conn-url').value.trim(),
      provider:existing?document.getElementById('mc-conn-engine').value:'',
      server_name:existing?document.getElementById('mc-conn-registration').value:''});
    sessionStorage.setItem('armada.connector.focus',data.capability);location.reload();
  }catch(error){document.getElementById('mc-conn-add-status').textContent=error.message;}
  finally{button.disabled=false;}
}
async function mcConnectorUnlink(button){
  const row=button.closest('.mc-conn-detail');button.disabled=true;
  try{await mcConnectorAction({action:'unlink',capability:row.dataset.cap,provider:row.dataset.provider});
    sessionStorage.setItem('armada.connector.focus',row.dataset.cap);location.reload();
  }catch(error){row.querySelector('.mc-conn-instructions').textContent=error.message;button.disabled=false;}
}
document.getElementById('mc-conn-modal')?.addEventListener('keydown',event=>{
  if(event.key==='Escape'){event.preventDefault();mcConnClose();}
  if(event.key!=='Tab')return;
  const controls=Array.from(event.currentTarget.querySelectorAll('button,input,select,a[href]')).filter(el=>!el.disabled&&el.getClientRects().length);
  const first=controls[0],last=controls.at(-1);
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
});
function mcConnectorPreset(){
  const option=document.getElementById('mc-conn-preset').selectedOptions[0];
  if(option.value){document.getElementById('mc-conn-name').value=option.dataset.name;
    document.getElementById('mc-conn-url').value=option.dataset.url;}
  document.getElementById('mc-conn-preset-note').textContent=option.dataset.note||'';
  const guide=document.getElementById('mc-conn-preset-guide');guide.hidden=!option.dataset.guide;
  if(option.dataset.guide)guide.href=option.dataset.guide;else guide.removeAttribute('href');
}
function mcConnectorRefresh(){
  mcConnectorAdd();document.getElementById('mc-conn-mode').value='existing';mcConnectorMode();
}

const MC_CONN_LABEL={ready:"Connected",missing:"Not connected",failed:"Connection failed",
  checking:"Checking…",starting:"Preparing sign-in…",setup_required:"Setup required",sign_in:"Sign-in required",unavailable:"Provider unavailable",
  provider_disabled:"Provider disconnected",realm_disabled:"Disabled in this realm",
  disabled:"Connector disabled",unknown:"Could not verify",different:"Configuration conflict",
  configured:"Registered · unverified",unsupported:"Unavailable through this integration"};
const MC_CONN_PROVIDERS={claude:"Claude",codex:"Codex",gemini:"Gemini"};
function mcCapConnectionState(cap,provider,state,supported,error,detail){
  const full=MC_CONN_LABEL[state]||MC_CONN_LABEL.unknown;
  const reason=(detail&&detail.reason)||error||"";
  document.querySelectorAll('.mc-conn-agent-state').forEach(el=>{
    if(el.dataset.cap===cap&&el.dataset.provider===provider){el.dataset.state=state;
      el.textContent=MC_CONN_PROVIDERS[provider]+': '+full;el.title=reason;}
  });
  document.querySelectorAll(".mc-conn-badge").forEach(function(b){
    if(b.dataset.cap!==cap||b.dataset.provider!==provider)return;
    b.dataset.state=state;b.title=MC_CONN_PROVIDERS[provider]+": "+full+(reason?" — "+reason:"");
    const mark=b.querySelector(".mc-conn-mark");
    if(mark){
      if(state==="checking"){
        if(!mark.dataset.loader)mark.dataset.loader=mark.innerHTML;
        mark.innerHTML=mark.dataset.loader;
      }else{
        mark.innerHTML="";mark.textContent=state==="ready"?"✓":
          ["unknown","configured"].includes(state)?"?":"×";
      }
      mark.setAttribute("aria-label",full);
    }
  });
  document.querySelectorAll(".mc-conn-detail").forEach(function(d){
    if(d.dataset.cap!==cap||d.dataset.provider!==provider)return;
    d.dataset.state=state;
    const label=d.querySelector(".mc-conn-state");if(label)label.textContent=full;
    const note=d.querySelector(".mc-conn-reason");if(note)note.textContent=reason;
    const registration=d.querySelector('.mc-conn-registration-name');
    if(registration)registration.textContent=detail&&detail.server_id?'Registration: '+detail.server_id:'';
    const tools=d.querySelector('.mc-conn-tools');
    if(tools)tools.textContent=detail&&detail.tool_names&&detail.tool_names.length?
      'Verified tool names: '+detail.tool_names.join(', '):'This check does not establish which read or write operations are available. Verify the tools before relying on them.';
    const recheck=d.querySelector(".mc-conn-recheck");
    if(recheck&&!recheck.dataset.busy)recheck.disabled=state==="checking";
    const login=d.querySelector(".mc-conn-login");
    if(login){
      let url="";
      try{const candidate=new URL((detail&&detail.login_url)||"");
        if(candidate.protocol==="https:"&&!candidate.username&&!candidate.password)url=candidate.href;
      }catch(e){}
      login.hidden=!url;if(url)login.href=url;else login.removeAttribute("href");
    }
    const button=d.querySelector(".mc-conn-action");if(!button||button.dataset.busy)return;
    button.style.display="none";
    const action=detail?detail.action:(provider==="codex"&&supported&&
      ["missing","sign_in","configured"].includes(state)?"connect":"");
    const help=d.querySelector(".mc-conn-help");if(help)help.style.display=action==="setup"?"none":"";
    if(action==="connect"){
      button.textContent=state==="missing"?"Connect":"Sign in";
      button.onclick=()=>mcProviderConnect(button);button.style.display="inline-flex";
    }else if(action==="authenticate"){
      button.textContent="Open sign-in controls";
      button.onclick=()=>mcProviderConnect(button,null,null,"authenticate");button.style.display="inline-flex";
    }else if(action==="setup"){
      button.textContent=state==="unsupported"?"View options":"Set up";
      button.onclick=()=>mcConnectorSetup(button);button.style.display="inline-flex";
    }else if(action==="provider_settings"){
      button.textContent="App settings";button.onclick=()=>{location.href="/settings?tab=app";};
      button.style.display="inline-flex";
    }
  });
}
let mcConnectionGeneration=0;
const mcProviderGenerations={claude:0,codex:0,gemini:0};
async function mcCapConnectionsRefresh(force=false,provider=null){
  const targets=provider?[provider]:Object.keys(MC_CONN_PROVIDERS);
  const generation=++mcConnectionGeneration,deadline=Date.now()+95000;
  targets.forEach(p=>{mcProviderGenerations[p]=generation;});
  document.querySelectorAll(".mc-conn-badge").forEach(function(el){
    if(targets.includes(el.dataset.provider))mcCapConnectionState(el.dataset.cap,el.dataset.provider,"checking",false);
  });
  const current=p=>targets.includes(p)&&mcProviderGenerations[p]===generation;
  try{
    do{
      const query=new URLSearchParams();if(force)query.set("force","1");if(provider)query.set("provider",provider);
      const response=await fetch("/api/capability-connections"+(query.size?"?"+query:""),
        {cache:"no-store",signal:AbortSignal.timeout(10000)});
      force=false;
      const data=await response.json();
      if(!targets.some(current))return;
      if(!response.ok||!data.providers||!data.connectors)throw new Error("Connection status unavailable. Recheck to try again.");
      document.querySelectorAll(".mc-provider-status").forEach(function(el){
        if(!current(el.dataset.provider))return;
        const state=data.providers[el.dataset.provider]||"unknown";
        el.dataset.state=state;el.textContent=MC_CONN_LABEL[state]||MC_CONN_LABEL.unknown;
      });
      Object.entries(data.connectors).forEach(function([cap,states]){
        targets.filter(current).forEach(p=>mcCapConnectionState(cap,p,states[p]||"unknown",
          p==="codex"&&states.codex_supported,(states.errors||{})[p],(states.details||{})[p]));
      });
      if(!targets.filter(current).some(p=>data.providers[p]==="checking"||
        Object.values(data.connectors).some(row=>row[p]==="starting")))break;
      if(Date.now()>=deadline)throw new Error("Connector check timed out. Recheck to try again.");
      await new Promise(resolve=>setTimeout(resolve,1200));
    }while(targets.some(current));
    document.querySelectorAll('.mc-conn-badge[data-state="checking"]').forEach(function(el){
      if(current(el.dataset.provider))mcCapConnectionState(el.dataset.cap,el.dataset.provider,"unknown",false,"The connector was not returned by the provider check.");
    });
  }catch(e){
    if(!targets.some(current))return;
    document.querySelectorAll(".mc-conn-badge").forEach(function(el){
      if(current(el.dataset.provider))mcCapConnectionState(el.dataset.cap,el.dataset.provider,"unknown",false,e.message||String(e),{action:"setup",reason:e.message||String(e)});
    });
    document.querySelectorAll(".mc-provider-status").forEach(function(el){
      if(!current(el.dataset.provider))return;
      el.dataset.state="unknown";el.textContent=MC_CONN_LABEL.unknown;
    });
  }
}
// Compatibility with older generated cards; all new controls are provider-specific.
async function mcCodexConnect(button,id){return mcProviderConnect(button,"codex",id);}
async function mcCodexRecheck(button,id){return mcProviderRecheck(button,"codex");}

async function mcConnectorRequest(detail,action){
  const response=await fetch("/api/connector-action",{method:"POST",headers:{"Content-Type":"application/json"},
    signal:AbortSignal.timeout(["connect","authenticate"].includes(action)?60000:10000),
    body:JSON.stringify({capability:detail.dataset.cap,provider:detail.dataset.provider,action})});
  const data=await response.json();
  if(!response.ok||!data.ok){
    const error=new Error(data.error||"The connector action failed. Recheck and try again.");
    error.data=data;throw error;
  }
  return data;
}
async function mcProviderConnect(button,provider,id,action="connect"){
  const detail=button.closest(".mc-conn-detail");if(!detail)return;
  if(provider)detail.dataset.provider=provider;if(id)detail.dataset.cap=id;
  const note=detail.querySelector(".mc-conn-reason");
  button.disabled=true;button.dataset.busy="1";
  if(note)note.textContent="Preparing "+MC_CONN_PROVIDERS[detail.dataset.provider]+" sign-in…";
  try{
    const data=await mcConnectorRequest(detail,action);
    delete button.dataset.busy;
    mcCapConnectionState(detail.dataset.cap,detail.dataset.provider,data.state||"starting",true,"",data);
    if(data.login_url)return; // Keep the provider sign-in link visible until the owner rechecks.
    await mcCapConnectionsRefresh(true,detail.dataset.provider);
  }catch(e){
    delete button.dataset.busy;
    const state=(e.data&&e.data.state)||"failed";
    mcCapConnectionState(detail.dataset.cap,detail.dataset.provider,state,true,e.message||String(e),
      {action:state==="setup_required"?"setup":"connect",reason:e.message||String(e)});
  }
  finally{delete button.dataset.busy;button.disabled=false;}
}
async function mcProviderRecheck(button,provider){
  const detail=button.closest(".mc-conn-detail");
  provider=provider||(detail&&detail.dataset.provider);if(!provider)return;
  button.disabled=true;button.dataset.busy="1";
  try{await mcCapConnectionsRefresh(true,provider);}
  finally{delete button.dataset.busy;button.disabled=false;}
}
async function mcConnectorSetup(button){
  const detail=button.closest(".mc-conn-detail");if(!detail)return;
  const panel=detail.querySelector(".mc-conn-setup");
  if(!panel.hidden&&detail._setupData){panel.hidden=true;return;}
  panel.hidden=false;button.disabled=true;
  const text=panel.querySelector(".mc-conn-instructions");text.textContent="Loading setup instructions…";
  try{
    const data=detail._setupData||await mcConnectorRequest(detail,"setup");detail._setupData=data;
    text.textContent=data.instructions;
    const snippet=panel.querySelector(".mc-conn-snippet");snippet.textContent=data.snippet||"";snippet.hidden=!data.snippet;
    const copy=panel.querySelector(".mc-conn-copy");copy.hidden=!data.snippet;
    copy.textContent=data.copy_label||"Copy configuration";
    panel.querySelector(".mc-conn-copy-status").textContent="";
    [[".mc-conn-web","web_url"],[".mc-conn-guide","guide_url"],[".mc-conn-service-guide","service_guide_url"]].forEach(([selector,key])=>{
      const link=panel.querySelector(selector),url=data[key]||"";
      link.hidden=!url;if(url)link.href=url;
    });
  }catch(e){text.textContent=e.message||String(e);}
  finally{button.disabled=false;}
}
async function mcConnectorCopy(button){
  const panel=button.closest(".mc-conn-setup");
  const text=panel.querySelector(".mc-conn-snippet").textContent;
  const status=panel.querySelector(".mc-conn-copy-status");
  if(!text){status.textContent="There is no configuration text to copy.";return;}
  button.disabled=true;let copied=false;
  try{
    if(navigator.clipboard)try{await navigator.clipboard.writeText(text);copied=true;}catch(e){}
    if(!copied){
      const focus=document.activeElement,selection=window.getSelection();
      const ranges=selection?Array.from({length:selection.rangeCount},(_,i)=>selection.getRangeAt(i).cloneRange()):[];
      const input=document.createElement("textarea");input.value=text;input.readOnly=true;
      input.style.cssText="position:fixed;left:-9999px;top:0";document.body.appendChild(input);
      try{input.select();copied=document.execCommand("copy");}
      finally{input.remove();if(focus)focus.focus({preventScroll:true});
        if(selection){selection.removeAllRanges();ranges.forEach(r=>selection.addRange(r));}}
    }
    status.textContent=copied?"Configuration copied.":"Could not copy. Select the configuration text and copy it manually.";
  }catch(e){status.textContent="Could not copy. Select the configuration text and copy it manually.";}
  finally{button.disabled=false;}
}
if(document.getElementById("cap-pane-user")){
  mcCapConnectionsRefresh();
  const focus=sessionStorage.getItem('armada.connector.focus');
  if(focus){sessionStorage.removeItem('armada.connector.focus');
    const row=Array.from(document.querySelectorAll('.mc-conn-detail')).find(el=>el.dataset.cap===focus);
    if(row){const card=row.closest('details');if(card){card.open=true;card.scrollIntoView({block:'center'});}}
  }
}
