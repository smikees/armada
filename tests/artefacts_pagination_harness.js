const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
function fixture(count){
  const rows=Array.from({length:count},(_,i)=>({
    dataset:{search:'file '+i,owner:i%2?'finance':'hand',type:i%2?'input':'output',ymd:'2026-09-30'},
    style:{},cells:[{textContent:'file '+i,dataset:{}}],
  }));
  const header={dataset:{col:'0',sort:'text'},querySelector:()=>({style:{}})};
  const table={dataset:{today:'2026-10-01'},tBodies:[{rows,appendChild:r=>{rows.splice(rows.indexOf(r),1);rows.push(r);}}],
    tHead:{rows:[{cells:[header]}]}};
  const controls={'art-table':table};
  for(const id of ['art-q','art-owner','art-type','art-when','art-from','art-to','art-count','art-clear','art-q-x']){
    controls[id]={value:'',dataset:{},style:{},textContent:''};
  }
  const pagers=Array.from({length:2},()=>{
    const parts={'[data-art-prev]':{},'[data-art-next]':{},'[data-art-range]':{textContent:''}};
    return {style:{},querySelector:key=>parts[key]};
  });
  controls['art-pager-top']={scrollIntoView:()=>{}};
  const ctx={document:{getElementById:id=>controls[id]||null,
    querySelectorAll:selector=>selector==='.mc-art-pager'?pagers:[],addEventListener:()=>{}},
    location:{search:''},URLSearchParams,Date,clearTimeout:()=>{},setTimeout:fn=>fn()};
  ctx.window=ctx;vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/artefacts.js'),'utf8'),ctx);
  const visible=()=>rows.filter(r=>r.style.display!=='none');
  return {ctx,rows,controls,pagers,header,visible};
}
(async()=>{
  for(const count of [0,1,100,101,250]){
    const {pagers,visible}=fixture(count);
    assert.equal(visible().length,Math.min(count,100));
    assert.equal(pagers[0].style.display,count>100?'flex':'none');
  }
  let f=fixture(250);
  f.ctx.mcArtPage(1);
  assert.equal(f.visible().length,100);assert.equal(f.visible()[0].dataset.search,'file 100');
  assert.equal(f.pagers[1].querySelector('[data-art-range]').textContent,'101–200 of 250 · Page 2 of 3');
  f.ctx.mcArtPage(1);
  assert.equal(f.visible().length,50);assert.equal(f.visible()[0].dataset.search,'file 200');
  assert(f.pagers[0].querySelector('[data-art-next]').disabled);
  f.ctx.mcArtPage(-1);assert.equal(f.visible()[0].dataset.search,'file 100');
  // Filtering runs over every page and returns to page one of the matching set.
  f.controls['art-owner'].dataset.val='finance';f.ctx.mcArtApply();
  assert.equal(f.visible().length,100);assert.equal(f.visible()[0].dataset.search,'file 1');
  assert.equal(f.controls['art-count'].textContent,'125 artefacts of 250');
  f.ctx.mcArtPage(1);assert.equal(f.visible().length,25);
  f.controls['art-q'].value='file 249';f.ctx.mcArtApply();
  assert.equal(f.visible().length,1);assert.equal(f.visible()[0].dataset.search,'file 249');
  assert.equal(f.pagers[0].style.display,'none');
  f.controls['art-q'].value='no matches';f.ctx.mcArtApply();
  assert.equal(f.visible().length,0);assert.equal(f.controls['art-count'].textContent,'0 artefacts of 250');
  // Sorting also runs over the entire list, including rows on later pages.
  f=fixture(250);f.ctx.mcArtPage(1);f.ctx.mcArtSort(f.header);f.ctx.mcArtSort(f.header);
  assert.equal(f.visible()[0].dataset.search,'file 249');assert.equal(f.visible().length,100);
  assert(f.pagers[0].querySelector('[data-art-prev]').disabled);
  // Deleting the only row on the last page clamps to the remaining page and updates both pagers.
  f=fixture(101);f.ctx.mcArtPage(1);
  const deleted=f.visible()[0];deleted.remove=()=>f.rows.splice(f.rows.indexOf(deleted),1);
  f.ctx.mcArtConfirm=async()=>true;f.ctx.mcArtToast=()=>{};
  f.ctx.fetch=async()=>({json:async()=>({ok:true})});
  await f.ctx.mcArtDelete({closest:()=>deleted},'D:\\Realm\\report.md');
  assert.equal(f.visible().length,100);assert.equal(f.controls['art-count'].textContent,'100 artefacts');
  assert(f.pagers.every(p=>p.style.display==='none'));
  console.log('ok');
})().catch(error=>{console.error(error);process.exitCode=1;});
