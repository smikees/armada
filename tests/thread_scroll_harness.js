// Opening follows late layout; an owner's reading position wins over later callbacks.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const events=()=>{const handlers=new Map();return {
  addEventListener:(name,fn)=>{if(!handlers.has(name))handlers.set(name,[]);handlers.get(name).push(fn);},
  emit:(name,event={})=>{for(const fn of handlers.get(name)||[])fn(event);}
};};
function fixture(){
  const timers=[],frames=[],observers=[];
  const box={...events(),dataset:{agent:'captain',thread:'main'},style:{},children:[{}],
    scrollHeight:2000,clientHeight:500,querySelectorAll:()=>[],contains:()=>false};
  let top=0;Object.defineProperty(box,'scrollTop',{get:()=>top,set:value=>{top=Math.max(0,Math.min(value,box.scrollHeight-box.clientHeight));}});
  const jump={hidden:true};
  const document={...events(),readyState:'loading',fonts:{...events(),ready:Promise.resolve()},
    getElementById:id=>({'mc-turns':box,'mc-jump-bottom':jump}[id]||null),querySelector:()=>null,querySelectorAll:()=>[]};
  const window={...events(),document,URLSearchParams,mcIcon:()=>'',location:{pathname:'/agent/captain/threads',search:''},
    localStorage:{getItem:()=>null,setItem:()=>{},removeItem:()=>{}},
    setTimeout:(fn,delay)=>{timers.push({fn,delay});return timers.length;},clearTimeout:()=>{},
    setInterval:()=>1,clearInterval:()=>{},requestAnimationFrame:fn=>frames.push(fn),
    ResizeObserver:class{constructor(fn){this.fn=fn;this.targets=new Set();observers.push(this);}observe(node){this.targets.add(node);}disconnect(){this.targets.clear();}},
    MutationObserver:class{constructor(fn){this.fn=fn;}observe(){}disconnect(){}}
  };
  window.window=window;window.parent=window;vm.createContext(window);
  vm.runInContext(fs.readFileSync(__dirname+'/../armada/webui/static/js/chat.js','utf8'),window);
  return {box,window,document,jump,
    flush:()=>{frames.splice(0).forEach(fn=>fn());timers.splice(0).filter(t=>t.delay===120).forEach(t=>t.fn());},
    resize:()=>{for(const observer of observers)if(observer.targets.size)observer.fn();},
    latest:()=>box.scrollHeight-box.scrollTop-box.clientHeight===0};
}
(async()=>{
  const f=fixture();f.flush();await Promise.resolve();assert(f.latest());
  f.box.scrollHeight+=900;f.resize();assert(f.latest(),'Late turn growth must keep latest visible');
  f.box.clientHeight=300;f.resize();assert(f.latest(),'Late viewport layout must keep latest visible');
  f.box.emit('wheel');f.box.scrollTop=200;f.box.scrollHeight+=900;f.resize();
  f.document.fonts.emit('loadingdone');f.window.emit('load');f.flush();
  assert.equal(f.box.scrollTop,200,'Manual reading must survive layout and delayed load callbacks');
  const early=fixture();early.box.emit('wheel');early.box.scrollTop=100;early.flush();await Promise.resolve();
  assert.equal(early.box.scrollTop,100,'Even the initial timer must respect an early owner scroll');
  f.window.emit('pageshow',{persisted:true});assert(f.latest(),'Returning to the conversation opens latest');
  f.box.emit('wheel');f.box.scrollTop=100;f.box.scrollHeight+=200;f.resize();
  assert.equal(f.box.scrollTop,100,'Reading remains available after returning from browser history');
  console.log('Thread initial scrolling and reader ownership passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
