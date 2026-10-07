const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/threadlist.js'),'utf8');
const calls=[],popups=new Map(),alerts=[];
let native=false,fail=false;
const ctx={document:{addEventListener:()=>{},getElementById:()=>null,querySelectorAll:()=>[]},
 location:{},mcRealmId:'realm-A',encodeURIComponent,mcAlert:message=>alerts.push(message),
 fetch:async()=>{
   calls.push('fetch');
   return {ok:!fail,json:async()=>fail?{error:'unavailable'}:{ok:true,native,url:'/thread-window?agent=alpha&thread=main&_realm=realm-A'}};
 },
 open:(url,name)=>{
   calls.push('open');
   if(!popups.has(name))popups.set(name,{closed:false,location:{href:'about:blank',replace:function(value){this.href=value;}},
     focus:function(){this.focused=true;},close:function(){this.closed=true;}});
   return popups.get(name);
 }};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(source,ctx);
const event=()=>({preventDefault:()=>{},stopPropagation:()=>{},currentTarget:{disabled:false}});
(async()=>{
 const click=event();await ctx.mcOpenThreadWindow(click,'alpha','main');
 assert.deepEqual(calls.slice(0,2),['open','fetch'],'create browser fallback during the click');
 const first=[...popups.values()][0];assert(first.location.href.startsWith('/thread-window'));
 assert(first.focused&&!click.currentTarget.disabled);
 await ctx.mcOpenThreadWindow(event(),'alpha','main');
 assert.equal(popups.size,1);assert(!first.closed);
 await ctx.mcOpenThreadWindow(event(),'a-b','c');await ctx.mcOpenThreadWindow(event(),'a','b-c');
 assert.equal(popups.size,3,'different agent/thread pairs never share a named window');
 fail=true;await ctx.mcOpenThreadWindow(event(),'missing','main');
 assert([...popups.values()].at(-1).closed);assert(alerts.includes('unavailable'));
 await ctx.mcOpenThreadWindow(event(),'alpha','main');assert(!first.closed,'error must not close an existing conversation');
 fail=false;native=true;ctx.pywebview={};calls.length=0;
 await ctx.mcOpenThreadWindow(event(),'native','main');assert.deepEqual(calls,['fetch']);
 console.log('browser fallback, native preference, focus and error checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
