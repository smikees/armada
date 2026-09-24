async function mcUpdSection(i){if(!mcReq(["s-name","s-src"]))return;
const p={index:i,name:document.getElementById("s-name").value,src:document.getElementById("s-src").value};const m=document.getElementById("s-msg");m.textContent="saving…";
try{const r=await(await fetch("/api/update-section",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)})).json();
if(r.ok){location.href="/section/"+i;}else{m.textContent="error: "+(r.error||"failed");}}catch(e){m.textContent="error: "+e;}}
function mcDelSection(i){document.getElementById("sec-del-modal").style.display="flex";}
function mcSecDelClose(){document.getElementById("sec-del-modal").style.display="none";}
async function mcSecDelGo(i){const m=document.getElementById("sec-del-msg");m.textContent="deleting…";
try{const r=await(await fetch("/api/delete-section",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({index:i})})).json();
if(r.ok){location.href="/";}else{m.textContent="error: "+(r.error||"failed");}}catch(e){m.textContent="error: "+e;}}
