(function(){try{var s=localStorage.getItem('mcThLeft');if(s){var g=document.getElementById('mc-thgrid');if(g)g.style.setProperty('--mc-thleft',s);}}catch(e){}})();
function mcThResizeStart(e){e.preventDefault();var g=document.getElementById('mc-thgrid');if(!g)return;
  var startX=e.clientX, startW=g.children[0].getBoundingClientRect().width;
  function mv(ev){var w=Math.min(500,Math.max(150,startW+(ev.clientX-startX)));g.style.setProperty('--mc-thleft',w+'px');}
  function up(){document.removeEventListener('mousemove',mv);document.removeEventListener('mouseup',up);document.body.style.userSelect='';
    try{localStorage.setItem('mcThLeft',getComputedStyle(g).getPropertyValue('--mc-thleft').trim());}catch(e){}}
  document.body.style.userSelect='none';document.addEventListener('mousemove',mv);document.addEventListener('mouseup',up);}
