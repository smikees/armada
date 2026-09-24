(function(){const sw=document.querySelector('.mc-realmsw');if(!sw||sw._w)return;sw._w=1;
 sw.addEventListener('toggle',async()=>{if(!sw.open)return;const box=document.getElementById('mc-realmlist');
  try{const r=await (await fetch('/api/realms')).json();
   box.innerHTML=(r.realms||[]).map(x=>{const cur=x.name===r.current_name;
     return `<a href="/switch?path=${encodeURIComponent(x.path)}" style="display:flex;align-items:center;gap:7px;${cur?'font-weight:700':''}">`
       +`<span style="width:10px;display:inline-flex;justify-content:center;color:var(--color-accent-2)">${cur?'▶':''}</span><span>${String(x.name==null?'':x.name).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}</span></a>`;}).join('')
     +'<div style="border-top:1px solid var(--color-divider);margin:4px 0"></div>'
     +'<a href="#" onclick="mcNewRealmOpen(event)" style="display:flex;align-items:center;gap:7px;color:var(--color-accent)"><span style="width:10px;text-align:center">+</span><span>New realm</span></a>';
  }catch(e){box.innerHTML='<div style="padding:6px 8px;font-size:12px">error</div>';}});})();
// Close any open <details> menu (realm switcher, jobs filters) on a click outside it. Native
// <details> doesn't do this on its own, so it otherwise only closed when the click happened to
// hit another actionable element.
document.addEventListener('click',function(e){
  document.querySelectorAll('details.mc-realmsw[open],details.mc-fdrop[open]').forEach(function(d){
    if(!d.contains(e.target))d.removeAttribute('open');});});
