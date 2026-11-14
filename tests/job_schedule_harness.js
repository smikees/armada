const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const elements=new Map();
function el(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,style:{},dataset:{},textContent:''});return elements.get(id);}
el('j-cron').dataset.cadence='mon-fri 17:45';
el('j-kind').value='agent';el('j-time').value='17:45';
const sent=[];
const context=vm.createContext({document:{getElementById:el,querySelectorAll:()=>[]},
  mcJobReadiness:()=>({}),mcConfirm:async()=>true,
  fetch:async(url,options)=>{const payload=JSON.parse(options.body);sent.push(payload);return {json:async()=>({
    ok:true,path:'brief.json',schedule_changed:'cron' in payload,
    schedule_before:'mon-fri 17:45',schedule_after:payload.cron||'manual'})};}});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/job.js'),'utf8'),context);
(async()=>{
  assert.match(el('j-next').textContent,/mon-fri 17:45/);
  el('j-critical').checked=true;
  await context.mcSaveJob('a','brief');
  assert.equal(sent[0].critical,true);assert.equal('cron' in sent[0],false);
  context.mcPreset('on demand');await context.mcSaveJob('a','brief');
  assert.equal(sent[1].cron,'');assert.match(el('j-savemsg').textContent,/Schedule changed: mon-fri 17:45 → manual/);
  await context.mcSaveJob('a','brief');assert.equal('cron' in sent[2],false);
  el('j-cron').value='0 9 * * 1-5';context.mcCronManual();
  await context.mcSaveJob('a','brief');assert.equal(sent[3].cron,'0 9 * * 1-5');
})().catch(error=>{console.error(error);process.exitCode=1;});
