// Run the actual browser scripts with a small DOM fixture, without touching the user's app.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const html=fs.readFileSync(0,'utf8');
const script=name=>fs.readFileSync(path.join(__dirname,'../armada/webui/static/js',name+'.js'),'utf8');
function element(value=''){
  const classes=new Set();
  return {value,style:{},dataset:{},textContent:'',innerHTML:'',
    classList:{toggle:(name,on)=>on?classes.add(name):classes.delete(name),contains:name=>classes.has(name)},
    previousElementSibling:{tagName:'LABEL',querySelector:()=>null},addEventListener:()=>{},
    setAttribute:()=>{}};
}
function base(){
  const events={}, mediaEvents=[];
  const elements={};
  const media={matches:false,addEventListener:(type,fn)=>mediaEvents.push(fn)};
  const document={body:element(),documentElement:element(),
    getElementById:id=>elements[id]||null,querySelector:()=>null,querySelectorAll:()=>[],
    addEventListener:(type,fn)=>(events[type]??=[]).push(fn)};
  const ctx={document,URLSearchParams,localStorage:{getItem:()=>null,setItem:()=>{}},
    sessionStorage:{getItem:()=>null,setItem:()=>{}},
    location:{search:'',hash:'',reload:()=>{ctx.reloads++;}},reloads:0,
    matchMedia:()=>media,addEventListener:()=>{},setTimeout:fn=>fn()};
  ctx.window=ctx;ctx.parent=ctx;vm.createContext(ctx);
  return {ctx,document,elements,events,media,mediaEvents};
}
async function run(){
  if(process.argv[2]==='newrealm'){
    const {ctx,document,elements}=base();
    for(const id of ['r-name','r-path','r-msg','r-mode','r-agents-intro','r-agents','wiz-1','wiz-2'])elements[id]=element();
    elements['r-name'].value='Test realm';elements['r-path'].value='D:\\Work\\Test realm';
    elements['r-mode'].value='create';elements['wiz-2'].style.display='none';
    for(const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g))vm.runInContext(match[1],ctx);
    // This helper must be present inside the iframe, not merely on its parent page.
    assert.equal(typeof ctx.mcIcon,'function');
    vm.runInContext(script('form'),ctx);
    vm.runInContext(script('newrealm_wizard'),ctx);
    for(const template of ['state','company','crew','scratch']){
      document.querySelectorAll=selector=>[];
      const card=element();card.dataset.tpl=template;ctx.mcPickTpl(card);
      ctx.mcNext();
      assert.equal(elements['wiz-1'].style.display,'none');
      assert.equal(elements['wiz-2'].style.display,'block');
      if(template!=='scratch')assert.match(elements['r-agents'].innerHTML,/<svg.*Coordinator agent|Coordinator agent.*<svg/s);
      else assert.match(elements['r-agents'].innerHTML,/Blank template/);
      ctx.mcBack();assert.equal(elements['wiz-1'].style.display,'block');
    }
  }else{
    const {ctx,document,elements,media,mediaEvents}=base();
    const choice=element('light'),theme=element();theme.dataset.themeId='armada';
    elements['st-approot']=element('D:\\Work');elements['app-msg']=element();
    document.querySelector=selector=>selector.includes('mc-mode')?choice:selector.includes('mc-themecard')?theme:null;
    const calls=[];
    ctx.fetch=async(url,init)=>{calls.push({url,body:JSON.parse(init.body)});return {json:async()=>({ok:true})};};
    vm.runInContext(script('settings'),ctx);
    assert.match(html,/name="mc-mode"[^>]*onchange="mcPreviewMode\(this.value\)"/);
    choice.value='dark';ctx.mcPreviewMode(choice.value);
    assert(document.body.classList.contains('armada-dark'));
    assert(document.documentElement.classList.contains('armada-dark'));
    assert.equal(calls.length,0,'Preview must not save preferences');
    ctx.mcSettingsCancel();assert.equal(ctx.reloads,1);assert.equal(calls.length,0);
    // Settings must never change folder locations, even if stale page code supplies an input.
    elements['st-approot'].value='D:\\Changed';
    await ctx.mcSaveAppSettings();
    assert.deepEqual(calls,[{url:'/api/save-appearance',body:{mode:'dark'}}]);
    choice.value='system';media.matches=false;ctx.mcPreviewMode(choice.value);
    assert(!document.body.classList.contains('armada-dark'));
    media.matches=true;mediaEvents.forEach(fn=>fn());
    assert(document.body.classList.contains('armada-dark'));
    // A page booted in System mode must respect a manual preview when the OS changes.
    vm.runInContext(script('modeboot'),ctx);
    choice.value='light';ctx.mcPreviewMode(choice.value);mediaEvents.forEach(fn=>fn());
    assert(!document.body.classList.contains('armada-dark'));
    assert.equal(calls.length,1);
  }
  console.log('ok');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
