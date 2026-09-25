// Report an issue (launch plan 5.6). The support icon beside the gear opens this dialog:
//   1. Write — what happened, an optional reply address, whether to include recent logs.
//   2. Review — the exact report, as the server built it (secrets removed). Nothing has been sent.
//   3. Send — sends that same text (by token), or says where it was saved if it couldn't go.
(function(){
  function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
  let ov=null, draft={message:'',email:'',include_logs:true}, token='';

  async function post(url,body){
    const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
    return r.json();
  }
  function close(){ if(ov){ov.remove();ov=null;} document.removeEventListener('keydown',onKey); }
  function onKey(e){ if(e.key==='Escape') close(); }
  function shell(inner){
    if(!ov){
      ov=document.createElement('div'); ov.className='mc-modal-ov'; ov.style.display='flex'; ov.style.zIndex='700';
      ov.addEventListener('mousedown',e=>{ if(e.target===ov) close(); });
      document.body.appendChild(ov); document.addEventListener('keydown',onKey);
    }
    ov.innerHTML='<div class="mc-modal-box mc-frame mc-support" role="dialog" aria-modal="true" aria-labelledby="mc-sup-t">'
      +'<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
      +'<span class="mc-h-card" id="mc-sup-t" style="margin:0">Report an issue</span>'
      +'<button type="button" class="mc-x" aria-label="Close" data-x>&times;</button></div>'+inner+'</div>';
    ov.querySelector('[data-x]').onclick=close;
  }
  function msg(text,bad){ const m=ov&&ov.querySelector('[data-msg]'); if(m){m.textContent=text||''; m.classList.toggle('is-bad',!!bad);} }

  function stepWrite(){
    shell('<p class="mc-hint" style="margin:0 0 10px">Tell us what went wrong or what felt off. You’ll see the whole report before anything is sent.</p>'
      +'<label class="mc-label" for="mc-sup-msg" style="margin-top:0">What happened?</label>'
      +'<textarea id="mc-sup-msg" class="mc-textarea" rows="6" maxlength="8000" placeholder="What you did, what you expected, what happened instead.">'+esc(draft.message)+'</textarea>'
      +'<label class="mc-label" for="mc-sup-email">Your email <span style="text-transform:none;letter-spacing:0">(optional — only if you’d like a reply)</span></label>'
      +'<input id="mc-sup-email" class="mc-field" type="email" maxlength="200" value="'+esc(draft.email)+'">'
      +'<label style="display:flex;gap:8px;align-items:flex-start;margin-top:12px;font-size:12.5px;cursor:pointer">'
      +'<input type="checkbox" id="mc-sup-logs" style="margin:2px 0 0"'+(draft.include_logs?' checked':'')+'>'
      +'<span>Include the last lines of ARMADA’s logs <span class="mc-hint">— they usually show what went wrong. Keys, tokens and email addresses are removed first.</span></span></label>'
      +'<div style="display:flex;gap:8px;align-items:center;justify-content:flex-end;margin-top:16px">'
      +'<span class="mc-hint" data-msg style="margin-right:auto"></span>'
      +'<button type="button" class="btn btn-secondary" data-cancel>Cancel</button>'
      +'<button type="button" class="btn btn-primary" data-next>Review report</button></div>');
    ov.querySelector('[data-cancel]').onclick=close;
    ov.querySelector('[data-next]').onclick=review;
    setTimeout(()=>{const t=document.getElementById('mc-sup-msg'); if(t) t.focus();},30);
  }

  async function review(){
    draft.message=(document.getElementById('mc-sup-msg').value||'').trim();
    draft.email=(document.getElementById('mc-sup-email').value||'').trim();
    draft.include_logs=!!document.getElementById('mc-sup-logs').checked;
    if(!draft.message){ msg('Say what happened first — a sentence is enough.',true); return; }
    msg('Building the report…');
    try{
      const r=await post('/api/support-preview',{...draft,page:location.pathname+location.search,title:document.title});
      if(!r.ok){ msg(r.error||'Couldn’t build the report.',true); return; }
      token=r.token; stepReview(r);
    }catch(e){ msg('Couldn’t build the report: '+e,true); }
  }

  function stepReview(r){
    shell('<p class="mc-hint" style="margin:0 0 8px">This is exactly what will be sent to the ARMADA team at <b>armada@stamih.com</b>. Nothing has been sent yet.</p>'
      +'<div class="mc-sup-subject"><span class="mc-hint">Subject</span> '+esc(r.subject)+'</div>'
      +'<pre class="mc-sup-preview" tabindex="0">'+esc(r.text)+'</pre>'
      +'<div style="display:flex;gap:8px;align-items:center;justify-content:flex-end;margin-top:14px">'
      +'<span class="mc-hint" data-msg style="margin-right:auto"></span>'
      +'<button type="button" class="btn btn-secondary" data-back>Back</button>'
      +'<button type="button" class="btn btn-primary" data-send>Send report</button></div>');
    ov.querySelector('[data-back]').onclick=stepWrite;
    ov.querySelector('[data-send]').onclick=send;
  }

  async function send(e){
    const b=e.currentTarget; b.disabled=true; msg('Sending…');
    try{
      const r=await post('/api/support-send',{token:token});
      if(r.ok){
        draft={message:'',email:'',include_logs:true}; token='';
        shell('<p style="font-size:13px;margin:4px 0 14px">Sent — thank you. '
          +'We read every report.</p>'
          +'<div style="display:flex;justify-content:flex-end"><button type="button" class="btn btn-primary" data-x2>Close</button></div>');
        ov.querySelector('[data-x2]').onclick=close;
        return;
      }
      b.disabled=false; msg(r.error||'Couldn’t send the report.',true);
    }catch(err){ b.disabled=false; msg('Couldn’t send the report: '+err,true); }
  }

  // `pre.message` pre-fills the report: Alexander's "Review the report" card opens it this way.
  window.mcSupportOpen=function(pre){ if(pre&&pre.message){draft.message=String(pre.message);} stepWrite(); };
})();
