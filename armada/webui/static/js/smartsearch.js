// Add a capability: smart search (armada/smart_search.py). Alexander searches the switched-on
// sources in the background; this polls for his progress and the finished result cards.
var MC_SS_KEY="armada.smartsearch.sources",mcSsJob=0;
function mcSsChecks(){return Array.prototype.slice.call(document.querySelectorAll(".mc-ss-src input"));}
function mcSsSources(){
  var on=mcSsChecks().filter(function(c){return c.checked;}).map(function(c){return c.value;});
  try{localStorage.setItem(MC_SS_KEY,JSON.stringify(on));}catch(e){}
  var n=document.getElementById("ss-src-count");
  if(n)n.textContent=on.length+" of "+mcSsChecks().length+" on";
  return on;
}
(function(){
  var saved=null;try{saved=JSON.parse(localStorage.getItem(MC_SS_KEY)||"null");}catch(e){}
  if(Array.isArray(saved))mcSsChecks().forEach(function(c){c.checked=saved.indexOf(c.value)>=0;});
  mcSsSources();
})();
function mcSsEsc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
function mcSsExample(b){var q=document.getElementById("ss-q");q.value=b.textContent;mcSmartSearch();}
function mcSsProgress(steps,elapsed){
  var rows=(steps||[]).map(function(s){return '<li>'+mcSsEsc(s)+'</li>';}).join("");
  return '<div class="mc-ss-progress"><div class="mc-ss-progress-h"><img src="/static/alexander.png" alt="" class="mc-ss-av">'+
    '<span>Alexander is searching</span><span class="mc-catdots"><i></i><i></i><i></i></span>'+
    '<span class="mc-ss-elapsed">'+(elapsed||0)+'s</span></div>'+(rows?'<ul>'+rows+'</ul>':'')+'</div>';
}
async function mcSmartSearch(ev){
  if(ev)ev.preventDefault();
  var q=(document.getElementById("ss-q").value||"").trim(),out=document.getElementById("ss-out"),go=document.getElementById("ss-go");
  if(!q){document.getElementById("ss-q").focus();return;}
  var sources=mcSsSources();
  if(!sources.length){out.innerHTML='<div class="mc-ss-error">Switch on at least one source under Sources.</div>';return;}
  var job=++mcSsJob;go.disabled=true;out.innerHTML=mcSsProgress([],0);
  try{
    var r=await(await fetch("/api/smart-search",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({q:q,sources:sources})})).json();
    if(!r||!r.ok)throw new Error((r&&r.error)||"The search couldn't start.");
    for(;;){
      await new Promise(function(res){setTimeout(res,900);});
      if(job!==mcSsJob)return;
      var s=await(await fetch("/api/smart-search?id="+encodeURIComponent(r.id),{cache:"no-store"})).json();
      if(job!==mcSsJob)return;
      if(!s||!s.ok)throw new Error((s&&s.error)||"The search was lost.");
      if(s.state==="done"){out.innerHTML=s.html||"";break;}
      out.innerHTML=mcSsProgress(s.steps,s.elapsed);
    }
  }catch(e){if(job===mcSsJob)out.innerHTML='<div class="mc-ss-error">'+mcSsEsc(e.message||e)+'</div>';}
  finally{if(job===mcSsJob)go.disabled=false;}
}
async function mcSsReview(b,url,key){
  var card=b.closest(".mc-ss-card"),box=card.querySelector(".mc-ss-review");
  b.disabled=true;var t0=Date.now(),was=b.textContent;
  var tick=function(){b.textContent="Reviewing… "+Math.floor((Date.now()-t0)/1000)+"s";};tick();var timer=setInterval(tick,1000);
  box.innerHTML='<p class="mc-ss-note"><span class="mc-catdots"><i></i><i></i><i></i></span> An agent is reading it before anything is added. This can take a minute or two.</p>';
  try{
    var r=await(await fetch("/api/catalogue-review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({url:url})})).json();
    if(!r||!r.ok){box.innerHTML='<p class="mc-ss-error">'+mcSsEsc((r&&r.error)||"The review did not complete.")+'</p>';}
    else{window._mcCatReview={url:url,review:r,key:key};box.innerHTML=r.html||"";}
  }catch(e){box.innerHTML='<p class="mc-ss-error">Could not run the review: '+mcSsEsc(e)+'</p>';}
  clearInterval(timer);b.disabled=false;b.textContent=was;
}
async function mcSsAddPlugin(b,plugin){
  b.disabled=true;var was=b.innerHTML;b.textContent="Adding…";
  try{
    var r=await(await fetch("/api/smart-search-add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({plugin:plugin})})).json();
    if(!r||!r.ok)throw new Error((r&&r.error)||"Could not add it.");
    var done=document.createElement("span");done.className="mc-cat-eng is-added";
    done.textContent="Added for Codex — install it in ChatGPT if you haven't, then Connect on the User tab";
    b.replaceWith(done);mcCatSyncUser();
  }catch(e){b.disabled=false;b.innerHTML=was;await mcAlert(e.message||String(e),"Could not add it");}
}
async function mcSsBringIn(b){
  b.disabled=true;var was=b.innerHTML;b.textContent="Bringing in…";
  try{
    var r=await(await fetch("/api/refresh-connectors",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({scope:"realm"})})).json();
    if(!r||!r.ok)throw new Error((r&&r.error)||"Could not read Claude's connectors.");
    var done=document.createElement("span");done.className="mc-cat-eng is-added";
    done.textContent=r.added?(r.added+" brought in from Claude"):"Already in this realm";
    b.replaceWith(done);if(r.added)mcCatSyncUser();
  }catch(e){b.disabled=false;b.innerHTML=was;await mcAlert(e.message||String(e),"Could not bring it in");}
}
function mcSsShow(name){
  mcCapTab("user");var s=document.getElementById("cap-search");
  if(s){s.value=name;if(typeof mcCapFilter==="function")mcCapFilter();s.scrollIntoView({block:"center"});}
}
async function mcSsRefresh(b){
  b.disabled=true;var ic=b.querySelector("svg");if(ic)ic.classList.add("mc-spin");
  try{var r=await(await fetch("/api/catalogue-refresh",{method:"POST"})).json();
    if(!r||!r.ok)await mcAlert((r&&r.error)||"Could not refresh the lists.");}
  catch(e){await mcAlert("Could not refresh the lists: "+e);}
  b.disabled=false;if(ic)ic.classList.remove("mc-spin");
}
var mcSsWarmed=0;
// Claude Code's list health-checks every server (seconds); start it while the owner is typing.
function mcSsWarm(){if(mcSsWarmed)return;mcSsWarmed=1;fetch("/api/smart-search-warm",{method:"POST"}).catch(function(){});}
if(document.getElementById("cap-pane-catalogue")&&document.getElementById("cap-pane-catalogue").style.display!=="none")mcSsWarm();
