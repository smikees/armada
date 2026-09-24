function mcJobsTab(t){var u=t!=="system";
document.getElementById("jobs-pane-user").style.display=u?"":"none";
document.getElementById("jobs-pane-system").style.display=u?"none":"";
var a=document.getElementById("jobs-tab-user"),b=document.getElementById("jobs-tab-system");
if(a)a.setAttribute("aria-selected",u?"true":"false");
if(b)b.setAttribute("aria-selected",u?"false":"true");
try{sessionStorage.setItem("mcJobsTab",t);}catch(e){}
if(window.mcJobcalRefresh)window.mcJobcalRefresh();}
mcJobsTab((function(){try{return sessionStorage.getItem("mcJobsTab")||"user";}
catch(e){return "user";}})());
