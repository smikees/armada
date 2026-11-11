const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const listeners={};
const context={document:{addEventListener:(name,fn)=>(listeners[name]??=[]).push(fn)},Event:class{constructor(type,props){this.type=type;Object.assign(this,props);}}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('armada/webui/static/js/form.js','utf8'),context);
function field(value,id='mc-msg'){
  return {value,id,tagName:'TEXTAREA',dataset:{},selectionStart:value.length,selectionEnd:value.length,inputs:0,
    setRangeText(text,start,end){this.value=this.value.slice(0,start)+text+this.value.slice(end);this.selectionStart=this.selectionEnd=start+text.length;},
    dispatchEvent(e){this.inputs++;for(const f of listeners[e.type]||[])f({...e,target:this});}};
}
function key(t,key,shiftKey=false){const e={target:t,key,shiftKey,preventDefault(){this.defaultPrevented=true;}};for(const f of listeners.keydown)f(e);return e.defaultPrevented;}
const t=field('- ');t.dispatchEvent({type:'input'});assert.equal(t.value,'• ');
t.value+='first';t.selectionStart=t.selectionEnd=t.value.length;
assert.equal(key(t,'Enter',true),true);assert.equal(t.value,'• first\n• ');
assert.equal(key(t,'Tab'),true);assert.equal(t.value,'• first\n  • ');
t.value+='nested';t.selectionStart=t.selectionEnd=t.value.length;
key(t,'Enter',true);assert.equal(t.value,'• first\n  • nested\n  • ');
key(t,'Enter',true);assert.equal(t.value,'• first\n  • nested\n• ');
key(t,'Enter',true);assert.equal(t.value,'• first\n  • nested\n');
assert.equal(key(t,'Tab'),undefined,'Tab outside a list navigates focus');
const plain=field('• send');assert.equal(key(plain,'Enter'),undefined,'Enter still sends in chat');
const ordinary=field('• continue','form');key(ordinary,'Enter');assert.equal(ordinary.value,'• continue\n• ');
assert.equal(key(ordinary,'Enter',true),undefined,'Shift+Enter outside chat keeps its ordinary line break');
const indent=field('  - ');indent.dispatchEvent({type:'input'});assert.equal(indent.value,'  • ');key(indent,'Tab',true);assert.equal(indent.value,'• ');
assert.ok(t.inputs>4,'programmatic changes notify draft and layout observers');
console.log('Bullet continuation, nesting, exit, send and input events passed.');
