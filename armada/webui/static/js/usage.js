(function(){
const INTERVALS={line:[["today","Today"],["7d","7D"],["mtd","MTD"]],
                 graph:[["daily","Daily"],["weekly","Weekly"],["monthly","Monthly"]]};
const DEFWIN={line:"7d",graph:"daily"};
// Remember the viewer's last usage view (mode + per-mode window + agents/models split) across visits.
const VKEY="mc_usage_view";
function loadView(){try{return JSON.parse(localStorage.getItem(VKEY))||{};}catch(e){return {};}}
function saveView(w){try{localStorage.setItem(VKEY,JSON.stringify(
  {mode:w._mode,winLine:w._winLine,winGraph:w._winGraph,by:w._by}));}catch(e){}}
function esc(s){return (s||"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function htok(n){n=+n||0;if(n>=1e6)return (n/1e6).toFixed(1)+"M";if(n>=1e3)return (n/1e3).toFixed(1)+"k";return ""+n;}
// Short-term client cache (sessionStorage) so jumping between sections within a few seconds reuses
// the last fetched usage/limits instead of re-fetching and re-showing skeletons. Each nav is a full
// page load (JS state is lost), so we persist to sessionStorage keyed by request; entries expire
// after CACHE_TTL, after which the next load refetches. Manual refresh + the 30-min tick force a miss.
const CACHE_TTL=30000;   // ms — "a matter of seconds" window where content stays put
const LIMITS_TTL=300000;
function limitsKey(k){return /^mc_uc_.*lim_v3$/.test(k)?k+'_'+(document.getElementById('mc-hdr-limits')?.dataset.appSession||''):k;}
function cacheGet(k,ttl=CACHE_TTL){try{const o=JSON.parse(sessionStorage.getItem(limitsKey(k)));
  if(ttl!==Infinity&&/^mc_uc_.*lim_v3$/.test(k)&&o&&(!o.d.available||o.d.stale))ttl=Math.min(ttl,30000);
  if(o&&(Date.now()-o.t)<ttl)return o.d;}catch(e){}return null;}
function cacheSet(k,d){try{sessionStorage.setItem(limitsKey(k),JSON.stringify({t:Date.now(),d:d}));}catch(e){}}
function uKey(mode,win,by){return "mc_uc_u_v2_"+mode+"_"+win+"_"+(by||"agents");}
async function fetchUsage(mode,win,by,force){const k=uKey(mode,win,by);
  if(!force){const c=cacheGet(k);if(c)return c;}
  try{const r=await(await fetch("/api/usage?mode="+mode+"&window="+win+"&by="+(by||"agents"))).json();if(r&&!r.error)cacheSet(k,r);return r;}catch(e){return {error:String(e)};}}
// Real account-wide subscription usage. Missing readings stay visible as gray placeholders.
const limitsRequests={};
function fetchProviderLimits(provider,key,force){
  const cached=!force&&cacheGet(key,LIMITS_TTL);if(cached)return Promise.resolve(cached);
  if(limitsRequests[provider])return limitsRequests[provider];
  const request=(async()=>{let timer,controller=new AbortController();
    const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(Error('Usage check timed out.'));},60000);});
    try{
      const poll=async()=>{let first=true;
        for(;;){
          const response=await fetch('/api/usage-limits?provider='+provider+(first&&force?'&force=1':''),{signal:controller.signal});first=false;
          if(!response.ok)throw Error('Usage check failed');
          const data=await response.json();if(!data||typeof data.available!=='boolean')throw Error('Invalid usage response');
          if(!data.pending)return data;
          await new Promise(resolve=>setTimeout(resolve,1000));
          if(controller.signal.aborted)throw Error('Usage check timed out.');
        }};
      const data=await Promise.race([poll(),deadline]);cacheSet(key,data);return data;
    }catch(e){const previous=cacheGet(key,Infinity);
      const data={...(previous&&previous.available?previous:{}),available:!!(previous&&previous.available),stale:!!(previous&&previous.available),
        connected:previous&&previous.connected,reason:'error',message:e.message||'Usage is temporarily unavailable.'};
      cacheSet(key,data);return data;
    }finally{clearTimeout(timer);controller.abort();}})();
  limitsRequests[provider]=request;request.finally(()=>{delete limitsRequests[provider];});return request;
}
function fetchLimits(force){return fetchProviderLimits('claude','mc_uc_lim_v3',force);}
function limClr(p){return p>=90?"var(--status-bad)":p>=70?"var(--status-warn)":"var(--color-accent-2)";}
// How old a reading is, in the fewest words that stay honest.
function limAge(s){const m=Math.floor((s||0)/60);if(m<60)return Math.max(m,1)+" min ago";
  const h=Math.floor(m/60);return h<48?h+"h ago":Math.floor(h/24)+"d ago";}
