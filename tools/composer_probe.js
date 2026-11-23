// Executed in both real WebView2 thread surfaces by thread_window_probe.py.
(()=>{
  const t=document.getElementById('mc-msg'),checks=[];
  function check(label,ok){if(!ok)throw new Error(label+': '+JSON.stringify({value:t.value,html:t.innerHTML}));checks.push(label);}
  const input=()=>t.dispatchEvent(new Event('input',{bubbles:true}));
  const key=(name,shift=false)=>t.dispatchEvent(new KeyboardEvent('keydown',{key:name,shiftKey:shift,bubbles:true,cancelable:true}));
  const edit=(command,text)=>document.execCommand(command,false,text);
  const style=t.getAttribute('style');t.style.maxWidth='310px';
  for(const prefix of ['• ','    ◦ ','        ◦ ','1. ','    12) ','\t◦ ']){
    t.value=prefix+'A long list item with enough words to wrap onto several lines in the input field. '.repeat(3);input();
    const node=t.firstElementChild.firstChild,range=document.createRange(),rects=[];
    for(let i=prefix.length;i<node.length;i++){range.setStart(node,i);range.setEnd(node,i+1);rects.push(range.getBoundingClientRect());}
    const first=rects[0],next=rects.find(r=>r.top>first.top+2&&r.width>0);
    check('wrapped '+JSON.stringify(prefix)+' aligns with item text',!!next&&Math.abs(next.left-first.left)<1.5);
    check('wrapped item stays inside composer',t.scrollWidth<=t.clientWidth+1);
  }
  t.setAttribute('style',style);
  t.value='';t.focus();t.setSelectionRange(0,0);edit('insertText','-');edit('insertText',' ');
  check('native typing converts a bullet prefix',t.value==='• ');
  edit('insertText','Typed item');check('typing after bullet conversion keeps caret',t.value==='• Typed item');
  edit('undo');edit('redo');check('bullet typing survives native undo and redo',t.value==='• Typed item');
  t.value='Alpha\nBeta';t.focus();t.setSelectionRange(2,8);
  check('multiline selection offsets are plain-text offsets',t.selectionStart===2&&t.selectionEnd===8);
  edit('insertText','X');check('typing replaces multiline selection',t.value==='AlXta');
  edit('undo');check('native undo restores multiline text',t.value==='Alpha\nBeta');
  edit('redo');check('native redo restores replacement',t.value==='AlXta');
  t.value='';t.setSelectionRange(0,0);edit('insertText','first');edit('insertParagraph');edit('insertText','second');
  check('native paragraphs serialize as plain text',t.value==='first\nsecond');
  edit('undo');check('undo removes native typing group',['','first\n'].includes(t.value));
  edit('redo');check('redo restores latest typing',t.value==='first\nsecond');
  t.setSelectionRange(6,6);edit('delete');check('backspace joins adjacent lines',t.value==='firstsecond');
  edit('undo');check('undo restores joined newline',t.value==='first\nsecond');
  t.value='';t.setSelectionRange(0,0);
  const data=new DataTransfer();data.setData('text/plain','<tag> & plain\n    ◦ pasted item');data.setData('text/html','<b>rich text</b>');
  t.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));
  check('paste keeps only exact plain text',t.value==='<tag> & plain\n    ◦ pasted item'&&!t.querySelector('b,tag'));
  t.value='9. Nine';t.setSelectionRange(t.value.length,t.value.length);key('Enter',true);
  check('Shift Enter continues numbered items',t.value==='9. Nine\n10. ');
  key('Tab');check('Tab nests numbered items',t.value==='9. Nine\n    10. ');
  key('Enter',true);check('empty nested number outdents',t.value==='9. Nine\n10. ');
  key('Enter',true);check('empty number exits list',t.value==='9. Nine\n');
  t.disabled=true;t.disabled=false;check('reenabled composer stays plain text',t.contentEditable==='plaintext-only');
  t.value='';input();return checks;
})()
