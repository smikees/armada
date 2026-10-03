const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const output={open:false},calls=[];
let toggle;
const job={open:false,dataset:{},querySelector:s=>s==='.mc-job-output-pane'?output:null,
  addEventListener:(name,fn)=>{if(name==='toggle')toggle=fn;}};
const context={document:{querySelectorAll:()=>[job],addEventListener:()=>{}},setInterval:()=>{},
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
