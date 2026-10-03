// Client mirror of models.combo_index + the gradient sampler, so a model/effort/verbosity picker
// moves its marker and recolours its model icon live (no server round-trip). Called once per
// picker with that picker's own config — C (the shared tables + gradient stops), the element ids
// to watch/paint, and SEL (a CSS-selector prefix so two pickers on one page don't recolour each
// other's icons).
function mcConsumptionInit(C,MID,EID,KID,VID,SEL){
function fam(m){m=(m||'').toLowerCase();var f=['opus','sonnet','haiku','fable'];
for(var i=0;i<f.length;i++){if(m.indexOf(f[i])>=0)return f[i];}return '';}
function codex(m){return /^(codex:|openai:|gpt[- ]|chatgpt-|o[1-9](?:-|$))/i.test(m||'');}
function gemini(m){return /^(gemini[: -]|google.*gemini)/i.test(m||'');}
function cfam(m){m=(m||'').toLowerCase();if(m.indexOf('astra')>=0)return 'astra';
if(m.indexOf('luna')>=0)return 'luna';if(m.indexOf('terra')>=0)return 'terra';
if(m.indexOf('5.6-sol')>=0)return 'sol-5.6';if(m.indexOf('sol')>=0)return 'sol';return 'legacy';}
function price(m){return C.prices[fam(m)]||C.priceDefault;}
function baseCost(m){if(codex(m))return C.codexWeights[cfam(m)]||C.codexDefault;
if(gemini(m))return /pro/i.test(m)?4:1;
var p=price(m);return 0.25*p[0]+0.75*p[1];}
// Same three factors as models.combo_index, in the same order, against the same range.
// If these two ever disagree the marker lies about what the server would compute.
function idx(m,e,vb){var c=codex(m),et=c?C.codexEffort:C.effort;
var mult=et[(e||C.effortDefault).toLowerCase()]||et[C.effortDefault];
var vm=C.verbosity[(vb||C.defaultVerbosity).toLowerCase()]||C.verbosity[C.verbosityDefault];
if(gemini(m)&&/^(xhigh|max|ultra)$/.test(e||''))mult=C.effort.high;
if(gemini(m)&&/pro/i.test(m)&&(e==='medium'||e==='auto'))mult=C.effort.high;
else if(gemini(m)&&e==='auto')mult=C.effort.medium;
var v=baseCost(m)*mult*vm,lo=gemini(m)?C.geminiComboMin:c?C.codexComboMin:C.comboMin,hi=gemini(m)?C.geminiComboMax:c?C.codexComboMax:C.comboMax;
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
function modelLabel(m){
  if(gemini(m)){var match=m.match(/^gemini-([0-9.]+)-(flash|pro)(?:-(?:low|medium|high))?$/i);
    return match?'Gemini '+match[1]+' '+match[2].charAt(0).toUpperCase()+match[2].slice(1):m==='gemini:auto'?'Gemini Auto (latest Flash)':m;}
  if(codex(m)||gemini(m)||!fam(m))return m;
  if(m.indexOf(' ')>=0&&!/^claude-/i.test(m))return m;
  var f=fam(m),match=m.toLowerCase().split(f)[1].match(/^[-_.]?(\d{1,5})(?:[-_.](\d{1,5})(?!\d))?/);
  return 'Claude '+f.charAt(0).toUpperCase()+f.slice(1)+(match?' '+match[1]+(match[2]?'.'+match[2]:''):'');
}
// Measure the real label so only combinations near the right edge flip sides.
// ResizeObserver also handles pickers first rendered inside a hidden pane/modal.
function placeLabel(){var mk=document.getElementById(KID),badge=mk&&mk.querySelector('.mc-cost-badge');
  if(!badge||mk.style.display==='none')return;
  var width=mk.parentElement.clientWidth;if(!width)return;
  badge.style.maxWidth='';
  var center=width*parseFloat(mk.style.left)/100,overhang=mk.offsetWidth/2-4;
  var left=badge.offsetWidth+overhang>width-center;
  mk.dataset.labelSide=left?'left':'right';
  badge.style.maxWidth=Math.max(0,Math.min(260,(left?center:width-center)-overhang))+'px';
}
function upd(){var m=rm(),c=codex(m),known=c||gemini(m)||!!fam(m),i=idx(m,re(),rv()),col=grad(i);
var effortSelect=document.getElementById(EID),allowed=gemini(m)&&(C.geminiEfforts||{})[m];
if(effortSelect&&effortSelect.options)Array.from(effortSelect.options).forEach(function(o){
  var unsupported=!!allowed&&!!o.value&&o.value!=='auto'&&allowed.indexOf(o.value)<0;
  o.disabled=unsupported;o.hidden=unsupported&&!o.selected;
});
if(effortSelect&&allowed&&effortSelect.selectedOptions&&effortSelect.selectedOptions[0]&&effortSelect.selectedOptions[0].disabled){
  effortSelect.value=allowed.indexOf('medium')>=0?'medium':'high';
  i=idx(m,re(),rv());col=grad(i);
}
var mk=document.getElementById(KID);if(mk){mk.style.left=(i/99*100)+'%';
  mk.style.display=known?'':'none';
  var badge=mk.querySelector('.mc-cost-badge');if(badge&&known){badge.textContent=modelLabel(m)+' · '+re();badge.title=badge.textContent;}
  mk.setAttribute('aria-label',m+' · '+re()+' · '+rv()+'; estimated relative cost');
  if(mk.parentElement)mk.parentElement.title=known?'Estimated relative cost within this provider':'Cost estimate unavailable for this model';}
document.querySelectorAll(SEL).forEach(function(el){el.style.color=known?col:'var(--text-muted)';
  el.style.visibility=known?'':'hidden';
  el.querySelectorAll('[data-provider]').forEach(function(mark){mark.style.display=mark.dataset.provider===(gemini(m)?'gemini':c?'codex':'claude')?'':'none';});});
placeLabel();}
var cm=document.getElementById(MID),ce=document.getElementById(EID),
cv=VID&&document.getElementById(VID);
if(cm)cm.addEventListener('change',upd);if(ce)ce.addEventListener('change',upd);
if(cv)cv.addEventListener('change',upd);upd();
var marker=document.getElementById(KID);
if(marker&&typeof ResizeObserver!=='undefined')new ResizeObserver(placeLabel).observe(marker.parentElement);
window.addEventListener('resize',placeLabel);
if(document.fonts&&document.fonts.ready)document.fonts.ready.then(placeLabel);
}
