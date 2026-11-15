// Run the production calendar: all views retain frequent system work and live updates.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const button=mode=>({dataset:{jc:mode},style:{},setAttribute(k,v){this[k]=v;}});
function widget(scope){
  const views=['month','week','day'].map(mode=>({...button(mode),addEventListener(name,fn){this.click=()=>fn({stopPropagation(){}});}}));
  const sources=['all','user','system'].map(mode=>({...button(mode),dataset:{source:mode},addEventListener(name,fn){this.click=()=>fn({stopPropagation(){}});}}));
  const body={innerHTML:'',scrollTop:0,insertAdjacentHTML(where,html){assert.equal(where,'afterbegin');this.innerHTML=html+this.innerHTML;}};
  return {dataset:{scope},views,sources,body,label:{},querySelector(s){return s==='.mc-jc-body'?body:this.label;},
    querySelectorAll(s){return s==='.mc-jc-view'?views:s==='.mc-jc-source'?sources:[];},addEventListener(){},getClientRects:()=>[1],contains:()=>false};
}
function localToday(){const d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
const widgets=[widget(''),widget('system')],timers=[];
const storage={};
let state='queued',fail=false,requests=0;
const ctx={Date,console,location:{},localStorage:{getItem:k=>storage[k],setItem:(k,v)=>storage[k]=v},setInterval:(fn,ms)=>timers.push({fn,ms}),
  document:{readyState:'complete',hidden:false,querySelectorAll:()=>widgets},
  mcIcon:name=>'<svg data-icon="'+name+'"></svg>',
  fetch:async(url)=>{requests++;return {json:async()=>fail?{ok:false,error:'offline'}:{ok:true,events:[
    {agent:'system',agent_disp:'ARMADA',job:'inbox-dispatch',job_name:'Inbox <unsafe>',ts:localToday()+'T09:00',status:state},
    {agent:'system',agent_disp:'ARMADA',job:'telegram-inbox',job_name:'Telegram inbox',ts:localToday()+'T10:00',status:'success'},
    ...(!url.includes('scope=system')?[{agent:'captain',agent_disp:'Captain',job:'daily',job_name:'User daily',ts:localToday()+'T11:00',status:'scheduled'}]:[])]}};}};
ctx.window=ctx;vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/jobcal.js'),'utf8'),ctx);
(async()=>{
  await settle();assert.equal(requests,2,'calendar scopes have independent caches');
  for(const w of widgets)for(const mode of ['month','week','day']){
    w.views.find(b=>b.dataset.jc===mode).click();await settle();
    assert.doesNotMatch(w.body.innerHTML,/mc-jc-systems|mc-jc-system-list/);
    assert.equal((w.body.innerHTML.match(/class="mc-jc-ev"/g)||[]).length,w.dataset.scope==='system'?2:3,'system jobs appear only as individual calendar entries');
    assert.match(w.body.innerHTML,/mc-armada-symbol/);
    assert.match(w.body.innerHTML,/Inbox &lt;unsafe&gt;/);
    assert.match(w.body.innerHTML,/queued/);
  }
  const main=widgets[0];
  for(const mode of ['month','week','day']){
    main.views.find(b=>b.dataset.jc===mode).click();await settle();
    main.sources.find(b=>b.dataset.source==='user').click();await settle();
    assert.match(main.body.innerHTML,/User daily/);assert.doesNotMatch(main.body.innerHTML,/Inbox|Telegram/);
    assert.equal(storage['mc-jobcal-source'],'user');
    main.sources.find(b=>b.dataset.source==='system').click();await settle();
    assert.doesNotMatch(main.body.innerHTML,/User daily/);assert.match(main.body.innerHTML,/Inbox/);
  }
  main.sources.find(b=>b.dataset.source==='all').click();await settle();
  state='running';widgets[0].body.scrollTop=37;
  timers.find(t=>t.ms===15000).fn();await settle();
  assert.match(widgets[0].body.innerHTML,/running/);assert.equal(widgets[0].body.scrollTop,37);
  state='success';timers.find(t=>t.ms===15000).fn();await settle();
  assert.match(widgets[0].body.innerHTML,/success/);
  fail=true;timers.find(t=>t.ms===15000).fn();await settle();
  assert.match(widgets[0].body.innerHTML,/could not be refreshed/);
  console.log('Calendar scopes, all views, frequent inbox jobs, escaping and live transitions passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
