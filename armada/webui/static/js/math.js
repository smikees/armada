// Server-recognized TeX only. Markdown remains the server's responsibility.
(function(){
  'use strict';
  function render(root){
    const nodes=[];
    if(root.nodeType===1&&root.matches('.mc-math[data-tex]'))nodes.push(root);
    if(root.querySelectorAll)nodes.push(...root.querySelectorAll('.mc-math[data-tex]'));
    for(const node of nodes){
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
