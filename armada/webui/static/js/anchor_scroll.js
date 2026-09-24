document.addEventListener("click",function(e){
var a=e.target.closest&&e.target.closest('a[href^="#"]');if(!a)return;
var el=document.getElementById(a.getAttribute("href").slice(1));
if(el){e.preventDefault();el.scrollIntoView({behavior:"smooth"});}},true);
