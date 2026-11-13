// Run inside the real WebView after production filtering, sorting and updates.
window.checkSystemJobColumns=function(){
  const table=document.getElementById('mc-sysjobstable'),errors=[];
  const header=table.firstElementChild,heads=[...header.children].map(e=>e.getBoundingClientRect());
  const rows=[...table.querySelectorAll('.mc-sysjob')].filter(e=>e.getClientRects().length);
  if(heads.length!==7||!rows.length)errors.push('Missing header columns or visible rows');
  for(const row of rows){
    const id=row.dataset.sysjob,cells=[...row.children],boxes=cells.map(e=>e.getBoundingClientRect());
    if(getComputedStyle(row).display!=='grid'||cells.length!==7){errors.push(id+': row lost its grid');continue;}
    for(let col=1;col<7;col++){
      const h=heads[col],r=boxes[col];
      if(col<5&&Math.abs(h.left-r.left)>1.5)errors.push(id+': column '+col+' is misaligned');
      if(col>=5&&Math.abs(h.right-r.right)>1.5)errors.push(id+': action '+col+' is misaligned');
      if(r.top<header.getBoundingClientRect().bottom||r.top<boxes[0].top-1||r.bottom>row.getBoundingClientRect().bottom+1)
        errors.push(id+': cell left its row');
    }
    if(cells[0].scrollWidth>cells[0].clientWidth+1)errors.push(id+': description or status overlaps metadata');
    if(cells[4].querySelectorAll('[title]').length!==7)errors.push(id+': week strip is incomplete');
    if(!cells[5].querySelector('button')||!cells[6].querySelector('input[type=checkbox]'))errors.push(id+': actions left their columns');
  }
  if(document.documentElement.scrollWidth>innerWidth+1)errors.push('The page overflowed instead of scrolling the list');
  return {ok:!errors.length,errors,rows:rows.length,width:innerWidth,
    listWidth:table.clientWidth,scrollWidth:table.scrollWidth,overflow:getComputedStyle(table).overflowX};
};
