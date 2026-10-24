// One microphone owner; native user transcripts become either drafts or conversation turns.
(function(){
  'use strict';
  const button=document.getElementById('mc-voice'),box=document.getElementById('mc-turns');
  if(!button||!box)return;
  const dictate=document.getElementById('mc-dictate'),input=document.getElementById('mc-msg');
  const panel=document.getElementById('mc-voice-panel'),status=document.getElementById('mc-voice-status');
  const title=document.getElementById('mc-voice-title'),help=document.getElementById('mc-voice-help');
  const draft=document.getElementById('mc-dictation-text'),done=document.getElementById('mc-dictation-done');
  const mute=document.getElementById('mc-voice-mute'),end=document.getElementById('mc-voice-end');
  const audio=document.getElementById('mc-voice-audio'),play=document.getElementById('mc-voice-play');
  const inputState=document.getElementById('mc-voice-input'),meter=document.getElementById('mc-voice-meter');
  const inputLabel=document.getElementById('mc-voice-input-label');
  const destination={agent:box.dataset.agent,thread:box.dataset.thread};
  let call=null,remote=null,busy=false,ending=false,timer=null,generation=0;

  async function post(route,body,keepalive=false){
    const response=await fetch('/api/voice-'+route,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...destination,...body}),keepalive});
    const result=await response.json();
    if(!response.ok||!result.ok)throw new Error(result.error||'Voice could not connect. Try again.');
    return result;
  }
  function note(text,error=false){panel.hidden=false;status.textContent=text;panel.dataset.error=error?'1':'';}
  function paint(){
    const foreign=!!remote?.active&&!call,dict=(call||remote)?.mode==='dictation';
    button.disabled=ending||foreign||!!call&&dict||busy&&!call;
    dictate.disabled=ending||foreign||!!call&&!dict||busy&&!call;
    button.setAttribute('aria-expanded',String(!!call&&!dict||foreign&&!dict));
    dictate.setAttribute('aria-expanded',String(!!call&&dict||foreign&&dict));
    button.title=foreign?'Audio is active in another window':call&&!dict?'End voice chat':'Voice chat · speak and hear replies';
    dictate.title=call&&dict?'Finish dictation':'Dictate · speech to draft text';
    button.dataset.active=call&&!dict?'1':'';dictate.dataset.active=call&&dict?'1':'';
    end.hidden=ending||!call&&!foreign;end.textContent=dict?'Cancel':'End call';
    mute.hidden=dict||foreign||!call;mute.disabled=!call?.connected;
    done.hidden=!call||!dict;done.disabled=!call?.connected||!!call?.finishing;
    inputState.hidden=!call?.connected||ending;
    if(call||foreign){
      title.textContent=dict?'Dictation':'Voice chat preview';
      help.textContent=dict?'Speech to draft text · via Codex · review before sending':'Conversation only · audio uses your Codex connection';
      const stop=document.getElementById('mc-stop');if(stop)stop.style.display='none';
    }
    if(foreign)note(dict?'Dictation is active in another window':'Voice chat is active in another window');
    input.disabled=!!call||ending||busy;
    if(typeof mcSyncSend==='function')mcSyncSend();
  }
  function receive(owned,state){
    if(owned.mode==='voice'){
      owned.thinking=!!state?.thinking;
      if(call===owned&&owned.connected&&!owned.muted){
        const last=state?.partial_transcript?.at(-1);
        note(owned.thinking?'Thinking · you can keep speaking':last?.role==='assistant'?'Replying…':
          last?.role==='user'?'Speech recognized · live in thread':'Listening · you can speak naturally');
      }
      return;
    }
    if(owned.mode!=='dictation'||typeof state?.draft!=='string')return;
    if(owned.text!==state.draft){owned.text=state.draft;owned.lastText=Date.now();}
    draft.textContent=owned.text;draft.hidden=!owned.text;
  }
  function insert(owned){
    if(!owned.text||owned.inserted)return false;
    owned.inserted=true;
    const before=input.value.slice(0,owned.selection[0]),after=input.value.slice(owned.selection[1]);
    const text=(before&&!/\s$/.test(before)?' ':'')+owned.text+(after&&!/^\s/.test(after)?' ':'');
    input.setRangeText(text,owned.selection[0],owned.selection[1],'end');
    input.dispatchEvent(new Event('input',{bubbles:true}));
    return true;
  }
  function release(owned){
    clearInterval(owned.meterTimer);owned.meterSource?.disconnect();owned.analyser?.disconnect();
    owned.audioContext?.close().catch(()=>{});
    meter.style.setProperty('--mic-level','0');meter.setAttribute('aria-valuenow','0');
    owned.stream?.getTracks().forEach(track=>track.stop());owned.peer?.close();
    audio.pause();audio.srcObject=null;play.hidden=true;
  }
  function observeMicrophone(owned){
    const Context=window.AudioContext||window.webkitAudioContext;
    if(!Context){inputLabel.textContent='Microphone on · level unavailable';return;}
    try{
      const context=owned.audioContext=new Context(),analyser=owned.analyser=context.createAnalyser();
      analyser.fftSize=256;const samples=new Uint8Array(analyser.fftSize);
      owned.meterSource=context.createMediaStreamSource(owned.stream);owned.meterSource.connect(analyser);
      context.resume().catch(()=>{});
      const update=()=>{
        if(call!==owned)return;
        const paused=owned.muted||owned.finishing;
        let level=0;
        if(!paused&&context.state==='running'){
          analyser.getByteTimeDomainData(samples);
          level=Math.sqrt(samples.reduce((sum,value)=>sum+((value-128)/128)**2,0)/samples.length);
        }
        const strength=Math.min(100,Math.round(level*500));
        meter.style.setProperty('--mic-level',String(strength/100));meter.setAttribute('aria-valuenow',String(strength));
        inputLabel.textContent=paused?'Microphone off':context.state!=='running'?'Microphone on · level unavailable':
          level>.015?'Sound detected':'Microphone on · quiet';
      };
      owned.meterTimer=setInterval(update,100);update();
    }catch(e){inputLabel.textContent='Microphone on · level unavailable';}
  }
  async function finish(message='Voice chat ended',error=false,keepalive=false,save=false){
    const owned=call,id=owned?.id||remote?.id,mode=(call||remote)?.mode;
    const revision=++generation;call=null;remote=null;ending=true;clearTimeout(timer);
    if(owned)release(owned);
    if(keepalive&&save&&owned?.mode==='dictation')insert(owned);
    note(message,error);paint();
    if(id){try{
      const result=await post('stop',{id,discard:mode==='dictation'&&!save},keepalive);
      if(owned)receive(owned,result.voice);
      if(result.voice?.active)remote=result.voice;
    }catch(e){if(!keepalive){remote={id,active:true,mode:owned?.mode};
      note('Microphone off. Could not confirm the session ended. Use the stop control to retry.',true);
    }}}
    if(revision!==generation)return;
    if(owned?.mode==='dictation'&&save){
      const added=insert(owned);
      if(!error&&!remote?.active)note(added?'Added to your draft. Review, then send.':'No speech was captured. Try Dictate again.');
    }
    draft.hidden=true;ending=false;busy=!!remote?.active;paint();
    window.mcThreadChanged?.();
    if(save&&!keepalive)input.focus();
  }
  async function poll(owned){
    if(call!==owned)return;
    try{
      const result=await post('state',{id:owned.id});
      if(call!==owned)return;
      receive(owned,result.voice);
      if(!result.voice.active){await finish(result.voice.error||'Audio session ended',!!result.voice.error,false,owned.mode==='dictation');return;}
    }catch(e){if(call===owned)await finish(e.message,true,false,owned.mode==='dictation');return;}
    timer=setTimeout(()=>poll(owned),750);
  }
  async function complete(){
    const owned=call;if(!owned||owned.mode!=='dictation'||owned.finishing)return;
    if(!owned.connected){await finish('Dictation cancelled');return;}
    owned.finishing=true;owned.stream.getAudioTracks().forEach(track=>{track.enabled=false;});
    note('Finishing transcription…');paint();
    const started=Date.now();
    // Keep the connection alive with silence while Codex finalizes the last utterance.
    while(call===owned&&Date.now()-started<8000){
      await new Promise(resolve=>setTimeout(resolve,250));
      if(Date.now()-started>=3000&&Date.now()-owned.lastText>=2000)break;
    }
    if(call===owned)await finish('Dictation finished',false,false,true);
  }
  async function start(mode){
    if(call){if(call.mode==='dictation')await complete();else await finish();return;}
    if(remote?.active||busy||ending)return;
    if(!navigator.mediaDevices?.getUserMedia||typeof RTCPeerConnection!=='function'){
      note('Audio needs microphone access in the ARMADA app or a supported local browser.',true);return;
    }
    const revision=++generation;
    const owned={id:crypto.randomUUID().replaceAll('-',''),mode,stream:null,peer:null,connected:false,
      muted:false,text:'',lastText:Date.now(),selection:[input.selectionStart,input.selectionEnd]};
    mute.setAttribute('aria-pressed','false');mute.innerHTML=window.mcIcon('mic',16)+'<span>Mute</span>';
    draft.textContent='';draft.hidden=true;call=owned;note('Allow your microphone, then we’ll connect to Codex.');paint();
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      owned.stream=stream;if(revision!==generation){release(owned);return;}
      observeMicrophone(owned);
      note('Connecting to Codex…');
      const peer=owned.peer=new RTCPeerConnection();stream.getTracks().forEach(track=>peer.addTrack(track,stream));
      peer.createDataChannel('oai-events');
      peer.ontrack=event=>{
        // Never attach incoming audio to a player in dictation, even if the provider replies.
        if(call!==owned||owned.mode==='dictation')return;
        audio.srcObject=event.streams[0]||new MediaStream([event.track]);
        audio.play().catch(()=>{play.hidden=false;note('Connected. Select Listen to hear replies.');});
      };
      peer.onconnectionstatechange=()=>{
        if(call!==owned)return;
        if(peer.connectionState==='connected'){
          owned.connected=true;note(mode==='dictation'?'Listening · select Done when you finish':'Listening · you can speak naturally');paint();
        }else if(peer.connectionState==='failed'||peer.connectionState==='closed'){
          finish('Audio disconnected. Start again to reconnect.',true,false,mode==='dictation');
        }
      };
      await peer.setLocalDescription(await peer.createOffer());
      const result=await post('start',{id:owned.id,sdp:peer.localDescription.sdp,mode});
      if(revision!==generation){release(owned);await post('stop',{id:owned.id});return;}
      await peer.setRemoteDescription({type:'answer',sdp:result.sdp});poll(owned);window.mcThreadChanged?.();
    }catch(e){
      if(revision!==generation)return;
      const denied=e.name==='NotAllowedError'||e.name==='PermissionDeniedError';
      await finish(denied?'Microphone access was denied. Allow it in your browser or Windows privacy settings, then try again.':e.message||'Audio could not connect.',true,false,mode==='dictation');
    }
  }
  button.addEventListener('click',()=>start('voice'));dictate.addEventListener('click',()=>start('dictation'));
  done.addEventListener('click',complete);
  end.addEventListener('click',()=>finish((call||remote)?.mode==='dictation'?'Dictation cancelled':'Voice chat ended'));
  mute.addEventListener('click',()=>{
    if(!call?.connected)return;
    call.muted=!call.muted;call.stream.getAudioTracks().forEach(track=>{track.enabled=!call.muted;});
    mute.setAttribute('aria-pressed',String(call.muted));
    mute.innerHTML=window.mcIcon(call.muted?'mic-off':'mic',16)+'<span>'+(call.muted?'Unmute':'Mute')+'</span>';
    note(call.muted?'Microphone muted · you can still hear replies':'Listening · you can speak naturally');
  });
  play.addEventListener('click',()=>audio.play().then(()=>{play.hidden=true;note('Listening · you can speak naturally');}).catch(()=>note('Audio playback is blocked. Check your browser’s sound permissions.',true)));
  window.mcAudioBusy=()=>!!call||ending||!!remote?.active;
  window.mcVoiceSync=(value,working)=>{remote=value;busy=working;if(!call&&!ending&&!remote?.active&&!panel.dataset.error)panel.hidden=true;paint();};
  window.mcVoiceStop=()=>{if(!call)return false;finish(call.mode==='dictation'?'Dictation cancelled':'Voice chat ended');return true;};
  window.addEventListener('pagehide',()=>{if(call)finish('Audio session ended',false,true,call.mode==='dictation');});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&call){event.preventDefault();finish(call.mode==='dictation'?'Dictation cancelled':'Voice chat ended');}});
})();
