// Verify the shared menu preserves form values/events and live provider option changes.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let document;const observers=[];
class Element{
  constructor(tag){this.tagName=tag.toUpperCase();this.children=[];this.attrs={};this.dataset={};this.events={};this.style={};this.className='';this.textContent='';this.scrollTop=0;this.scrollHeight=200;this.disabled=false;this.open=false;
    this.classList={add:c=>this.className+=' '+c,toggle:(c,on)=>{this.className=this.className.split(' ').filter(x=>x!==c).join(' ')+(on?' '+c:'');}};}
  get firstElementChild(){return this.children[0];}
  append(...nodes){nodes.forEach(n=>{n.parentElement=this;this.children.push(n);});}
  after(node){const p=this.parentElement;p.children.splice(p.children.indexOf(this)+1,0,node);node.parentElement=p;}
  replaceChildren(){this.children=[];}
  contains(node){return this===node||this.children.some(c=>c.contains(node));}
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k]??null;}
  getBoundingClientRect(){return this.rect||{top:700,bottom:732,left:20,width:340};}
  cloneNode(){return new Element(this.tagName);}
  addEventListener(type,fn){(this.events[type]??=[]).push(fn);}
  dispatchEvent(e){e.target??=this;(this.events[e.type]||[]).forEach(fn=>fn(e));if(e.bubbles&&this.parentElement)this.parentElement.dispatchEvent(e);}
  focus(){document.activeElement=this;}
  click(){this.dispatchEvent(new Event('click',{bubbles:true}));}
}
class Event{constructor(type,opts={}){Object.assign(this,{type,bubbles:false,preventDefault(){this.prevented=true;}},opts);}}
const root=new Element('div');
document={activeElement:null,createElement:t=>new Element(t),events:{},
  addEventListener(type,fn){(this.events[type]??=[]).push(fn);},
  querySelectorAll(){const found=[];function walk(n){if(n.className.includes('mc-select-dropdown')&&n.open)found.push(n);n.children.forEach(walk);}walk(root);return found;}};
const label=new Element('label');label.textContent='Model';root.append(label);
const select=new Element('select');select.id='model';select.value='auto';select.previousElementSibling=label;select.labels=[label];root.append(select);
Object.defineProperty(select,'selectedOptions',{get(){return this.options.filter(o=>o.value===this.value);}});
function options(rows){select.options=rows.map(([value,text,disabled=false])=>({value,textContent:text,disabled,parentElement:select}));}
options([['auto','Automatic'],['blocked','Unavailable',true],['gpt','GPT']]);
let changes=0,inputs=0;select.addEventListener('change',()=>changes++);select.addEventListener('input',()=>inputs++);
const ctx={document,Event,Date,innerHeight:800,innerWidth:1000,addEventListener(){},MutationObserver:class{constructor(fn){observers.push(fn);}observe(){} }};ctx.window=ctx;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),ctx);
ctx.mcFDFromSelect(select,new Element('svg'));
const dropdown=root.children[2],summary=dropdown.children[0],menu=dropdown.children[1];
assert.equal(select.hidden,true);assert.equal(summary.attrs['aria-label'],'Model');
assert.equal(menu.attrs.role,'listbox');assert.equal(menu.children[0].attrs['aria-selected'],'true');
function key(node,key){node.dispatchEvent(new Event('keydown',{key,bubbles:true}));}
summary.focus();key(summary,'ArrowDown');assert.equal(dropdown.open,true);assert.equal(document.activeElement,menu.children[0]);
assert.equal(dropdown.dataset.menuSide,'up','Menus near the bottom must open above the control');
key(document.activeElement,'ArrowDown');assert.equal(document.activeElement,menu.children[2],'Disabled options must be skipped');
key(document.activeElement,'Enter');assert.equal(select.value,'gpt');assert.equal(changes,1);assert.equal(inputs,1);assert.equal(dropdown.open,false);assert.equal(document.activeElement,summary);
menu.children[1].click();assert.equal(select.value,'gpt');assert.equal(changes,1);
// A provider refresh must update labels and disabled choices without resetting keyboard focus.
key(summary,'Enter');assert.equal(document.activeElement,menu.children[2]);
options([['auto','Automatic'],['gpt','GPT renamed'],['new','New model']]);observers[0]();
assert.equal(document.activeElement.dataset.val,'gpt');assert.equal(summary.children[0].textContent,'GPT renamed');
assert.equal(menu.children[2].textContent,'New model');assert.equal(changes,1);
key(document.activeElement,'n');assert.equal(document.activeElement.dataset.val,'new');
key(document.activeElement,'Escape');assert.equal(dropdown.open,false);assert.equal(select.value,'gpt');
// Select values changed by existing page code stay reflected in the visible control.
select.value='new';select.dispatchEvent(new Event('change'));assert.equal(summary.children[0].textContent,'New model');
select.disabled=true;observers[0]();key(summary,'Enter');assert.equal(dropdown.open,false);assert.equal(summary.tabIndex,-1);
select.disabled=false;observers[0]();key(summary,'Enter');
document.events.click.forEach(fn=>fn({target:new Element('span')}));assert.equal(dropdown.open,false);
assert.equal(root.children.length,3);ctx.mcFDFromSelect(select,new Element('svg'));assert.equal(root.children.length,3);
// A wide option list stays inside either viewport edge.
summary.rect={top:700,bottom:732,left:760,width:200};menu.rect={width:480};
summary.focus();key(summary,'Enter');assert.equal(menu.style.left,'-248px');key(summary,'Escape');
summary.rect.left=-20;summary.focus();key(summary,'Enter');assert.equal(menu.style.left,'28px');
console.log('ok');
