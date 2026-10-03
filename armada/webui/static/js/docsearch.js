(function(){
  const input=document.getElementById('doc-search'),results=document.getElementById('doc-search-results');
  const status=document.getElementById('doc-search-status'),clear=document.getElementById('doc-search-x');
  if(!input||!results||!status)return;
  const normalise=text=>String(text||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();
  let documents=[];
  try{documents=JSON.parse(document.getElementById('doc-search-index').textContent).map(doc=>({...doc,
    searchable:normalise(doc.title+' '+doc.body),titleSearch:normalise(doc.title)}));}catch(e){status.textContent='Help search is unavailable.';return;}
  function snippet(body,terms){
    const position=normalise(body).indexOf(terms[0]);
    let start=Math.max(0,position-55),end=Math.min(body.length,start+210);
    if(start){const boundary=body.indexOf(' ',start);if(boundary>=0&&boundary<position)start=boundary+1;}
    return (start?'…':'')+body.slice(start,end).trim()+(end<body.length?'…':'');
  }
  window.mcDocSearch=function(){
    const query=input.value.trim(),terms=normalise(query).split(' ').filter(Boolean);
    try{sessionStorage.setItem('armada:docs-search',input.value);}catch(e){}
    clear.hidden=!terms.length;results.replaceChildren();results.hidden=!terms.length;
    if(!terms.length){status.textContent='Search titles and content across all help pages.';return;}
    const matches=documents.filter(doc=>terms.every(term=>doc.searchable.includes(term)))
      .map(doc=>({...doc,score:terms.reduce((n,term)=>n+(doc.titleSearch.includes(term)?4:0)+(doc.titleSearch.startsWith(term)?2:0),0)}))
      .sort((a,b)=>b.score-a.score);
    status.textContent=matches.length?matches.length+' '+(matches.length===1?'page matches':'pages match'):'No help pages match “'+query+'”.';
    matches.forEach(doc=>{
      const link=document.createElement('a'),title=document.createElement('strong'),excerpt=document.createElement('span');
      link.className='mc-docitem';link.href=doc.href;title.textContent=doc.title;excerpt.textContent=snippet(doc.body,terms);
      link.append(title,excerpt);results.append(link);
    });
  };
  window.mcDocSearchClear=function(){input.value='';window.mcDocSearch();input.focus();};
  input.addEventListener('keydown',e=>{
    if(e.key==='Escape'){e.preventDefault();window.mcDocSearchClear();}
    if(e.key==='ArrowDown'){const first=results.querySelector('a');if(first){e.preventDefault();first.focus();}}
  });
  try{input.value=sessionStorage.getItem('armada:docs-search')||'';}catch(e){}
  window.mcDocSearch();
})();
