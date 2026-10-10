// Minimal fake DOM for capreach.js (section switcher) and reachhint.js (model picker line).
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const [capreachJs,hintJs]=process.argv.slice(2);

function el(dataset){return {dataset,hidden:false,attrs:{},setAttribute(k,v){this.attrs[k]=v;},
  addEventListener(){},focus(){}};}
const pills=[el({reach:''}),el({reach:'any'}),el({reach:'claude'}),el({reach:'codex'})];
const secs=[el({reachSec:'any'}),el({reachSec:'claude'}),el({reachSec:'codex'})];
const store={};
const ctx={sessionStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v;}},
  document:{querySelector(){return null;},querySelectorAll(s){
    if(s==='.mc-reach-pill')return pills;if(s==='.mc-reach-sec')return secs;return [];}}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(capreachJs,'utf8'),ctx);
ctx.mcReachPick(pills[2]);
assert.deepEqual(secs.map(s=>s.hidden),[true,false,true]);
assert.equal(pills[2].attrs['aria-pressed'],'true');
assert.equal(pills[0].attrs['aria-pressed'],'false');
assert.equal(store['armada.cap.reach'],'claude');
ctx.mcReachPick(pills[0]);
assert.deepEqual(secs.map(s=>s.hidden),[false,false,false]);
// A saved choice is restored on the next page load.
store['armada.cap.reach']='codex';secs.forEach(s=>{s.hidden=false;});
const ctx2={...ctx};vm.createContext(ctx2);vm.runInContext(fs.readFileSync(capreachJs,'utf8'),ctx2);
assert.deepEqual(secs.map(s=>s.hidden),[true,true,false]);

// reachhint.js: a late answer for an earlier choice never overwrites the current one.
let onChange=null;const text={textContent:''},list={hidden:true,children:[],replaceChildren(...c){this.children=c;}};
const select={value:'gpt-6.1-sol',addEventListener(e,f){onChange=f;}};
const hint={dataset:{reachFor:'c-model',agent:'warren'},querySelector(s){return s==='[data-text]'?text:list;}};
const answers=[];
const ctx3={URLSearchParams,document:{getElementById:()=>select,querySelectorAll:()=>[hint],
  createElement:()=>({textContent:''})},
  fetch:url=>new Promise(r=>answers.push({url,r}))};
vm.createContext(ctx3);vm.runInContext(fs.readFileSync(hintJs,'utf8'),ctx3);
(async()=>{
  onChange();select.value='claude-opus-5-5';onChange();
  assert.equal(answers.length,2);assert(answers[0].url.includes('model=gpt-6.1-sol'));
  const reply=body=>({json:async()=>body});
  answers[1].r(reply({ok:true,engine:'claude',lost:[],text:'All of Warren\'s capabilities work with Claude.'}));
  await new Promise(r=>setImmediate(r));
  answers[0].r(reply({ok:true,engine:'codex',lost:[{why:'IBKR is connected to Claude, one engine at a time.'}],
    text:'On Codex, Warren can\'t use IBKR.'}));
  await new Promise(r=>setImmediate(r));
  assert.equal(hint.dataset.state,'ok');assert.equal(hint.dataset.engine,'claude');
  assert.equal(text.textContent,'All of Warren\'s capabilities work with Claude.');
  assert.equal(list.hidden,true);
  console.log('Reach switcher filters and restores sections; the model hint ignores stale answers.');
})();
