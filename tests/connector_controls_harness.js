const fs=require('fs'),vm=require('vm'),assert=require('assert');
function node(){return {dataset:{},style:{},textContent:'',innerHTML:'',disabled:false,hidden:true,
  setAttribute(){},removeAttribute(k){delete this[k];},focus(){},select(){},remove(){}};}
const details=['claude','codex','gemini'].map(provider=>{
  const d=node();d.dataset={cap:'drive',provider};
  d.parts=Object.fromEntries(['state','reason','action','recheck','login','instructions','snippet','copy','copy-status','web','guide','service-guide']
    .map(k=>['.mc-conn-'+k,node()]));
  const panel=node();panel.querySelector=s=>d.parts[s];d.parts['.mc-conn-setup']=panel;
  d.querySelector=s=>d.parts[s];
  Object.values(d.parts).forEach(n=>n.closest=s=>s==='.mc-conn-setup'?panel:d);
  return d;
});
const badges=details.map(d=>{const b=node();b.dataset={...d.dataset};b.mark=node();
  b.mark.innerHTML='<svg class="loader"></svg>';b.querySelector=()=>b.mark;return b;});
let calls=[],nextFetch,clipboard='',fallback=false,selected;
const context={document:{getElementById(){return null;},querySelectorAll(s){
  if(s==='.mc-conn-detail')return details;
  if(s==='.mc-conn-badge')return badges;
  if(s.includes('badge[data-state'))return badges.filter(b=>b.dataset.state==='checking');
  return [];
},activeElement:node(),createElement(){const n=node();n.select=()=>{selected=n.value;};return n;},
  body:{appendChild(){}},execCommand(){if(fallback)clipboard=selected;return fallback;}},
  window:{getSelection(){return null;}},URL,URLSearchParams,AbortSignal:{timeout(){}},Date,setTimeout,location:{},
  navigator:{clipboard:{async writeText(t){clipboard=t;}}},fetch:async(url,options)=>{
    calls.push({url,options,body:options.body&&JSON.parse(options.body)});return nextFetch(url,options);
  }};
vm.createContext(context);vm.runInContext(fs.readFileSync(process.argv[2],'utf8'),context);
const reply=data=>({ok:true,json:async()=>data});
const state=(provider,s,action='')=>context.mcCapConnectionState('drive',provider,s,true,'',{action,reason:provider+' reason'});
const snapshot=(provider,s,detail)=>reply({providers:{[provider]:'ready'},connectors:{drive:{[provider]:s,
  codex_supported:true,details:{[provider]:detail}}},pending:false});
(async()=>{
  state('claude','ready');state('codex','missing','connect');state('gemini','configured','setup');
  assert.equal(details[0].parts['.mc-conn-action'].style.display,'none');
  assert.equal(details[1].parts['.mc-conn-action'].textContent,'Connect');
  assert.equal(details[2].parts['.mc-conn-action'].textContent,'Set up');
  assert.equal(details[2].parts['.mc-conn-state'].textContent,'Registered · unverified');
  nextFetch=url=>url.includes('connector-action')?reply({ok:true,state:'sign_in'}):
    snapshot('codex','failed',{action:'connect',reason:'Dynamic registration not supported'});
  await details[1].parts['.mc-conn-action'].onclick();
  assert.deepEqual(calls.find(c=>c.body).body,{capability:'drive',provider:'codex',action:'connect'});
  assert.equal(details[1].parts['.mc-conn-action'].disabled,false);
  assert.equal(details[1].parts['.mc-conn-reason'].textContent,'Dynamic registration not supported');
  assert.equal(details[1].parts['.mc-conn-login'].hidden,true);
  context.mcCapConnectionState('drive','codex','sign_in',true,'',{action:'connect',reason:'Sign in',
    login_url:'https://accounts.example.invalid/?response_type=code&client_id=test'});
  assert.equal(details[1].parts['.mc-conn-login'].hidden,false);
  context.mcCapConnectionState('drive','codex','failed',true,'',{action:'connect',login_url:'javascript:alert(1)'});
  assert.equal(details[1].parts['.mc-conn-login'].hidden,true);
  assert.equal(details[1].parts['.mc-conn-login'].href,undefined);
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
  assert.equal(details[2].parts['.mc-conn-copy-status'].textContent,'Configuration copied.');
  context.navigator.clipboard.writeText=async()=>{throw Error('WebView clipboard denied');};
  fallback=true;clipboard='old';
  await context.mcConnectorCopy(details[2].parts['.mc-conn-copy']);
  assert.equal(clipboard,'<script>not HTML</script>');
  fallback=false;
  await context.mcConnectorCopy(details[2].parts['.mc-conn-copy']);
  assert(details[2].parts['.mc-conn-copy-status'].textContent.includes('copy it manually'));
  assert.equal(details[2].parts['.mc-conn-instructions'].textContent,'Use your own sign-in');
  details[2].parts['.mc-conn-snippet'].textContent='';clipboard='keep';
  await context.mcConnectorCopy(details[2].parts['.mc-conn-copy']);
  assert.equal(clipboard,'keep');
  assert.equal(details[2].parts['.mc-conn-copy'].disabled,false);
  state('claude','failed','connect');
  nextFetch=url=>url.includes('connector-action')?reply({ok:true,state:'sign_in'}):
    snapshot('claude','sign_in',{action:'connect',reason:'Sign-in required'});
  await details[0].parts['.mc-conn-action'].onclick();
  assert.equal(calls.filter(c=>c.body).at(-1).body.provider,'claude');
  assert.equal(details[0].parts['.mc-conn-reason'].textContent,'Sign-in required');
  nextFetch=()=>({ok:false,json:async()=>({ok:false,state:'setup_required',error:'Configure your own OAuth client'})});
  await context.mcProviderConnect(details[1].parts['.mc-conn-action']);
  assert.equal(details[1].parts['.mc-conn-state'].textContent,'Setup required');
  assert.equal(details[1].parts['.mc-conn-action'].textContent,'Set up');
  // A late full-page response must not overwrite a newer provider-specific check.
  const waiting=[];nextFetch=()=>new Promise(r=>waiting.push(r));
  const old=context.mcCapConnectionsRefresh();const fresh=context.mcCapConnectionsRefresh(true,'codex');
  waiting[1](reply({providers:{claude:'ready',codex:'ready',gemini:'ready'},connectors:{drive:{codex:'ready'}}}));
  await fresh;
  waiting[0](reply({providers:{claude:'ready',codex:'ready',gemini:'ready'},connectors:{drive:{claude:'ready',codex:'failed',gemini:'configured'}}}));
  await old;assert.equal(badges[1].dataset.state,'ready');
  console.log('Provider-specific actions, rechecks, races, errors and setup copy passed.');
})().catch(e=>{console.error(e);process.exit(1);});
