// Exercise the production sender and observer together; SSE is never a second transcript.
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=name=>fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/'+name+'.js'),'utf8');
const settle=async()=>{for(let i=0;i<3;i++)await new Promise(resolve=>setImmediate(resolve));};
let shared={revision:'initial',html:'saved initial transcript',title:'Main',run_id:'',stopping:false,
  metrics:{messages:2,pct:1,chars:40,context_window:200000}};
let stream,stopError=false,deferAdmission=false,pendingAdmission,stopRequests=[],closedStreams=0;
function view(hidden=false){
  const node=()=>({dataset:{},style:{},textContent:'',addEventListener:()=>{}});
  const nodes={'mc-turns':{...node(),dataset:{agent:'captain',thread:'main'},innerHTML:shared.html,
    scrollTop:0,scrollHeight:100,clientHeight:100,querySelector:()=>null,querySelectorAll:()=>[],contains:()=>false},
    'mc-msg':{...node(),value:'',scrollHeight:26,focus:()=>{}},'mc-stop':{...node(),lastChild:{nodeType:3,textContent:'Stop'}},
    'mc-send':node(),'mc-chatmsg':node(),'mc-message-count':node(),'mc-cttitle':node()};
  const timers=new Map();let timerId=0;
  const ctx={URLSearchParams,AbortController,TextDecoder,ReadableStream,Date,Math,
    document:{hidden,readyState:'loading',getElementById:id=>nodes[id]||null,
      querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{}},
    mcIcon:()=>'',location:{pathname:'/thread',search:''},getSelection:()=>null,
    localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},
    addEventListener:()=>{},requestAnimationFrame:fn=>fn(),
    setTimeout:(fn,delay)=>{timers.set(++timerId,{fn,delay});return timerId;},
    clearTimeout:id=>timers.delete(id),
    fetch:async(url,options={})=>{
      const parsed=new URL('http://localhost'+url);
      const json=data=>({ok:true,json:async()=>data});
      if(parsed.pathname==='/api/thread-state'){
        const state={...shared,metrics:{...shared.metrics}};
        if(parsed.searchParams.get('revision')===state.revision)delete state.html;
        return json(state);
      }
      if(parsed.pathname==='/api/chat-stream'){
        const request=JSON.parse(options.body);
        const body=new ReadableStream({start(controller){stream=controller;},cancel(){closedStreams++;}});
        options.signal.addEventListener('abort',()=>{
          const error=new Error('transport disconnected');error.name='AbortError';stream.error(error);
        });
        let admitted;
        pendingAdmission=()=>{shared={...shared,revision:request.tid,run_id:request.tid,
          html:'saved user: '+request.message+'; live **Markdown** and tool activity',
          metrics:{...shared.metrics,messages:3}};admitted?.({ok:true,body});};
        if(deferAdmission)return new Promise(resolve=>admitted=resolve);
        pendingAdmission();return {ok:true,body};
      }
      if(parsed.pathname==='/api/chat-stop'){
        stopRequests.push(parsed.searchParams);
        if(stopError)return {ok:false,json:async()=>({ok:false,error:'Synthetic cancellation failure'})};
        const stopped=!!shared.run_id;
        if(stopped){
          shared={...shared,revision:shared.revision+'-stopped',run_id:'',stopping:false,
            html:'saved partial reply; stopped by owner',metrics:{...shared.metrics,messages:4}};
          stream.enqueue(new TextEncoder().encode('data: {"kind":"done"}\n\n'));
        }
        return json({ok:true,stopped});
      }
      return json({});
    }};
  ctx.window=ctx;ctx.parent=ctx;vm.createContext(ctx);
  vm.runInContext(source('chat'),ctx);vm.runInContext(source('thread_sync'),ctx);
  return {ctx,nodes,get:name=>vm.runInContext(name,ctx),
    send:message=>{nodes['mc-msg'].value=message;ctx.mcChat('captain','main');},
    retry:()=>{for(const [id,timer] of timers)if(timer.delay===200){timers.delete(id);timer.fn();}}};
}
async function sync(...views){await settle();await Promise.all(views.map(v=>v.ctx.mcThreadSync()));await settle();}
function same(a,b){assert.equal(a.nodes['mc-turns'].innerHTML,b.nodes['mc-turns'].innerHTML);
  assert.equal(a.nodes['mc-message-count'].textContent,b.nodes['mc-message-count'].textContent);}
