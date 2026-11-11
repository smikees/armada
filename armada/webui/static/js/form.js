function mcReq(ids){let ok=true;ids.forEach(id=>{const el=document.getElementById(id);if(!el)return;
  const empty=!((el.value||'').trim());
  el.style.borderColor=empty?'var(--status-bad)':'';
  const lab=(el.previousElementSibling&&el.previousElementSibling.tagName==='LABEL')?el.previousElementSibling:el.parentNode;
  let n=lab.querySelector('.mc-reqmsg');
  if(empty){ok=false; if(!n){n=document.createElement('span');n.className='mc-reqmsg';
    n.style.cssText='color:var(--status-bad);font-size:11px;margin-left:8px;font-weight:600';n.textContent='Mandatory field';lab.appendChild(n);}
    el.addEventListener('input',function h(){el.style.borderColor='';const m=lab.querySelector('.mc-reqmsg');if(m)m.remove();el.removeEventListener('input',h);});}
  else if(n){n.remove();}});return ok;}
// Shared by ordinary forms and both thread windows. Dispatch input after edits so
// drafts, send state and autosizing observe keyboard-generated changes too.
function mcBulletEdit(t,start,end,text,caret){
  t.setRangeText(text,start,end,'end');
  if(caret!==undefined)t.selectionStart=t.selectionEnd=caret;
  t.dispatchEvent(new Event('input',{bubbles:true}));
}
document.addEventListener('input',function(e){const t=e.target;if(!t||t.tagName!=='TEXTAREA'||t.dataset.nobullet)return;
  if(e.isComposing||(e.inputType&&e.inputType.startsWith('delete')))return;
  const p=t.selectionStart,v=t.value,ls=v.lastIndexOf('\n',p-1)+1,line=v.slice(ls,p);
  const m=line.match(/^([ \t]*)[-*] $/);
  if(m&&p===t.selectionEnd)mcBulletEdit(t,ls,p,m[1]+'• ');});
document.addEventListener('keydown',function(e){const t=e.target;if(!t||t.tagName!=='TEXTAREA'||t.dataset.nobullet)return;
  if(e.defaultPrevented||e.isComposing||e.ctrlKey||e.metaKey||e.altKey)return;
  const p=t.selectionStart,v=t.value,ls=v.lastIndexOf('\n',p-1)+1;
  const end=v.indexOf('\n',ls),line=v.slice(ls,end<0?v.length:end),m=line.match(/^([ \t]*)• (.*)$/);
  if(!m)return;
  if(e.key==='Tab'){
    // Outside a list Tab keeps its normal focus-navigation behavior.
    if(t.selectionEnd>ls+line.length)return;
    e.preventDefault();const old=m[1],indent=e.shiftKey?old.replace(/(?: {1,2}|\t)$/,''):old+'  ';
    const finish=t.selectionEnd+indent.length-old.length;
    mcBulletEdit(t,ls,ls+old.length,indent,Math.max(ls,p+indent.length-old.length));
    t.selectionEnd=Math.max(t.selectionStart,finish);
  }else if(e.key==='Enter'&&(t.id==='mc-msg'?e.shiftKey:!e.shiftKey)){
    e.preventDefault();
    if(!m[2].trim()){
      const indent=m[1].replace(/(?: {1,2}|\t)$/,'');
      mcBulletEdit(t,ls,ls+line.length,m[1]?indent+'• ':'');
    }else mcBulletEdit(t,p,t.selectionEnd,'\n'+m[1]+'• ');
  }
});
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
