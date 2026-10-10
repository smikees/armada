const fs=require('fs'),vm=require('vm'),assert=require('assert');
const badges=['claude','codex','gemini'].map(provider=>{
  const mark={dataset:{},innerHTML:'<svg class="loader"></svg>',textContent:'',setAttribute(){}};
  return {dataset:{cap:'ibkr',provider},title:'',mark,querySelector(){return mark;}};
});
let fetched=0;
const context={document:{getElementById(id){return id==='cap-pane-user'?{}:null;},querySelectorAll(selector){
  if(selector==='.mc-conn-badge')return badges;
  if(selector==='.mc-conn-badge[data-state="checking"]')return badges.filter(b=>b.dataset.state==='checking');
  return [];
}},sessionStorage:{getItem(){return null;}},AbortSignal:{timeout(){}},Date,setTimeout,URLSearchParams,fetch:async()=>{
  fetched++;return {ok:true,json:async()=>({providers:{claude:'ready',codex:'ready',gemini:'ready'},
    connectors:{ibkr:{claude:'failed',codex:'ready',gemini:'unknown'}},pending:false})};
}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
setImmediate(async()=>{
  assert.equal(fetched,1);
  assert.deepEqual(badges.map(b=>b.dataset.state),['failed','ready','unknown']);
  assert.equal(badges[1].mark.textContent,'✓');
  await context.mcCapConnectionsRefresh(true);
  assert.equal(fetched,2);
  assert(badges.every(b=>b.mark.dataset.loader.includes('<svg')));
  console.log('Connector loaders settle without a global icon helper; refresh preserves SVG.');
});
