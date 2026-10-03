const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const listeners={}, requests=[];
const note={textContent:''};
const document={readyState:'complete',getElementById:id=>id==='mc-chatmsg'?note:null,
  querySelectorAll:()=>[],querySelector:()=>null,
  addEventListener:(name,fn)=>(listeners[name]??=[]).push(fn)};
let response={ok:true};
const ctx={document,mcIcon:()=>'',addEventListener:()=>{},
  fetch:async(url,options)=>{requests.push({url,options});return {json:async()=>response};}};
ctx.window=ctx;ctx.parent=ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/chat.js'),'utf8'),ctx);
async function run(){
  const file='D:/Work/Work2/Cabinet-realm/Finance/A - Options trading/report (October).md';
  let prevented=false;
  const link={dataset:{localFile:file}};
  for(const listener of listeners.click){listener({target:{closest:selector=>selector==='a[data-local-file]'?link:null},
    preventDefault:()=>{prevented=true;}});}
  await new Promise(resolve=>setImmediate(resolve));
  assert(prevented,'file links must not navigate the webview');
  assert.equal(requests.length,1);
  assert.equal(requests[0].url,'/api/open-file');
  assert.equal(requests[0].options.method,'POST');
  assert.equal(JSON.parse(requests[0].options.body).path,file);
  response={ok:false,error:'file not found on disk'};
  await ctx.mcOpenThreadFile(file);
  assert.equal(note.textContent,'file not found on disk');
  response={ok:true,revealed:true,error:'Scripts are shown in their folder.'};
  await ctx.mcOpenThreadFile(file);
  assert.equal(note.textContent,response.error);
}
run().catch(error=>{console.error(error);process.exitCode=1;});
