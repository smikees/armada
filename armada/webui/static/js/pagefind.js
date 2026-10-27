// Find in the current section without changing its DOM, editor contents or event handlers.
(function(){
  let panel,input,count,ranges=[],index=-1,previous,observer,timer;
  // Preserve UTF-16 offsets when lowercasing dotted capital I for DOM ranges.
  const fold=text=>text.replace(/\u0130/g,'I').toLowerCase();
  function position(){
    const nav=document.querySelector('.mc-mainnav');
    panel.style.top=((nav?nav.getBoundingClientRect().bottom:0)+8)+'px';
  }
  function close(){
    if(!panel)return;panel.hidden=true;clearTimeout(timer);observer?.disconnect();
    if(window.CSS?.highlights){CSS.highlights.delete('mc-find-all');CSS.highlights.delete('mc-find-current');}
    if(previous?.isConnected)previous.focus({preventScroll:true});
  }
  function paint(scroll){
    if(window.CSS?.highlights){
      CSS.highlights.set('mc-find-all',new Highlight(...ranges));
      CSS.highlights.set('mc-find-current',new Highlight(...(index>=0?[ranges[index]]:[])));
    }
    count.textContent=ranges.length?(index+1)+' / '+ranges.length:(input.value?'No matches':'');
    panel.querySelectorAll('[data-step]').forEach(b=>b.disabled=!ranges.length);
    if(scroll&&index>=0){
      const range=ranges[index],node=range.startContainer.parentElement;
      // Scroll every nested scroller (including the thread) without stealing input focus.
      node.scrollIntoView({block:'center',inline:'nearest'});
      if(!window.CSS?.highlights){const selection=getSelection();selection.removeAllRanges();selection.addRange(range);}
    }
  }
  function find(scroll){
    ranges=[];const query=fold(input.value);
    if(query){
      const root=document.querySelector('.mc-appscroll')||document.querySelector('main');
      if(root){
        const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),groups=[];
        let node,group;
        while((node=walker.nextNode())){
          const parent=node.parentElement;
          if(!node.textContent||parent.closest('script,style,textarea,input,select,[contenteditable], [aria-hidden="true"]'))continue;
          let hidden=false;
          for(let ancestor=parent;ancestor&&ancestor!==root;ancestor=ancestor.parentElement){
            if(ancestor.tagName==='DETAILS'&&!ancestor.open){
              const summary=ancestor.querySelector(':scope > summary');
              if(!summary||!summary.contains(parent)){hidden=true;break;}
            }
          }
          if(hidden)continue;
          const visible=document.createRange();visible.selectNodeContents(node);
          if(!visible.getClientRects().length||getComputedStyle(parent).visibility==='hidden')continue;
          let block=parent;
          while(block!==root&&getComputedStyle(block).display==='inline')block=block.parentElement;
          if(!group||group.block!==block){group={block,text:'',nodes:[]};groups.push(group);}
          group.nodes.push({node,start:group.text.length});group.text+=node.textContent;
        }
        for(const group of groups){
          const text=fold(group.text);let from=0,at;
          while((at=text.indexOf(query,from))>=0){
            const end=at+query.length;
            const first=group.nodes.findLast(n=>n.start<=at),last=group.nodes.findLast(n=>n.start<end);
            const range=document.createRange();range.setStart(first.node,at-first.start);range.setEnd(last.node,end-last.start);ranges.push(range);from=end;
          }
        }
      }
    }
    index=ranges.length?Math.max(0,Math.min(index,ranges.length-1)):-1;paint(scroll);
  }
  function move(step){if(ranges.length){index=(index+step+ranges.length)%ranges.length;paint(true);}}
  function open(){
    if(!panel||panel.hidden)previous=document.activeElement;
    if(!panel){
      panel=document.createElement('section');panel.className='mc-pagefind';panel.setAttribute('aria-label','Find in this section');panel.hidden=true;
      panel.innerHTML='<input type="search" aria-label="Find in this section" placeholder="Find in this section" autocomplete="off"><span class="mc-pagefind-count" role="status" aria-live="polite"></span><button type="button" data-step="-1" aria-label="Previous match" title="Previous match (Shift+Enter)">↑</button><button type="button" data-step="1" aria-label="Next match" title="Next match (Enter)">↓</button><button type="button" data-close aria-label="Close search" title="Close (Escape)">×</button>';
      document.body.appendChild(panel);input=panel.querySelector('input');count=panel.querySelector('[role="status"]');
      input.addEventListener('input',()=>{index=0;find(true);});
      panel.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>move(Number(b.dataset.step)));
      panel.querySelector('[data-close]').onclick=close;
      observer=new MutationObserver(()=>{clearTimeout(timer);timer=setTimeout(()=>find(false),150);});
      window.addEventListener('resize',position);
    }
    panel.hidden=false;position();input.focus();input.select();find(false);
    const root=document.querySelector('.mc-appscroll')||document.querySelector('main');
    if(root)observer.observe(root,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['style','class','open','hidden']});
  }
  document.addEventListener('keydown',function(e){
    if((e.ctrlKey||e.metaKey)&&!e.altKey&&e.key.toLowerCase()==='f'){e.preventDefault();e.stopImmediatePropagation();open();}
    else if(panel&&!panel.hidden&&e.key==='Escape'){e.preventDefault();e.stopImmediatePropagation();close();}
    else if(panel&&!panel.hidden&&(e.key==='F3'||(e.key==='Enter'&&panel.contains(e.target)))){e.preventDefault();move(e.shiftKey?-1:1);}
  },true);
})();
