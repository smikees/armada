// Client mirror of models.combo_index + the gradient sampler, so a model/effort/verbosity picker
// moves its marker and recolours its model icon live (no server round-trip). Called once per
// picker with that picker's own config — C (the shared tables + gradient stops), the element ids
// to watch/paint, and SEL (a CSS-selector prefix so two pickers on one page don't recolour each
// other's icons).
function mcConsumptionInit(C,MID,EID,KID,VID,SEL){
function fam(m){m=(m||'').toLowerCase();var f=['opus','sonnet','haiku','fable'];
for(var i=0;i<f.length;i++){if(m.indexOf(f[i])>=0)return f[i];}return '';}
function price(m){return C.prices[fam(m)]||C.priceDefault;}
function baseCost(m){var p=price(m);return 0.25*p[0]+0.75*p[1];}
// Same three factors as models.combo_index, in the same order, against the same range.
// If these two ever disagree the marker lies about what the server would compute.
function idx(m,e,vb){var mult=C.effort[(e||C.effortDefault).toLowerCase()]||C.effort[C.effortDefault];
var vm=C.verbosity[(vb||C.defaultVerbosity).toLowerCase()]||C.verbosity[C.verbosityDefault];
var v=baseCost(m)*mult*vm,lo=C.comboMin,hi=C.comboMax;
if(v<=lo||hi<=lo)return 0;if(v>=hi)return 99;
return Math.round(99*(Math.log(v)-Math.log(lo))/(Math.log(hi)-Math.log(lo)));}
function grad(i){var t=Math.max(0,Math.min(99,i))/99,s=C.stops,k;
for(k=1;k<s.length;k++){var p0=s[k-1][0],c0=s[k-1][1],p1=s[k][0],c1=s[k][1];
if(t<=p1){var f=(p1==p0)?0:(t-p0)/(p1-p0);
var r=Math.round(c0[0]+(c1[0]-c0[0])*f),g=Math.round(c0[1]+(c1[1]-c0[1])*f),b=Math.round(c0[2]+(c1[2]-c0[2])*f);
return '#'+[r,g,b].map(function(x){return ('0'+x.toString(16)).slice(-2);}).join('');}}return '#000';}
function rm(){var el=document.getElementById(MID);var v=(el&&el.value)||'';return v||C.defaultModel;}
function re(){var el=document.getElementById(EID);var v=(el&&el.value)||'';return v||C.defaultEffort;}
// Blank in any of these selects means "inherit the realm default", so the marker has to
// resolve it the same way a run would — not treat it as a missing value.
function rv(){var el=VID&&document.getElementById(VID);var v=(el&&el.value)||'';return v||C.defaultVerbosity;}
function upd(){var i=idx(rm(),re(),rv()),col=grad(i);
var mk=document.getElementById(KID);if(mk)mk.style.left=(i/99*100)+'%';
document.querySelectorAll(SEL).forEach(function(el){el.style.color=col;});}
var cm=document.getElementById(MID),ce=document.getElementById(EID),
cv=VID&&document.getElementById(VID);
if(cm)cm.addEventListener('change',upd);if(ce)ce.addEventListener('change',upd);
if(cv)cv.addEventListener('change',upd);upd();
}
