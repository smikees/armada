// Both views come from the server: raw markdown for the editor, HTML rendered by the same
// _md() the rest of the app uses for the reader. Nothing is parsed in the browser.
//
// mc-cov-sub already carries its original text server-rendered into the page; snapshot it once
// on load so mcCovOpen(false) can restore it without needing the value baked into this script.
var MC_COV_SUB=(function(){var e=document.getElementById("mc-cov-sub");return e?e.textContent:"";})();
function mcCovDecode(id){var t=document.getElementById(id);var d=document.createElement("textarea");
d.innerHTML=t?t.innerHTML:"";return d.value;}
function mcCovOpen(edit){
document.getElementById("mc-cov-edit").value=mcCovDecode("mc-cov-raw");
document.getElementById("mc-cov-read").innerHTML=mcCovDecode("mc-cov-rendered");
document.getElementById("mc-cov-read").style.display=edit?"none":"";
document.getElementById("mc-cov-edit").style.display=edit?"":"none";
document.getElementById("mc-cov-save").style.display=edit?"":"none";
document.getElementById("mc-cov-sub").textContent=edit?"editing — every minister reads this":MC_COV_SUB;
document.getElementById("mc-cov-msg").textContent="";
document.getElementById("mc-cov-modal").style.display="flex";}
function mcCovClose(){document.getElementById("mc-cov-modal").style.display="none";}
async function mcCovSave(b){var m=document.getElementById("mc-cov-msg");
b.disabled=true;m.style.color="var(--text-muted)";m.textContent="saving…";
try{var r=await(await fetch("/api/save-covenant",{method:"POST",
headers:{"Content-Type":"application/json"},
body:JSON.stringify({text:document.getElementById("mc-cov-edit").value})})).json();
if(!r.ok){m.style.color="var(--status-bad)";m.textContent=r.error||"could not save";}
else{m.textContent="saved — reloading…";location.reload();}}
catch(e){m.style.color="var(--status-bad)";m.textContent="error: "+e;}b.disabled=false;}
