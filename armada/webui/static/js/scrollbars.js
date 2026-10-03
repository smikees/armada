// Overlay chrome only: content keeps its own native scrolling, selection and keyboard behavior.
(function(){
  if(document.querySelector('.mc-scroll-overlay'))return;
  const root=document.createElement('div');root.className='mc-scroll-overlay';root.setAttribute('aria-hidden','true');
  const tracks={};
  for(const axis of ['x','y']){
    const track=document.createElement('div'),thumb=document.createElement('div');
    track.className='mc-scroll-track mc-scroll-track-'+axis;thumb.className='mc-scroll-thumb';
    track.append(thumb);root.append(track);tracks[axis]={track,thumb};
  }
  document.body.append(root);
  const contrast=window.matchMedia('(forced-colors: active)');
  let owner=null,pointer=null,drag=null,idle=0,frame=0,pending=null,visible=false;
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  function axes(el){
    const style=getComputedStyle(el),isPage=el===document.scrollingElement;
    const allowed=v=>/^(auto|scroll|overlay)$/.test(v);
    return {x:el.scrollWidth>el.clientWidth+1&&(allowed(style.overflowX)||(isPage&&!/hidden|clip/.test(style.overflowX))),
      y:el.scrollHeight>el.clientHeight+1&&(allowed(style.overflowY)||(isPage&&!/hidden|clip/.test(style.overflowY))),rtl:style.direction==='rtl'};
  }
  function nearest(target){
    for(let el=target instanceof Element?target:target?.parentElement;el;el=el.parentElement){
      if(root.contains(el))return owner;
      const a=axes(el);if(a.x||a.y)return el;
    }
    return null;
  }
  function clientRect(el){
    if(el===document.scrollingElement)return {left:0,top:0,right:window.innerWidth,bottom:window.innerHeight};
    const r=el.getBoundingClientRect();return {left:r.left+el.clientLeft,top:r.top+el.clientTop,
      right:r.left+el.clientLeft+el.clientWidth,bottom:r.top+el.clientTop+el.clientHeight};
  }
  function clippedRect(el){
    const r=clientRect(el);r.left=Math.max(0,r.left);r.top=Math.max(0,r.top);
    r.right=Math.min(window.innerWidth,r.right);r.bottom=Math.min(window.innerHeight,r.bottom);
    for(let p=el.parentElement;p&&p!==document.body&&p!==document.documentElement;p=p.parentElement){
      const s=getComputedStyle(p),b=clientRect(p);
      if(/auto|scroll|hidden|clip/.test(s.overflowX)){r.left=Math.max(r.left,b.left);r.right=Math.min(r.right,b.right);}
      if(/auto|scroll|hidden|clip/.test(s.overflowY)){r.top=Math.max(r.top,b.top);r.bottom=Math.min(r.bottom,b.bottom);}
    }
    return r;
  }
  const inside=r=>pointer&&pointer.x>=r.left&&pointer.x<=r.right&&pointer.y>=r.top&&pointer.y<=r.bottom;
  function hide(){visible=false;root.dataset.visible='false';clearTimeout(idle);}
  function activity(){
    if(contrast.matches)return;visible=true;root.dataset.visible='true';clearTimeout(idle);
    // 800ms idle plus the 200ms fade: fully hidden about one second after the last movement.
    if(!drag)idle=setTimeout(hide,800);
  }
  function draw(){
    if(!owner||!owner.isConnected){hide();owner=null;return;}
    const a=axes(owner),r=clippedRect(owner);
    if((!a.x&&!a.y)||r.right-r.left<20||r.bottom-r.top<20||(!drag&&!inside(r))){hide();return;}
    const corner=owner.classList.contains('mc-scroll')?18:(a.x&&a.y?12:0);
    for(const axis of ['x','y']){
      const item=tracks[axis],vertical=axis==='y';item.track.hidden=!a[axis];if(!a[axis])continue;
      const start=(vertical?r.top:r.left)+2,length=Math.max(1,(vertical?r.bottom-r.top:r.right-r.left)-4-corner);
      const viewport=vertical?owner.clientHeight:owner.clientWidth,total=vertical?owner.scrollHeight:owner.scrollWidth;
      const range=Math.max(0,total-viewport),size=Math.min(length,Math.max(28,length*viewport/total));
      const value=vertical?owner.scrollTop:a.rtl?range+owner.scrollLeft:owner.scrollLeft;
      const position=range?clamp(value/range,0,1)*(length-size):0;
      item.geometry={start,length,size,range,rtl:a.rtl};
      // Keep the narrow visible thumb at the container edge; its invisible hit area stays inside.
      Object.assign(item.track.style,vertical?{left:(r.right-9)+'px',top:start+'px',height:length+'px'}:
        {left:start+'px',top:(r.bottom-9)+'px',width:length+'px'});
      Object.assign(item.thumb.style,vertical?{top:position+'px',height:size+'px'}:{left:position+'px',width:size+'px'});
    }
  }
  function select(el){
    if(el!==owner){owner=el;resize.disconnect();if(owner)resize.observe(owner);}
    if(!owner){hide();return;}activity();draw();
  }
  function schedule(){if(frame)return;frame=requestAnimationFrame(()=>{
    frame=0;if(pending){const target=pending;pending=null;if(!drag)select(nearest(target));}
    else if(visible||drag)draw();
  });}
  const resize=new ResizeObserver(schedule);
  new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true,characterData:true});
  document.addEventListener('pointermove',e=>{
    if(pointer&&pointer.x===e.clientX&&pointer.y===e.clientY)return;
    pointer={x:e.clientX,y:e.clientY};if(drag)return;pending=e.target;schedule();
  },{passive:true});
  // Streaming updates and automatic scrolling update geometry without restarting the idle timer.
  document.addEventListener('scroll',schedule,{capture:true,passive:true});
  document.addEventListener('wheel',e=>{if(!root.contains(e.target)&&!drag)select(nearest(e.target));},{passive:true});
  document.addEventListener('pointerout',e=>{if(!e.relatedTarget&&!drag)hide();},{passive:true});
  function stopDrag(){
    const capture=drag;drag=null;root.dataset.dragging='false';
    if(capture){try{capture.track.releasePointerCapture(capture.id);}catch(e){}}
    if(owner&&inside(clippedRect(owner)))activity();else hide();
  }
  function setPosition(axis,value){
    const g=tracks[axis].geometry;if(!g||!owner)return;
    if(axis==='y')owner.scrollTop=clamp(value,0,g.range);
    else owner.scrollLeft=g.rtl?clamp(value,0,g.range)-g.range:clamp(value,0,g.range);
  }
  for(const axis of ['x','y']){
    const {track,thumb}=tracks[axis];
    // The chrome is a portal outside dropdowns/modal content; dragging it is not an outside click.
    track.addEventListener('click',e=>e.stopPropagation());
    track.addEventListener('pointerdown',e=>{
      if(e.button!==0||!owner)return;e.preventDefault();e.stopPropagation();pointer={x:e.clientX,y:e.clientY};draw();
      const g=tracks[axis].geometry,point=axis==='y'?e.clientY:e.clientX;
      if(!g||track.hidden)return;
      const offset=e.target===thumb?point-g.start-parseFloat(thumb.style[axis==='y'?'top':'left']):g.size/2;
      if(e.target!==thumb)setPosition(axis,(point-g.start-offset)/Math.max(1,g.length-g.size)*g.range);
      drag={axis,offset,id:e.pointerId,track};root.dataset.dragging='true';activity();track.setPointerCapture(e.pointerId);draw();
    });
    track.addEventListener('pointermove',e=>{
      if(!drag||drag.axis!==axis)return;pointer={x:e.clientX,y:e.clientY};
      const g=tracks[axis].geometry;setPosition(axis,((axis==='y'?e.clientY:e.clientX)-g.start-drag.offset)/Math.max(1,g.length-g.size)*g.range);draw();
    });
    track.addEventListener('pointerup',stopDrag);track.addEventListener('pointercancel',stopDrag);
    track.addEventListener('lostpointercapture',()=>{if(drag)stopDrag();});
    // Wheel events on overlay chrome must reach its content, including normal parent chaining.
    track.addEventListener('wheel',e=>{
      const scale=e.deltaMode===1?16:e.deltaMode===2?(owner?.clientHeight||window.innerHeight):1;
      const dx=(e.shiftKey&&!e.deltaX?e.deltaY:e.deltaX)*scale,dy=(e.shiftKey&&!e.deltaX?0:e.deltaY)*scale;
      for(let el=owner;el;el=el.parentElement){
        const a=axes(el),x=el.scrollLeft,y=el.scrollTop;
        el.scrollBy({left:a.x?dx:0,top:a.y?dy:0,behavior:'instant'});
        if(el.scrollLeft!==x||el.scrollTop!==y){e.preventDefault();select(el);return;}
        const s=getComputedStyle(el);if((dy&&/contain|none/.test(s.overscrollBehaviorY))||(dx&&/contain|none/.test(s.overscrollBehaviorX))){e.preventDefault();return;}
      }
    },{passive:false});
  }
  window.addEventListener('resize',schedule);
  window.addEventListener('blur',()=>{stopDrag();hide();});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){stopDrag();hide();}});
  function applyContrast(){if(contrast.matches){stopDrag();hide();}document.documentElement.classList.toggle('mc-overlay-scrollbars',!contrast.matches);}
  contrast.addEventListener('change',applyContrast);applyContrast();
})();
