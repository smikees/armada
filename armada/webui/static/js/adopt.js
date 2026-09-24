// Held-realm banner on the Jobs page (5.8c, THREAT_MODEL T5). An adopted realm's jobs wait for the
// owner's go-ahead; this is the go-ahead. The banner already lists every command job verbatim, so
// the confirm only has to say what happens next.
async function mcAdoptRelease(btn){
  var ok=await mcConfirm('Let this realm’s jobs run?',
    'Its command jobs will run on this computer, as you, on their own schedule, and its agent jobs '+
    'will run with the tools their agents are allowed. You can switch any job off afterwards.',
    {ok:'Let them run'});
  if(!ok)return;
  btn.disabled=true;
  try{
    var r=await(await fetch('/api/adopt-release',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})).json();
    if(r.ok){location.reload();}
    else{btn.disabled=false;mcAlert(r.error||'Could not release the realm.');}
  }catch(e){btn.disabled=false;mcAlert('error: '+e);}
}
