const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
let now=1000,calls=0,blocked=false,pending=[];
const storage=new Map(),header={dataset:{codexEnabled:'true'},innerHTML:'',querySelector:()=>null};
const data={claude:{available:true,weekly:{pct:20},session:{pct:10}},
 codex:{available:true,groups:[{id:'codex',windows:[{label:'Weekly',window_minutes:10080,pct:30}]}]},
 gemini:{available:true,weekly:{pct:5}}};
const source=fs.readFileSync(process.argv[2],'utf8');
const boot=source.slice(0,source.lastIndexOf('if(document.readyState'))+
 'window.check={renderHeaderLimits};})();';
function context(){
 const window={mcIcon:()=>'<svg></svg>'};
 const env={window,Date:{now:()=>now},AbortSignal,AbortController,setTimeout,clearTimeout,console,
  document:{getElementById:()=>header},
  sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
  fetch:async url=>{calls++;const provider=url.split('provider=')[1].split('&')[0];
   if(blocked)await new Promise(resolve=>pending.push(resolve));
   return {ok:true,json:async()=>data[provider]};}};
 vm.runInNewContext(boot,env);return window.check;
}
(async()=>{
 let api=context();
 await Promise.all([api.renderHeaderLimits(),api.renderHeaderLimits()]);
 assert.equal(calls,3,'Overlapping initialization must share provider requests');
 assert(!header.innerHTML.includes('is-loading'));
 for(let i=0;i<8;i++){now+=5000;await api.renderHeaderLimits();}
 assert.equal(calls,3,'Focus/navigation within five minutes must reuse readings');
 api=context();await api.renderHeaderLimits();assert.equal(calls,3,'Navigation must reuse session cache');
 now=301001;blocked=true;
 const refresh=api.renderHeaderLimits();
 assert.equal(calls,6);assert(!header.innerHTML.includes('is-loading'),'Refresh must retain the last readings');
 const overlapping=api.renderHeaderLimits();assert.equal(calls,6);
 pending.forEach(resolve=>resolve());await Promise.all([refresh,overlapping]);
 blocked=false;await api.renderHeaderLimits();assert.equal(calls,6);
 await api.renderHeaderLimits(true);assert.equal(calls,9,'An explicit manual refresh still works');
 console.log('Five-minute limits cache, warm navigation, overlap and background refresh passed.');
})().catch(error=>{console.error(error);process.exit(1)});
