// Check session-wide notice behavior against the actual client script, without a live CLI login.
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm'), path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/authbar.js'),'utf8');
const saved=new Map();
const storage={getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v)};
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function page(status, failStorage=false){
  const bar={innerHTML:''}, message={textContent:''}, intervals=new Map(), events={};
  const p={status,bar,message,reloads:0,logins:0};
  const context={window:{},Date,document:{hidden:false,
    getElementById:id=>id==='mc-authbar'?bar:id==='mc-authmsg'?message:null,
    addEventListener:(name,fn)=>events[name]=fn},
    localStorage:failStorage?{getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}}:storage,
    sessionStorage:storage,location:{reload(){p.reloads++;}},
    setInterval(fn,ms){intervals.set(ms,fn);return ms;},clearInterval:id=>intervals.delete(id),
    fetch:async(url,options)=>({json:async()=>{
      if(url==='/api/auth-login'){assert.equal(options.method,'POST');p.logins++;return {ok:true};}
      assert.ok(url.startsWith('/api/auth-status'));return p.status;
    }})};
  vm.runInNewContext(source,context);
  await flush();
  p.api=context.window;p.intervals=intervals;p.events=events;
  return p;
}
(async()=>{
  const signedOut={logged_in:false,app_session:'run-one'};
  const first=await page(signedOut);
  assert.match(first.bar.innerHTML,/Claude Code is signed out/);
  assert.match(first.bar.innerHTML,/Dismiss Claude sign-in notification/);
  const html=first.bar.innerHTML;
  await first.api.mcAuthCheck(true);
  assert.equal(first.bar.innerHTML,html,'polling must not replace an open notice');
  first.api.mcAuthDismiss();
  await first.intervals.get(60000)();await flush();
  first.events.visibilitychange();await flush();
  assert.equal(first.bar.innerHTML,'','dismissed notices must not reappear on polling or focus');
  assert.equal((await page(signedOut)).bar.innerHTML,'','page reload/navigation must remember the session');
  const next=await page({...signedOut,app_session:'run-two'});
  assert.match(next.bar.innerHTML,/Claude Code is signed out/,'an app restart allows a new notice');
  assert.equal((await page({...signedOut,app_session:'run-two'})).bar.innerHTML,'','seen means once even before dismissal');
  await next.api.mcAuthLogin({disabled:false});
  assert.equal(next.logins,1);
  const progress=next.message.textContent;
  await next.intervals.get(3000)();
  assert.equal(next.message.textContent,progress,'auth polling preserves sign-in progress');
  next.api.mcAuthDismiss();
  await next.intervals.get(3000)();
  assert.equal(next.bar.innerHTML,'','login polling must respect dismissal');
  next.status={logged_in:true,app_session:'run-two'};
  await next.intervals.get(3000)();
  assert.equal(next.reloads,1,'successful login still refreshes the app');
  next.status={...signedOut,app_session:'run-two'};await next.api.mcAuthCheck();
  assert.equal(next.bar.innerHTML,'','a later sign-out in the same session stays quiet');
  const later=await page({logged_in:true,app_session:'run-three'});
  assert.equal(later.bar.innerHTML,'');
  later.status={...signedOut,app_session:'run-three'};await later.api.mcAuthCheck();
  assert.match(later.bar.innerHTML,/Claude Code is signed out/,'signed-in startup must not consume the notice');
  later.status={logged_in:true,app_session:'run-three'};await later.api.mcAuthCheck();
  assert.equal(later.bar.innerHTML,'','sign-in clears the notice');
  const blocked=await page({...signedOut,app_session:'storage-blocked'},true);
  blocked.api.mcAuthDismiss();await blocked.api.mcAuthCheck();
  assert.equal(blocked.bar.innerHTML,'','storage failure must not break dismissal on the current page');
  console.log('Sign-out notice lifecycle passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
