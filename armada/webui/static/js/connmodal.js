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
  checking:"Checking…",
  sign_in:"Sign-in required",unavailable:"Provider unavailable",disabled:"Disconnected in App settings",
  unknown:"Could not verify",different:"Codex configuration conflict",
  configured:"Configured; sign-in unverified",unsupported:"Not configured in Codex"};
function mcCapConnectionState(cap,provider,state,supported,error){
  const providerName=({codex:'Codex',claude:'Claude',gemini:'Gemini'}[provider]||provider);
  const full=state==='unsupported'?'Not configured in '+providerName:MC_CONN_LABEL[state]||"Could not verify";
  document.querySelectorAll(".mc-conn-badge").forEach(function(b){
    if(b.dataset.cap!==cap||b.dataset.provider!==provider)return;
    b.dataset.state=state;
    b.title=({codex:'Codex',claude:'Claude',gemini:'Gemini'}[provider]||provider)+": "+full+(error?" — "+error:"");
    const mark=b.querySelector(".mc-conn-mark");
    if(mark){
      if(state==="checking"){
        if(!mark.dataset.loader)mark.dataset.loader=mark.innerHTML;
        mark.innerHTML=mark.dataset.loader;
      }else {mark.innerHTML='';mark.textContent=state==="ready"?"✓":"×";}
      mark.setAttribute('aria-label',full);}
  });
  document.querySelectorAll(".mc-conn-detail").forEach(function(d){
    if(d.dataset.cap!==cap||d.dataset.provider!==provider)return;
    const label=d.querySelector(".mc-conn-state");if(label){label.textContent=full+(error?" — "+error:"");label.title=error||"";}
    const button=d.querySelector(".mc-conn-action");if(!button)return;
    button.style.display="none";
    if(state==="ready"||state==="unknown"||state==="failed"){
      button.textContent="Recheck";button.onclick=()=>mcCodexRecheck(button,cap);button.style.display="inline-flex";
    }else if(supported&&(state==="missing"||state==="sign_in"||state==="configured")){
      button.textContent=state==="missing"?"Connect to Codex":"Sign in to Codex";
      button.onclick=()=>mcCodexConnect(button,cap);button.style.display="inline-flex";
    }
  });
}
let mcConnectionGeneration=0;
async function mcCapConnectionsRefresh(force=false){
  const generation=++mcConnectionGeneration,deadline=Date.now()+95000;
  document.querySelectorAll('.mc-conn-badge').forEach(function(el){
    mcCapConnectionState(el.dataset.cap,el.dataset.provider,'checking',false);
  });
  try{
    do{
    const response=await fetch("/api/capability-connections"+(force?'?force=1':''),
      {cache:"no-store",signal:AbortSignal.timeout(10000)});
    force=false;
    const data=await response.json();
    if(generation!==mcConnectionGeneration)return;
    if(!response.ok||!data.providers||!data.connectors)throw new Error("status unavailable");
    document.querySelectorAll(".mc-provider-status").forEach(function(el){
      const state=data.providers[el.dataset.provider]||"unknown";
      el.dataset.state=state;el.textContent=MC_CONN_LABEL[state]||"Could not verify";
    });
    Object.entries(data.connectors).forEach(function([cap,states]){
      mcCapConnectionState(cap,"claude",states.claude,false,(states.errors||{}).claude);
      mcCapConnectionState(cap,"codex",states.codex,states.codex_supported,(states.errors||{}).codex);
      mcCapConnectionState(cap,"gemini",states.gemini,false,(states.errors||{}).gemini);
    });
    if(!data.pending)break;
    if(Date.now()>=deadline)throw new Error('Connector check timed out. Recheck to try again.');
    await new Promise(resolve=>setTimeout(resolve,1200));
    }while(generation===mcConnectionGeneration);
    if(generation!==mcConnectionGeneration)return;
    document.querySelectorAll('.mc-conn-badge[data-state="checking"]').forEach(function(el){
      mcCapConnectionState(el.dataset.cap,el.dataset.provider,'unknown',false);
    });
  }catch(e){
    if(generation!==mcConnectionGeneration)return;
    document.querySelectorAll(".mc-provider-status").forEach(function(el){
      el.dataset.state="unknown";el.textContent="Could not verify";
    });
    document.querySelectorAll(".mc-conn-badge").forEach(function(el){
      el.dataset.state="unknown";el.title="Could not verify provider connection — "+(e.message||e);
      const mark=el.querySelector(".mc-conn-mark");if(mark){mark.textContent="?";mark.setAttribute('aria-label','Could not verify');}
    });
    document.querySelectorAll(".mc-conn-state").forEach(function(el){el.textContent="Could not verify";});
    document.querySelectorAll(".mc-conn-action").forEach(function(el){el.style.display="none";});
  }
}
async function mcCodexConnect(button,id){
  const detail=button.closest(".mc-conn-detail");
  const label=detail&&detail.querySelector(".mc-conn-state");
  button.disabled=true;if(label)label.textContent="Opening Codex sign-in…";
  try{
    const r=await(await fetch("/api/codex-connector",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({capability:id})})).json();
    if(!r.ok){if(label)label.textContent=r.error||"Connection failed";return;}
    if(r.state==="ready"){await mcCapConnectionsRefresh(true);return;}
    if(label)label.textContent="Complete sign-in in your browser, then recheck";
    button.textContent="Recheck";button.onclick=()=>mcCodexRecheck(button,id);
  }catch(e){if(label)label.textContent="Could not start Codex sign-in";}
  finally{button.disabled=false;}
}
async function mcCodexRecheck(button,id){
  button.disabled=true;
  try{await mcCapConnectionsRefresh(true);}
  finally{button.disabled=false;}
}
if(document.getElementById("cap-pane-user"))mcCapConnectionsRefresh();
