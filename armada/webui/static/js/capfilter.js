// The filters are the app's own dropdown (a <details> carrying its value in
// data-val); only the search box is an <input> with a .value. One reader for both.
function mcCapVal(id){var e=document.getElementById(id);if(!e)return "";
return (e.dataset&&e.dataset.val!==undefined)?e.dataset.val:(e.value||"");}
var MC_CAP_F=["cap-f-type","cap-f-avail","cap-f-source","cap-f-tier"];
function mcCapFilterClear(){mcFDClear(MC_CAP_F,"mcCapFilter");}
function mcCapFilter(){
var s=document.getElementById("cap-search"),q=((s&&s.value)||"").toLowerCase().trim();
var av=mcCapVal("cap-f-avail"),md=mcCapVal("cap-f-source"),tr=mcCapVal("cap-f-tier"),ty=mcCapVal("cap-f-type");
document.querySelectorAll(".mc-cap").forEach(function(c){
// whole-word match on the id list, so "hand" can't match an agent called "handover"
var ids=" "+(c.getAttribute("data-agents")||"")+" ";
var ok=(!q||c.textContent.toLowerCase().indexOf(q)>=0)&&(!av||ids.indexOf(" "+av+" ")>=0)
&&(!md||c.getAttribute("data-source")===md)&&(!tr||c.getAttribute("data-tier")===tr)&&(!ty||c.getAttribute("data-kind")===ty);c.style.display=ok?"":"none";});
// A group with no cards at all (an empty "Skills" bucket showing "None yet.") has
// nothing to count, so the old test hid it and it could never come back — once
// hidden it stayed hidden even after the filter was cleared, until something
// re-rendered the page. An empty bucket is part of the page's structure when
// nothing is filtered, and irrelevant when something is.
var filtering=!!(q||av||md||tr||ty);
[".mc-cap-grp",".mc-cap-agent",".mc-cap-region"].forEach(function(sel){
document.querySelectorAll(sel).forEach(function(g){var any=false,total=0;
g.querySelectorAll(".mc-cap").forEach(function(c){total++;if(c.style.display!=="none")any=true;});
g.style.display=(total===0?(filtering?"none":""):(any?"":"none"));});});
var x=document.getElementById("cap-search-x");if(x)x.style.display=q?"flex":"none";
var cb=document.getElementById("cap-f-clear");
if(cb)cb.style.display=(av||md||tr||ty)?"inline-flex":"none";}
function mcCapSearchClear(){var i=document.getElementById("cap-search");if(i){i.value="";i.focus();}mcCapFilter();}
