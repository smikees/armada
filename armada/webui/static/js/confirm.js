// The app's own confirm dialog — ARMADA never uses the browser's confirm()/alert(), which look
// foreign, can't be styled, and can't ask someone to type a name back.
//
// Two call shapes, one dialog. Positional:
//   mcConfirm(title, detail, {ok, danger, mustType})
// or the older options-object form still used by section and job-proposal deletes:
//   mcConfirm({title, body, confirm, danger})
// Accepting both matters: this is a global, and a second definition with a different contract is
// how "[object Object]" ends up in a dialog someone is trying to read.
//
// Resolves to false (cancelled), true (confirmed), or the typed string when mustType was given.
(function(){
  // Drop-in replacement for the browser's alert(): same call shape, app-native dialog, and
  // awaitable if the caller cares when it's dismissed.
  window.mcAlert=function(message,title){
    return window.mcConfirm(title||'Something went wrong',String(message==null?'':message),
                            {ok:'OK',noCancel:true});
  };
  window.mcConfirm=function(title,detail,opts){
    if(title&&typeof title==='object'){          // options-object form
      const o=title;
      detail=o.body!==undefined?o.body:o.detail;
      opts={ok:o.confirm||o.ok,danger:o.danger,mustType:o.mustType};
      title=o.title;
    }
    opts=opts||{};
    const mustType=opts.mustType||'';
    return new Promise(function(resolve){
      const ov=document.createElement('div');
      ov.className='mc-confirm-ov';
      ov.style.cssText='position:fixed;inset:0;z-index:800;background:rgba(0,0,0,.45);'+
        'display:flex;align-items:center;justify-content:center';
      ov.innerHTML='<div class="mc-frame" style="background:var(--color-bg);border-radius:var(--r);'+
        'padding:18px 20px;width:min(460px,92vw);box-shadow:var(--shadow-lg)">'+
        '<div style="font-family:var(--font-heading);font-weight:600;font-size:15px;'+
        'margin-bottom:7px" data-t></div>'+
        '<div style="font-size:12.5px;color:var(--text-muted);line-height:1.55;'+
        'white-space:pre-line" data-d></div>'+
        // A box that says "type to confirm" without saying what to type is a locked door with no
        // keyhole: the button stays dead and nothing on screen explains why. Name it, right above
        // the field, in the exact characters that will be accepted.
        (mustType?'<div style="font-size:12px;color:var(--text-muted);margin-top:14px">'+
          'Type <b data-n style="color:var(--color-text);font-weight:600"></b> to confirm</div>'+
          '<input data-i autocomplete="off" spellcheck="false" style="width:100%;box-sizing:border-box;'+
          'margin-top:5px;padding:7px 9px;border:1px solid var(--color-divider);'+
          'border-radius:var(--r);background:var(--color-bg);color:var(--color-text);'+
          'font:inherit;font-size:13px">':'')+
        '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:16px">'+
        (opts.noCancel?'':'<button class="btn btn-secondary" style="font-size:12.5px;padding:6px 14px" data-no>Cancel</button>')+
        '<button class="btn btn-primary" style="font-size:12.5px;padding:6px 14px;color:#fff'+
        (opts.danger?';background:var(--status-bad);border-color:var(--status-bad)':'')+
        '" data-yes></button></div></div>';
      ov.querySelector('[data-t]').textContent=title||'Are you sure?';
      ov.querySelector('[data-d]').textContent=detail||'';
      const yes=ov.querySelector('[data-yes]'),inp=ov.querySelector('[data-i]');
      yes.textContent=opts.ok||'Confirm';
      if(inp){
        // textContent, not innerHTML: the string to type is an agent or realm NAME, which the
        // owner chose and can contain anything.
        const nm=ov.querySelector('[data-n]');
        if(nm)nm.textContent=String(mustType);
        yes.disabled=true;
        inp.addEventListener('input',function(){
          yes.disabled=inp.value.trim().toLowerCase()!==String(mustType).toLowerCase();});
      }
      function close(v){document.removeEventListener('keydown',key);ov.remove();resolve(v);}
      function key(e){
        if(e.key==='Escape')close(false);
        if(e.key==='Enter'&&!yes.disabled)close(inp?inp.value.trim():true);
      }
      const no=ov.querySelector('[data-no]');
      if(no)no.onclick=function(){close(false);};
      yes.onclick=function(){close(inp?inp.value.trim():true);};
      ov.addEventListener('mousedown',function(e){if(e.target===ov)close(false);});
      document.addEventListener('keydown',key);
      document.body.appendChild(ov);
      (inp||yes).focus();
    });
  };
})();
