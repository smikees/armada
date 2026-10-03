const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const data=fs.readFileSync(0,'utf8'),source=fs.readFileSync(process.argv[2],'utf8'),saved=new Map();
function page(){
  const elements={};let focused;
  function element(tag='div'){return {tag,children:[],value:'',textContent:'',hidden:false,events:{},
    append(...nodes){this.children.push(...nodes);},replaceChildren(){this.children=[];},
    querySelector(tag){return this.children.find(c=>c.tag===tag);},
    addEventListener(type,fn){this.events[type]=fn;},focus(){focused=this;}};}
  for(const id of ['doc-search','doc-search-results','doc-search-status','doc-search-x','doc-search-index'])elements[id]=element();
  elements['doc-search-index'].textContent=data;
  const ctx={document:{getElementById:id=>elements[id],createElement:tag=>element(tag)},
    sessionStorage:{getItem:key=>saved.get(key)||null,setItem:(key,value)=>saved.set(key,value)}};
  ctx.window=ctx;vm.runInNewContext(source,ctx);
  return {ctx,elements,focused:()=>focused};
}
let first=page();const input=first.elements['doc-search'],results=first.elements['doc-search-results'];
assert.equal(results.hidden,true);
input.value='ARMADA_JOB_RESULT';first.ctx.mcDocSearch();
assert(results.children.some(link=>link.href==='/docs/jobs'),'Full page content must be searchable');
assert(results.children.find(link=>link.href==='/docs/jobs').children[1].textContent.includes('ARMADA_JOB_RESULT'));
assert.equal(first.elements['doc-search-x'].hidden,false);
// A new section gets a new document, but keeps the same query and matching links.
const next=page();assert.equal(next.elements['doc-search'].value,'ARMADA_JOB_RESULT');
assert(next.elements['doc-search-results'].children.some(link=>link.href==='/docs/jobs'));
input.value='  DELIVERY   RECEIPTS ';first.ctx.mcDocSearch();assert(results.children.some(link=>link.href==='/docs/jobs'));
input.events.keydown({key:'ArrowDown',preventDefault(){}});assert.equal(first.focused(),results.children[0]);
input.value='OpenAI models';first.ctx.mcDocSearch();assert.equal(results.children[0].href,'/docs/codex','Title matches rank first');
input.value='<script>not-in-any-help-page</script>';first.ctx.mcDocSearch();
assert.equal(results.children.length,0);assert(first.elements['doc-search-status'].textContent.startsWith('No help pages match'));
input.events.keydown({key:'Escape',preventDefault(){}});assert.equal(input.value,'');assert.equal(results.hidden,true);assert.equal(first.focused(),input);
assert.equal(page().elements['doc-search'].value,'','Clearing search must also clear the saved query');
console.log('ok');
