// Memory cards clamp to one line and grow a caret when there's more to see.
//
// The caret sits under the card's scope icon, sharing one narrow left gutter with it, and the whole
// card is the click target — hitting a 13px chevron to read a memory was needless precision. Clicks
// on the row's own controls (edit, delete, refresh) and on links inside the body still do their own
// thing, and a click that ends a text selection doesn't collapse what you were selecting.
(function(){
  function open(c){ return c.querySelector('.mc-membody').dataset.open==='1'; }

  function chk(){
    document.querySelectorAll('.mc-memcard').forEach(function(c){
      var body=c.querySelector('.mc-membody');
      var caret=c.querySelector('.mc-memexpand');
      if(!body||!caret)return;
      if(body.dataset.open==='1')return;                  // expanded: the caret stays put
      var overflows=body.scrollHeight-body.clientHeight>2;
      caret.style.display=overflows?'inline-flex':'none';
      c.style.cursor=overflows?'pointer':'';
    });
  }
  if(document.readyState!=='loading')chk(); else document.addEventListener('DOMContentLoaded',chk);

  function toggle(c){
    var body=c.querySelector('.mc-membody'); if(!body)return;
    var was=open(c);
    body.dataset.open=was?'':'1';
    body.style.maxHeight=was?'1.55em':'none';
    var caret=c.querySelector('.mc-memexpand');
    if(caret){
      caret.title=was?'Show all':'Show less';
      var ic=caret.querySelector('svg');
      if(ic){ic.style.transition='transform .15s';ic.style.transform=was?'':'rotate(90deg)';}
    }
  }
  // Kept for any caller that still passes an element inside the card.
  window.mcMemToggle=function(el){ var c=el&&el.closest?el.closest('.mc-memcard'):null; if(c)toggle(c); };

  document.addEventListener('click',function(e){
    var c=e.target.closest&&e.target.closest('.mc-memcard'); if(!c)return;
    if(e.target.closest('a,button,input,textarea,select,.mc-memactions'))return;
    var sel=window.getSelection&&window.getSelection();
    if(sel&&!sel.isCollapsed&&c.contains(sel.anchorNode))return;   // don't collapse a selection
    var body=c.querySelector('.mc-membody'); if(!body)return;
    if(body.dataset.open!=='1'&&body.scrollHeight-body.clientHeight<=2)return;   // nothing more to show
    toggle(c);
  });
})();
