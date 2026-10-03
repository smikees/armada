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

// Use the filter menu for form controls while keeping the select as the value source.
// Existing save handlers, provider refreshes and change listeners continue to use that select.
function mcFDFromSelect(select,chevron){
  if(select.dataset.dropdown)return;
  const d=document.createElement('details'),summary=document.createElement('summary');
  const label=document.createElement('span'),menu=document.createElement('div');
  d.className='mc-fdrop mc-select-dropdown';d.id=select.id+'-dropdown';
  if(select.id.endsWith('-verbosity'))d.classList.add('is-verbosity');
  label.className='mc-fdrop-lbl';menu.className='mc-fdrop-menu';menu.id=d.id+'-menu';
  summary.setAttribute('role','combobox');summary.setAttribute('aria-haspopup','listbox');
  summary.setAttribute('aria-controls',menu.id);summary.setAttribute('aria-expanded','false');
  const fieldLabel=select.labels?.[0]||select.previousElementSibling;
  const fieldName=select.getAttribute('aria-label')||(fieldLabel?.contains(select)?fieldLabel.firstElementChild?.textContent:fieldLabel?.textContent)?.trim()||'Choose an option';
  summary.setAttribute('aria-label',fieldName);menu.setAttribute('role','listbox');menu.setAttribute('aria-label',fieldName);
  summary.append(label,chevron.cloneNode(true));d.append(summary,menu);select.after(d);
  select.dataset.dropdown=d.id;
  let signature='',rows=[],search='',searchAt=0;
  const enabled=()=>rows.filter(r=>r.getAttribute('aria-disabled')!=='true');
  const close=()=>{d.open=false;summary.setAttribute('aria-expanded','false');};
  function position(){
    if(!d.open)return;
    const rect=summary.getBoundingClientRect(),below=window.innerHeight-rect.bottom-8,above=rect.top-8;
    const up=below<Math.min(menu.scrollHeight,320)&&above>below;
    d.dataset.menuSide=up?'up':'down';
    menu.style.maxHeight=Math.max(80,Math.min(320,up?above:below))+'px';
    menu.style.left='0px';
    const width=menu.getBoundingClientRect().width;
    menu.style.left=Math.max(8-rect.left,Math.min(0,window.innerWidth-8-rect.left-width))+'px';
  }
  function sync(){
    const options=[...select.options],key=JSON.stringify(options.map(o=>[o.value,o.textContent,o.disabled,o.parentElement?.disabled]));
    if(key!==signature){
      signature=key;
      const active=menu.contains(document.activeElement)?document.activeElement.dataset.val:null,scroll=menu.scrollTop;
      menu.replaceChildren();rows=options.map(o=>{
        const row=document.createElement('a');row.textContent=o.textContent;row.dataset.val=o.value;
        row.setAttribute('role','option');row.tabIndex=-1;
        const disabled=o.disabled||!!o.parentElement?.disabled;
        row.setAttribute('aria-disabled',String(disabled));if(disabled)row.classList.add('is-empty');
        row.addEventListener('click',e=>{
          e.preventDefault();if(disabled||select.disabled)return;
          select.value=o.value;sync();close();summary.focus();
          select.dispatchEvent(new Event('input',{bubbles:true}));
          select.dispatchEvent(new Event('change',{bubbles:true}));
        });menu.append(row);return row;
      });
      menu.scrollTop=scroll;
      if(active!==null&&d.open)rows.find(r=>r.dataset.val===active&&r.getAttribute('aria-disabled')!=='true')?.focus();
    }
    label.textContent=select.selectedOptions[0]?.textContent||'Choose an option';summary.title=label.textContent;
    d.dataset.val=select.value;d.classList.toggle('is-off',select.disabled);
    summary.setAttribute('aria-disabled',String(select.disabled));summary.tabIndex=select.disabled?-1:0;
    rows.forEach(row=>row.setAttribute('aria-selected',String(row.dataset.val===select.value)));
    position();
  }
  function openAndFocus(last=false){
    if(select.disabled)return;sync();d.open=true;summary.setAttribute('aria-expanded','true');
    position();
    const choices=enabled();(choices.find(r=>r.dataset.val===select.value)||(last?choices.at(-1):choices[0]))?.focus();
  }
  summary.addEventListener('click',e=>{if(select.disabled)e.preventDefault();else sync();});
  d.addEventListener('toggle',()=>{
    summary.setAttribute('aria-expanded',String(d.open));
    position();
    if(d.open)document.querySelectorAll('.mc-select-dropdown[open]').forEach(other=>{if(other!==d)other.open=false;});
  });
  d.addEventListener('keydown',e=>{
    if(select.disabled)return;
    const choices=enabled(),index=choices.indexOf(document.activeElement);
    if(e.key==='Escape'){e.preventDefault();close();summary.focus();}
    else if(e.key==='Tab')close();
    else if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){
      e.preventDefault();
      if(!d.open||index<0){openAndFocus(e.key==='ArrowUp');return;}
      const next=e.key==='Home'?0:e.key==='End'?choices.length-1:Math.max(0,Math.min(choices.length-1,index+(e.key==='ArrowDown'?1:-1)));
      choices[next]?.focus();
    }else if(e.key==='Enter'||e.key===' '){
      e.preventDefault();if(index>=0)choices[index].click();else if(d.open)close();else openAndFocus();
    }else if(e.key.length===1&&!e.ctrlKey&&!e.metaKey&&!e.altKey){
      e.preventDefault();const now=Date.now();search=(now-searchAt>700?'':search)+e.key.toLowerCase();searchAt=now;
      if(!d.open)openAndFocus();choices.find(r=>r.textContent.trim().toLowerCase().startsWith(search))?.focus();
    }
  });
  select.addEventListener('change',sync);
  // Model/effort choices are replaced after each provider probe; never leave stale options.
  new MutationObserver(sync).observe(select,{childList:true,subtree:true,characterData:true,attributes:true,attributeFilter:['disabled','label','selected']});
  document.addEventListener('click',e=>{if(d.open&&!d.contains(e.target))close();});
  window.addEventListener('resize',position);
  document.addEventListener('scroll',position,true);
  fieldLabel?.addEventListener('click',e=>{if(e.target===fieldLabel){e.preventDefault();summary.focus();}});
  sync();select.hidden=true;
}