(async()=>{
  const main=view(),detached=view(true);await sync(main,detached);same(main,detached);
  main.send('from main');
  assert.equal(main.nodes['mc-turns'].innerHTML,'saved initial transcript','sending must not invent optimistic transcript HTML');
  await sync(main,detached);same(main,detached);assert(main.get('mcCtrl'));assert(detached.get('mcGen'));
  stream.enqueue(new TextEncoder().encode('data: {"kind":"render","html":"different SSE rendering"}\n\n'));
  await sync(main,detached);same(main,detached);assert.match(main.nodes['mc-turns'].innerHTML,/saved user/);
  vm.runInContext("mcTid='stale-id'",detached.ctx);
  await detached.ctx.mcStop();await sync(main,detached);same(main,detached);
  assert.equal(stopRequests.at(-1).get('agent'),'captain');assert.equal(stopRequests.at(-1).get('thread'),'main');
  assert.equal(stopRequests.at(-1).get('tid'),'stale-id');assert(!main.get('mcGen')&&!detached.get('mcGen'));
  detached.send('from detached');await sync(main,detached);same(main,detached);
  stopError=true;await detached.ctx.mcStop();await sync(main,detached);
  assert.match(detached.nodes['mc-chatmsg'].textContent,/Synthetic cancellation failure/);
  assert(!detached.nodes['mc-stop'].disabled,'failed Stop must be retryable');
  assert(detached.get('mcCtrl')&&!detached.get('mcCtrl.signal.aborted'),'a failed Stop cannot disconnect the stream');
  stopError=false;await detached.ctx.mcStop();await sync(main,detached);same(main,detached);
  assert.equal(detached.nodes['mc-chatmsg'].textContent,'','successful Stop clears its previous failure');
  main.send('survives transport interruption');await sync(main,detached);
  main.get('mcCtrl').abort();await sync(main,detached);same(main,detached);
  assert(main.get('mcGen')&&detached.get('mcGen'),'disconnect does not pretend the engine stopped');
  assert.equal(main.nodes['mc-chatmsg'].textContent,'','successful snapshot observation clears the connection warning');
  assert(main.nodes['mc-msg'].disabled);const liveId=shared.run_id;
  main.send('must not start another turn');assert.equal(shared.run_id,liveId);
  // Stop from the disconnected view targets the admitted conversation, not its lost transport.
  // This closed observer no longer needs completion; the backend still owns the running turn.
  stream={enqueue:()=>{},close:()=>{}};
  await main.ctx.mcStop();await sync(main,detached);same(main,detached);assert(!main.get('mcGen'));
  deferAdmission=true;detached.send('Stop before admission');await settle();
  await detached.ctx.mcStop();await settle();
  assert(detached.get('mcStopRequested')&&detached.get('mcLocalTid'));
  assert(!detached.get('mcCtrl.signal.aborted'),'early Stop must retain the transport until admission');
  pendingAdmission();detached.retry();await sync(main,detached);same(main,detached);
  assert.equal(shared.run_id,'');assert(!detached.get('mcGen'));
  deferAdmission=false;main.send('terminal error');await sync(main,detached);
  shared={...shared,revision:'terminal-error',run_id:'',html:'canonical saved failure'};
  const closedBefore=closedStreams;
  stream.enqueue(new TextEncoder().encode('data: {"kind":"error","error":"Terminal synthetic failure"}\n\n'));
  await sync(main,detached);same(main,detached);assert(!main.get('mcGen')&&!main.get('mcCtrl'));
  assert.equal(closedStreams,closedBefore+1,'terminal errors release the keep-alive stream');
  main.send('backend finishes without terminal SSE');await sync(main,detached);
  shared={...shared,revision:'completed-with-stalled-transport',run_id:'',html:'canonical completion despite stalled SSE'};
  await sync(main,detached);same(main,detached);
  assert(main.get('mcCtrl')&&!main.get('mcGen'),'server completion overrides a stalled transport');
  assert(!main.nodes['mc-msg'].disabled&&!detached.nodes['mc-msg'].disabled);
  main.get('mcCtrl').abort();await settle();
  console.log('shared canonical rendering, Stop from either view, disconnect and admission races passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
