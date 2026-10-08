const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const output={open:false},calls=[];
let toggle;
const job={open:false,dataset:{},querySelector:s=>s==='.mc-job-output-pane'?output:null,
  addEventListener:(name,fn)=>{if(name==='toggle')toggle=fn;}};
const context={URLSearchParams,location:{search:''},document:{querySelectorAll:()=>[job],addEventListener:()=>{}},setInterval:()=>{},
  clearInterval:()=>{},setTimeout:()=>{},clearTimeout:()=>{}};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
context.mcLoadJobOutput=d=>calls.push(d);
job.open=true;
// Opening a nested section must not trigger a second outer-job load.
toggle({target:output});assert.equal(calls.length,0);
toggle({target:job});assert.deepEqual(calls,[job]);
const row={closest:selector=>{assert.equal(selector,'details.mc-job');return job;}};
context.mcSelectJobRun(row,'run-123');
assert.equal(output.open,true);assert.equal(job.dataset.run,'run-123');
assert.equal(job._resetOutputScroll,true);assert.deepEqual(calls,[job,job]);
// A calendar entry opens its exact final attempt, retaining the normal history selector.
job.open=false;job.dataset={jid:'work'};output.open=false;
context.location.search='?job=work&run=final-attempt';
const deepLink={...context};delete deepLink.mcLoadJobOutput;
vm.createContext(deepLink);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),deepLink);
assert.equal(job.dataset.run,'final-attempt');assert.equal(output.open,true);
