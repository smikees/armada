const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const element={innerHTML:''};
let reply={installed:true,version:'0.99.82',latest:'0.99.83',newer:true,status:'needs-installer',releases:'https://example.com'};
const context={document:{getElementById:()=>element},window:{},setInterval:()=>0,
  fetch:async()=>({json:async()=>reply})};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/updbar.js'),'utf8'),context);
(async()=>{
  await context.window.mcUpdCheck();
  assert.match(element.innerHTML,/v0\.99\.83 is out/);
  for(const status of ['needs-installer','staged','available']){
    reply={...reply,status,newer:false,latest:'0.99.82',staged:status==='staged'?'0.99.82':''};
    await context.window.mcUpdCheck(); assert.equal(element.innerHTML,'');
  }
  reply={...reply,newer:true,staged:'0.99.83',phase:'ready'};
  await context.window.mcUpdCheck(); assert.match(element.innerHTML,/Restart to update/);
  reply={...reply,newer:false,staged:'',phase:'error',message:'Startup failed <details>'};
  await context.window.mcUpdCheck(); assert.match(element.innerHTML,/Restart needs attention/);
  assert.match(element.innerHTML,/&lt;details&gt;/);
  reply={...reply,phase:'ready',status:'current'};
  await context.window.mcUpdCheck(); assert.equal(element.innerHTML,'');
  console.log('Update banner availability checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
