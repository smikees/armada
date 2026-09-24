async function mcSnap(i,b){b.disabled=true;b.textContent="Refreshing…";
try{await fetch("/api/section-snapshot",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({index:i})});}catch(e){}location.reload();}
