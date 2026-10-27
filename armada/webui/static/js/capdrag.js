// Only the changed card is refreshed; grant writes never wait for a provider login check.
function mcCapDragStart(e,id){e.dataTransfer.setData('text/plain',id);e.dataTransfer.effectAllowed='copy';}
function mcCapDragOver(e){e.preventDefault();e.dataTransfer.dropEffect='copy';e.currentTarget.classList.add('mc-cap-drop');}
function mcCapDragLeave(e){e.currentTarget.classList.remove('mc-cap-drop');}
async function mcCapAccess(card,cap,agent,remove){
  if(!card||card.dataset.saving||card.dataset.deleting)return;
  card.dataset.saving='1';card.setAttribute('aria-busy','true');
  var progress=document.createElement('span');progress.className='mc-cap-saving';progress.setAttribute('role','status');progress.textContent='Saving access…';card.appendChild(progress);
  try{
    var r=await(await fetch(remove?'/api/cap-revoke':'/api/cap-grant',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({agent:agent,capability:cap,inline:true})})).json();
    if(!r.ok)throw Error(r.error||'Could not save access.');
    if(r.availability){
      var summary=card.querySelector('.mc-cap-availability'),grants=card.querySelector('.mc-cap-grants');
      if(summary)summary.outerHTML=r.availability;
      if(grants)grants.innerHTML=r.grants;
      card.dataset.agents=r.agents;
      // Reuse provider status already checked on this card; no new health check is needed.
      card.querySelectorAll('.mc-conn-agent-state').forEach(function(chip){
        var badge=Array.from(card.querySelectorAll('.mc-conn-badge')).find(function(b){return b.dataset.provider===chip.dataset.provider;});
        if(badge&&badge.dataset.state){chip.dataset.state=badge.dataset.state;chip.textContent=badge.title;chip.title=badge.title;}
      });
      if(typeof mcCapFilter==='function')mcCapFilter();
    }
    if(r.coordinator)await mcAlert(r.detail||'The coordinator already has access.');
  }catch(e){await mcAlert(e.message||String(e),'Could not save access');}
  finally{delete card.dataset.saving;card.removeAttribute('aria-busy');progress.remove();}
}
function mcCapDrop(e,cap){e.preventDefault();mcCapDragLeave(e);var agent=e.dataTransfer.getData('text/plain');if(agent)mcCapAccess(e.currentTarget,cap,agent,false);}
function mcCapRemoveAgent(e,cap,agent){e.stopPropagation();e.preventDefault();mcCapAccess(e.target.closest('details.mc-cap'),cap,agent,true);}
