// `el` is the menu row that was clicked. The swatch is COPIED from it rather than rebuilt from a
// colour passed in: a status swatch is now a tinted fill, a hollow border or an SVG glyph
// depending on which status it is, and only the markup carries all three faithfully.
function mcFDPick(el,fid,val,label,cb){
  const d=document.getElementById(fid); if(!d)return;
  d.dataset.val=val;
  const lbl=d.querySelector('.mc-fdrop-lbl'); if(lbl)lbl.textContent=label;
  const sw=d.querySelector('.mc-fdrop-sw');
  const src=el&&el.querySelector?el.querySelector('.mc-fdrop-dot'):null;
  if(sw){
    if(src&&val){sw.outerHTML=src.outerHTML.replace('mc-fdrop-dot','mc-fdrop-sw');}
    else{sw.style.display='none';}
  }
  d.removeAttribute('open');
  if(cb&&window[cb])window[cb]();
}
function mcFDClear(ids,cb){ids.forEach(id=>{const d=document.getElementById(id);if(!d)return;
  d.dataset.val='';const lbl=d.querySelector('.mc-fdrop-lbl');if(lbl)lbl.textContent=d.dataset.default||'All';
  const sw=d.querySelector('.mc-fdrop-sw');if(sw)sw.style.display='none';d.removeAttribute('open');});
  if(cb&&window[cb])window[cb]();}
