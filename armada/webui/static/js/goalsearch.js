function mcGoalSearch(){var i=document.getElementById("goal-search"),q=((i&&i.value)||"").toLowerCase().trim(),n=0;
document.querySelectorAll(".mc-goalcard").forEach(function(c){var ok=!q||c.textContent.toLowerCase().indexOf(q)>=0;
c.style.display=ok?"":"none";if(ok)n++;});
var x=document.getElementById("goal-search-x");if(x)x.style.display=q?"flex":"none";
var e=document.getElementById("goal-search-empty");if(e)e.style.display=(q&&!n)?"block":"none";}
function mcGoalSearchClear(){var i=document.getElementById("goal-search");if(i){i.value="";mcGoalSearch();i.focus();}}
