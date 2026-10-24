// One microphone session and normal thread; the mode controls spoken or text-only replies.
(function(){
  'use strict';
  const button=document.getElementById('mc-voice'),box=document.getElementById('mc-turns');
  if(!button||!box)return;
  const dictate=document.getElementById('mc-dictate'),input=document.getElementById('mc-msg');
  const panel=document.getElementById('mc-voice-panel'),status=document.getElementById('mc-voice-status');
  const title=document.getElementById('mc-voice-title'),help=document.getElementById('mc-voice-help');
  const mute=document.getElementById('mc-voice-mute'),end=document.getElementById('mc-voice-end');
  const play=document.getElementById('mc-voice-play'),modeSwitch=document.getElementById('mc-voice-mode');
  const audio=document.getElementById('mc-voice-audio');
  const inputState=document.getElementById('mc-voice-input'),meter=document.getElementById('mc-voice-meter');
  const inputLabel=document.getElementById('mc-voice-input-label'),connecting=document.getElementById('mc-voice-connecting');
  const destination={agent:box.dataset.agent,thread:box.dataset.thread};
  let call=null,remote=null,busy=false,ending=false,timer=null,generation=0;
  async function post(route,body,keepalive=false){
    const response=await fetch('/api/voice-'+route,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...destination,...body}),keepalive});
    const result=await response.json();
    if(!response.ok||!result.ok)throw new Error(result.error||'Audio could not connect. Try again.');
    return result;
  }
  function note(text,error=false){panel.hidden=false;status.textContent=text;panel.dataset.error=error?'1':'';}
  function loading(mode){return mode==='voice'?'Enabling voice mode, just a few seconds…':'Enabling dictation, just a few seconds…';}
  function paint(){
    const foreign=!!remote?.active&&!call,dict=(call||remote)?.mode==='dictation';
    button.disabled=dictate.disabled=ending||foreign||!!call?.switching||!!call&&!call.connected;
    button.setAttribute('aria-expanded',String(!!(call||foreign)&&!dict));dictate.setAttribute('aria-expanded',String(!!(call||foreign)&&dict));
    button.title=foreign?'Audio is active in another window':call?(dict?'Switch to voice chat':'End voice chat'):'Voice chat · speak and hear replies';
    dictate.title=call?(dict?'End dictation':'Switch to dictation · text replies'):'Dictate · speak and get text replies';
    button.dataset.active=call&&!dict?'1':'';dictate.dataset.active=call&&dict?'1':'';
    end.hidden=ending||!call&&!foreign;end.textContent='End';mute.hidden=foreign||!call;mute.disabled=!call?.connected;
    modeSwitch.hidden=!call;modeSwitch.disabled=!!call?.switching||!call?.connected;modeSwitch.textContent=dict?'Voice chat':'Dictation';
    modeSwitch.title=dict?'Keep speaking and hear replies aloud':'Keep speaking; replies will be text only';
    inputState.hidden=!call?.connected||ending;connecting.hidden=!call||call.connected||ending;panel.setAttribute('aria-busy',String(!connecting.hidden));
    if(call||foreign){title.textContent=dict?'Dictation · text replies':'Voice chat';help.textContent=dict?'Speech is sent to this thread · replies stay in text':'Same agent and tools · replies are spoken and saved';}
    if(foreign)note((busy?'Agent working · ':'')+(dict?'dictation':'voice chat')+' is active in another window');
    input.disabled=!!call||ending||busy;if(typeof mcSyncSend==='function')mcSyncSend();
  }
  function gate(owned,on){if(owned.outputGain)owned.outputGain.gain.value=on&&owned.mode==='voice'&&!owned.switching?1:0;}
  function showState(owned,state){
    if(owned.soundError){note(owned.soundError,true);return;}
    if(owned.muted){note('Microphone muted'+(owned.mode==='voice'?' · spoken replies are on':''));return;}
    const last=state?.partial_transcript?.at(-1);
    note(state?.playing&&owned.mode==='voice'?'Replying…':state?.thinking?'Agent working · you can keep speaking':last?.role==='user'?'Speech recognized · live in thread':owned.mode==='dictation'?'Listening · replies will be text only':'Listening · you can speak naturally');
  }
  async function receive(owned,state){
    if(call!==owned)return;owned.state=state;gate(owned,!!state?.playing);
    const transcript=JSON.stringify([state?.partial_transcript,state?.spoken_reply,state?.playing,state?.playback_done]);
    if(transcript!==owned.transcript){owned.transcript=transcript;window.mcThreadChanged?.();}
    if(owned.reply!==state?.playing){owned.reply=state?.playing;owned.heard=false;owned.lastSound=0;owned.replyStarted=Date.now();}
    if(owned.mode==='voice'&&state?.reply_ready&&!owned.switching){
      if(owned.audioContext.state!=='running'){owned.soundError='Sound is paused. Select Enable sound to hear replies.';play.hidden=false;}
      else{
        // Ready the output before sending text; avoid muted-autoplay/unmute races.
        gate(owned,true);const result=await post('state',{id:owned.id,play:state.reply_ready});if(call!==owned)return;
        owned.state=state=result.voice;owned.reply=state.playing;owned.heard=false;owned.lastSound=0;owned.replyStarted=Date.now();gate(owned,!!state.playing);
      }
    }
    if(owned.connected)showState(owned,state);
  }
  function release(owned){
    clearInterval(owned.meterTimer);owned.meterSource?.disconnect();owned.outputSource?.disconnect();owned.analyser?.disconnect();owned.outputAnalyser?.disconnect();owned.outputGain?.disconnect();owned.audioContext?.close().catch(()=>{});
    meter.style.setProperty('--mic-level','0');meter.setAttribute('aria-valuenow','0');owned.stream?.getTracks().forEach(track=>track.stop());owned.peer?.close();audio.pause();audio.srcObject=null;play.hidden=true;
  }
  function observeAudio(owned){
    const context=owned.audioContext,analyser=owned.analyser=context.createAnalyser();analyser.fftSize=256;
    const inputSamples=new Float32Array(256),outputSamples=new Float32Array(256);
    owned.meterSource=context.createMediaStreamSource(owned.stream);owned.meterSource.connect(analyser);
    const rms=(node,samples)=>{node.getFloatTimeDomainData(samples);return Math.sqrt(samples.reduce((sum,v)=>sum+v*v,0)/samples.length);};
    owned.meterTimer=setInterval(()=>{
      if(call!==owned)return;
      const level=owned.muted||!owned.connected||context.state!=='running'?0:rms(analyser,inputSamples),strength=Math.min(100,Math.round(level*500));
      meter.style.setProperty('--mic-level',String(strength/100));meter.setAttribute('aria-valuenow',String(strength));
      inputLabel.textContent=owned.muted?'Microphone muted':context.state!=='running'?'Microphone on · level unavailable':level>.015?'Sound detected':'Microphone on · quiet';
      if(!owned.reply||owned.mode!=='voice'||!owned.outputAnalyser)return;
      if(context.state!=='running'){
        owned.soundError='Sound is paused. Select Enable sound to hear replies.';play.hidden=false;note(owned.soundError,true);return;
      }
      const sound=context.state==='running'?rms(owned.outputAnalyser,outputSamples):0;
      if(sound>.001){
        if(!owned.heard)post('state',{id:owned.id,heard:owned.reply}).catch(()=>{});
        owned.heard=true;owned.lastSound=Date.now();
      }
      // Transcript completion is not proof buffered audio has finished playing.
      if(owned.heard&&owned.state?.playback_done&&Date.now()-owned.lastSound>1200){
        const identity=owned.reply;owned.reply=null;gate(owned,false);post('state',{id:owned.id,played:identity}).catch(()=>{});
      }else if(!owned.heard&&Date.now()-owned.replyStarted>12000&&!owned.soundError){
        owned.soundError='No reply audio received. Your answer is saved in the thread. Select Enable sound to retry.';play.hidden=false;note(owned.soundError,true);
      }
    },100);
  }
  async function finish(message='Audio ended · accepted work continues',error=false,keepalive=false){
    const owned=call,id=owned?.id||remote?.id,revision=++generation;call=null;remote=null;ending=true;clearTimeout(timer);
    if(owned)release(owned);note(message,error);paint();
    if(id){try{const result=await post('stop',{id,heard:owned?.heard?owned.reply:null},keepalive);if(result.voice?.active)remote=result.voice;}
      catch(e){if(!keepalive){remote={id,active:true,mode:owned?.mode};note('Microphone off. Could not confirm audio ended. Select End to retry.',true);}}}
    if(revision!==generation)return;ending=false;paint();window.mcThreadChanged?.();
  }
  async function poll(owned){
    if(call!==owned)return;
    try{const result=await post('state',{id:owned.id,heard:owned.heard?owned.reply:null});if(call!==owned)return;await receive(owned,result.voice);
      if(!result.voice.active){await finish(result.voice.error||'Audio session ended',!!result.voice.error);return;}}
    catch(e){if(call===owned)await finish(e.message,true);return;}
    timer=setTimeout(()=>poll(owned),250);
  }
  async function switchMode(mode){
    const owned=call;if(!owned||owned.switching)return;owned.switching=true;gate(owned,false);paint();
    try{
      if(mode==='voice')await owned.audioContext.resume();
      const result=await post('state',{id:owned.id,mode,heard:owned.heard?owned.reply:null});if(call!==owned)return;
      owned.mode=result.voice.mode;owned.soundError='';owned.reply=null;play.hidden=true;owned.switching=false;await receive(owned,result.voice);
    }catch(e){if(call===owned)note('Could not switch modes. Try again.',true);}
    finally{owned.switching=false;if(call===owned)paint();}
  }
  async function start(mode){
    if(call){if(call.mode!==mode)await switchMode(mode);else await finish();return;}if(remote?.active||ending)return;
    const Context=window.AudioContext||window.webkitAudioContext;
    if(!navigator.mediaDevices?.getUserMedia||typeof RTCPeerConnection!=='function'||!Context){note('Audio needs microphone access in the ARMADA app or a supported local browser.',true);return;}
    const revision=++generation,owned={id:crypto.randomUUID().replaceAll('-',''),mode,connected:false,muted:false};call=owned;
    mute.setAttribute('aria-pressed','false');mute.innerHTML=window.mcIcon('mic',16)+'<span>Mute</span>';note(loading(mode));paint();
    try{
      // Unlock playback in the actual click, before permission/signaling awaits.
      owned.audioContext=new Context();owned.audioContext.resume().catch(()=>{});owned.outputGain=owned.audioContext.createGain();owned.outputGain.gain.value=0;
      owned.outputAnalyser=owned.audioContext.createAnalyser();owned.outputAnalyser.fftSize=256;owned.outputGain.connect(owned.outputAnalyser);owned.outputAnalyser.connect(owned.audioContext.destination);
      let permission;try{permission=await navigator.permissions?.query({name:'microphone'});}catch(e){}
      if(revision!==generation)return;
      if(permission?.state==='prompt')note('Allow microphone access to start '+(mode==='voice'?'voice chat.':'dictation.'));
      const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});owned.stream=stream;
      if(revision!==generation){release(owned);return;}stream.getAudioTracks().forEach(track=>{track.enabled=false;track.onended=()=>{if(call===owned)finish('Microphone disconnected. Reconnect it and start again.',true);};});observeAudio(owned);note(loading(owned.mode));
      const peer=owned.peer=new RTCPeerConnection();stream.getTracks().forEach(track=>peer.addTrack(track,stream));peer.createDataChannel('oai-events');
      peer.ontrack=event=>{
        if(call!==owned)return;
        const incoming=event.streams[0]||new MediaStream([event.track]);
        // Chromium/WebView2 needs an active media sink to pull remote WebRTC audio.
        // Keep this sink permanently muted; only the unlocked gain-controlled graph is audible.
        audio.muted=true;audio.srcObject=incoming;audio.play().catch(()=>{owned.soundError='Sound is paused. Select Enable sound to hear replies.';play.hidden=false;});
        owned.outputSource?.disconnect();owned.outputSource=owned.audioContext.createMediaStreamSource(incoming);owned.outputSource.connect(owned.outputGain);
      };
      peer.onconnectionstatechange=()=>{
        if(call!==owned)return;
        if(peer.connectionState==='connected'){owned.connected=true;owned.stream.getAudioTracks().forEach(track=>{track.enabled=!owned.muted;});showState(owned,owned.state);paint();}
        else if(peer.connectionState==='failed'||peer.connectionState==='closed')finish('Audio disconnected. Start again to reconnect.',true);
      };
      await peer.setLocalDescription(await peer.createOffer());const result=await post('start',{id:owned.id,sdp:peer.localDescription.sdp,mode:owned.mode});
      if(revision!==generation){release(owned);await post('stop',{id:owned.id});return;}
      await peer.setRemoteDescription({type:'answer',sdp:result.sdp});poll(owned);window.mcThreadChanged?.();
    }catch(e){if(revision!==generation)return;const denied=e.name==='NotAllowedError'||e.name==='PermissionDeniedError';
      await finish(denied?'Microphone access was denied. Allow it in your browser or Windows privacy settings, then try again.':e.message||'Audio could not connect.',true);}
  }
  button.addEventListener('click',()=>start('voice'));dictate.addEventListener('click',()=>start('dictation'));
  modeSwitch.addEventListener('click',()=>switchMode(call?.mode==='voice'?'dictation':'voice'));end.addEventListener('click',()=>finish());
  mute.addEventListener('click',()=>{if(!call?.connected)return;call.muted=!call.muted;call.stream.getAudioTracks().forEach(track=>{track.enabled=!call.muted;});mute.setAttribute('aria-pressed',String(call.muted));mute.innerHTML=window.mcIcon(call.muted?'mic-off':'mic',16)+'<span>'+(call.muted?'Unmute':'Mute')+'</span>';showState(call,call.state);});
  play.addEventListener('click',async()=>{const owned=call;if(!owned)return;try{await Promise.all([owned.audioContext.resume(),audio.play()]);if(owned.audioContext.state!=='running')throw Error('Sound is blocked. Check the app or browser sound settings.');owned.soundError='';play.hidden=true;if(owned.reply)await post('state',{id:owned.id,retry:owned.reply});}catch(e){note(e.message,true);}});
  window.mcAudioBusy=()=>!!call||ending||!!remote?.active;
  window.mcVoiceSync=(value,working)=>{remote=value;busy=working;if(!call&&!ending&&!remote?.active&&!panel.dataset.error)panel.hidden=true;paint();};
  window.addEventListener('pagehide',()=>{if(call)finish('Audio session ended',false,true);});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&call){event.preventDefault();finish();}});
})();
