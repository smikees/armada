const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const listeners={},classes=new Set();
const field={id:'setting',value:'original',type:'text',matches:()=>false,closest:()=>null};
const root={querySelectorAll:()=>[field]};
const button={dataset:{},classList:{toggle:(k,v)=>v?classes.add(k):classes.delete(k)},setAttribute(){},removeAttribute(){},closest:()=>root};
const ctx={Map,queueMicrotask:f=>f(),setTimeout:f=>f(),setInterval(){},document:{readyState:'complete',querySelector:s=>s==='#c-save'?button:null,addEventListener:(e,f)=>listeners[e]=f}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync('armada/webui/static/js/settings_dirty.js','utf8'),ctx);
function edit(v){field.value=v;listeners.input();}
edit('changed');assert.equal(button.dataset.unsaved,'true');assert.ok(classes.has('mc-save-dirty'));
edit('original');assert.equal(button.dataset.unsaved,'false');
edit('submitted');const pending=ctx.mcDirtyCapture('#c-save');
edit('newer while saving');ctx.mcDirtySaved(pending);assert.equal(button.dataset.unsaved,'true');
edit('submitted');assert.equal(button.dataset.unsaved,'false');
edit('failed save');ctx.mcDirtyCapture('#c-save');assert.equal(button.dataset.unsaved,'true');
ctx.mcDirtySaved(ctx.mcDirtyCapture('#c-save'));assert.equal(button.dataset.unsaved,'false');
console.log('Dirty state, reverting, successful save and edits during save passed.');
