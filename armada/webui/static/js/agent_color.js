// Preview the current portrait's colour disc without saving the agent configuration.
function mcAvPreview(col){document.querySelectorAll('#c-avatar-prev .mc-avdisc,#mc-agent-header .mc-avdisc')
  .forEach(d=>{d.style.background=col;});}
function mcColorChanged(fid,col){const input=document.getElementById(fid);input.value=col;
  if(fid==='c-color')mcAvPreview(col);
  input.dispatchEvent(new Event('input',{bubbles:true}));
  input.dispatchEvent(new Event('change',{bubbles:true}));}
function mcPickColor(el){const fid=el.dataset.fid,c=el.dataset.c;
  el.parentNode.querySelectorAll('.mc-color-sw').forEach(s=>s.classList.toggle('is-selected',s===el));
  const cir=document.getElementById(fid+'-circle'); if(cir)cir.classList.remove('is-selected');
  mcColorChanged(fid,c);}
function mcColorCustom(fid,v){document.querySelectorAll('.mc-color-sw[data-fid="'+fid+'"]')
    .forEach(s=>s.classList.remove('is-selected'));
  if(!/^#[0-9a-f]{6}$/i.test(v))return;
  const picker=document.getElementById(fid+'-pick');if(picker)picker.value=v;
  const cir=document.getElementById(fid+'-circle'); if(cir){cir.dataset.color=v;cir.classList.add('is-selected');cir.style.background=v;cir.style.border='2px solid '+v;}
  const input=document.getElementById(fid);
  try{localStorage.setItem('mc-custom-color:'+input.dataset.colorKey,v);}catch(e){}
  mcColorChanged(fid,v);}
function mcSelectCustom(fid){const cir=document.getElementById(fid+'-circle');
  if(cir&&cir.dataset.color)mcColorCustom(fid,cir.dataset.color);
  else document.getElementById(fid+'-pick').click();}
function mcRestoreCustomColors(){document.querySelectorAll('[data-color-key]').forEach(input=>{
  const cir=document.getElementById(input.id+'-circle');if(!cir)return;
  let color='';try{color=localStorage.getItem('mc-custom-color:'+input.dataset.colorKey)||'';}catch(e){}
  if(cir.classList.contains('is-selected')){color=input.value;
    try{localStorage.setItem('mc-custom-color:'+input.dataset.colorKey,color);}catch(e){}}
  if(/^#[0-9a-f]{6}$/i.test(color)){cir.dataset.color=color;cir.style.background=color;cir.style.border='2px solid '+color;
    const picker=document.getElementById(input.id+'-pick');if(picker)picker.value=color;}
});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mcRestoreCustomColors);else mcRestoreCustomColors();
