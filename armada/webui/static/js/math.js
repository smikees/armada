// Server-recognized TeX only. Markdown remains the server's responsibility.
(function(){
  'use strict';
  let loading=null,failed=false;
  function load(){
    if(window.katex)return Promise.resolve();
    if(loading)return loading;
    loading=new Promise((resolve,reject)=>{
      const css=document.createElement('link'),script=document.createElement('script');
      css.rel='stylesheet';css.href='/static/vendor/katex/katex.min.css?v=0.19.1';
      script.src='/static/vendor/katex/katex.min.js?v=0.19.1';script.async=true;
      script.onload=()=>window.katex?resolve():reject(Error('Formula renderer unavailable'));
      script.onerror=()=>reject(Error('Formula renderer unavailable'));
      document.head.append(css,script);
    });
    return loading;
  }
  async function render(root){
    const nodes=[];
    if(root.nodeType===1&&root.matches('.mc-math[data-tex]'))nodes.push(root);
    if(root.querySelectorAll)nodes.push(...root.querySelectorAll('.mc-math[data-tex]'));
    const pending=nodes.filter(n=>!n.dataset.mathRendered);
    if(!pending.length||failed)return;
    try{await load();}catch(_){failed=true;return;} // Readable original text survives a failed load.
    for(const node of pending){
      if(node.dataset.mathRendered||!window.katex)continue;
      node.dataset.mathRendered='1';
      const source=node.textContent;
      try{
        window.katex.render(node.dataset.tex,node,{displayMode:node.classList.contains('is-display'),
          output:'htmlAndMathml',throwOnError:true,trust:false,strict:'error',maxSize:20,maxExpand:1000,macros:{}});
      }catch(_){
        // Neither provider errors nor TeX source may become HTML.
        node.textContent=source;
        node.classList.add('is-unrendered');
        node.title='This formula could not be displayed. Its original text is shown.';
      }
    }
  }
  function start(){
    render(document);
    new MutationObserver(records=>{
      for(const record of records)for(const node of record.addedNodes)render(node);
    }).observe(document.body,{childList:true,subtree:true});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
