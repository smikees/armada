// Live-recolour the Configure avatar preview as the colour changes, before Save. The colour is the
// plume under the avatar now, not its ring — the ring is the same grey as every other border — so
// this rebuilds the gradient. Kept in step with _colour_plume() in agentbits.py: same three stops.
function mcAvPreview(col){document.querySelectorAll('#c-avatar-prev .mc-avglow')
  .forEach(g=>{const w=Math.round(g.offsetWidth/2),h=g.offsetHeight;
    g.style.background='radial-gradient(ellipse '+w+'px '+h+'px at 50% 0%,'
      +'color-mix(in srgb,'+col+' 62%,transparent) 0%,'
      +'color-mix(in srgb,'+col+' 26%,transparent) 42%,transparent 75%)';});}
function mcPickColor(el){const fid=el.dataset.fid,c=el.dataset.c;document.getElementById(fid).value=c;
  const pk=document.getElementById(fid+'-pick'); if(pk&&/^#/.test(c))pk.value=c;
  el.parentNode.querySelectorAll('.mc-color-sw').forEach(s=>{const on=s===el;
    s.style.boxShadow='0 0 0 2px '+(on?'var(--color-text)':'transparent')+',0 0 0 4px var(--color-bg)';});
  const cir=document.getElementById(fid+'-circle'); if(cir){cir.style.background='transparent';cir.style.border='2px dashed var(--color-divider)';}
  mcAvPreview(c);}
function mcColorCustom(fid,v){document.getElementById(fid).value=v;
  const pk=document.getElementById(fid+'-pick'); if(pk)document.querySelectorAll('.mc-color-sw[data-fid="'+fid+'"]')
    .forEach(s=>{s.style.boxShadow='0 0 0 2px transparent,0 0 0 4px var(--color-bg)';});
  const cir=document.getElementById(fid+'-circle'); if(cir){cir.style.background=v;cir.style.border='2px solid '+v;}
  mcAvPreview(v);}
