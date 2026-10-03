// Exercise subscription rendering and clearing through the real provider refresh.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements={};
function element(){return {textContent:'',hidden:true,dataset:{},classList:{toggle(){},remove(){}},removeAttribute(){}};}
const cards=[];
for(const p of ['claude','codex']){
  cards.push({dataset:{connection:p}});
  for(const id of ['status','installed','plan','connect','disconnect','install','guide','open','url','url-wrap','cancel'])elements['provider-'+p+'-'+id]=element();
  elements['provider-'+p+'-plan'].dataset.planPrefix=p==='codex'?'ChatGPT':'Claude';
  elements['provider-'+p+'-connect'].querySelector=()=>({dataset:{defaultLabel:'Sign in'}});
}
let states={},fail=false;
const context={document:{getElementById:id=>elements[id],querySelectorAll:sel=>sel==='[data-connection]'?cards:[],addEventListener(){}},
  AbortController,setTimeout(){},clearTimeout(){},setInterval(){},CustomEvent:class {},
  fetch:async()=>{if(fail)throw Error('Unavailable');return {ok:true,json:async()=>({providers:states,models:[]})};},
  dispatchEvent(){},addEventListener(){}};
context.window=context;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
async function refresh(p,state){states={[p]:{installed:true,version:'1',...state}};await context.mcRefreshProviders();return elements['provider-'+p+'-plan'];}
(async()=>{
  assert.equal((await refresh('codex',{connected:true,plan:'prolite'})).textContent,'ChatGPT Pro');
  assert.equal((await refresh('codex',{connected:true,plan:'promax'})).textContent,'ChatGPT Pro');
  assert.equal((await refresh('codex',{connected:true,plan:'plus'})).textContent,'ChatGPT Plus');
  assert.equal((await refresh('claude',{connected:true,plan:'max_20x'})).textContent,'Claude Max 20×');
  assert.equal((await refresh('claude',{connected:true,plan:'pro'})).textContent,'Claude Pro');
  assert.equal((await refresh('codex',{connected:false,plan:'pro'})).hidden,true);
  for(const plan of ['',null,'unknown','<script>','constructor']){
    const shown=await refresh('codex',{connected:true,plan});assert.equal(shown.hidden,true);assert.equal(shown.textContent,'');
  }
  await refresh('codex',{connected:true,plan:'pro'});
  fail=true;await context.mcRefreshProviders();assert.equal(elements['provider-codex-plan'].hidden,true);
  assert.equal(elements['provider-codex-plan'].textContent,'');
})().catch(e=>{console.error(e);process.exitCode=1;});
