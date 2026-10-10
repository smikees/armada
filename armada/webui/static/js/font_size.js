// Text sizing shared by every first-party page. Pixel typography becomes relative to one
// reference; widths, icons, images and panel geometry keep their existing dimensions.
(function(){
  const DEFAULT=13,MIN=10,MAX=26,root=document.documentElement;
  const pixel=/^(\d+(?:\.\d+)?)px$/;
  let current=DEFAULT,persisted=DEFAULT,defaultSize=DEFAULT,pending=null,saving=false,waiters=[],noticeTimer,syncingSelect=false;
  const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('armada-font-size'):null;
  function valid(value){return Number.isInteger(value)&&value>=MIN&&value<=MAX;}
  function scaleDeclaration(style){
    if(!style)return;
    const match=pixel.exec(style.getPropertyValue('font-size').trim());
    if(match)style.setProperty('font-size',`calc(${match[1]}px * var(--mc-font-scale, 1))`,style.getPropertyPriority('font-size'));
  }
  function sheet(stylesheet){
    try{
      function rules(list){for(const rule of list){scaleDeclaration(rule.style);if(rule.cssRules)rules(rule.cssRules);}}
      rules(stylesheet.cssRules);
    }catch(e){ /* Cross-origin styles belong to their publisher, not Armada's controls. */ }
  }
  function element(node){
    scaleDeclaration(node.style);
    // SVG chart labels use presentation attributes rather than CSS declarations.
    if(node.hasAttribute?.('font-size')){
      const value=node.getAttribute('font-size');
      if(/^\d+(?:\.\d+)?(?:px)?$/.test(value))node.setAttribute('font-size',`calc(${parseFloat(value)}px * var(--mc-font-scale, 1))`);
    }
    if(node.sheet)sheet(node.sheet);
  }
  function scan(node){
    if(node.nodeType!==1)return;
    element(node);
    node.querySelectorAll('[style],[font-size],style,link[rel="stylesheet"]').forEach(element);
  }
  // Work before the body is parsed, then process only newly added/changed typography.
  [...document.styleSheets].forEach(sheet);
  root.style.fontSize='calc(16px * var(--mc-font-scale, 1))';
  new MutationObserver(records=>{
    for(const record of records){
      if(record.type==='attributes')element(record.target);
      else if(record.target.nodeName==='STYLE')sheet(record.target.sheet);
      else record.addedNodes.forEach(scan);
    }
  }).observe(root,{subtree:true,childList:true,attributes:true,attributeFilter:['style','font-size']});
  document.addEventListener('load',event=>{if(event.target.sheet)sheet(event.target.sheet);},true);
  function apply(value,saved=false){
    if(!valid(value))throw Error(`Choose a whole size from ${MIN} to ${MAX} px.`);
    current=value;
    for(const node of [root,document.body])if(node){
      node.style.setProperty('--mc-font-reference',String(value));
      node.style.setProperty('--mc-font-scale',String(value/DEFAULT));
    }
    window.dispatchEvent(new CustomEvent('armada-font-size',{detail:{value,defaultSize,persisted:saved}}));
  }
  function setDefault(value){
    if(!valid(value))return;
    const previous=defaultSize;defaultSize=value;
    const select=document.getElementById('mc-font-size');
    // Update another window's clean control, preserving an unsaved default-size selection.
    if(select&&Number(select.value)===previous&&previous!==value){
      select.value=String(value);syncingSelect=true;
      try{select.dispatchEvent(new Event('change',{bubbles:true}));}finally{syncingSelect=false;}
    }
  }
  function notice(message,error=false){
    let node=document.getElementById('mc-font-size-notice');
    if(!node){node=document.createElement('div');node.id='mc-font-size-notice';node.className='mc-font-size-notice';
      node.setAttribute('role','status');node.setAttribute('aria-live','polite');document.body.appendChild(node);}
    node.hidden=false;node.textContent=message;node.style.color=error?'var(--status-bad)':'';
    clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>{node.hidden=true;},error?6000:1500);
  }
  async function drain(){
    if(saving)return;
    saving=true;
    try{
      while(pending!==null){
        const target=pending;pending=null;
        const body={font_size:target.value};
        if(valid(target.defaultSize))body.font_size_default=target.defaultSize;
        const response=await fetch('/api/save-appearance',{method:'POST',keepalive:true,
          headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const result=await response.json();
        if(!response.ok||!result.ok||!valid(result.font_size))throw Error(result.error||'Font size was not saved.');
        persisted=result.font_size;
        setDefault(result.font_size_default);
        if(current===target.value&&pending===null)apply(persisted,true);
        else window.dispatchEvent(new CustomEvent('armada-font-size',{detail:{value:persisted,defaultSize,persisted:true}}));
        if(pending===null)channel?.postMessage({value:persisted,defaultSize});
      }
      const complete=waiters;waiters=[];complete.forEach(item=>item.resolve(persisted));
    }catch(error){
      pending=null;apply(persisted,true);notice('Could not save font size: '+error.message,true);
      const failed=waiters;waiters=[];failed.forEach(item=>item.reject(error));
    }finally{saving=false;}
  }
  function save(value,asDefault=false){
    if(!valid(value))return Promise.reject(Error(`Choose a whole size from ${MIN} to ${MAX} px.`));
    apply(value);pending={value,defaultSize:asDefault?value:pending?.defaultSize};
    const result=new Promise((resolve,reject)=>waiters.push({resolve,reject}));
    void drain();return result;
  }
  document.addEventListener('keydown',event=>{
    if(!event.ctrlKey||event.altKey||event.metaKey||event.isComposing||event.defaultPrevented)return;
    let value;
    if(['+','='].includes(event.key)||['Equal','NumpadAdd'].includes(event.code))value=Math.min(MAX,current+1);
    else if(event.key==='-'||['Minus','NumpadSubtract'].includes(event.code))value=Math.max(MIN,current-1);
    else if(event.key==='0'||['Digit0','Numpad0'].includes(event.code))value=defaultSize;
    else return;
    event.preventDefault();
    notice(`Font size: ${value} px${value===defaultSize?' (default)':''}`);
    // Shortcut persistence is independent of unsaved font-family/colour preferences.
    if(value!==current||value!==persisted)save(value).catch(()=>{});
  },true);
  if(channel)channel.onmessage=event=>{
    setDefault(event.data?.defaultSize);
    if(!saving&&pending===null&&current===persisted&&valid(event.data?.value)){
      persisted=event.data.value;apply(persisted,true);
    }
  };
  async function refresh(){
    if(saving||pending!==null||current!==persisted)return;
    const previous=persisted;
    try{
      const response=await fetch('/api/font-size');if(!response.ok)return;
      const data=await response.json();
      if(!saving&&persisted===previous&&current===persisted&&valid(data.font_size)){
        setDefault(data.font_size_default);persisted=data.font_size;apply(persisted,true);
      }
    }catch(e){ /* Keep the saved reading while the local server is restarting. */ }
  }
  window.addEventListener('focus',refresh);
  function ready(){
    const initial=Number(getComputedStyle(root).getPropertyValue('--mc-font-reference'))||DEFAULT;
    const baseline=Number(getComputedStyle(root).getPropertyValue('--mc-font-default'))||DEFAULT;
    defaultSize=valid(baseline)?baseline:DEFAULT;
    persisted=valid(initial)?initial:DEFAULT;apply(persisted);scan(root);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',ready,{once:true});else ready();
  window.mcFontSize={preview:value=>{if(!syncingSelect)apply(value);},save,
    saveDefault:value=>save(value,true),get:()=>current,getDefault:()=>defaultSize};
})();
