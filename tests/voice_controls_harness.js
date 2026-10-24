const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/thread_voice.js'),'utf8');
function view(){
  const elements={},events={},timers=[];let clock=0;
  function element(id){return elements[id]||=({id,dataset:{},style:{setProperty(k,v){this[k]=v;}},hidden:false,disabled:false,value:'',textContent:'',selectionStart:0,selectionEnd:0,
    addEventListener(type,fn){this[type]=fn;},setAttribute(name,value){this[name]=value;},dispatchEvent(){this.inputs=(this.inputs||0)+1;},
    setRangeText(text,start,end){this.value=this.value.slice(0,start)+text+this.value.slice(end);},focus(){},pause(){},play(){this.played=true;return Promise.resolve();}});}
  element('mc-turns').dataset={agent:'ada',thread:'main'};
  const track={enabled:true,stopped:false,stop(){this.stopped=true;}},stream={getTracks:()=>[track],getAudioTracks:()=>[track]};
  const peers=[];class Peer{
    constructor(){peers.push(this);this.connectionState='new';}
    addTrack(){}createDataChannel(){}async createOffer(){return {type:'offer',sdp:'v=0'};}
    async setLocalDescription(v){this.localDescription=v;}
    async setRemoteDescription(){this.connectionState='connected';this.ontrack({streams:[stream]});this.onconnectionstatechange();}
    close(){this.connectionState='closed';this.onconnectionstatechange?.();}
  }
  const ctx={document:{getElementById:element,addEventListener:(n,f)=>events[n]=f},navigator:{mediaDevices:{getUserMedia:async()=>stream}},
    crypto:{randomUUID:()=> '123456781234123412341234567890ab'},RTCPeerConnection:Peer,Event:class{},Date:{now:()=>clock},
    mcIcon:()=>'',mcSyncSend(){},mcThreadChanged(){},addEventListener:(n,f)=>events[n]=f,
    setTimeout(fn,ms){if(ms===250){clock+=250;Promise.resolve().then(fn);}else timers.push(fn);return timers.length;},clearTimeout(){},clearInterval(){},
    state:{active:true,draft:'spoken words',mode:'dictation'},requests:[],
    fetch:async(url,opts)=>{const body=JSON.parse(opts.body);ctx.requests.push({url,body});
      if(ctx.fail)throw Error('Connection failed');
      if(url.endsWith('stop')){ctx.state.active=false;if(body.discard)ctx.state.draft='';else if(ctx.tail)ctx.state.draft+=ctx.tail;}
      return {ok:true,json:async()=>({ok:true,sdp:'v=0',voice:{...ctx.state,id:body.id}})};}};
  ctx.window=ctx;vm.createContext(ctx);vm.runInContext(source,ctx);
  return {ctx,element,track,peers,events,async tick(){const next=timers.shift();if(next)await next();await settle();}};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  const a=view(),input=a.element('mc-msg');input.value='Before AFTER';input.selectionStart=7;input.selectionEnd=12;
  await a.element('mc-dictate').click();await settle();
  assert.equal(a.ctx.requests[0].body.mode,'dictation');assert(input.disabled);assert(a.ctx.mcAudioBusy());
  assert(!a.element('mc-voice-audio').played,'Dictate must never play response audio');
  assert.equal(input.value,'Before AFTER','live speech must not send or replace the draft');
  a.ctx.tail=' finalized tail';await a.element('mc-dictation-done').click();
  assert.equal(input.value,'Before spoken words finalized tail');assert(a.track.stopped);assert(!input.disabled);
  assert(a.peers.every(p=>p.connectionState==='closed'));assert.equal(input.inputs,1);
  assert(a.ctx.requests.every(r=>r.url.startsWith('/api/voice-')),'dictation must never invoke normal chat');

  const b=view();b.element('mc-msg').value='Keep this';await b.element('mc-dictate').click();await settle();
  await b.element('mc-voice-end').click();assert.equal(b.element('mc-msg').value,'Keep this');assert(b.track.stopped);
  assert.equal(b.ctx.requests.at(-1).body.discard,true);

  const c=view();await c.element('mc-dictate').click();await settle();c.ctx.state.active=false;c.ctx.state.draft='';
  await c.tick();assert.equal(c.element('mc-msg').value,'','remote Cancel must discard the unsent transcript');assert(c.track.stopped);

  const d=view();await d.element('mc-dictate').click();await settle();d.ctx.fail=true;await d.tick();
  assert.equal(d.element('mc-msg').value,'spoken words','recover received speech on connection loss');assert(d.track.stopped);

  const e=view();e.ctx.state.mode='voice';await e.element('mc-voice').click();await settle();
  assert(e.element('mc-voice-audio').played);e.element('mc-voice-mute').click();assert(!e.track.enabled);
  e.element('mc-voice-mute').click();assert(e.track.enabled);await e.element('mc-voice-end').click();assert(e.track.stopped);

  const connecting=view();let connect;
  connecting.ctx.fetch=async()=>new Promise(resolve=>connect=()=>resolve({ok:true,json:async()=>({ok:true,sdp:'v=0',voice:{active:true,mode:'voice'}})}));
  const starting=connecting.element('mc-voice').click();await settle();
  assert(!connecting.track.enabled,'microphone must not transmit before connected');
  assert(!connecting.element('mc-voice-connecting').hidden);
  assert.match(connecting.element('mc-voice-status').textContent,/Wait for Listening/);
  connect();await starting;await settle();
  assert(connecting.track.enabled&&connecting.element('mc-voice-connecting').hidden);

  const working=view();working.ctx.mcVoiceSync(null,true);working.ctx.state.mode='voice';
  assert(!working.element('mc-voice').disabled);
  await working.element('mc-voice').click();await settle();
  assert(working.track.enabled,'voice can open during normal work');
  await working.element('mc-voice-end').click();
  assert(working.element('mc-msg').disabled,'End call must not clear normal work state');
  assert(working.ctx.requests.every(r=>!r.url.includes('chat-stop')),'End call never cancels work');

  const speech=view();speech.ctx.state={active:true,mode:'voice'};
  await speech.element('mc-voice').click();await settle();
  assert(speech.element('mc-voice-audio').muted,'unsolicited frontend speech stays muted');
  speech.ctx.state.reply_ready='trusted-reply';speech.ctx.state.playing='trusted-reply';
  await speech.tick();await settle();
  assert(speech.ctx.requests.some(r=>r.body.play==='trusted-reply'));
  assert(!speech.element('mc-voice-audio').muted,'the saved agent reply is audible');
  speech.ctx.state.playing=null;speech.ctx.state.reply_ready=null;await speech.tick();
  assert(speech.element('mc-voice-audio').muted);

  const metered=view();let meterTick,closed=false,cleared=false,sample=128;
  metered.ctx.AudioContext=class {
    constructor(){this.state='running';}
    createAnalyser(){return {fftSize:256,getByteTimeDomainData(data){data.fill(sample);},disconnect(){}};}
    createMediaStreamSource(){return {connect(){},disconnect(){}};}
    resume(){return Promise.resolve();}close(){closed=true;return Promise.resolve();}
  };
  metered.ctx.setInterval=fn=>{meterTick=fn;return 9;};metered.ctx.clearInterval=id=>{if(id===9)cleared=true;};
  metered.ctx.state={active:true,mode:'voice',partial_transcript:[{role:'user',text:'Recognized question'}]};
  await metered.element('mc-voice').click();await settle();
  assert.equal(metered.element('mc-voice-meter')['aria-valuenow'],'0');
  assert.match(metered.element('mc-voice-status').textContent,/Speech recognized/);
  sample=144;meterTick();assert(Number(metered.element('mc-voice-meter')['aria-valuenow'])>0);
  assert.equal(metered.element('mc-voice-input-label').textContent,'Sound detected');
  metered.element('mc-voice-mute').click();meterTick();assert.equal(metered.element('mc-voice-meter')['aria-valuenow'],'0');
  await metered.element('mc-voice-end').click();assert(closed&&cleared,'ending must release the meter and AudioContext');

  const f=view();let allow;f.ctx.navigator.mediaDevices.getUserMedia=()=>new Promise(resolve=>allow=resolve);
  const pending=f.element('mc-dictate').click();await settle();await f.element('mc-voice-end').click();
  allow({getTracks:()=>[f.track]});await pending;assert(f.track.stopped);assert(!f.peers.length,'Cancel during permission must not launch a connection');
  console.log('dictation/voice controls: draft insertion, late final text, cancel, disconnect, mute and permission races passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
