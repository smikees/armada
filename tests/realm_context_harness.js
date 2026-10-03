const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const calls=[], listeners={}, notices=[];
global.window=global;
global.location={origin:'http://127.0.0.1:8756',href:'http://127.0.0.1:8756/agent/captain'};
const meta={content:'realm-A'};
global.document={querySelector:()=>meta,addEventListener:(name,callback)=>listeners[name]=callback};
global.mcToast=message=>notices.push(message);
let mismatch=false;
global.fetch=async(input,init)=>{
  calls.push({input,init});
  return mismatch?new Response(JSON.stringify({code:'realm_mismatch',error:'Reload the page'}),{status:409}):new Response('{}');
};
eval(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/realm-context.js'),'utf8'));
(async()=>{
  meta.content='realm-B'; // another selection cannot change this document's destination
  await fetch('/api/save-agent',{method:'POST',body:'{"name":"A"}',headers:{'Content-Type':'application/json'}});
  assert.equal(calls.at(-1).init.headers.get('X-Armada-Realm'),'realm-A');
  assert.equal(calls.at(-1).init.body,'{"name":"A"}');
  const req=new Request(location.origin+'/api/save-agent',{method:'POST',body:'original',headers:{'X-Test':'kept'}});
  await fetch(req);
  assert.equal(calls.at(-1).init.headers.get('X-Test'),'kept');
  assert.equal(await req.text(),'original');
  await fetch('https://example.com/data');
  assert.equal(calls.at(-1).init,undefined);
  await fetch('/static/js/chat.js');
  assert.equal(calls.at(-1).init,undefined);
  assert.equal(new URL(mcRealmUrl('/embed/thread?agent=captain')).searchParams.get('_realm'),'realm-A');
  function click(href){
    const link={href,getAttribute:()=>href};
    listeners.click({target:{closest:()=>link}});
    return link.href;
  }
  assert.equal(new URL(click('/agent/captain')).searchParams.get('_realm'),'realm-A');
  assert.equal(click('/switch?path=B'),'/switch?path=B');
  assert.equal(click('https://example.com/'),'https://example.com/');
  assert.equal(click('#section'),'#section');
  const form={action:'/api/save-agent'};
  listeners.submit({target:form});
  assert.equal(new URL(form.action).searchParams.get('_realm'),'realm-A');
  mismatch=true;
  let continued=false;
  await assert.rejects(async()=>{await fetch('/api/save-agent',{method:'POST'});continued=true;},/Reload/);
  assert.equal(continued,false);
  assert.deepEqual(notices,['Reload the page']);
  console.log('Realm browser harness passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
