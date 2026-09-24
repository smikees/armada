function mcOpenAppoint(){var o=document.getElementById('mc-appoint-ov');if(!o)return;o.style.display='flex';
  // Always opens on Appoint, and repaints the tabs so a modal reopened after a Reinstate attempt
  // doesn't come back on the tab you left it on with the other one's heading above it.
  mcAppointTab('new');
  var n=document.getElementById('n-name');if(n)setTimeout(function(){n.focus();},30);}
function mcCloseAppoint(){var o=document.getElementById('mc-appoint-ov');if(o)o.style.display='none';}
document.addEventListener('keydown',function(e){if(e.key==='Escape')mcCloseAppoint();});

// --- Appoint / Reinstate ------------------------------------------------------------------------
// The Reinstate tab exists only when somebody is retired, so everything below no-ops on a realm
// that has never retired anyone. The title changes with the tab: "Appoint a new minister" and
// "Reinstate a minister" are different enough acts that one heading over both reads as wrong.
function mcAppointTab(t){
  var re=t==='reinstate';
  var a=document.getElementById('mc-appoint-new'),b=document.getElementById('mc-appoint-reinstate');
  if(a)a.style.display=re?'none':'';
  if(b)b.style.display=re?'':'none';
  var ta=document.getElementById('mc-appoint-tab-new'),tb=document.getElementById('mc-appoint-tab-reinstate');
  if(ta)ta.setAttribute('aria-selected',re?'false':'true');
  if(tb)tb.setAttribute('aria-selected',re?'true':'false');
  var h=document.getElementById('mc-appoint-title');
  var role=window.MC_ROLE_LABEL||'agent';
  if(h)h.textContent=re?('Reinstate a '+role):('Appoint a new '+role);
}

// Choosing a name fills the form from what that agent actually was. Retyping a settled agent's
// details is both tedious and a way to bring them back subtly different from how they left.
function mcReinstatePick(){
  var sel=document.getElementById('r-agent'),box=document.getElementById('r-fields');
  if(!sel||!box)return;
  var a=(window.MC_RETIRED||{})[sel.value];
  box.style.display=a?'':'none';
  if(!a)return;
  var set=function(id,v){var e=document.getElementById(id);if(e)e.value=v||'';};
  set('r-name',a.display);set('r-role',a.role);set('r-leader',a.leader);
  set('r-model',a.model);set('r-effort',a.effort);
  // What comes back that the form doesn't show. Said out loud because "and everything else" is
  // exactly the part someone would otherwise assume they have to rebuild by hand.
  var bits=[];
  if(a.jobs)bits.push(a.jobs+(a.jobs===1?' job':' jobs'));
  if(a.threads)bits.push(a.threads+(a.threads===1?' thread':' threads'));
  var c=document.getElementById('r-carry');
  if(c)c.textContent='Returning with '+(bits.length?bits.join(', ')+', plus ':'')+
    'their mandate, soul, tenets, memories, capability grants and run history'+
    (a.appointed?(' — first appointed '+String(a.appointed).slice(0,10)):'')+'.';
}

async function mcReinstate(){
  var sel=document.getElementById('r-agent'),m=document.getElementById('r-msg');
  if(!sel||!sel.value){if(m){m.textContent='Choose who to bring back first.';m.style.color='var(--status-bad)';}return;}
  var g=function(id){var e=document.getElementById(id);return e?e.value:'';};
  m.style.color='var(--text-muted)';m.textContent='reinstating…';
  try{
    var r=await(await fetch('/api/agent-reinstate',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({agent:sel.value,display:g('r-name'),role:g('r-role'),leader:g('r-leader'),
                           model:g('r-model'),effort:g('r-effort')})})).json();
    if(r.ok){m.textContent='reinstated ✓';location.href='/agent/'+r.id;}
    else{m.textContent=r.error||'could not reinstate';m.style.color='var(--status-bad)';}
  }catch(e){m.textContent='could not reinstate: '+e;m.style.color='var(--status-bad)';}
}
