function mcConnClose(){document.getElementById("mc-conn-modal").style.display="none";}
function mcConnectorAdd(){document.getElementById("mc-conn-modal").style.display="flex";}
async function mcConnectorRefresh(el){
  const m=document.querySelector(".mc-connref-msg");
  if(m)m.textContent="checking Claude…";
  try{
    const r=await(await fetch("/api/refresh-connectors",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scope:"realm"})})).json();
    if(r.ok){
      if(r.added>0)location.reload();
      else if(m)m.textContent=r.found?("up to date · "+r.found+" found"):"no MCP connectors found in Claude";
      mcCapConnectionsRefresh();
    }else if(m)m.textContent="error: "+(r.error||"failed");
  }catch(e){if(m)m.textContent="error: "+e;}
}

const MC_CONN_LABEL={ready:"Connected",missing:"Not connected",failed:"Connection failed",
  checking:"Checking…",sign_in:"Sign-in required",unavailable:"Provider unavailable",
  provider_disabled:"Provider disconnected",realm_disabled:"Disabled in this realm",
  disabled:"Connector disabled",unknown:"Could not verify",different:"Configuration conflict",
  configured:"Registered · unverified",unsupported:"Unavailable through this integration"};
const MC_CONN_PROVIDERS={claude:"Claude",codex:"Codex",gemini:"Gemini"};
function mcCapConnectionState(cap,provider,state,supported,error,detail){
  const full=MC_CONN_LABEL[state]||MC_CONN_LABEL.unknown;
  const reason=(detail&&detail.reason)||error||"";
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
    const recheck=d.querySelector(".mc-conn-recheck");
    if(recheck&&!recheck.dataset.busy)recheck.disabled=state==="checking";
    const button=d.querySelector(".mc-conn-action");if(!button||button.dataset.busy)return;
    button.style.display="none";
    const action=detail?detail.action:(provider==="codex"&&supported&&
      ["missing","sign_in","configured"].includes(state)?"connect":"");
    const help=d.querySelector(".mc-conn-help");if(help)help.style.display=action==="setup"?"none":"";
    if(action==="connect"){
      button.textContent=state==="missing"?"Connect":"Sign in";
      button.onclick=()=>mcProviderConnect(button);button.style.display="inline-flex";
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
      if(!targets.filter(current).some(p=>data.providers[p]==="checking"))break;
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
    signal:AbortSignal.timeout(action==="connect"?60000:10000),
    body:JSON.stringify({capability:detail.dataset.cap,provider:detail.dataset.provider,action})});
  const data=await response.json();
  if(!response.ok||!data.ok)throw new Error(data.error||"The connector action failed. Recheck and try again.");
  return data;
}
async function mcProviderConnect(button,provider,id){
  const detail=button.closest(".mc-conn-detail");if(!detail)return;
  if(provider)detail.dataset.provider=provider;if(id)detail.dataset.cap=id;
  const note=detail.querySelector(".mc-conn-reason");
  button.disabled=true;button.dataset.busy="1";
  if(note)note.textContent="Opening "+MC_CONN_PROVIDERS[detail.dataset.provider]+" sign-in…";
  try{
    const data=await mcConnectorRequest(detail,"connect");
    button.style.display="none";
    if(data.state==="ready"){await mcCapConnectionsRefresh(true,detail.dataset.provider);}
    else if(note)note.textContent="Complete sign-in in your browser, then recheck this provider.";
  }catch(e){if(note)note.textContent=e.message||String(e);}
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
    panel.querySelector(".mc-conn-copy").hidden=!data.snippet;
    [[".mc-conn-web","web_url"],[".mc-conn-guide","guide_url"],[".mc-conn-service-guide","service_guide_url"]].forEach(([selector,key])=>{
      const link=panel.querySelector(selector),url=data[key]||"";
      link.hidden=!url;if(url)link.href=url;
    });
  }catch(e){text.textContent=e.message||String(e);}
  finally{button.disabled=false;}
}
async function mcConnectorCopy(button){
  const panel=button.closest(".mc-conn-setup");
  try{await navigator.clipboard.writeText(panel.querySelector(".mc-conn-snippet").textContent);button.textContent="Copied";}
  catch(e){panel.querySelector(".mc-conn-instructions").textContent="Could not copy. Select the configuration text and copy it manually.";}
}
if(document.getElementById("cap-pane-user"))mcCapConnectionsRefresh();
