async function mcUploadRealmIcon(inp){const f=inp.files[0];if(!f)return;const m=document.getElementById('ri-msg');m.textContent='processing…';
  try{const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=URL.createObjectURL(f);});
  const S=128,c=document.createElement('canvas');c.width=S;c.height=S;const x=c.getContext('2d');x.imageSmoothingQuality='high';
  const side=Math.min(img.naturalWidth,img.naturalHeight);x.drawImage(img,(img.naturalWidth-side)/2,(img.naturalHeight-side)/2,side,side,0,0,S,S);
  const r=await(await fetch('/api/upload-realm-icon',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:c.toDataURL('image/png')})})).json();
  if(r.ok){location.reload();}else{m.textContent='error: '+(r.error||'failed');}}catch(e){m.textContent='error: '+e;}}
