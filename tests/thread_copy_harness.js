const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/chat.js'),'utf8');
const copy=source.slice(source.indexOf('async function mcCopyText('),source.indexOf('function mcCopyTurn('));
let copied,finish,denied=false,fallback=false,removed=0,restored=0;
const note={textContent:''},active={focus:()=>restored++};
const context={MC_ACT:{check:'CHECK'},setTimeout:fn=>{finish=fn;},navigator:{clipboard:{writeText:async text=>{if(denied)throw Error('denied');copied=text;}}},
 document:{activeElement:active,getElementById:()=>note,body:{appendChild:()=>{}},execCommand:()=>fallback,
 createElement:()=>({style:{},select:()=>{},remove:()=>removed++})},
 window:{getSelection:()=>null}};
vm.createContext(context);vm.runInContext(copy,context);
const button=()=>({disabled:false,innerHTML:'COPY',title:'Copy code',setAttribute:()=>{}});
(async()=>{
 const text='  line one & <tags>\n\t"line two" — τέλος\n';const b=button();
 await context.mcCopyText(text,b);assert.equal(copied,text);assert.equal(b.innerHTML,'CHECK');finish();assert.equal(b.innerHTML,'COPY');assert(!b.disabled);
 denied=true;const failed=button();await context.mcCopyText(text,failed);
 assert.equal(failed.innerHTML,'COPY','A rejected clipboard must never display success');assert(!failed.disabled);assert.match(note.textContent,/Could not copy/);assert.equal(removed,1);assert.equal(restored,1);
 fallback=true;const legacy=button();await context.mcCopyText(text,legacy);assert.equal(legacy.innerHTML,'CHECK');finish();assert(!legacy.disabled);
 console.log('Exact copy contents, rejected permissions, fallback, focus and honest status passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
