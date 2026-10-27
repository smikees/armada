const MC_CAP_EX={connectors:{name:"e.g. Interactive Brokers",descr:"e.g. reads balances & positions (read-only)",note:"A remote service (broker, Google Drive, a data feed) enabled in Claude. Record it here to scope it to this agent."},extensions:{name:"e.g. Local filesystem (D:/Work)",descr:"e.g. reads & writes files on this machine",note:"A local tool that runs on this machine \u2014 local files, a private script, a developer tool."},skills:{name:"e.g. House writing style",descr:"e.g. drafts the Monday note in our house format",note:"Packaged know-how that teaches an agent a repeatable way of doing something."},plugins:{name:"e.g. Finance toolkit",descr:"e.g. bundles the earnings, comps & DCF skills",note:"A bundle that brings several skills and connectors together, installed as one unit."}};function mcCapPh(kind){var x=MC_CAP_EX[kind]||{};var n=document.getElementById("mc-cap-name"),d=document.getElementById("mc-cap-descr"),o=document.getElementById("mc-cap-note");if(n)n.placeholder=x.name||"Name";if(d)d.placeholder=x.descr||"Short description";if(o)o.textContent=x.note||"";}function mcCapClose(){document.getElementById("mc-cap-modal").style.display="none";}function mcCapAdd(scope,kind){document.getElementById("mc-cap-title").textContent="Add "+kind.replace(/s$/,"");document.getElementById("mc-cap-scope").value=scope;document.getElementById("mc-cap-kind").value=kind;document.getElementById("mc-cap-id").value="";document.getElementById("mc-cap-name").value="";document.getElementById("mc-cap-descr").value="";document.getElementById("mc-cap-status").value="connected";mcCapPh(kind);document.getElementById("mc-cap-msg").textContent="";document.getElementById("mc-cap-modal").style.display="flex";setTimeout(()=>document.getElementById("mc-cap-name").focus(),50);}function mcCapEdit(el){document.getElementById("mc-cap-title").textContent="Edit "+el.dataset.kind.replace(/s$/,"");document.getElementById("mc-cap-scope").value=el.dataset.scope;document.getElementById("mc-cap-kind").value=el.dataset.kind;document.getElementById("mc-cap-id").value=el.dataset.id;document.getElementById("mc-cap-name").value=el.dataset.name;document.getElementById("mc-cap-descr").value=el.dataset.descr;document.getElementById("mc-cap-status").value=el.dataset.status;mcCapPh(el.dataset.kind);document.getElementById("mc-cap-msg").textContent="";document.getElementById("mc-cap-modal").style.display="flex";}async function mcCapSave(){const m=document.getElementById("mc-cap-msg");if(!mcReq(["mc-cap-name"])){m.textContent="";return;}m.textContent="saving…";const p={scope:document.getElementById("mc-cap-scope").value,kind:document.getElementById("mc-cap-kind").value,id:document.getElementById("mc-cap-id").value,name:document.getElementById("mc-cap-name").value,descr:document.getElementById("mc-cap-descr").value,status:document.getElementById("mc-cap-status").value};try{const r=await(await fetch("/api/save-capability",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)})).json();if(r.ok){location.reload();}else{m.textContent="error: "+(r.error||"failed");}}catch(e){m.textContent="error: "+e;}}function mcCapDelete(scope,kind,id){document.getElementById("mc-capdel-scope").value=scope;document.getElementById("mc-capdel-kind").value=kind;document.getElementById("mc-capdel-id").value=id;document.getElementById("mc-capdel-note").textContent="Remove \""+id+"\" from "+(scope==="realm"?"the realm":scope)+"? This cannot be undone.";document.getElementById("mc-capdel-msg").textContent="";document.getElementById("mc-cap-del").style.display="flex";}function mcCapDelClose(){document.getElementById("mc-cap-del").style.display="none";}// Keep the pending card in place until the server confirms removal.
async function mcCapDelGo(){
  const p={scope:document.getElementById('mc-capdel-scope').value,kind:document.getElementById('mc-capdel-kind').value,id:document.getElementById('mc-capdel-id').value};
  const cards=Array.from(document.querySelectorAll('details.mc-cap')).filter(c=>c.dataset.owner===p.scope&&c.dataset.kind===p.kind&&c.dataset.cap===p.id);
  if(cards.some(c=>c.dataset.deleting))return;
  if(cards.some(c=>c.dataset.saving)){
    document.getElementById('mc-capdel-msg').textContent='Access is still being saved. Please try again in a moment.';return;
  }
  if(!cards.length){document.getElementById('mc-capdel-msg').textContent='This capability is no longer on the page.';return;}
  mcCapDelClose();
  let live=document.getElementById('mc-cap-delete-announcer');
  if(!live){live=document.createElement('span');live.id='mc-cap-delete-announcer';live.className='mc-cap-delete-announcer';live.setAttribute('role','status');document.body.appendChild(live);}
  live.textContent='Deleting '+p.id+'…';
  const started=performance.now();
  const states=cards.map(card=>{
    card.querySelectorAll('.mc-cap-delete-status').forEach(el=>el.remove());
    const status=document.createElement('span');status.className='mc-cap-delete-status';status.textContent='Deleting…';
    const summary=card.querySelector(':scope > summary');
    (summary.children[1]||summary).appendChild(status);
    const state={card,status,inert:card.inert,busy:card.getAttribute('aria-busy')};
    card.dataset.deleting='1';card.inert=true;card.setAttribute('aria-busy','true');card.classList.add('mc-cap-deleting');return state;
  });
  let result;
  try{
    result=await(await fetch('/api/delete-capability',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)})).json();
    if(!result.ok)throw Error(result.error||'The capability could not be deleted.');
  }catch(e){
    states.forEach(({card,status,inert,busy})=>{
      delete card.dataset.deleting;card.inert=inert;card.classList.remove('mc-cap-deleting');
      if(busy===null)card.removeAttribute('aria-busy');else card.setAttribute('aria-busy',busy);
      status.classList.add('mc-cap-delete-error');status.setAttribute('role','alert');status.textContent='Could not delete: '+(e.message||String(e))+' Try Remove again.';
    });
    live.textContent='Could not delete '+p.id+'. The capability is still available.';
    if(document.activeElement===document.body)cards[0].querySelector('summary').focus({preventScroll:true});
    return;
  }
  // A brief pending state also makes very fast local deletes understandable.
  await new Promise(resolve=>setTimeout(resolve,Math.max(0,300-(performance.now()-started))));
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  await Promise.all(cards.map(async card=>{
    if(!reduced&&card.isConnected&&typeof card.animate==='function'){
      const style=getComputedStyle(card),height=card.getBoundingClientRect().height;
      try{await card.animate([
        {height:height+'px',opacity:.55,marginTop:style.marginTop,marginBottom:style.marginBottom},
        {height:'0px',opacity:0,marginTop:'0px',marginBottom:'0px',paddingTop:'0px',paddingBottom:'0px',borderTopWidth:'0px',borderBottomWidth:'0px'}
      ],{duration:180,easing:'cubic-bezier(.16,1,.3,1)',fill:'forwards'}).finished;}catch(e){/* Navigation can cancel the animation after the delete has succeeded. */}
    }
    const group=card.closest('.mc-cap-grp');
    const next=card.nextElementSibling||card.previousElementSibling;
    card.remove();
    if(group&&!group.querySelector('.mc-cap')&&!group.querySelector('.mc-cap-empty')){
      const empty=document.createElement('p');empty.className='mc-cap-empty';empty.textContent='None yet.';group.appendChild(empty);
    }
    if(document.activeElement===document.body&&next?.isConnected)next.querySelector('summary')?.focus({preventScroll:true});
  }));
  live.textContent='Deleted '+p.id+'.';
  if(typeof mcCapFilter==='function')mcCapFilter();
}
async function mcCapToggle(el,scope,kind,id){var on=el.checked;var d=el.closest("details");try{const r=await(await fetch("/api/toggle-capability",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scope:scope,kind:kind,id:id,enabled:on})})).json();if(r.ok){if(d)d.classList.toggle("mc-cap-off",!on);var lb=el.closest(".mc-toggle");if(lb)lb.title=on?"Enabled \u2014 click to disable":"Disabled \u2014 click to enable";}else{el.checked=!on;mcAlert("error: "+(r.error||"failed"));}}catch(e){el.checked=!on;mcAlert("error: "+e);}}async function mcCapScan(b){var ic=b.querySelector("svg");if(ic)ic.classList.add("mc-spin");b.disabled=true;try{await fetch("/api/scan-updates",{method:"POST"});location.reload();}catch(e){b.disabled=false;if(ic)ic.classList.remove("mc-spin");mcAlert("error: "+e);}}async function mcCapUpdate(btn,scope,kind,id){var orig=btn.innerHTML;btn.disabled=true;btn.innerHTML='<svg class="mc-spin" width="13" height="13" viewBox="0 0 24 24" style="display:block"><g fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.2-8.5"/></g></svg> Updating\u2026';try{const r=await(await fetch("/api/cap-update",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scope:scope,kind:kind,id:id})})).json();if(r.ok){location.reload();}else{btn.disabled=false;btn.innerHTML=orig;mcAlert("error: "+(r.error||"failed"));}}catch(e){btn.disabled=false;btn.innerHTML=orig;mcAlert("error: "+e);}}async function mcCapPerm(el,scope,kind,id){var v=el.value;try{const r=await(await fetch("/api/cap-permission",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scope:scope,kind:kind,id:id,permission:v})})).json();if(!r.ok)mcAlert("error: "+(r.error||"failed"));}catch(e){mcAlert("error: "+e);}}async function mcSkillReveal(ev,id,scope){if(ev)ev.stopPropagation();try{const r=await(await fetch("/api/reveal-skill",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id:id,scope:scope||""})})).json();if(!r.ok)mcAlert(r.error||"Could not open the file location.");}catch(e){mcAlert("Could not open the file location: "+e);}}async function mcSkillView(id,name){var ov=document.createElement("div");ov.style.cssText="position:fixed;inset:0;z-index:400;background:rgba(0,0,0,.4);display:flex;align-items:center;justify-content:center";ov.innerHTML='<div class="mc-frame" style="background:var(--color-bg);border-radius:var(--r);padding:20px;width:min(680px,92vw);max-height:82vh;overflow:auto;box-shadow:var(--shadow-lg)"><div style="display:flex;align-items:center;gap:10px;margin-bottom:10px"><div class="mc-h-card" style="margin-bottom:0px">'+String(name==null?'':name).replace(/[&<>"']/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];})+'</div><button class="btn btn-secondary" data-x style="margin-left:auto;font-size:12px;padding:4px 10px">Close</button></div><div data-body style="font-size:13px;line-height:1.55;color:var(--color-text)">Loading\u2026</div></div>';document.body.appendChild(ov);function done(){ov.remove();document.removeEventListener("keydown",esc);}function esc(e){if(e.key==="Escape")done();}ov.addEventListener("mousedown",function(e){if(e.target===ov)done();});ov.querySelector("[data-x]").onclick=done;document.addEventListener("keydown",esc);try{const r=await(await fetch("/api/skill-content?id="+encodeURIComponent(id)+(name==="system"?"&scope=system":""))).json();ov.querySelector("[data-body]").innerHTML=r.ok?r.html:('<span style="color:var(--text-muted)">'+(r.error||"Not available")+'</span>');}catch(e){ov.querySelector("[data-body]").innerHTML='<span style="color:var(--status-bad)">error: '+e+'</span>';}}