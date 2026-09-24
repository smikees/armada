function mcMemFocusHighlight(id){var el=document.getElementById(id);if(el){
el.scrollIntoView({behavior:"smooth",block:"center"});el.style.transition="box-shadow .3s";
el.style.boxShadow="0 0 0 2px var(--color-accent)";setTimeout(function(){el.style.boxShadow="";},2000);}}
