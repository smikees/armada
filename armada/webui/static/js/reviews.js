// Reports belong to ARMADA, not the page that happened to launch them.
var mcReviewTimer;
async function mcReviewStart(url,key,button){
  if(button)button.disabled=true;
  try{
    var r=await(await fetch('/api/capability-review-start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:url,key:key||''})})).json();
    if(!r.ok)throw Error(r.error||'Could not start the review.');
    await mcReviewsRefresh();
    var card=document.getElementById('review-'+r.id);
    if(card){card.open=true;card.scrollIntoView({block:'nearest'});}
  }catch(e){await mcAlert(e.message||String(e),'Could not start review');}
  finally{if(button)button.disabled=false;}
}
async function mcReviewsRefresh(){
  clearTimeout(mcReviewTimer);
  var box=document.getElementById('cat-review-out');if(!box)return;
  var pending=true;
  try{
    var response=await fetch('/api/capability-reviews',{cache:'no-store'});
    if(!response.ok)throw Error('Could not load saved reviews.');
    var data=await response.json();
    pending=(data.reviews||[]).some(row=>row.state==='running');
    var error=box.querySelector('.mc-review-load-error');if(error)error.remove();
    (data.reviews||[]).forEach(function(row,index){
      var card=document.getElementById('review-'+row.id),stamp=JSON.stringify(row);
      if(card&&card._stamp===stamp)return;
      if(!card){card=document.createElement('details');card.className='mc-review-run';card.id='review-'+row.id;card.dataset.reviewId=row.id;card.open=index===0||row.state==='running';box.appendChild(card);}
      card._stamp=stamp;card._mcReviewData={url:row.url,key:row.key,review:row.result};
      var name=(row.result&&row.result.name)||row.url||row.key;
      card.innerHTML='<summary>'+mcCatEsc(name)+' · '+mcCatEsc(row.stage)+'</summary><div class="mc-review-body"></div>';
      var body=card.querySelector('.mc-review-body');
      if(row.state==='running')body.innerHTML='<p role="status"><span class="mc-catdots"><i></i><i></i><i></i></span> '+mcCatEsc(row.stage)+' You can leave this page; the review will continue.</p>';
      else if(row.state==='done')body.innerHTML='<p class="mc-review-meta">'+(row.cached?'Saved review reused. ':'')+(row.revision?'Version '+mcCatEsc(row.revision.slice(0,12))+'.':'Version could not be verified; a new review will not reuse this report.')+'</p>'+(row.result.html||'');
      else{
        var message=document.createElement('p');message.className='mc-ss-error';message.textContent=(row.result||{}).error||'Review failed.';body.appendChild(message);
        var retry=document.createElement('button');retry.className='btn btn-secondary';retry.textContent='Retry review';retry.onclick=function(){mcReviewStart(row.url,row.key,retry);};body.appendChild(retry);
      }
    });
  }catch(e){
    if(!box.querySelector('.mc-review-load-error')){
      var notice=document.createElement('p');notice.className='mc-review-load-error mc-ss-note';notice.textContent='Saved reviews are temporarily unavailable. Reconnecting…';box.prepend(notice);
    }
  }
  if(pending)mcReviewTimer=setTimeout(mcReviewsRefresh,2500);
}
mcReviewsRefresh();
