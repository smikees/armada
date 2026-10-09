const fs=require('fs'),vm=require('vm'),assert=require('assert');
function node(){return {dataset:{},style:{},textContent:'',innerHTML:'',disabled:false,hidden:true,setAttribute(){}};}
const details=['claude','codex','gemini'].map(provider=>{
  const d=node();d.dataset={cap:'drive',provider};
  d.parts=Object.fromEntries(['state','reason','action','recheck','instructions','snippet','copy','web','guide','service-guide']
    .map(k=>['.mc-conn-'+k,node()]));
  const panel=node();panel.querySelector=s=>d.parts[s];d.parts['.mc-conn-setup']=panel;
  d.querySelector=s=>d.parts[s];
  Object.values(d.parts).forEach(n=>n.closest=s=>s==='.mc-conn-setup'?panel:d);
  return d;
});
const badges=details.map(d=>{const b=node();b.dataset={...d.dataset};b.mark=node();
  b.mark.innerHTML='<svg class="loader"></svg>';b.querySelector=()=>b.mark;return b;});
let calls=[],nextFetch,clipboard='';
const context={document:{getElementById(){return null;},querySelectorAll(s){
  if(s==='.mc-conn-detail')return details;
  if(s==='.mc-conn-badge')return badges;
  if(s.includes('badge[data-state'))return badges.filter(b=>b.dataset.state==='checking');
  return [];
}},URLSearchParams,AbortSignal:{timeout(){}},Date,setTimeout,location:{},
  navigator:{clipboard:{async writeText(t){clipboard=t;}}},fetch:async(url,options)=>{
    calls.push({url,options,body:options.body&&JSON.parse(options.body)});return nextFetch(url,options);
  }};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
const reply=data=>({ok:true,json:async()=>data});
const state=(provider,s,action='')=>context.mcCapConnectionState('drive',provider,s,true,'',{action,reason:provider+' reason'});
(async()=>{
  state('claude','ready');state('codex','missing','connect');state('gemini','configured','setup');
  assert.equal(details[0].parts['.mc-conn-action'].style.display,'none');
  assert.equal(details[1].parts['.mc-conn-action'].textContent,'Connect');
  assert.equal(details[2].parts['.mc-conn-action'].textContent,'Set up');
  assert.equal(details[2].parts['.mc-conn-state'].textContent,'Registered · unverified');
  nextFetch=()=>reply({ok:true,state:'sign_in'});
  await details[1].parts['.mc-conn-action'].onclick();
  assert.deepEqual(calls.at(-1).body,{capability:'drive',provider:'codex',action:'connect'});
  assert.equal(details[1].parts['.mc-conn-action'].disabled,false);
  assert(details[1].parts['.mc-conn-reason'].textContent.includes('browser'));
  let resolve;nextFetch=()=>new Promise(r=>resolve=r);
  const pending=context.mcProviderRecheck(details[1].parts['.mc-conn-recheck']);
  assert.equal(badges[0].dataset.state,'ready');assert.equal(badges[1].dataset.state,'checking');
  assert(calls.at(-1).url.includes('provider=codex'));
  resolve(reply({providers:{claude:'ready',codex:'ready',gemini:'ready'},connectors:{drive:{
    claude:'failed',codex:'ready',gemini:'missing'}},pending:false}));await pending;
  assert.equal(badges[0].dataset.state,'ready');assert.equal(badges[2].dataset.state,'configured');
  assert.equal(badges[1].dataset.state,'ready');
  nextFetch=()=>{throw Error('offline');};
  await context.mcProviderRecheck(details[1].parts['.mc-conn-recheck']);
  assert.equal(badges[1].dataset.state,'unknown');assert.equal(badges[0].dataset.state,'ready');
  assert.equal(details[1].parts['.mc-conn-recheck'].disabled,false);
  assert.equal(details[1].parts['.mc-conn-reason'].textContent,'offline');
  nextFetch=()=>reply({ok:true,instructions:'Use your own sign-in',snippet:'<script>not HTML</script>',
    guide_url:'https://antigravity.google/docs/mcp'});
  await details[2].parts['.mc-conn-action'].onclick();
  assert.deepEqual(calls.at(-1).body,{capability:'drive',provider:'gemini',action:'setup'});
  assert.equal(details[2].parts['.mc-conn-snippet'].textContent,'<script>not HTML</script>');
  assert.equal(details[2].parts['.mc-conn-snippet'].innerHTML,'');
  await context.mcConnectorCopy(details[2].parts['.mc-conn-copy']);
  assert.equal(clipboard,'<script>not HTML</script>');
  state('claude','failed','connect');
  nextFetch=()=>reply({ok:true,state:'sign_in'});
  await details[0].parts['.mc-conn-action'].onclick();
  assert.equal(calls.at(-1).body.provider,'claude');
  // A late full-page response must not overwrite a newer provider-specific check.
  const waiting=[];nextFetch=()=>new Promise(r=>waiting.push(r));
  const old=context.mcCapConnectionsRefresh();const fresh=context.mcCapConnectionsRefresh(true,'codex');
  waiting[1](reply({providers:{claude:'ready',codex:'ready',gemini:'ready'},connectors:{drive:{codex:'ready'}}}));
  await fresh;
  waiting[0](reply({providers:{claude:'ready',codex:'ready',gemini:'ready'},connectors:{drive:{claude:'ready',codex:'failed',gemini:'configured'}}}));
  await old;assert.equal(badges[1].dataset.state,'ready');
  console.log('Provider-specific actions, rechecks, races, errors and setup copy passed.');
})().catch(e=>{console.error(e);process.exit(1);});