function fetchCodexLimits(force){return fetchProviderLimits('codex','mc_uc_openai_lim_v3',force);}
function limitRowHTML(provider,period,w,d){
  if(d&&d.loading)return '<div class="mc-limit-row is-loading" aria-busy="true">'
    +'<span class="mc-limit-loading" role="status" aria-label="Loading '+provider+' '+period.toLowerCase()+' limit">'
    +'<i aria-hidden="true"></i><i aria-hidden="true"></i><i aria-hidden="true"></i></span></div>';
  const known=w&&typeof w.pct==='number'&&Number.isFinite(w.pct);
  const available=!!(d&&d.available&&!d.stale&&known);
  const p=known?Math.max(0,Math.min(100,w.pct)):null;
  const reset=available&&w.resets_in?w.resets_in:'';
  let reason=(d&&d.message)||provider+' usage is unavailable right now.';
  if(d&&d.stale&&known)reason='Last reading: '+p+'%, '+limAge(d.age_sec)+'. '+reason;
  else if(d&&d.available&&!w)reason=provider+' does not report a '+period.toLowerCase()+' limit for this account.';
  const description=provider+' · '+period+' · '+(available?p+'% used'+(reset?' · resets in '+reset:''):reason);
  return '<div class="mc-limit-row'+(available?'':' is-unavailable')+'" title="'+esc(description)+'"'+(available?'':' tabindex="0"')+'>'
    +'<span class="mc-limit-bar" role="'+(available?'meter':'img')+'" aria-label="'+esc(description)+'"'
    +(available?' aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+p+'"':'')+'>'
    +(available?'<i style="width:'+p+'%;background:'+limClr(p)+'"></i>':'')+'</span>'
    +(available?'<span class="mc-limit-text"><span class="mc-limit-pct">'+p+'%</span>'
      +(reset?'<span class="mc-limit-reset">resets in '+esc(reset)+'</span>':'')+'</span>':
      '<span class="mc-limit-unavailable">'+(d&&d.stale&&known?p+'% · last reading':d&&d.reason==='disconnected'?'Disconnected':d&&d.available&&!known?'Not reported':'Unavailable')+'</span>')+'</div>';
}
function headerLimitsHTML(claude,codex,bucket,gemini){
  const groups=codex&&codex.available&&Array.isArray(codex.groups)?codex.groups:[];
  const g=groups.find(g=>g.id===bucket)||groups[0];
  const windows=g&&Array.isArray(g.windows)?g.windows:[];
  // Primary can be weekly (and secondary null). Classify by duration, never array position.
  const weekly=windows.find(w=>w.window_minutes===10080||w.label==='Weekly');
  const session=windows.find(w=>w.window_minutes>0&&w.window_minutes<1440||w.label==='5h window');
  let select='';
  if(groups.length>1)select='<select aria-label="Codex usage bucket">'
    +groups.map(x=>'<option value="'+esc(x.id)+'"'+(x.id===g.id?' selected':'')+'>'+esc(x.name)+'</option>').join('')+'</select>';
  return '<div class="mc-limits-title">Subscription limits</div><div class="mc-limit-groups">'
    +'<div class="mc-limit-periods" aria-hidden="true"><span class="mc-limit-label">Week</span><span class="mc-limit-label">Session</span></div>'
    +[['Codex',weekly,session,codex],['Claude',claude&&claude.weekly,claude&&claude.session,claude],
      ['Gemini',gemini&&gemini.weekly,null,gemini||{available:false,message:'Checking Gemini connection…'}]].map(([provider,week,session,d])=>
      '<div class="mc-limit-group'+(d&&d.loading?' is-loading':!d||!(d.connected??d.available)?' is-inactive':'')+(d&&d.placeholder?' is-placeholder':'')+'" role="group" aria-label="'+provider+' subscription limits"'+(d&&d.loading?' aria-busy="true"':'')+(d&&d.placeholder?' title="Gemini support is planned; not available yet."':'')+'>'
      +'<div class="mc-limit-group-head"><span class="mc-limit-provider" role="img" aria-label="'+provider+'" title="'+provider+'">'
      +(window.mcProviderLogo?window.mcProviderLogo(provider.toLowerCase(),16,!!(d&&(d.connected??d.available))):window.mcIcon(provider.toLowerCase(),16))+'</span></div>'
      +limitRowHTML(provider,'Week',week,d)+limitRowHTML(provider,'Session',session,d)+(provider==='Codex'?select:'')+'</div>').join('')+'</div>';
}
let limitsData={},limitsGeneration=0;
async function renderHeaderLimits(force){
  const el=document.getElementById('mc-hdr-limits');if(!el)return;
  const generation=++limitsGeneration,codexEnabled=el.dataset.codexEnabled==='true';
  // Only fresh cached data is ready to display. Pending requests get dots, not
  // unavailable bars or old readings that look current during a forced refresh.
  for(const [provider,key] of [['claude','mc_uc_lim_v3'],['codex','mc_uc_openai_lim_v3'],['gemini','mc_uc_gemini_lim_v3']]){
    // Keep the last reading during a background refresh; dots are only for the first load.
    const landmark=el.querySelector('.mc-engine-logo[data-provider="'+provider+'"]');
    limitsData[provider]=cacheGet(key,Infinity)||{loading:true,connected:!!(landmark&&landmark.classList.contains('is-connected'))};
  }
  if(!codexEnabled)limitsData.codex={available:false,message:'Codex is not enabled for this realm.'};
  function paint(){
    if(generation!==limitsGeneration)return;
    el.innerHTML=headerLimitsHTML(limitsData.claude,limitsData.codex,cacheGet('mc_openai_bucket'),limitsData.gemini);
    const sel=el.querySelector('select');if(sel)sel.onchange=()=>{cacheSet('mc_openai_bucket',sel.value);paint();};
  }
  paint();
  // Paint each result as it arrives: a slow provider must not hide the other's reading.
  const geminiRequest=fetchProviderLimits('gemini','mc_uc_gemini_lim_v3',force);
  await Promise.all([['claude',fetchLimits(force)],['gemini',geminiRequest],...(codexEnabled?[['codex',fetchCodexLimits(force)]]:[])].map(async ([provider,request])=>{
    const d=await request;if(generation!==limitsGeneration)return;limitsData[provider]=d||{available:false};paint();
  }));
}
// Keep the Overview header's Tokens/30d + API-eq KPIs in sync with live usage (they're static at page
// load otherwise). Called from render(), which runs on init, the 30-min tick, manual refresh and refreshAll.
function fixHeaderTotals(d){
  if(!d||!("total_30d" in d))return;
  cacheSet("mc_uc_h30",{total_30d:d.total_30d,usd_30d:d.usd_30d,
    unknown_token_runs_30d:d.unknown_token_runs_30d,unknown_cost_runs_30d:d.unknown_cost_runs_30d});
  const tk=document.getElementById("mc-kpi-tokens"),ap=document.getElementById("mc-kpi-apieq");
  if(tk){tk.textContent=d.total_30d!=null?htok(d.total_30d)+(d.unknown_token_runs_30d?'+':''):"—";
    tk.title='Reported tokens'+(d.unknown_token_runs_30d?'; partial total: '+d.unknown_token_runs_30d+' run(s) did not report tokens':'');}
  if(ap){ap.textContent=d.usd_30d!=null?"≈$"+Math.round(d.usd_30d).toLocaleString()+(d.unknown_cost_runs_30d?'+':''):"—";
    ap.title='Approximate standard-text API equivalent across all engines; excludes tool fees and long-context surcharges'+
      (d.unknown_cost_runs_30d?'; partial total: '+d.unknown_cost_runs_30d+' run(s) have unavailable accounting':'');}}
// Fallback: replace any header KPI still showing its loading skeleton with the value the server
// embedded in data-v. Covers a slow/failed usage fetch or a dashboard with the Usage widget removed,
// so the skeleton never gets stuck. A successful fetch fills the value first, making this a no-op.
function mcHeaderFallback(){["mc-kpi-tokens","mc-kpi-apieq"].forEach(function(id){
  const el=document.getElementById(id);if(el&&el.querySelector(".mc-skel"))el.textContent=el.getAttribute("data-v")||"—";});}
function drawLine(body,d,by){
  by=(by==="models")?"models":"agents";
  const items=((by==="models")?d.models:d.agents)||[];
  if(!d.total&&(by!=="models"||!items.length)){body.innerHTML='<div style="padding:22px 14px;font-size:12.5px;color:var(--text-muted)">'+(d.unknown_runs?'Token usage is unavailable for '+d.unknown_runs+' run(s).':'No usage in this window yet.')+'</div>';return;}
  // overall bar = segments of the SELECTED dimension (agents or models), each in its colour and
  // proportional to its usage, with a 2px bg-coloured divider so adjacent similar colours read apart
  const _segs=items.filter(x=>x.tok);
  let seg="";_segs.forEach((x,i)=>{const w=x.tok/d.total*100;const div=(i<_segs.length-1)?';border-right:2px solid var(--color-bg)':'';
    seg+='<div title="'+esc((x.name||x.label)+" · "+htok(x.tok))+'" style="box-sizing:border-box;width:'+w.toFixed(2)+'%;background:'+esc(x.color||'var(--color-accent)')+div+'"></div>';});
  const usd=d.usd?(" · api-equiv $"+d.usd.toLocaleString()):"";
  let h='<div style="padding:12px 14px 10px"><div style="display:flex;align-items:baseline;gap:8px">'
   +'<span style="font-family:var(--font-heading);font-weight:700;font-size:26px;line-height:1">'+htok(d.total)+'</span>'
   +'<span style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)">'+(d.unknown_runs?'reported tokens · '+d.unknown_runs+' run(s) unavailable':'tokens · all agents, System &amp; models')+usd+'</span></div>'
   +'<div style="display:flex;height:10px;border-radius:6px;overflow:hidden;margin-top:8px;background:var(--color-neutral-200)">'+seg+'</div></div>';
  function rows(title,items,colorFn){
    const mx=Math.max(1,...items.map(x=>x.tok));let r="";
    items.forEach((x,i)=>{const w=x.tok/mx*100;const c=colorFn(x,i);
      // System (ARMADA's own use) closes the agent list, set apart by a hairline
      const sys=!!x.system,tt=sys?"System · ARMADA's own use: system jobs and Alexander":(x.description||x.name||x.label);
      const provider=x.provider||(x.claude?"claude":"");
      r+='<div'+(sys?' data-usage-system="1"':'')+' style="display:flex;align-items:center;gap:8px;margin:5px 0'+(sys?';padding-top:6px;border-top:1px dashed var(--color-divider)':'')+'">'
        +'<span style="flex:0 0 108px;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;font-family:var(--font-heading);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+esc(tt)+'">'
        +(provider&&window.mcIcon?'<span class="mc-model-icon" style="color:'+esc(x.color)+';display:flex;flex:none">'+window.mcIcon(provider,13)+'</span>'
           :(x.color?'<i style="width:9px;height:9px;border-radius:2px;flex:none;background:'+esc(x.color)+'"></i>':""))
        +'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(x.name||x.label)+'</span></span>'
        +'<div style="flex:1;height:8px;border-radius:5px;background:var(--color-neutral-200);overflow:hidden"><div style="width:'+w.toFixed(1)+'%;height:100%;background:'+esc(c)+'"></div></div>'
        +'<span style="flex:0 0 auto;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--text-65)">'+htok(x.tok)+'</span></div>';});
    return '<div style="padding:2px 14px 12px"><div'+(by==="models"?' title="Used models first; within each group, highest estimated quota impact first. Colours indicate relative model cost, not measured subscription charges."':'')+' style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--text-soft);margin:6px 0 6px">'+title+'</div>'+r+'</div>';}
  h+=rows(by==="models"?"By model":"By agent",items,(x)=>x.color||'var(--color-accent)');
  body.innerHTML=h;}
function drawGraph(body,d){
  const bars=d.bars||[];const mx=Math.max(1,...bars.map(b=>b.tok));
  const sub=(d.window==="monthly")?"last 12 months":(d.window==="weekly")?"last 8 weeks":"last 7 days";
  // smaller than before so it fits narrow windows; width still tracks the widget, capped so it
  // doesn't sprawl on wide ones.
  const H=196,pad=12,base=H-20,top=16;
  const W=Math.max(336,(body.clientWidth||480)-16),gap=(W-pad*2)/bars.length,bw=Math.min(64,gap*0.66);
  let svg="";
  bars.forEach((b,i)=>{const x=pad+i*gap+(gap-bw)/2;
    const fullh=b.tok?Math.max(2,(base-top)*b.tok/mx):0;let y=base;
    (b.segments||[]).forEach(s=>{const sh=(base-top)*s.tok/mx;y-=sh;
      svg+='<rect class="mc-bar" data-tip="'+esc(s.name+" · "+htok(s.tok))+'" x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+Math.max(0.6,sh).toFixed(1)+'" fill="'+esc(s.color)+'"></rect>';});
    if(b.tok)svg+='<text x="'+(x+bw/2).toFixed(1)+'" y="'+(base-fullh-5).toFixed(1)+'" text-anchor="middle" font-size="9.5" fill="var(--text-dim)">'+htok(b.tok)+'</text>';
    svg+='<text x="'+(x+bw/2).toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle" font-size="9.5" fill="var(--text-muted)">'+esc(b.label)+'</text>';});
  let h='<div style="padding:12px 14px 6px"><div style="display:flex;align-items:baseline;gap:8px">'
   +'<span style="font-family:var(--font-heading);font-weight:700;font-size:22px;line-height:1">'+htok(d.total)+'</span>'
   +'<span style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)">'+(d.unknown_runs?'reported tokens · '+d.unknown_runs+' run(s) unavailable · ':'tokens · ')+sub+' · by '+(d.by==="models"?"model":"agent")+'</span></div></div>';
  h+='<div style="padding:0 8px 14px"><svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'" style="display:block;height:'+H+'px">'
   +'<line x1="'+pad+'" y1="'+base+'" x2="'+(W-pad)+'" y2="'+base+'" stroke="var(--color-divider)" stroke-width="1"/>'+svg+'</svg></div>';
  if(!d.total)h+='<div style="padding:0 14px 14px;font-size:12px;color:var(--text-soft)">'+(d.unknown_runs?'Token usage is unavailable for '+d.unknown_runs+' run(s).':'No usage in this period yet.')+'</div>';
  body.innerHTML=h;
  // custom follow-cursor tooltip (native SVG <title> is unreliable in the embedded webview)
  const svgEl=body.querySelector("svg");if(!svgEl)return;
  let tip=body.querySelector(".mc-graph-tip");
  if(!tip){tip=document.createElement("div");tip.className="mc-graph-tip";
    tip.style.cssText="position:fixed;z-index:200;pointer-events:none;display:none;background:#1e1e28;color:#fff;font-size:11px;padding:3px 8px;border-radius:6px;box-shadow:var(--shadow-md);white-space:nowrap";
    document.body.appendChild(tip);}
  svgEl.addEventListener("mousemove",e=>{const r=e.target.closest?e.target.closest("rect.mc-bar"):null;
    if(r&&r.dataset.tip){tip.textContent=r.dataset.tip;tip.style.display="block";tip.style.left=(e.clientX+12)+"px";tip.style.top=(e.clientY+12)+"px";}
    else tip.style.display="none";});
  svgEl.addEventListener("mouseleave",()=>{tip.style.display="none";});}
const MC_SEL="var(--text-9)";      // grey selected pill (model-chip style)
const MC_MUT="var(--text-muted)";
function grp(items,active,cls,attr){
  return items.map(([k,lb])=>{const on=k===active;
    return '<button class="'+cls+'" '+attr+'="'+k+'" style="border:0;border-radius:var(--r);cursor:pointer;font-size:11px;padding:4px 10px;line-height:1;background:'+(on?MC_SEL:"transparent")+';color:'+(on?"var(--color-text)":MC_MUT)+'">'+lb+'</button>';}).join("");}
function paintTB(w){
  const modeWrap=w.querySelector(".mc-usage-tb");if(!modeWrap)return;
  modeWrap.querySelectorAll(".mc-um").forEach(b=>{const on=b.dataset.um===w._mode;b.style.background=on?MC_SEL:"transparent";b.style.color=on?"var(--color-text)":"var(--text-faint)";});
  const ic=w.querySelector(".mc-usage-intervals");
  const cw=w._mode==="graph"?w._winGraph:w._winLine;
  ic.innerHTML=grp(INTERVALS[w._mode],cw,"mc-ui","data-ui");
  ic.querySelectorAll(".mc-ui").forEach(b=>b.addEventListener("click",e=>{e.stopPropagation();if(w._mode==="graph")w._winGraph=b.dataset.ui;else w._winLine=b.dataset.ui;saveView(w);render(w);}));
  // Agents vs Models breakdown toggle — shown in BOTH line and graph views, to the left of the interval group
  let bc=w.querySelector(".mc-usage-by");
  if(!bc){bc=document.createElement("div");bc.className="mc-usage-by";
    bc.style.cssText="display:flex;gap:2px;margin-left:12px";
    const ic=w.querySelector(".mc-usage-intervals");ic.parentNode.insertBefore(bc,ic);}
  bc.style.display="flex";
  bc.innerHTML=grp([["agents","Agents"],["models","Models"]],w._by,"mc-uby","data-uby");
  bc.querySelectorAll(".mc-uby").forEach(b=>b.addEventListener("click",e=>{e.stopPropagation();w._by=b.dataset.uby;saveView(w);render(w);}));}
async function render(w,force){paintTB(w);const body=w.querySelector(".mc-usage-body");
  const cw=w._mode==="graph"?w._winGraph:w._winLine;
  // Warm cache (rapid tab-switching): paint synchronously from the last fetch — no "Loading…", no
  // skeleton, no network — so the content stays put. Skipped on a forced refresh.
  if(!force){const c=cacheGet(uKey(w._mode,cw,w._by));
    if(c){fixHeaderTotals(c);w._lastD=c;if(body){if(w._mode==="graph")drawGraph(body,c);else drawLine(body,c,w._by);}return;}}
  if(body)body.innerHTML='<div style="padding:16px;font-size:12px;color:var(--text-soft)">Loading…</div>';
  const d=await fetchUsage(w._mode,cw,w._by,force);if(!body)return;
  if(d.error){body.innerHTML='<div style="padding:16px;font-size:12px;color:var(--status-bad)">'+esc(d.error)+'</div>';return;}
  fixHeaderTotals(d);                                    // sync the header Tokens/30d + API-eq KPIs
  w._lastD=d;                                            // remember for a redraw on widget resize
  if(w._mode==="graph")drawGraph(body,d);else drawLine(body,d,w._by);}
function setup(w){if(w._us)return;w._us=1;
  const v=loadView();                                   // restore the viewer's last usage view
  w._mode=(v.mode==="graph")?"graph":"line";
  const lineWins=INTERVALS.line.map(x=>x[0]),graphWins=INTERVALS.graph.map(x=>x[0]);
  w._winLine=lineWins.includes(v.winLine)?v.winLine:DEFWIN.line;
  w._winGraph=graphWins.includes(v.winGraph)?v.winGraph:DEFWIN.graph;
  w._by=(v.by==="models")?"models":"agents";
  w.querySelectorAll(".mc-um").forEach(b=>b.addEventListener("click",e=>{e.stopPropagation();if(w._mode===b.dataset.um)return;w._mode=b.dataset.um;saveView(w);render(w);}));
  const rb=w.querySelector(".mc-usage-refresh");
  if(rb)rb.addEventListener("click",async e=>{e.stopPropagation();const ic=rb.querySelector("svg,span");if(ic){ic.style.transition="transform .5s";ic.style.transform="rotate(360deg)";setTimeout(()=>{ic.style.transition="";ic.style.transform="";},520);}
    await Promise.all([render(w,true),renderHeaderLimits(true)]);});   // manual refresh = force a fresh fetch
  // redraw the graph when the widget is resized so it always spans the full width (no refetch)
  const body=w.querySelector(".mc-usage-body");
  if(body&&window.ResizeObserver){let rw=body.clientWidth,t=null;
    new ResizeObserver(()=>{if(w._mode!=="graph"||!w._lastD)return;const nw=body.clientWidth;if(Math.abs(nw-rw)<8)return;rw=nw;
      clearTimeout(t);t=setTimeout(()=>{if(w._mode==="graph"&&w._lastD)drawGraph(body,w._lastD);},90);}).observe(body);}
  render(w);}
// Re-render every set-up widget so colour/usage edits made elsewhere show without a manual reload.
// force=false respects the short-term cache (quick tab-out/return stays put); the 30-min tick forces.
function refreshAll(force){document.querySelectorAll(".mc-usage").forEach(w=>{if(w._us)render(w,force);});renderHeaderLimits(force);}
let _wired=false;
function init(){
  const usageWidgets=document.querySelectorAll(".mc-usage");
  // Warm nav: fill the header KPIs synchronously from the cached 30-day totals BEFORE anything async,
  // so a quick return to Overview shows the numbers instantly (no skeleton flash).
  // Server-rendered totals are current and already visible; avoid replacing them with stale cache.
  usageWidgets.forEach(setup);
  // Header KPI skeletons: if a Usage widget is present it fills them via render()->fixHeaderTotals;
  // otherwise (or if that fetch stalls) drop back to the server-embedded value so nothing stays loading.
  if(!usageWidgets.length)mcHeaderFallback();else setTimeout(mcHeaderFallback,4000);
  renderHeaderLimits();                                 // Both providers share the same week/session layout.
  if(_wired)return; _wired=true;
  // refresh when the dashboard becomes visible again (e.g. back from Configure) or is restored from cache.
  // These are non-forcing, so within the cache window they repaint from cache (content stays put).
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshAll();});
  window.addEventListener("pageshow",e=>{if(e.persisted)refreshAll();});
  window.addEventListener("focus",()=>refreshAll());
  setInterval(()=>{if(!document.hidden)refreshAll(true);},1800000);   // auto-refresh every 30 min (forces a fresh fetch)
  setInterval(()=>{if(!document.hidden)renderHeaderLimits();},30000);
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
