// Drag an agent from the roster onto a capability to grant it. Dropping is a write, so the row
// is re-rendered from the server's answer rather than optimistically: a chip that appears and
// then turns out not to have been saved is worse than a half-second wait.

// Granting reloads the page, which returns every <details> to closed — so the card you were
// working in shut itself the moment you dropped an agent into it. Remember which were open
// across that one reload and reopen them. Deliberately a one-shot key, cleared on restore:
// persisting open state across ordinary navigation would be a different (and surprising)
// feature.
function mcCapKey(d){return (d.getAttribute("data-kind")||"")+"|"+(d.getAttribute("data-cap")||"");}
function mcCapSaveOpen(){try{var o=[];
document.querySelectorAll("details.mc-cap[open]").forEach(function(d){o.push(mcCapKey(d));});
sessionStorage.setItem("mcCapOpen",JSON.stringify(o));}catch(e){}}
function mcCapRestoreOpen(){try{var raw=sessionStorage.getItem("mcCapOpen");
if(!raw)return;sessionStorage.removeItem("mcCapOpen");var o=JSON.parse(raw)||[];
if(!o.length)return;document.querySelectorAll("details.mc-cap").forEach(function(d){
if(o.indexOf(mcCapKey(d))>=0)d.open=true;});}catch(e){}}
mcCapRestoreOpen();
function mcCapDragStart(e,id){e.dataTransfer.setData("text/plain",id);
e.dataTransfer.effectAllowed="copy";}
function mcCapDragOver(e){e.preventDefault();e.dataTransfer.dropEffect="copy";
var d=e.currentTarget;d.style.outline="2px solid var(--color-accent)";d.style.outlineOffset="-2px";}
function mcCapDragLeave(e){var d=e.currentTarget;d.style.outline="";d.style.outlineOffset="";}
async function mcCapDrop(e,cap){e.preventDefault();var d=e.currentTarget;
d.style.outline="";d.style.outlineOffset="";
// Snapshot synchronously, at the moment of the drop: anything that ran between here and the
// reload could have changed which cards are open, and what we want to restore is what the
// owner had in front of them when they let go.
mcCapSaveOpen();
var agent=e.dataTransfer.getData("text/plain");if(!agent)return;
try{var r=await(await fetch("/api/cap-grant",{method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({agent:agent,capability:cap})})).json();
if(!r.ok){await window.mcConfirm("Could not give access",r.error||"Unknown error",{ok:"OK"});return;}
if(r.coordinator){await window.mcConfirm("Already available",
(r.detail||"The coordinator can already use everything."),{ok:"OK"});return;}
location.reload();}
catch(err){await window.mcConfirm("Could not give access",String(err),{ok:"OK"});}}
async function mcCapRemoveAgent(e,cap,agent){e.stopPropagation();e.preventDefault();
mcCapSaveOpen();
try{var r=await(await fetch("/api/cap-revoke",{method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({agent:agent,capability:cap})})).json();
if(!r.ok){await window.mcConfirm("Could not remove access",r.error||"Unknown error",{ok:"OK"});return;}
location.reload();}
catch(err){await window.mcConfirm("Could not remove access",String(err),{ok:"OK"});}}
