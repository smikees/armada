// Behavioral contract: save the chip/label, never replace the card or navigate.
const vm=require('vm'),fs=require('fs'),path=require('path'),assert=require('assert');
let requests=[],alerts=[],respond,filters=0;
const tick=()=>new Promise(setImmediate);
const watchdog=setTimeout(()=>{console.error('Harness did not complete');process.exit(1);},3000);
const summary={outerHTML:'old summary'},grants={innerHTML:'old grants'};
const card={dataset:{agents:''},open:true,unrelatedControl:{value:'keep'},
  setAttribute(){},removeAttribute(){},appendChild(){},
  querySelector:s=>s==='.mc-cap-availability'?summary:grants,querySelectorAll:()=>[]};
const context={document:{createElement:()=>({setAttribute(){},remove(){}})},
  fetch:async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return {json:()=>new Promise(resolve=>respond=resolve)};},
  mcAlert:async(...args)=>alerts.push(args),mcCapFilter:()=>filters++,
  location:{reload(){throw Error('Must not reload');}},console};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/capdrag.js'),'utf8'),context);
(async()=>{
  let pending=context.mcCapAccess(card,'notes','reviewer',false);
  await tick();assert.equal(card.dataset.saving,'1');
  await context.mcCapAccess(card,'notes','reviewer',false);assert.equal(requests.length,1);
  respond({ok:true,availability:'new summary',grants:'Reviewer',agents:'reviewer'});await pending;
  assert.equal(summary.outerHTML,'new summary');assert.equal(grants.innerHTML,'Reviewer');
  assert.equal(card.dataset.agents,'reviewer');assert(card.open);assert.equal(card.unrelatedControl.value,'keep');
  assert.equal(card.dataset.saving,undefined);assert(requests[0].body.inline);assert.equal(filters,1);
  pending=context.mcCapAccess(card,'notes','reviewer',true);await tick();
  respond({ok:true,availability:'empty summary',grants:'',agents:''});await pending;
  assert.equal(requests[1].url,'/api/cap-revoke');assert.equal(grants.innerHTML,'');assert(card.open);
  pending=context.mcCapAccess(card,'notes','reviewer',false);await tick();
  respond({ok:false,error:'Cannot save'});await pending;
  assert.equal(grants.innerHTML,'');assert.equal(alerts[0][0],'Cannot save');assert.equal(card.dataset.saving,undefined);
  console.log('Access grant/revoke, duplicate admission, error recovery and UI preservation passed');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>clearTimeout(watchdog));
