const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const element={innerHTML:''};
const storage=new Map();let storageListener;
let reply={installed:true,version:'0.99.82',latest:'0.99.83',newer:true,status:'needs-installer',releases:'https://example.com'};
const context={document:{getElementById:()=>element},window:{addEventListener:(name,fn)=>{if(name==='storage')storageListener=fn;}},setInterval:()=>0,
  localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
  fetch:async()=>({json:async()=>reply})};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/updbar.js'),'utf8'),context);
(async()=>{
  await context.window.mcUpdCheck();
  assert.match(element.innerHTML,/v0\.99\.83 is out/);
  assert.match(element.innerHTML,/aria-label="Dismiss update notification"/);
  context.window.mcUpdateDismiss();assert.equal(element.innerHTML,'');
  await context.window.mcUpdCheck();assert.equal(element.innerHTML,'');
  reply={...reply,latest:'0.99.84'};
  await context.window.mcUpdCheck();assert.match(element.innerHTML,/v0\.99\.84 is out/);
  for(const status of ['needs-installer','staged','available']){
    reply={...reply,status,newer:false,latest:'0.99.82',staged:status==='staged'?'0.99.82':''};
    await context.window.mcUpdCheck(); assert.equal(element.innerHTML,'');
  }
  reply={...reply,newer:true,staged:'0.99.83',phase:'ready'};
  await context.window.mcUpdCheck();assert.equal(element.innerHTML,'');
  reply={...reply,staged:'0.99.85'};
  await context.window.mcUpdCheck(); assert.match(element.innerHTML,/Restart to update/);
  context.window.mcUpdateDismiss();assert.equal(element.innerHTML,'');
  reply={...reply,requested:true,phase:'waiting'};
  await context.window.mcUpdCheck();assert.match(element.innerHTML,/Postpone update/);
  assert.doesNotMatch(element.innerHTML,/mc-banner-dismiss/);
  reply={...reply,requested:false,phase:'error'};
  await context.window.mcUpdCheck();assert.match(element.innerHTML,/Restart to update/);
  assert.doesNotMatch(element.innerHTML,/mc-banner-dismiss/);
  reply={...reply,phase:'ready'};
  storageListener({key:'armada-dismissed-update',newValue:''});
  await context.window.mcUpdCheck();assert.match(element.innerHTML,/Restart to update/);
  // A new page on the same origin keeps the same dismissal without disabling updates.
  context.window.mcUpdateDismiss();
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/updbar.js'),'utf8'),context);
  await context.window.mcUpdCheck();assert.equal(element.innerHTML,'');
  reply={...reply,newer:false,staged:'',phase:'error',message:'Startup failed <details>'};
  await context.window.mcUpdCheck(); assert.match(element.innerHTML,/Restart needs attention/);
  assert.match(element.innerHTML,/&lt;details&gt;/);
  reply={...reply,phase:'ready',status:'current'};
  await context.window.mcUpdCheck(); assert.equal(element.innerHTML,'');
  console.log('Update banner availability checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
