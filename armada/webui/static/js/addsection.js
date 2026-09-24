async function mcAddSection(){const p={name:document.getElementById("s-name").value,src:document.getElementById("s-src").value};
const m=document.getElementById("s-msg");if(!mcReq(["s-name","s-src"])){m.textContent="";return;}m.textContent="adding…";
try{const r=await(await fetch("/api/add-section",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)})).json();
if(r.ok){location.href="/section/"+r.index;}else{m.textContent="error: "+(r.error||"failed");}}catch(e){m.textContent="error: "+e;}}
