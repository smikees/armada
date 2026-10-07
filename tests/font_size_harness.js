const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/font_size.js'),'utf8');
function style(size='',priority=''){
  const values={'font-size':size},priorities={'font-size':priority};
  const s={getPropertyValue:key=>values[key]||'',getPropertyPriority:key=>priorities[key]||'',
    setProperty:(key,value,p='')=>{values[key]=value;priorities[key]=p;}};
  Object.defineProperty(s,'fontSize',{get:()=>values['font-size'],set:value=>values['font-size']=value});
  return s;
}
function element(size=''){
  return {nodeType:1,nodeName:'DIV',style:style(size),dataset:{},value:'draft text',
    setAttribute:()=>{},hasAttribute:()=>false,querySelectorAll:()=>[],dispatchEvent:()=>{}};
}
const channels=[];
class Channel{
  constructor(){channels.push(this);}postMessage(data){channels.filter(c=>c!==this).forEach(c=>c.onmessage?.({data}));}
}
function browser(){
  const root=element(),body=element(),sample=element('17px'),em=element('1.2em'),select=element();select.value='13';
  const events={},windowEvents={},observers=[],calls=[],requests=[],nodes={'mc-font-size':select};
  root.querySelectorAll=()=>[sample,em];
  const rule=style('13px','important'),heading=style('26px');
  const doc={documentElement:root,body,readyState:'complete',styleSheets:[{cssRules:[{style:rule},{cssRules:[{style:heading}]}]}],
    getElementById:id=>nodes[id]||null,createElement:()=>element(),
    addEventListener:(key,fn)=>(events[key]??=[]).push(fn)};
  body.appendChild=node=>nodes[node.id]=node;
  const ctx={document:doc,console,BroadcastChannel:Channel,MutationObserver:class{
    constructor(fn){observers.push(fn);}observe(){}},
    CustomEvent:class{constructor(type,opts){this.type=type;this.detail=opts.detail;}},
    Event:class{constructor(type){this.type=type;}},
    setTimeout:()=>1,clearTimeout:()=>{},getComputedStyle:node=>node.style,
    addEventListener:(key,fn)=>(windowEvents[key]??=[]).push(fn),
    dispatchEvent:event=>(windowEvents[event.type]||[]).forEach(fn=>fn(event)),
    fetch:(url,opts)=>{calls.push({url,body:opts?JSON.parse(opts.body):null});
      return new Promise(resolve=>requests.push({url,resolve}));}};
  ctx.window=ctx;vm.createContext(ctx);vm.runInContext(source,ctx);
  function key(key,code='',extra={}){
    const event={key,code,ctrlKey:true,defaultPrevented:false,preventDefault(){this.defaultPrevented=true;},...extra};
    events.keydown.forEach(fn=>fn(event));return event;
  }
  async function complete(value,error='',index=0){
    const [request]=requests.splice(index,1);assert(request,'A request must be pending');
    request.resolve({ok:!error,json:async()=>request.url==='/api/font-size'?{font_size:value}:{ok:!error,font_size:value,error}});
    for(let i=0;i<8;i++)await Promise.resolve();
  }
  return {ctx,key,complete,calls,requests,rule,heading,sample,em,observers,windowEvents,nodes,root,select};
}
async function run(){
  const a=browser(),b=browser();
  assert.match(a.rule.fontSize,/calc\(13px/);assert.equal(a.rule.getPropertyPriority('font-size'),'important');
  assert.match(a.heading.fontSize,/calc\(26px/);assert.match(a.sample.style.fontSize,/calc\(17px/);
  assert.equal(a.em.style.fontSize,'1.2em','Relative text must not be scaled twice');
  assert(!a.key('+','Equal',{ctrlKey:false}).defaultPrevented);
  assert(!a.key('c','KeyC').defaultPrevented);
  assert(!a.key('+','Equal',{altKey:true}).defaultPrevented);
  assert(!a.key('+','Equal',{isComposing:true}).defaultPrevented);
  assert(a.key('+','Equal').defaultPrevented);
  assert.equal(a.ctx.mcFontSize.get(),14);assert.equal(a.select.value,'14');
  assert.equal(a.calls[0].body.font_size,14);
  assert.equal(a.sample.value,'draft text','Shortcuts must preserve drafts');
  // Coalesce repeat events behind one in-flight save; the newest choice wins.
  a.key('+','NumpadAdd');a.key('-','NumpadSubtract');a.key('0','Digit0');
  assert.equal(a.calls.length,1);await a.complete(14);
  assert.equal(a.calls.length,2);assert.equal(a.calls[1].body.font_size,13);
  await a.complete(13);assert.equal(a.ctx.mcFontSize.get(),13);
  a.key('=','Equal');await a.complete(14);
  assert.equal(b.ctx.mcFontSize.get(),14,'A companion must receive the saved size');
  const later=element('19px');a.observers[0]([{type:'childList',target:a.root,addedNodes:[later]}]);
  assert.match(later.style.fontSize,/calc\(19px/,'Streamed text must follow the reference');
  later.style.fontSize='20px';a.observers[0]([{type:'attributes',target:later}]);
  assert.match(later.style.fontSize,/calc\(20px/);
  const preview=b.ctx.mcFontSize.preview(22);assert.equal(b.calls.length,0);
  b.windowEvents.focus.forEach(fn=>fn());assert.equal(b.calls.length,0,'Do not discard an unsaved settings preview');
  a.key('+','Equal');await a.complete(0,'Write failed');
  assert.equal(a.ctx.mcFontSize.get(),14,'A failed save must restore the persisted preference');
  assert.match(a.nodes['mc-font-size-notice'].textContent,/Write failed/);
  const saved=a.ctx.mcFontSize.save(26);await a.complete(26);await saved;
  const count=a.calls.length;a.key('+','Equal');assert.equal(a.calls.length,count);
  a.ctx.mcFontSize.preview(10);a.key('-','Minus');await a.complete(10);
  a.key('0','Numpad0');await a.complete(13);assert.equal(a.ctx.mcFontSize.get(),13);
  await assert.rejects(a.ctx.mcFontSize.save(13.5));
  assert(a.calls.every(c=>!c.body||Object.keys(c.body).join()==='font_size'),'Shortcuts must never save other appearance changes');
  const c=browser(),savedValues=[];
  c.ctx.addEventListener('armada-font-size',event=>{if(event.detail.persisted)savedValues.push(event.detail.value);});
  c.key('+','Equal');c.ctx.mcFontSize.preview(22);await c.complete(14);
  assert.equal(c.ctx.mcFontSize.get(),22,'Saving a shortcut must not discard a newer unsaved preview');
  assert.equal(savedValues.at(-1),14,'Settings must track the actual saved baseline during a preview');
  c.ctx.mcFontSize.preview(14);c.windowEvents.focus.forEach(fn=>fn());
  c.key('+','Equal');await c.complete(15,'',1);await c.complete(14);
  assert.equal(c.ctx.mcFontSize.get(),15,'A delayed focus refresh must not overwrite a newer save');
  console.log('Keyboard, repeat/coalescing, persistence, failures, draft and companion checks passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
