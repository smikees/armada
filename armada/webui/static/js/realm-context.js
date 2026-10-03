// The identity belongs to this document, never to a later response or another tab's selection.
(function(){
  const meta=document.querySelector('meta[name="armada-realm"]');
  if(!meta)return;
  const realm=meta.content, nativeFetch=window.fetch.bind(window);
  window.mcRealmId=realm;
  const local=u=>u.origin===location.origin&&!u.pathname.startsWith('/static/');
  function bound(value){
    const u=new URL(value,location.href);
    if(local(u)&&!u.pathname.startsWith('/r/')&&!u.searchParams.has('_realm'))u.searchParams.set('_realm',realm);
    return u;
  }
  window.mcRealmUrl=value=>bound(value).href;
  window.fetch=async function(input,init){
    const request=input instanceof Request?input:null;
    const u=new URL(request?request.url:input,location.href);
    if(!local(u))return nativeFetch(input,init);
    const options={...(init||{})}, headers=new Headers(options.headers||(request&&request.headers)||{});
    headers.set('X-Armada-Realm',realm);
    options.headers=headers;
    const response=await nativeFetch(input,options);
    if(response.status===409){
      let error;try{error=await response.clone().json();}catch(e){}
      if(error&&error.code==='realm_mismatch'){
        if(window.mcToast)window.mcToast(error.error,'error');
        throw new Error(error.error); // callers must not treat a stale save as successful
      }
    }
    return response;
  };
  document.addEventListener('click',function(event){
    const link=event.target.closest&&event.target.closest('a[href]');
    if(!link||link.getAttribute('href').startsWith('#'))return;
    const u=new URL(link.href,location.href);
    // Switching is an explicit selection action, including notification links to another realm.
    if(local(u)&&u.pathname!=='/switch')link.href=bound(link.href).href;
  },true);
  document.addEventListener('submit',function(event){
    const form=event.target;
    if(form&&form.action&&local(new URL(form.action,location.href)))form.action=bound(form.action).href;
  },true);
})();
