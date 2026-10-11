const assert=require('assert');
const fs=require('fs');
const path=require('path');
const vm=require('vm');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/chat.js'),'utf8');
const code=source.slice(source.indexOf('function mcMarkDone(){'),source.indexOf('function mcEsc('));
for(const [status,label] of [['ok','Done'],['error','Failed'],['failed','Failed'],['stopped','Stopped'],['warn','Completed with warnings']]){
  let outcome;
  const col={querySelector:()=>null,appendChild:d=>{outcome=d;}};
  const turn={dataset:{status},querySelector:()=>({parentNode:col})};
  const document={querySelector:()=>null,querySelectorAll:q=>q.includes('.mc-turn[')?[turn]:[],
    createElement:()=>({style:{}})};
  const context={document,window:{mcIcon:()=>'<svg></svg>'},MC_DONE_ICON:'<svg></svg>'};
  vm.createContext(context);vm.runInContext(code+';mcMarkDone();',context);
  assert(outcome.innerHTML.includes('<span>'+label+'</span>'));
  if(status==='error'||status==='failed')assert.equal(outcome.style.color,'var(--status-bad)');
}
console.log('Persisted chat outcomes passed');
