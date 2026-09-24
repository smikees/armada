var MC_CAP_TABS=["user","system","catalogue"];
function mcCapTab(t){
if(MC_CAP_TABS.indexOf(t)<0)t="user";
// The User pane is rendered by the server, so anything added from the Catalogue
// is in the realm but not yet on the page — which reads as the add having failed.
// Reload on the way back, not on every add: adding three things in a row
// shouldn't cost three page loads.
if(t==="user"&&window._mcCatDirty){window._mcCatDirty=0;
try{sessionStorage.setItem("mcCapTab","user");}catch(e){}location.reload();return;}
MC_CAP_TABS.forEach(function(n){
var p=document.getElementById("cap-pane-"+n);if(p)p.style.display=(n===t)?"":"none";
var b=document.getElementById("cap-tab-"+n);
if(b)b.setAttribute("aria-selected",(n===t)?"true":"false");});
// header actions (scan / manage) act on user capabilities only
var h=document.getElementById("cap-actions");if(h)h.style.display=(t==="user")?"":"none";
// First time the Catalogue is opened, go and get the results. The server no longer
// renders them, because doing so put a registry request on the critical path of a
// page whose other two tabs don't need it.
if(t==="catalogue"&&typeof mcCatFilter==="function"){
var box=document.getElementById("cat-results");
if(box&&box.dataset.pending){delete box.dataset.pending;mcCatFilter();}}
try{sessionStorage.setItem("mcCapTab",t);}catch(e){}}
mcCapTab((function(){try{return sessionStorage.getItem("mcCapTab")||"user";}
catch(e){return "user";}})());
