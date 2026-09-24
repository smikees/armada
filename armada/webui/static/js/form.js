function mcReq(ids){let ok=true;ids.forEach(id=>{const el=document.getElementById(id);if(!el)return;
  const empty=!((el.value||'').trim());
  el.style.borderColor=empty?'var(--status-bad)':'';
  const lab=(el.previousElementSibling&&el.previousElementSibling.tagName==='LABEL')?el.previousElementSibling:el.parentNode;
  let n=lab.querySelector('.mc-reqmsg');
  if(empty){ok=false; if(!n){n=document.createElement('span');n.className='mc-reqmsg';
    n.style.cssText='color:var(--status-bad);font-size:11px;margin-left:8px;font-weight:600';n.textContent='Mandatory field';lab.appendChild(n);}
    el.addEventListener('input',function h(){el.style.borderColor='';const m=lab.querySelector('.mc-reqmsg');if(m)m.remove();el.removeEventListener('input',h);});}
  else if(n){n.remove();}});return ok;}
// Claude-app-style bullets: "- " at the start of a line becomes "• "; Enter continues the list.
document.addEventListener('input',function(e){const t=e.target;if(!t||t.tagName!=='TEXTAREA'||t.dataset.nobullet)return;
  if(e.inputType&&e.inputType.startsWith('delete'))return;
  const p=t.selectionStart,v=t.value,ls=v.lastIndexOf('\n',p-1)+1,line=v.slice(ls,p);
  if(line==='- '||line==='* '){t.value=v.slice(0,ls)+'• '+v.slice(p);t.selectionStart=t.selectionEnd=ls+2;}});
document.addEventListener('keydown',function(e){const t=e.target;if(!t||t.tagName!=='TEXTAREA'||t.dataset.nobullet)return;
  if(e.key!=='Enter'||e.shiftKey)return;const p=t.selectionStart,v=t.value,ls=v.lastIndexOf('\n',p-1)+1,line=v.slice(ls,p);
  if(/^•\s+\S/.test(line)){e.preventDefault();const ins='\n• ';t.value=v.slice(0,p)+ins+v.slice(t.selectionEnd);t.selectionStart=t.selectionEnd=p+ins.length;}
  else if(line==='• '){e.preventDefault();t.value=v.slice(0,ls)+v.slice(p);t.selectionStart=t.selectionEnd=ls;}});
// Modal overlays close only on a CLEAN outside click: the press and release must both
// land on the overlay itself. A drag that begins inside a field (e.g. selecting text)
// and releases over the overlay border must NOT close the modal. We record the mousedown
// target and, in the capture phase, swallow the overlay's click when the press started
// elsewhere — so the inline "if(event.target===this)mcClose()" handler never fires.
(function(){let down=null;
  document.addEventListener('mousedown',function(e){down=e.target;},true);
  document.addEventListener('click',function(e){const t=e.target;
    if(!t||!t.getAttribute)return;
    if((t.getAttribute('onclick')||'').indexOf('event.target===this')!==-1 && down!==t){e.stopPropagation();}
  },true);})();
