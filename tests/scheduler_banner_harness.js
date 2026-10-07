const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const bar={innerHTML:''},message={textContent:''},button={disabled:false};
let reading={running:false,scheduled:11,recovery:'starting',action_required:false};
let delay=0,startResult={ok:true},events={},calls=[];
const context={document:{hidden:false,getElementById:id=>id==='mc-schedbar'?bar:id==='mc-schedmsg'?message:button,
 addEventListener:(name,fn)=>events[name]=fn},setTimeout:(fn,ms)=>{delay=ms;return 1;},clearTimeout:()=>{},
 fetch:async(url,options)=>{calls.push(url);return{ok:true,json:async()=>url.includes('-start')?startResult:reading};}};
context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync('armada/webui/static/js/schedbar.js','utf8'),context);
const flush=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
(async()=>{
 await flush();assert.equal(bar.innerHTML,'');assert.equal(delay,2000);
 for(const phase of ['recovering','paused']){
  reading.recovery=phase;await context.mcSchedCheck();assert.equal(bar.innerHTML,'');
  assert.equal(delay,phase==='paused'?60000:2000);
 }
 reading={running:false,scheduled:11,recovery:'failed',action_required:true,error:'<Exact startup error>'};
 await context.mcSchedCheck();assert.match(bar.innerHTML,/couldn&#39;t restart/);
 assert.match(bar.innerHTML,/&lt;Exact startup error&gt;/);assert.match(bar.innerHTML,/>Retry</);
 reading={running:false,scheduled:11,recovery:'recovering',action_required:false};
 await context.mcSchedStart(button);assert.equal(bar.innerHTML,'');assert.equal(delay,2000);
 reading={running:true,scheduled:11,recovery:'running',action_required:false};
 await context.mcSchedCheck();assert.equal(bar.innerHTML,'');assert.equal(delay,60000);
 reading={running:false,scheduled:0,recovery:'failed',action_required:true};
 await context.mcSchedCheck();assert.equal(bar.innerHTML,'');
 reading={running:false,scheduled:11,recovery:'disabled',action_required:true};
 await context.mcSchedCheck();assert.match(bar.innerHTML,/turned off/);
 startResult={ok:false,error:'Specific permission error'};
 await context.mcSchedStart(button);assert.equal(message.textContent,startResult.error);assert(!button.disabled);
 reading={running:false,scheduled:11};await context.mcSchedCheck();
 assert.match(bar.innerHTML,/scheduler isn&#39;t running/,'Legacy unmanaged servers remain truthful');
 console.log('Quiet startup/recovery, exact failure, manual retry and legacy status checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
