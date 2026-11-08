// Shared modal focus ownership. Only the top dialog handles Escape or Tab.
(function(){
  'use strict';
  const stack=[];
  window.mcDialogFocus=function(dialog,close,label,initial){
    const previous=document.activeElement,entry={dialog,close};
    dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');
    if(label)dialog.setAttribute('aria-label',label);
    if(!dialog.hasAttribute('tabindex'))dialog.tabIndex=-1;
    const choices=()=>[...dialog.querySelectorAll('button,a[href],input,select,textarea,summary,[tabindex]')]
      .filter(el=>!el.disabled&&!el.hidden&&el.tabIndex>=0&&el.getClientRects().length);
    function focusFirst(){(choices()[0]||dialog).focus();}
    function key(event){
      if(stack.at(-1)!==entry)return;
      if(event.key==='Escape'){event.preventDefault();event.stopImmediatePropagation();close();}
      else if(event.key==='Tab'){
        const items=choices(),index=items.indexOf(document.activeElement);
        if(!items.length){event.preventDefault();dialog.focus();}
        else if(event.shiftKey&&(index<=0)){event.preventDefault();items.at(-1).focus();}
        else if(!event.shiftKey&&(index<0||index===items.length-1)){event.preventDefault();items[0].focus();}
      }
    }
    function contain(event){if(stack.at(-1)===entry&&!dialog.contains(event.target))focusFirst();}
    stack.push(entry);document.addEventListener('keydown',key,true);document.addEventListener('focusin',contain);
    (initial||choices()[0]||dialog).focus();
    let active=true;
    return function(){
      if(!active)return;active=false;
      const wasTop=stack.at(-1)===entry;
      stack.splice(stack.indexOf(entry),1);
      document.removeEventListener('keydown',key,true);document.removeEventListener('focusin',contain);
      if(wasTop&&previous?.isConnected)previous.focus({preventScroll:true});
    };
  };
})();
