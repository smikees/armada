const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/thread_sync.js'),'utf8');
let shared={revision:'1',html:'initial',title:'Main',run_id:''};
function view(){
  const box={dataset:{agent:'captain',thread:'main'},querySelector:()=>box.editing||null,contains:()=>false};
  const note={dataset:{},textContent:''},stop={style:{}};
  const ctx={mcCtrl:null,mcViewGeneration:0,mcTid:null,document:{hidden:false,
    getElementById:id=>id==='mc-turns'?box:id==='mc-stop'?stop:note,addEventListener:()=>{}},
    URLSearchParams,setTimeout:()=>1,clearTimeout:()=>{},addEventListener:()=>{},getSelection:()=>null,
    mcSetGen:on=>ctx.busy=on,mcSetThreadTitle:(thread,title)=>ctx.title=title,
    mcApplyTurns:(box,html)=>ctx.html=html,mcRefreshMetrics:()=>{},mcRefreshRail:()=>{},mcRefreshAgentDot:()=>{},
    fetch:async url=>{
      const current={...shared};
      if(new URL('http://localhost'+url).searchParams.get('revision')===current.revision)delete current.html;
      return {ok:true,json:async()=>current};
    }};
  ctx.window=ctx;ctx.box=box;
  vm.createContext(ctx);vm.runInContext(source,ctx);return ctx;
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 const main=view(),popout=view();await settle();
 assert.equal(main.html,popout.html);
 shared={revision:'2',html:'user + partial reply',title:'Renamed',run_id:'run-A'};
 await Promise.all([main.mcThreadSync(),popout.mcThreadSync()]);
 assert.equal(main.html,popout.html);assert.equal(popout.mcTid,'run-A');assert(popout.busy);
 shared={revision:'3',html:'user + final reply',title:'Renamed',run_id:''};
 await main.mcThreadSync();await popout.mcThreadSync();
 assert.equal(main.html,popout.html);assert(!popout.busy);
 popout.box.editing={};shared={...shared,revision:'4',html:'external edit'};
 await popout.mcThreadSync();assert.equal(popout.html,'user + final reply','do not destroy unsaved edits');
 popout.box.editing=null;await popout.mcThreadSync();assert.equal(popout.html,'external edit');
 let release;
 popout.fetch=()=>new Promise(resolve=>release=resolve);
 const pending=popout.mcThreadSync();popout.mcViewGeneration++;popout.mcCtrl={};
 release({ok:true,json:async()=>({revision:'old',html:'stale',title:'Old',run_id:''})});
 await pending;assert.equal(popout.html,'external edit','in-flight poll must not overwrite local streaming');
 popout.mcCtrl=null;popout.fetch=main.fetch;shared={...shared,revision:'5',html:''};
 await popout.mcThreadSync();assert.equal(popout.html,'','empty results replace old messages too');
 const header={dataset:{editing:'1'},textContent:'draft title'},row={dataset:{editing:'1'},textContent:'draft title'};
 const titleContext={document:{getElementById:()=>header,querySelector:selector=>selector.startsWith('meta')?null:row},window:{}};
 const chat=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/chat.js'),'utf8');
 vm.createContext(titleContext);
 vm.runInContext(chat.slice(chat.indexOf('function mcSetThreadTitle('),chat.indexOf("if(document.getElementById('mc-turns')){requestAnimationFrame")),titleContext);
 titleContext.mcSetThreadTitle('main','New title');
 assert.equal(header.textContent,'draft title');assert.equal(row.textContent,'draft title');
 delete header.dataset.editing;delete row.dataset.editing;titleContext.mcSetThreadTitle('main','New title');
 assert.equal(header.textContent,'New title');assert.equal(row.textContent,'New title');
 console.log('two-view synchronization and race checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
