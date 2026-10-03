const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const saved=new Map();let active,preview={style:{}},events=[];
function classes(initial=[]){const values=new Set(initial);return {add:v=>values.add(v),remove:v=>values.delete(v),contains:v=>values.has(v),toggle:(v,on)=>on?values.add(v):values.delete(v)};}
function page(key,current,custom){
 const input={id:'c-color',value:current,dataset:{colorKey:key},dispatchEvent:e=>events.push(e.type)};
 const circle={dataset:{},style:{},classList:classes(custom?['is-selected']:[])};
 const picker={value:current,click:()=>{}};
 const swatches=['#aabbcc','#112233'].map(color=>({dataset:{fid:'c-color',c:color},classList:classes(color===current?['is-selected']:[])}));
 swatches.forEach(s=>s.parentNode={querySelectorAll:()=>swatches});
 const elements={'c-color':input,'c-color-circle':circle,'c-color-pick':picker};
 const document={readyState:'complete',getElementById:id=>elements[id],querySelectorAll:selector=>selector==='[data-color-key]'?[input]:selector.startsWith('#c-avatar-prev')?[preview]:swatches};
 const context={document,localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},Event:class{constructor(type){this.type=type;}}};
 vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
 return {context,input,circle,picker,swatches};
}
active=page('realm:a','#aabbcc',false);
active.context.mcColorCustom('c-color','#654321');
assert.equal(preview.style.background,'#654321');assert(active.circle.classList.contains('is-selected'));
active.context.mcPickColor(active.swatches[1]);
assert.equal(active.input.value,'#112233');assert.equal(active.circle.style.background,'#654321');
assert.equal(active.picker.value,'#654321');assert(!active.circle.classList.contains('is-selected'));
active=page('realm:a','#112233',false);
assert.equal(active.input.value,'#112233','Remembering custom colour must not alter saved configuration');
assert.equal(active.circle.style.background,'#654321');assert.equal(active.picker.value,'#654321');
active.context.mcSelectCustom('c-color');assert.equal(active.input.value,'#654321');
assert.deepEqual(events.slice(-2),['input','change']);
assert.equal(page('realm:b','#112233',false).circle.dataset.color,undefined,'Preferences are scoped to realm and agent');
console.log('Custom swatch retention, navigation, selection, preview and agent isolation passed.');
