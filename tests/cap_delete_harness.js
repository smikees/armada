// Server-controlled deletion: no navigation, duplicate writes, or lost recovery state.
const vm=require('vm'),fs=require('fs'),path=require('path'),assert=require('assert');
const tick=()=>new Promise(setImmediate);
const watchdog=setTimeout(()=>{console.error('Delete harness did not finish');process.exit(1);},4000);
let requests=[],respond,filters=0,animations=0,reduced=false;
function element(){return {attrs:{},children:[],classList:{add(){},remove(){}},appendChild(x){this.children.push(x);},
  setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]??null;},removeAttribute(k){delete this.attrs[k];},
  remove(){this.removed=true;},focus(){}};}
const fields=Object.fromEntries(['scope','kind','id','msg'].map(k=>['mc-capdel-'+k,element()]));
fields['mc-capdel-scope'].value='realm';fields['mc-capdel-kind'].value='skills';fields['mc-capdel-id'].value='notes';
fields['mc-cap-del']={style:{display:'flex'}};
function makeCard(owner){const c=element(),summary=element();summary.children=[element(),element()];
  Object.assign(c,{dataset:{owner,kind:'skills',cap:'notes'},inert:false,isConnected:true,
    querySelector:()=>summary,querySelectorAll:()=>[],closest:()=>null,
    getBoundingClientRect:()=>({height:80}),animate:()=>{animations++;return {finished:Promise.resolve()};}});return c;}
let card=makeCard('realm'),other=makeCard('other-agent');
const body=element(),context={document:{body,activeElement:body,getElementById:id=>fields[id],
  querySelectorAll:()=>[card,other].filter(c=>!c.removed),createElement:element},
  window:{matchMedia:()=>({matches:reduced})},performance:{now:()=>1000},
  getComputedStyle:()=>({marginTop:'0px',marginBottom:'8px'}),setTimeout:fn=>setImmediate(fn),
  mcCapFilter:()=>filters++,fetch:async(url,options)=>{requests.push(JSON.parse(options.body));return {json:()=>new Promise(resolve=>respond=resolve)};},
  location:{reload(){throw Error('Deletion must not reload');}},console};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/capedit.js'),'utf8'),context);
(async()=>{
  card.dataset.saving='1';await context.mcCapDelGo();assert.equal(requests.length,0);delete card.dataset.saving;
  let pending=context.mcCapDelGo();await tick();assert(card.inert);assert.equal(card.attrs['aria-busy'],'true');assert(!other.inert);
  await context.mcCapDelGo();assert.equal(requests.length,1);
  respond({ok:false,error:'Disk is read-only'});await pending;
  assert(!card.inert&&!card.removed);assert.equal(card.dataset.deleting,undefined);assert.equal(card.attrs['aria-busy'],undefined);
  pending=context.mcCapDelGo();await tick();respond({ok:true});await pending;
  assert(card.removed);assert(!other.removed);assert.equal(animations,1);assert.equal(filters,1);
  card=makeCard('realm');reduced=true;pending=context.mcCapDelGo();await tick();respond({ok:true});await pending;
  assert(card.removed);assert.equal(animations,1);assert.equal(filters,2);
  console.log('Deletion pending, duplicate admission, scope isolation, rollback, reduced motion and no reload passed');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>clearTimeout(watchdog));
