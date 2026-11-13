// Run the production calendar: all views retain frequent system work and live updates.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const button=mode=>({dataset:{jc:mode},style:{}});
function widget(scope){
  const views=['month','week','day'].map(mode=>({...button(mode),addEventListener(name,fn){this.click=()=>fn({stopPropagation(){}});}}));
  const body={innerHTML:'',scrollTop:0,insertAdjacentHTML(where,html){assert.equal(where,'afterbegin');this.innerHTML=html+this.innerHTML;}};
  return {dataset:{scope},views,body,label:{},querySelector(s){return s==='.mc-jc-body'?body:this.label;},
    querySelectorAll(s){return s==='.mc-jc-view'?views:[];},addEventListener(){},getClientRects:()=>[1],contains:()=>false};
}
const widgets=[widget(''),widget('system')],timers=[];
let state='queued',fail=false,requests=0;
const ctx={Date,console,location:{},setInterval:(fn,ms)=>timers.push({fn,ms}),
  document:{readyState:'complete',hidden:false,querySelectorAll:()=>widgets},
  mcIcon:name=>'<svg data-icon="'+name+'"></svg>',
  fetch:async()=>{requests++;return {json:async()=>fail?{ok:false,error:'offline'}:{ok:true,events:[],systems:[
    {id:'inbox-dispatch',name:'Inbox <unsafe>',every_minutes:1,status:state,enabled:true},
    {id:'telegram-inbox',name:'Telegram inbox',every_minutes:1,status:'ok',enabled:true}]}};}};
ctx.window=ctx;vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/jobcal.js'),'utf8'),ctx);
(async()=>{
  await settle();assert.equal(requests,2,'calendar scopes have independent caches');
  for(const w of widgets)for(const mode of ['month','week','day']){
    w.views.find(b=>b.dataset.jc===mode).click();await settle();
    assert.match(w.body.innerHTML,/^<section class="mc-jc-systems"/);
    assert.equal((w.body.innerHTML.match(/data-system-job=/g)||[]).length,2,'frequent jobs appear once, including on empty days');
    assert.match(w.body.innerHTML,/data-icon="server-filled"/);
    assert.match(w.body.innerHTML,/Inbox &lt;unsafe&gt;/);
    assert.match(w.body.innerHTML,/Queued/);
  }
  state='running';widgets[0].body.scrollTop=37;
  timers.find(t=>t.ms===15000).fn();await settle();
  assert.match(widgets[0].body.innerHTML,/Running/);assert.equal(widgets[0].body.scrollTop,37);
  state='ok';timers.find(t=>t.ms===15000).fn();await settle();
  assert.match(widgets[0].body.innerHTML,/Completed/);
  fail=true;timers.find(t=>t.ms===15000).fn();await settle();
  assert.match(widgets[0].body.innerHTML,/could not be refreshed/);
  console.log('Calendar scopes, all views, frequent inbox jobs, escaping and live transitions passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
