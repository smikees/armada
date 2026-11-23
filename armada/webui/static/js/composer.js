// Plain-text composer with per-line hanging indents. Keep the textarea interface
// used by drafts, voice, steering and native recovery; editing/undo stays native.
(function(){
  const old=document.getElementById('mc-msg');if(!old||old.tagName!=='TEXTAREA')return;
  const editor=document.createElement('div');
  for(const attr of old.attributes)if(!['rows','placeholder'].includes(attr.name))editor.setAttribute(attr.name,attr.value);
  editor.contentEditable='plaintext-only';editor.classList.add('mc-composer-text');editor.dataset.composer='true';
  editor.setAttribute('role','textbox');editor.setAttribute('aria-multiline','true');
  editor.setAttribute('aria-label','Message');editor.dataset.placeholder=old.placeholder;
  let selection=[0,0],composing=false;
  function lineText(node){
    if(node.nodeType===3)return node.data.replace(/\u00a0/g,' ');
    if(node.nodeName==='BR')return '\n';
    let text='';
    [...node.childNodes].forEach((child,i)=>{
      if(child.nodeName==='BR'&&i===node.childNodes.length-1)return; // native empty-line filler
      if(i&&/^(DIV|P)$/.test(child.nodeName))text+='\n';
      text+=lineText(child);
    });return text;
  }
  function plain(root){return [...root.childNodes].map(lineText).join('\n');}
  function offset(node,index){const r=document.createRange();r.selectNodeContents(editor);r.setEnd(node,index);return plain(r.cloneContents()).length;}
  function current(){
    const s=getSelection();if(s?.rangeCount&&editor.contains(s.anchorNode)&&editor.contains(s.focusNode)){
      selection=[offset(s.anchorNode,s.anchorOffset),offset(s.focusNode,s.focusOffset)].sort((a,b)=>a-b);
    }return selection;
  }
  function point(index){
    let base=0;
    for(const line of editor.childNodes){
      const length=lineText(line).length;
      if(index<=base+length){
        const walk=document.createTreeWalker(line,NodeFilter.SHOW_TEXT);let node,remaining=index-base;
        while((node=walk.nextNode())){if(remaining<=node.length)return [node,remaining];remaining-=node.length;}
        return [line,line.childNodes.length&&line.lastChild.nodeName==='BR'?line.childNodes.length-1:line.childNodes.length];
      }base+=length+1;
    }return [editor,editor.childNodes.length];
  }
  function select(start,end=start){
    const length=editor.value.length;selection=[Math.max(0,Math.min(start,length)),Math.max(0,Math.min(end,length))];
    const r=document.createRange();r.setStart(...point(selection[0]));r.setEnd(...point(selection[1]));
    const s=getSelection();s.removeAllRanges();s.addRange(r);
  }
  function normalize(){
    const s=getSelection(),anchor=s?.anchorNode,focus=s?.focusNode,ao=s?.anchorOffset,fo=s?.focusOffset;
    let changed=false;
    for(const node of [...editor.childNodes])if(node.nodeName!=='DIV'){
      const line=document.createElement('div');editor.insertBefore(line,node);line.appendChild(node);changed=true;
    }
    if(!editor.childNodes.length){const line=document.createElement('div');line.appendChild(document.createElement('br'));editor.appendChild(line);}
    if(changed&&anchor&&focus&&editor.contains(anchor)&&editor.contains(focus))s.setBaseAndExtent(anchor,ao,focus,fo);
  }
  function layout(){
    if(composing)return;normalize();
    const canvas=layout.canvas||(layout.canvas=document.createElement('canvas')),ctx=canvas.getContext('2d'),style=getComputedStyle(editor);
    ctx.font=style.font;
    for(const line of editor.children){
      const prefix=lineText(line).match(/^[ \t]*(?:[-*+•◦]|\d+[.)])\s+/)?.[0];
      const width=prefix?ctx.measureText(prefix.replace(/\t/g,'    ')).width:0;
      line.style.paddingLeft=width+'px';line.style.textIndent=-width+'px';
    }
    editor.dataset.empty=editor.value?'false':'true';
  }
  Object.defineProperties(editor,{
    value:{get:()=>plain(editor),set:value=>{
      const focused=document.activeElement===editor;
      editor.replaceChildren(...String(value??'').replace(/\r\n?/g,'\n').split('\n').map(text=>{
        const line=document.createElement('div');if(text)line.textContent=text;else line.appendChild(document.createElement('br'));return line;
      }));selection=[editor.value.length,editor.value.length];layout();if(focused)select(...selection);
    }},
    selectionStart:{get:()=>current()[0],set:value=>{const end=current()[1];select(value,Math.max(value,end));}},
    selectionEnd:{get:()=>current()[1],set:value=>{const start=current()[0];select(Math.min(start,value),value);}},
    placeholder:{get:()=>editor.dataset.placeholder,set:value=>{editor.dataset.placeholder=value;}},
    disabled:{get:()=>editor.contentEditable==='false',set:value=>{editor.contentEditable=value?'false':'plaintext-only';editor.setAttribute('aria-disabled',String(!!value));}}
  });
  editor.setSelectionRange=select;
  editor.setRangeText=(text,start,end)=>{
    editor.focus();select(start,end);
    if(!document.execCommand('insertText',false,text)){
      editor.value=editor.value.slice(0,start)+text+editor.value.slice(end);select(start+text.length);
    }layout();
  };
  editor.addEventListener('compositionstart',()=>{composing=true;});
  editor.addEventListener('compositionend',()=>{composing=false;layout();});
  editor.addEventListener('input',()=>{layout();current();});
  editor.addEventListener('keyup',current);editor.addEventListener('pointerup',current);editor.addEventListener('blur',current);
  editor.addEventListener('beforeinput',event=>{
    if(event.inputType==='insertLineBreak'&&!event.isComposing){event.preventDefault();document.execCommand('insertParagraph');}
  });
  editor.addEventListener('paste',event=>{
    if([...event.clipboardData?.items||[]].some(item=>item.kind==='file'))return;
    event.preventDefault();document.execCommand('insertText',false,event.clipboardData?.getData('text/plain')||'');
  });
  editor.addEventListener('drop',event=>{event.preventDefault();});
  old.replaceWith(editor);editor.value=old.value;
  document.fonts?.ready.then(layout);
  window.addEventListener('resize',layout);
})();
