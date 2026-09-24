function mcPickAuto(el){const fid=el.dataset.fid;document.getElementById(fid).value=el.dataset.v;
  el.parentNode.querySelectorAll('.mc-auto-opt').forEach(o=>{const on=o===el;
    o.style.borderColor=on?'var(--color-accent)':'var(--color-divider)';
    o.style.background=on?'var(--color-accent-100)':'transparent';});}  /* icon keeps its per-mode colour */
