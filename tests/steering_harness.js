// Production composer: explicit steering, safe retries, draft preservation and Stop.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const node=()=>({dataset:{},style:{},textContent:'',addEventListener:()=>{},setAttribute:()=>{},classList:{toggle:()=>{}}});
const nodes={'mc-msg':{...node(),value:'',placeholder:'Message Captain',focus:()=>{}},'mc-send':node(),
  'mc-chatmsg':node(),'mc-plus':node(),'mc-stop':node()};
let requests=[],reply,status='pending',network=false,later;
const ctx={AbortController,Date,Math,URLSearchParams,setTimeout,clearTimeout,
 document:{getElementById:id=>nodes[id]||null,querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{}},
 localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},mcIcon:()=>'',addEventListener:()=>{},
 fetch:async(url,options)=>{
   assert.equal(url,'/api/chat-steer');requests.push(JSON.parse(options.body));
   if(network)throw Error('Connection lost');
   if(later)return await new Promise(resolve=>reply=resolve);
   return {ok:true,json:async()=>({ok:true,receipt:{id:requests.at(-1).request_id,status,error:status==='rejected'?'Run finished':''}})};
 }};
ctx.window=ctx;ctx.parent=ctx;vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/chat.js'),'utf8'),ctx);
const run=code=>vm.runInContext(code,ctx);
const ta=nodes['mc-msg'],button=nodes['mc-send'];
(async()=>{
 run("mcTid='exact-run';mcSetGen(true)");assert(ta.disabled);
 ta.value='Unsupported';await ctx.mcSteer('captain','main');assert.equal(requests.length,0);
 run('mcSteerable=true;mcSetGen(true)');assert(!ta.disabled);assert.equal(ta.placeholder,'Steer this run…');
 assert.equal(button.dataset.label,'Steer');assert(nodes['mc-plus'].disabled);
 ta.value='Focus on cost';network=true;await ctx.mcSteer('captain','main');
 assert.equal(ta.value,'Focus on cost');assert.equal(button.dataset.label,'Check');
 ta.value='';ctx.mcSyncSend();assert.equal(button.style.display,'inline-flex','Check survives clearing the draft');
 network=false;await ctx.mcSteer('captain','main');assert.deepEqual(requests[0],requests[1]);
 assert.equal(requests[0].tid,'exact-run');assert.equal(requests[0].message,'Focus on cost');
 ta.value='A newer draft';ctx.mcSteerObserve([{id:requests[0].request_id,status:'accepted'}]);
 assert.equal(ta.value,'A newer draft');assert(!run('mcSteerRequest'));
 status='rejected';await ctx.mcSteer('captain','main');assert.equal(ta.value,'A newer draft');
 assert.match(nodes['mc-chatmsg'].textContent,/Run finished/);
 status='accepted';await ctx.mcSteer('captain','main');assert.equal(ta.value,'');
 ta.value='Last instruction';later=true;const inflight=ctx.mcSteer('captain','main');
 ctx.mcSteerObserve([{id:requests.at(-1).request_id,status:'accepted'}]);
 ta.value='Keep this';reply({ok:true,json:async()=>({ok:false,error:'Late failure'})});await inflight;
 assert.equal(ta.value,'Keep this');assert.match(nodes['mc-chatmsg'].textContent,/sent to the active run/);
 later=false;status='uncertain';await ctx.mcSteer('captain','main');assert.equal(ta.value,'Keep this');
 run('mcStopRequested=true;mcSyncSend()');await ctx.mcSteer('captain','main');assert.equal(button.disabled,true);
 run('mcSteerable=false;mcSetGen(false)');assert(!ta.disabled);assert(!nodes['mc-plus'].disabled);
 assert.equal(ta.placeholder,'Message Captain');assert.equal(button.dataset.label,'');
 console.log('steering, explicit retries, late responses, draft preservation, Stop and unsupported engines passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
