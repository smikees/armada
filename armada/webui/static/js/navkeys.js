// Backspace goes back a section.
//
// Browsers removed this exact binding years ago, for a good reason: people pressed Backspace
// meaning "delete a character", focus wasn't quite where they thought, and the page navigated away
// taking their half-written text with it. So the guards below are the feature — the navigation is
// the easy part. If there is ANY doubt about whether the keystroke was meant for a field, we do
// nothing and let Backspace be Backspace.
(function(){
  function isEditable(el){
    if(!el||el.nodeType!==1)return false;
    if(el.isContentEditable)return true;                 // the chat composer uses this
    var tag=(el.tagName||'').toUpperCase();
    if(tag==='INPUT'||tag==='TEXTAREA'||tag==='SELECT'||tag==='OPTION')return true;
    if(el.getAttribute&&el.getAttribute('role')==='textbox')return true;
    return false;
  }

  // A dialog is open: Backspace belongs to whatever is on top, and Escape is how you leave it.
  function modalOpen(){
    if(document.querySelector('.mc-confirm-ov'))return true;
    var ids=['mc-caphelp','mc-cap-modal','mc-cap-del','mc-changelog','mc-newrealm'];
    for(var i=0;i<ids.length;i++){
      var m=document.getElementById(ids[i]);
      if(m&&m.style&&m.style.display&&m.style.display!=='none')return true;
    }
    return !!document.querySelector('dialog[open]');
  }

  document.addEventListener('keydown',function(e){
    if(e.key!=='Backspace')return;
    if(e.ctrlKey||e.altKey||e.metaKey||e.shiftKey)return;  // leave shortcuts alone
    if(e.defaultPrevented)return;                          // someone already handled it
    if(modalOpen())return;
    // Check both the event target and where focus actually is — they differ when a click landed
    // on a container while a field still holds the caret.
    if(isEditable(e.target)||isEditable(document.activeElement))return;
    // Inside any editable subtree (a field nested in the element that got the event)
    if(e.target&&e.target.closest&&e.target.closest('input,textarea,select,[contenteditable=""],[contenteditable="true"]'))return;
    // A text selection means the user is working with text, not navigating.
    try{ var s=window.getSelection(); if(s&&!s.isCollapsed)return; }catch(err){}
    if(history.length<=1)return;                           // nothing to go back to
    e.preventDefault();
    history.back();
  });
})();
