const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../armada/webui/static/js/thread_voice.js'),'utf8');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
function view(){
  const elements={},events={},timers=[],intervals=[],contexts=[];let clock=0;
  function element(id){return elements[id]||=({id,dataset:{},style:{setProperty(k,v){this[k]=v;}},hidden:false,disabled:false,value:'',textContent:'',
    addEventListener(n,f){this[n]=f;},setAttribute(n,v){this[n]=v;},pause(){},play(){return Promise.resolve();}});}
  element('mc-turns').dataset={agent:'ada',thread:'main'};
  const track={enabled:true,stopped:false,stop(){this.stopped=true;}},stream={getTracks:()=>[track],getAudioTracks:()=>[track]};
  const peers=[];class Peer{
    constructor(){peers.push(this);this.connectionState='new';}addTrack(){}createDataChannel(){}async createOffer(){return {type:'offer',sdp:'v=0'};}
    async setLocalDescription(v){this.localDescription=v;}async setRemoteDescription(){this.connectionState='connected';this.ontrack({streams:[stream]});this.onconnectionstatechange();}
    close(){this.connectionState='closed';this.onconnectionstatechange?.();}
  }
  class Context{
    constructor(){this.state='running';this.nodes=[];this.destination={};contexts.push(this);}
    node(extra={}){const n={connect(){},disconnect(){this.disconnected=true;},...extra};this.nodes.push(n);return n;}
    createGain(){return this.node({gain:{value:1}});}createAnalyser(){return this.node({sample:0,getFloatTimeDomainData(data){data.fill(this.sample);}});}
    createMediaStreamSource(){return this.node();}resume(){if(!this.blocked)this.state='running';return Promise.resolve();}close(){this.state='closed';return Promise.resolve();}
  }
  const ctx={document:{getElementById:element,addEventListener:(n,f)=>events[n]=f},navigator:{mediaDevices:{getUserMedia:async()=>{ctx.gums++;return stream;}},permissions:{query:async()=>({state:'granted'})}},
    crypto:{randomUUID:()=> '123456781234123412341234567890ab'},RTCPeerConnection:Peer,AudioContext:Context,Float32Array,Date:{now:()=>clock},
    mcIcon:()=>'',mcSyncSend(){},mcThreadChanged(){},addEventListener:(n,f)=>events[n]=f,
    setTimeout(fn){timers.push(fn);return timers.length;},clearTimeout(){},setInterval(fn){intervals.push(fn);return intervals.length;},clearInterval(id){intervals[id-1]=null;},
    state:{active:true,mode:'voice'},requests:[],gums:0,
    fetch:async(url,opts)=>{const body=JSON.parse(opts.body);ctx.requests.push({url,body});if(ctx.fail)throw Error('Connection failed');
      if(url.endsWith('start'))ctx.state.mode=body.mode;
      if(url.endsWith('stop'))ctx.state.active=false;
      if(body.mode)ctx.state.mode=body.mode;
      if(body.mode==='dictation'){ctx.state.playing=null;ctx.state.reply_ready=null;}
      if(body.play){ctx.state.playing=body.play;ctx.state.reply_ready=null;}
      if(body.played){ctx.state.playing=null;ctx.state.playback_done=false;}
      return {ok:true,json:async()=>({ok:true,sdp:'v=0',voice:{...ctx.state,id:body.id}})};}};
  ctx.window=ctx;vm.createContext(ctx);vm.runInContext(source,ctx);
  return {ctx,element,track,peers,events,contexts,async tick(){const next=timers.shift();if(next)await next();await settle();},meter(ms=100){clock+=ms;intervals.forEach(fn=>fn?.());},output(){return contexts[0].nodes[1];},gain(){return contexts[0].nodes[0].gain;}};
}
(async()=>{
  const a=view();a.element('mc-msg').value='Keep my draft';await a.element('mc-voice').click();await settle();
  assert.equal(a.gain().value,0,'native acknowledgements stay silent');assert(a.track.enabled);assert.equal(a.contexts.length,1);
  a.ctx.state.reply_ready='reply';await a.tick();assert.equal(a.gain().value,1);
  a.output().sample=.1;a.meter();a.ctx.state.playback_done=true;await a.tick();a.meter(3000);
  assert.equal(a.gain().value,1,'transcript completion must not cut off real audio');
  a.contexts[0].state='suspended';a.output().sample=0;a.meter(3000);
  assert(!a.ctx.requests.some(r=>r.body.played),'a suspended context is not finished audio');
  a.contexts[0].state='running';
  a.output().sample=0;a.meter(1300);await settle();assert.equal(a.gain().value,0);assert(a.ctx.requests.some(r=>r.body.played==='reply'));
  await a.element('mc-dictate').click();assert(a.track.enabled&&!a.track.stopped);assert.equal(a.gain().value,0);assert.match(a.element('mc-voice-title').textContent,/text replies/);
  await a.element('mc-voice').click();assert(a.track.enabled);assert.equal(a.ctx.gums,1);assert.equal(a.peers.length,1);assert.equal(a.contexts.length,1);
  a.ctx.state.reply_ready='second';await a.tick();assert.equal(a.gain().value,1);await a.element('mc-dictate').click();assert.equal(a.gain().value,0,'switch silences in-flight audio');
  a.element('mc-voice-mute').click();assert(!a.track.enabled);await a.element('mc-voice').click();assert(!a.track.enabled,'mode change preserves mute');
  a.element('mc-voice-mute').click();assert(a.track.enabled);a.ctx.mcVoiceSync(null,true);await a.element('mc-voice-end').click();
  assert(a.track.stopped);assert.equal(a.contexts[0].state,'closed');assert(a.element('mc-msg').disabled,'End does not clear real work');assert.equal(a.element('mc-msg').value,'Keep my draft');
  assert(a.ctx.requests.every(r=>!r.url.includes('chat-stop')));

  const b=view();let connect;b.ctx.fetch=async()=>new Promise(resolve=>connect=()=>resolve({ok:true,json:async()=>({ok:true,sdp:'v=0',voice:{active:true,mode:'voice'}})}));
  const starting=b.element('mc-voice').click();await settle();assert(!b.track.enabled);assert(!b.element('mc-voice-connecting').hidden);assert.match(b.element('mc-voice-status').textContent,/Enabling voice mode, just a few seconds/);
  connect();await starting;assert(b.track.enabled&&b.element('mc-voice-connecting').hidden);

  const c=view();let allow;c.ctx.navigator.permissions.query=async()=>({state:'prompt'});c.ctx.navigator.mediaDevices.getUserMedia=()=>new Promise(resolve=>allow=resolve);
  const pending=c.element('mc-dictate').click();await settle();assert.match(c.element('mc-voice-status').textContent,/Allow microphone access/);
  await c.element('mc-voice-end').click();allow({getTracks:()=>[c.track]});await pending;assert(c.track.stopped);assert(!c.peers.length);

  const blocked=view();await blocked.element('mc-voice').click();await settle();blocked.contexts[0].state='suspended';blocked.ctx.state.reply_ready='blocked';await blocked.tick();
  assert.equal(blocked.gain().value,0);assert(!blocked.element('mc-voice-play').hidden);assert(!blocked.ctx.requests.some(r=>r.body.play));
  await blocked.element('mc-voice-play').click();await blocked.tick();assert.equal(blocked.gain().value,1);
  blocked.meter(13000);assert.match(blocked.element('mc-voice-status').textContent,/No reply audio received/);
  await blocked.element('mc-voice-play').click();assert(blocked.ctx.requests.some(r=>r.body.retry==='blocked'));

  const denied=view();denied.ctx.navigator.mediaDevices.getUserMedia=async()=>{const e=Error();e.name='NotAllowedError';throw e;};await denied.element('mc-voice').click();assert.match(denied.element('mc-voice-status').textContent,/denied/);assert.equal(denied.contexts[0].state,'closed');
  console.log('Voice/dictation: shared input, live switching, audio drain, sound recovery, permission and cancellation checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
