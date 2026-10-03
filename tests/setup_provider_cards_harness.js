// Real refresh logic: authentication, installation and enabled state are independent.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const elements={},cards=[];
function element(){return {textContent:'',innerHTML:'',hidden:true,dataset:{},classes:new Set(),
  classList:{toggle(name,on){if(on)this.owner.classes.add(name);else this.owner.classes.delete(name);},
    remove(name){this.owner.classes.delete(name);}},removeAttribute(){}};}
for(const p of ['claude','codex','gemini']){
  cards.push({dataset:{connection:p}});
  for(const id of ['status','installed','plan','subscription','feedback','connect','disconnect','install','guide','open','url','url-wrap','cancel']){
    const e=element();e.classList.owner=e;elements['provider-'+p+'-'+id]=e;
  }
  elements['provider-'+p+'-status'].dataset.authPill='true';
  elements['provider-'+p+'-plan'].dataset.planPrefix=p==='codex'?'ChatGPT':p==='claude'?'Claude':'Gemini';
  elements['provider-'+p+'-connect'].querySelector=()=>({dataset:{defaultLabel:'Sign in'}});
}
let states={},fail=false;
const context={document:{getElementById:id=>elements[id],querySelectorAll:sel=>sel==='[data-connection]'?cards:[],addEventListener(){}},
  AbortController,setTimeout(){},clearTimeout(){},setInterval(){},CustomEvent:class {},MC_SU:{icons:{ok:'<svg data-check></svg>'}},
  fetch:async()=>{if(fail)throw Error('Unavailable');return {ok:true,json:async()=>({providers:states,models:[]})};},
  dispatchEvent(){},addEventListener(){}};
context.window=context;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),context);
async function refresh(p,state){states={[p]:{installed:true,version:'1',enabled:true,ok:true,...state}};
  await context.mcRefreshProviders();return elements['provider-'+p+'-status'];}
(async()=>{
  for(const p of ['claude','codex','gemini']){
    const status=await refresh(p,{logged_in:true,connected:true});
    assert.match(status.innerHTML,/data-check.*signed-in/);
    assert.ok(status.classes.has('mc-provider-signed-in'));
    assert.equal(elements['provider-'+p+'-connect'].hidden,true);
    assert.equal(elements['provider-'+p+'-disconnect'].hidden,false);
    assert.match((await refresh(p,{logged_in:true,connected:false,enabled:false})).innerHTML,/signed-in/);
    assert.equal(Boolean(elements['provider-'+p+'-connect'].hidden),false);
    assert.match((await refresh(p,{logged_in:true,version_ok:false})).innerHTML,/signed-in/);
    assert.match((await refresh(p,{logged_in:false})).innerHTML,/not signed in/);
    assert.ok(!status.classes.has('mc-provider-signed-in'));
    assert.match((await refresh(p,{logged_in:false,ok:false})).innerHTML,/Check unavailable/);
    assert.match((await refresh(p,{installed:false})).innerHTML,/Not available/);
    assert.equal(elements['provider-'+p+'-install'].hidden,false);
    await refresh(p,{pending:true,login_url:'https://example.com/login'});
    assert.match(status.innerHTML,/Signing in/);
    assert.equal(elements['provider-'+p+'-cancel'].hidden,false);
    assert.equal(elements['provider-'+p+'-url-wrap'].hidden,false);
  }
  for(const [provider,plan,label] of [['codex','prolite','ChatGPT Pro'],['claude','max_20x','Claude Max 20×'],['gemini','free','Gemini Free']]){
    await refresh(provider,{logged_in:true,connected:true,plan});
    assert.equal(elements['provider-'+provider+'-plan'].textContent,label);
    assert.equal(elements['provider-'+provider+'-subscription'].hidden,false);
    await refresh(provider,{logged_in:true,connected:false,enabled:false,plan});
    assert.equal(elements['provider-'+provider+'-plan'].textContent,label);
    assert.equal(elements['provider-'+provider+'-subscription'].hidden,false);
    await refresh(provider,{logged_in:false,plan});
    assert.equal(elements['provider-'+provider+'-subscription'].hidden,true);
    assert.equal(elements['provider-'+provider+'-plan'].textContent,'');
  }
  for(const plan of [undefined,'unknown','<script>','constructor']){
    await refresh('gemini',{logged_in:true,connected:true,plan});
    assert.equal(elements['provider-gemini-plan'].textContent,'Not reported by CLI');
    assert.equal(elements['provider-gemini-subscription'].hidden,false);
  }
  await refresh('codex',{logged_in:true,connected:true,plan:'plus'});
  fail=true;await context.mcRefreshProviders();
  assert.equal(elements['provider-codex-status'].textContent,'Check unavailable');
  assert.ok(!elements['provider-codex-status'].classes.has('mc-provider-signed-in'));
  assert.equal(elements['provider-codex-subscription'].hidden,true);
  assert.equal(elements['provider-codex-plan'].textContent,'');
})().catch(e=>{console.error(e);process.exitCode=1;});
