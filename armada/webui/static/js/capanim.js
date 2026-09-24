// Re-opening a <details> doesn't re-run its CSS open animation: the panel element is never
// re-created, so the animation only ever played on first expand. Restart it by hand on each
// open (clear → force reflow → restore). `toggle` doesn't bubble, hence capture.
document.addEventListener("toggle",function(e){
var d=e.target;if(!d||d.tagName!=="DETAILS"||!d.open)return;
var b=d.querySelector(".mc-cap-prov,.mc-cap-advbody");
if(!b||b.parentNode!==d)return;
b.style.animation="none";void b.offsetWidth;b.style.animation="";
},true);
