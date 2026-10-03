// Execute the shipped controller with deterministic DOM geometry and an idle clock.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Target{
  constructor(){this.events={};}
  addEventListener(name,fn){(this.events[name]??=[]).push(fn);}
  emit(name,data={}){const e={target:this,button:0,pointerId:1,preventDefault(){this.prevented=true;},stopPropagation(){this.stopped=true;},...data};for(const f of this.events[name]||[])f(e);return e;}
}
class El extends Target{
  constructor(){super();this.children=[];this.dataset={};this.style={};this.classes=new Set();this.classList={contains:c=>this.className?.split(' ').includes(c)||this.classes.has(c),toggle:(c,on)=>on?this.classes.add(c):this.classes.delete(c)};this.isConnected=true;this.clientLeft=this.clientTop=0;this.clientWidth=300;this.clientHeight=200;this.scrollWidth=300;this.scrollHeight=200;this.scrollLeft=this.scrollTop=0;this.rect={left:0,top:0};this.css={overflowX:'auto',overflowY:'auto',direction:'ltr'};}
  append(el){el.parentElement=this;this.children.push(el);}
  contains(el){return el===this||this.children.some(c=>c.contains(el));}
  setAttribute(){}
  getBoundingClientRect(){return this.rect;}
  setPointerCapture(){}
  releasePointerCapture(){}
  scrollBy({left,top}){this.scrollLeft=Math.max(0,Math.min(this.scrollWidth-this.clientWidth,this.scrollLeft+left));this.scrollTop=Math.max(0,Math.min(this.scrollHeight-this.clientHeight,this.scrollTop+top));}
}
const doc=new Target(),win=new Target(),contrast=new Target();contrast.matches=false;
doc.documentElement=new El();doc.body=new El();doc.documentElement.append(doc.body);doc.scrollingElement=doc.documentElement;
doc.createElement=()=>new El();doc.querySelector=()=>null;
win.innerWidth=1200;win.innerHeight=800;win.matchMedia=()=>contrast;
let now=0,next=1,timers=new Map(),frames=[],observers=[];
class Observer{constructor(fn){this.fn=fn;observers.push(this);}observe(){}disconnect(){}}
const source=fs.readFileSync(process.argv[2],'utf8');
vm.runInNewContext(source,{document:doc,window:win,Element:El,getComputedStyle:e=>e.css,ResizeObserver:Observer,MutationObserver:Observer,
  requestAnimationFrame:fn=>(frames.push(fn),next++),setTimeout:(fn,delay)=>{const id=next++;timers.set(id,{fn,time:now+delay});return id;},clearTimeout:id=>timers.delete(id)});
const root=doc.body.children[0],x=root.children[0],y=root.children[1],thumb=y.children[0];
const flush=()=>{while(frames.length)frames.shift()();};
const move=(target,px,py)=>{doc.emit('pointermove',{target,clientX:px,clientY:py});flush();};
const tick=ms=>{now+=ms;for(const [id,t] of [...timers])if(t.time<=now){timers.delete(id);t.fn();}};
const outer=new El(),inner=new El(),text=new El();outer.clientWidth=600;outer.clientHeight=500;outer.scrollHeight=1500;outer.rect={left:20,top:20};
inner.rect={left:50,top:50};inner.scrollHeight=1000;inner.append(text);outer.append(inner);doc.body.append(outer);
assert(doc.documentElement.classes.has('mc-overlay-scrollbars'));
move(text,80,80);assert.equal(root.dataset.visible,'true');assert.equal(y.style.left,'341px');assert.equal(x.hidden,true); // nearest scroller, vertical only
tick(799);assert.equal(root.dataset.visible,'true');tick(1);assert.equal(root.dataset.visible,'false');
move(text,81,80);assert.equal(root.dataset.visible,'true');tick(400);doc.emit('scroll',{target:inner});flush();tick(400);assert.equal(root.dataset.visible,'false'); // automatic updates don't postpone idle
move(text,82,80);const press=y.emit('pointerdown',{target:thumb,clientX:342,clientY:62});assert(press.prevented&&press.stopped);
tick(2000);assert.equal(root.dataset.visible,'true');y.emit('pointermove',{clientX:342,clientY:205});assert(inner.scrollTop>650&&inner.scrollTop<800);
y.emit('pointerup');tick(800);assert.equal(root.dataset.visible,'false');assert(y.emit('click').stopped); // dropdown remains open
move(text,83,80);inner.scrollTop=0;y.emit('pointerdown',{clientX:342,clientY:200});assert(inner.scrollTop>600);y.emit('pointerup');
inner.scrollTop=800;outer.scrollTop=0;const wheel=y.emit('wheel',{deltaX:0,deltaY:100,deltaMode:0});assert(wheel.prevented);assert.equal(outer.scrollTop,100); // chain at end
move(text,84,80);inner.css.overscrollBehaviorY='contain';outer.scrollTop=0;y.emit('wheel',{deltaX:0,deltaY:100,deltaMode:0});assert.equal(outer.scrollTop,0);delete inner.css.overscrollBehaviorY;
inner.scrollWidth=900;inner.css.direction='rtl';inner.scrollLeft=-600;move(text,85,80);assert.equal(x.hidden,false);assert.equal(x.children[0].style.left,'0px');
x.emit('pointerdown',{clientX:330,clientY:244});assert(inner.scrollLeft>-50);x.emit('pointerup');
move(outer,25,25);assert.equal(y.style.left,'611px'); // exposed outer area owns its own bar
move(text,86,80);inner.isConnected=false;observers[1].fn();flush();assert.equal(root.dataset.visible,'false');inner.isConnected=true;
contrast.matches=true;contrast.emit('change');assert(!doc.documentElement.classes.has('mc-overlay-scrollbars'));move(text,87,80);assert.equal(root.dataset.visible,'false');
contrast.matches=false;contrast.emit('change');move(text,88,80);assert.equal(root.dataset.visible,'true');doc.emit('pointerout',{relatedTarget:null});assert.equal(root.dataset.visible,'false');
console.log('Scrollbar contracts passed: nesting, idle, streaming, drag, track clicks, wheel chaining, containment, RTL, removal and high contrast.');
