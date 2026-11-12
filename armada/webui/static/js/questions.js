// Native engine questions share one run-bound panel across cockpit and companions.
(function(){
  const container=document.getElementById('mc-questions');if(!container)return;
  const nodes=new Map();
  function element(tag,className,text){
    const node=document.createElement(tag);if(className)node.className=className;
    if(text!==undefined)node.textContent=text;return node;
  }
  function build(request){
    const form=element('form','mc-question-form');
    const heading=element('h3','','The agent needs your input');form.append(heading);
    request.questions.forEach((question,index)=>{
      const fieldset=element('fieldset');fieldset.dataset.questionId=question.id;
      fieldset.append(element('legend','',question.question));
      const inputs=[];
      question.options.forEach(option=>{
        const label=element('label','mc-question-option');
        const input=element('input');input.type=question.multi_select?'checkbox':'radio';
        input.name=request.id+'-'+index;input.value=option.label;inputs.push(input);
        const copy=element('span');copy.append(element('span','mc-question-option-name',option.label));
        if(option.description)copy.append(element('span','mc-question-option-description',option.description));
        label.append(input,copy);fieldset.append(label);
      });
      if(question.allow_other){
        const label=element('label','mc-question-custom',question.options.length?'Or write your answer':'Your answer');
        const custom=element('textarea');custom.rows=2;custom.maxLength=16000;
        custom.spellcheck=true;custom.dataset.questionCustom='';
        label.append(custom);fieldset.append(label);
        custom.addEventListener('input',()=>{if(!question.multi_select&&custom.value.trim())inputs.forEach(input=>input.checked=false);});
        inputs.forEach(input=>input.addEventListener('change',()=>{if(!question.multi_select&&input.checked)custom.value='';}));
      }
      form.append(fieldset);
    });
    const actions=element('div','mc-question-actions');
    const send=element('button','btn btn-primary btn-sm','Send answers');send.type='submit';
    const skip=element('button','btn btn-secondary btn-sm','Skip');skip.type='button';
    const status=element('p','mc-question-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
    actions.append(send,skip);form.append(actions,status);
    const row={form,request,status,busy:false};
    async function submit(cancelled){
      if(row.busy||row.request.status!=='pending')return;
      const answers={};
      if(!cancelled){
        for(const fieldset of form.querySelectorAll('fieldset')){
          const values=[...fieldset.querySelectorAll('input:checked')].map(input=>input.value);
          const custom=fieldset.querySelector('[data-question-custom]')?.value.trim();
          if(custom)values.push(custom);
          if(!values.length){
            status.textContent='Answer each question before sending.';
            fieldset.querySelector('input,textarea')?.focus();return;
          }
          answers[fieldset.dataset.questionId]=values;
        }
      }
      const context=window.mcThreadCtx?.()||{};
      row.busy=true;form.querySelectorAll('input,textarea,button').forEach(input=>input.disabled=true);
      status.textContent=cancelled?'Skipping…':'Sending answers…';
      try{
        const response=await fetch('/api/thread-answer',{method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({agent:context.agent,thread:context.thread,run_id:row.request.run_id,
            question_id:row.request.id,answers,cancelled}),signal:AbortSignal.timeout(15000)});
        const data=await response.json();
        if(!response.ok||!data.ok)throw Error(data.error||'Your answer could not be sent. Try again.');
        row.request={...row.request,...data.request};
        status.textContent=cancelled?'Question skipped.':'Answers submitted. Waiting for the agent…';
        window.mcThreadChanged?.();
      }catch(error){
        status.textContent=error.message||'Your answer could not be sent. Try again.';
        form.querySelectorAll('input,textarea,button').forEach(input=>input.disabled=false);
      }finally{row.busy=false;}
    }
    form.addEventListener('submit',event=>{event.preventDefault();event.stopPropagation();submit(false);});
    skip.addEventListener('click',()=>submit(true));
    return row;
  }
  window.mcSyncQuestions=requests=>{
    const keep=new Set();
    requests.forEach(request=>{
      keep.add(request.id);
      let row=nodes.get(request.id);
      if(!row){row=build(request);nodes.set(request.id,row);container.append(row.form);}
      row.request=request;
      if(request.status!=='pending'){
        row.form.querySelectorAll('input,textarea,button').forEach(input=>input.disabled=true);
        if(!row.busy)row.status.textContent='Answers submitted. Waiting for the agent…';
      }
    });
    nodes.forEach((row,id)=>{
      if(keep.has(id))return;
      const focused=row.form.contains(document.activeElement);
      row.form.remove();nodes.delete(id);
      if(focused){
        const message=document.getElementById('mc-msg');
        (message&&!message.disabled?message:document.getElementById('mc-stop'))?.focus({preventScroll:true});
      }
    });
    container.hidden=!nodes.size;
  };
})();
