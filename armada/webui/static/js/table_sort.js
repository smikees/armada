function mcSortTable(th,i){
  const tb=th.closest('table').querySelector('tbody'); const rows=[...tb.rows];
  const dir=th._d=(th._d===1?-1:1);
  rows.sort((a,b)=>{const x=(a.cells[i]||{}).innerText||'',y=(b.cells[i]||{}).innerText||'';
    return x.localeCompare(y,undefined,{numeric:true})*dir;});
  rows.forEach(r=>tb.appendChild(r));
}
