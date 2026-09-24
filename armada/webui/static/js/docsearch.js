function mcDocSearch(){var i=document.getElementById("doc-search"),q=((i&&i.value)||"").toLowerCase().trim();
var n=0;document.querySelectorAll(".mc-docitem").forEach(function(r){var hit=(!q||r.textContent.toLowerCase().indexOf(q)>=0);
r.style.display=hit?"":"none";if(hit)n++;});
var x=document.getElementById("doc-search-x");if(x)x.style.display=q?"flex":"none";
var e=document.getElementById("mc-docempty");if(e)e.style.display=n?"none":"block";}
function mcDocSearchClear(){var i=document.getElementById("doc-search");if(i){i.value="";mcDocSearch();i.focus();}}
