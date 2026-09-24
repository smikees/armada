(function(){
 function paint(d,s){var m={working:['color-mix(in srgb,var(--color-text) 55%,var(--color-bg))',1],input:['var(--status-warn)',0],unseen:['var(--color-accent-2)',0],idle:['color-mix(in srgb,var(--color-text) 20%,var(--color-bg))',0]};var x=m[s]||m.idle;
  // backgroundColor, never the `background` shorthand — the dot's CSS transition is on that
  // property and the shorthand would clear anything else the server set on the element.
  d.style.backgroundColor=x[0];
  d.style.animation=x[1]?'mc-actwork 1.4s ease-in-out infinite':'';d.dataset.act=s;}
 async function tick(){if(document.hidden)return;var m;try{m=await(await fetch('/api/agent-activity',{cache:'no-store'})).json();}catch(e){return;}if(!m)return;
  document.querySelectorAll('[data-agentdot]').forEach(function(el){var s=m[el.dataset.agentdot];var d=el.querySelector('.mc-actdot');if(d&&s)paint(d,s);});}
 if(document.querySelector('[data-agentdot]')){tick();setInterval(tick,4000);document.addEventListener('visibilitychange',function(){if(!document.hidden)tick();});}
})();
