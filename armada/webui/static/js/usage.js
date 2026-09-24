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
function cacheGet(k){try{const o=JSON.parse(sessionStorage.getItem(k));if(o&&(Date.now()-o.t)<CACHE_TTL)return o.d;}catch(e){}return null;}
function cacheSet(k,d){try{sessionStorage.setItem(k,JSON.stringify({t:Date.now(),d:d}));}catch(e){}}
function uKey(mode,win,by){return "mc_uc_u_"+mode+"_"+win+"_"+(by||"agents");}
async function fetchUsage(mode,win,by,force){const k=uKey(mode,win,by);
  if(!force){const c=cacheGet(k);if(c)return c;}
  try{const r=await(await fetch("/api/usage?mode="+mode+"&window="+win+"&by="+(by||"agents"))).json();if(r&&!r.error)cacheSet(k,r);return r;}catch(e){return {error:String(e)};}}
// Real Claude subscription usage (session 5h + weekly, % of limit) — the same numbers as the Claude
// app's Usage view. Read-only/best-effort; hidden when the local token is expired or unavailable.
async function fetchLimits(force){if(!force){const c=cacheGet("mc_uc_lim");if(c)return c;}
  try{const r=await(await fetch("/api/usage-limits")).json();if(r)cacheSet("mc_uc_lim",r);return r;}
  catch(e){return {available:false,reason:"error",message:"Usage is temporarily unavailable."};}}
function limClr(p){return p>=90?"var(--status-bad)":p>=70?"var(--status-warn)":"var(--color-accent-2)";}
function limRow(lb,w){
  if(!w)return "";
  const p=Math.max(0,Math.min(100,w.pct||0));
  const rin=w.resets_in?(" · resets in "+esc(w.resets_in)):"";
  return '<div style="display:flex;align-items:center;gap:8px;margin:6px 0">'
    +'<span style="flex:0 0 128px;font-size:12px;font-weight:600;font-family:var(--font-heading);white-space:nowrap">'+esc(lb)+'</span>'
    +'<div style="flex:1;height:8px;border-radius:5px;background:var(--color-neutral-200);overflow:hidden"><div style="width:'+p+'%;height:100%;background:'+limClr(p)+'"></div></div>'
    +'<span style="flex:0 0 auto;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--text-muted)">'+p+'%'+rin+'</span></div>';}
// Compact limit row for the Overview header.
function limRowH(lb,w){
  if(!w)return "";
  const p=Math.max(0,Math.min(100,w.pct||0));
  const rin=w.resets_in?(" · resets in "+esc(w.resets_in)):"";
  // Both columns are FIXED, not flexible. A label that shrinks to fit means the two rows start
  // their bars at different x, which reads as a wonky layout rather than as two different-length
  // words. The trailing text keeps flex:none too: "resets in 5d 17" is not a duration.
  return '<div style="display:flex;align-items:center;gap:8px;line-height:1.4">'
    +'<span style="flex:0 0 128px;font-size:12px;font-weight:600;font-family:var(--font-heading);white-space:nowrap">'+esc(lb)+'</span>'
    +'<div style="flex:0 0 70px;height:6px;border-radius:4px;background:var(--color-neutral-200);overflow:hidden"><div style="width:'+p+'%;height:100%;background:'+limClr(p)+'"></div></div>'
    +'<span style="flex:0 0 auto;font-family:ui-monospace,Menlo,monospace;font-size:10.5px;color:var(--text-muted);white-space:nowrap"><span style="display:inline-block;min-width:30px">'+p+'%</span>'+rin+'</span></div>';}
// How old a reading is, in the fewest words that stay honest.
function limAge(s){const m=Math.floor((s||0)/60);if(m<60)return Math.max(m,1)+" min ago";
  const h=Math.floor(m/60);return h<48?h+"h ago":Math.floor(h/24)+"d ago";}
function headerLimitsHTML(d){
  // Always say something. Rendering "" here is what made the header go silently blank — no bars and
  // no reason — when the stored token was emptied. The server supplies the wording per reason.
  if(!d||!d.available){
    const msg=(d&&d.message)||"Claude usage is unavailable right now.";
    return '<div style="font-size:10.5px;color:var(--text-muted);line-height:1.45;max-width:330px">'+esc(msg)+'</div>';}
  // A remembered reading still shows its numbers — they were real — but says how old they are and
  // fades, so nobody plans a long run against a figure from this morning. Past six hours the label
  // stops implying currency at all.
  const st=!!d.stale, age=d.age_sec||0, old=st&&age>6*3600;
  const head=st?("Claude limits · "+limAge(age)+(old?" · may have moved":""))
                :"Claude subscription limits";
  const dim=st?(old?"opacity:.55":"opacity:.75"):"";
  return '<div style="'+dim+'"><div style="font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--text-muted);margin-bottom:3px">'+esc(head)+'</div>'
    +limRowH("Current session · 5h",d.session)+limRowH("Current week",d.weekly)+'</div>';}
async function renderHeaderLimits(){
  const el=document.getElementById("mc-hdr-limits");if(!el)return;
  el.innerHTML=headerLimitsHTML(await fetchLimits());}
// Keep the Overview header's Tokens/30d + API-eq KPIs in sync with live usage (they're static at page
// load otherwise). Called from render(), which runs on init, the 30-min tick, manual refresh and refreshAll.
function fixHeaderTotals(d){
  if(!d||typeof d.total_30d!=="number")return;
  cacheSet("mc_uc_h30",{total_30d:d.total_30d,usd_30d:d.usd_30d});   // let a warm nav fill KPIs instantly
  const tk=document.getElementById("mc-kpi-tokens");if(tk)tk.textContent=d.total_30d?htok(d.total_30d):"—";
  const ap=document.getElementById("mc-kpi-apieq");if(ap)ap.textContent=d.usd_30d?("≈$"+Math.round(d.usd_30d).toLocaleString()):"—";}
// Fallback: replace any header KPI still showing its loading skeleton with the value the server
// embedded in data-v. Covers a slow/failed usage fetch or a dashboard with the Usage widget removed,
// so the skeleton never gets stuck. A successful fetch fills the value first, making this a no-op.
function mcHeaderFallback(){["mc-kpi-tokens","mc-kpi-apieq"].forEach(function(id){
  const el=document.getElementById(id);if(el&&el.querySelector(".mc-skel"))el.textContent=el.getAttribute("data-v")||"—";});}
function drawLine(body,d,by){
  if(!d.total){body.innerHTML='<div style="padding:22px 14px;font-size:12.5px;color:var(--text-muted)">No usage in this window yet.</div>';return;}
  by=(by==="models")?"models":"agents";
  const items=((by==="models")?d.models:d.agents)||[];
  // overall bar = segments of the SELECTED dimension (agents or models), each in its colour and
  // proportional to its usage, with a 2px bg-coloured divider so adjacent similar colours read apart
  const _segs=items.filter(x=>x.tok);
  let seg="";_segs.forEach((x,i)=>{const w=x.tok/d.total*100;const div=(i<_segs.length-1)?';border-right:2px solid var(--color-bg)':'';
    seg+='<div title="'+esc((x.name||x.label)+" · "+htok(x.tok))+'" style="box-sizing:border-box;width:'+w.toFixed(2)+'%;background:'+esc(x.color||'var(--color-accent)')+div+'"></div>';});
  const usd=d.usd?(" · api-equiv $"+d.usd.toLocaleString()):"";
  let h='<div style="padding:12px 14px 10px"><div style="display:flex;align-items:baseline;gap:8px">'
   +'<span style="font-family:var(--font-heading);font-weight:700;font-size:26px;line-height:1">'+htok(d.total)+'</span>'
   +'<span style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)">tokens · all agents &amp; models'+usd+'</span></div>'
   +'<div style="display:flex;height:10px;border-radius:6px;overflow:hidden;margin-top:8px;background:var(--color-neutral-200)">'+seg+'</div></div>';
  function rows(title,items,colorFn){
    const mx=Math.max(1,...items.map(x=>x.tok));let r="";
    items.forEach((x,i)=>{const w=x.tok/mx*100;const c=colorFn(x,i);
      r+='<div style="display:flex;align-items:center;gap:8px;margin:5px 0">'
        +'<span style="flex:0 0 108px;display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;font-family:var(--font-heading);white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+esc(x.name||x.label)+'">'
        +(x.claude&&window.mcIcon?'<span style="color:'+esc(x.color)+';display:flex;flex:none">'+window.mcIcon("claude",13)+'</span>'
           :(x.color?'<i style="width:9px;height:9px;border-radius:2px;flex:none;background:'+esc(x.color)+'"></i>':""))
        +'<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(x.name||x.label)+'</span></span>'
        +'<div style="flex:1;height:8px;border-radius:5px;background:var(--color-neutral-200);overflow:hidden"><div style="width:'+w.toFixed(1)+'%;height:100%;background:'+esc(c)+'"></div></div>'
        +'<span style="flex:0 0 auto;font-family:ui-monospace,Menlo,monospace;font-size:11px;color:color-mix(in srgb,var(--color-text) 65%,transparent)">'+htok(x.tok)+'</span></div>';});
    return '<div style="padding:2px 14px 12px"><div style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:color-mix(in srgb,var(--color-text) 50%,transparent);margin:6px 0 6px">'+title+'</div>'+r+'</div>';}
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
    if(b.tok)svg+='<text x="'+(x+bw/2).toFixed(1)+'" y="'+(base-fullh-5).toFixed(1)+'" text-anchor="middle" font-size="9.5" fill="color-mix(in srgb,var(--color-text) 60%,transparent)">'+htok(b.tok)+'</text>';
    svg+='<text x="'+(x+bw/2).toFixed(1)+'" y="'+(H-6)+'" text-anchor="middle" font-size="9.5" fill="var(--text-muted)">'+esc(b.label)+'</text>';});
  let h='<div style="padding:12px 14px 6px"><div style="display:flex;align-items:baseline;gap:8px">'
   +'<span style="font-family:var(--font-heading);font-weight:700;font-size:22px;line-height:1">'+htok(d.total)+'</span>'
   +'<span style="font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)">tokens · '+sub+' · by '+(d.by==="models"?"model":"agent")+'</span></div></div>';
  h+='<div style="padding:0 8px 14px"><svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'" style="display:block;height:'+H+'px">'
   +'<line x1="'+pad+'" y1="'+base+'" x2="'+(W-pad)+'" y2="'+base+'" stroke="var(--color-divider)" stroke-width="1"/>'+svg+'</svg></div>';
  if(!d.total)h+='<div style="padding:0 14px 14px;font-size:12px;color:color-mix(in srgb,var(--color-text) 50%,transparent)">No usage in this period yet.</div>';
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
const MC_SEL="color-mix(in srgb,var(--color-text) 9%,transparent)";      // grey selected pill (model-chip style)
const MC_MUT="var(--text-muted)";
function grp(items,active,cls,attr){
  return items.map(([k,lb])=>{const on=k===active;
    return '<button class="'+cls+'" '+attr+'="'+k+'" style="border:0;border-radius:var(--r);cursor:pointer;font-size:11px;padding:4px 10px;line-height:1;background:'+(on?MC_SEL:"transparent")+';color:'+(on?"var(--color-text)":MC_MUT)+'">'+lb+'</button>';}).join("");}
function paintTB(w){
  const modeWrap=w.querySelector(".mc-usage-tb");if(!modeWrap)return;
  modeWrap.querySelectorAll(".mc-um").forEach(b=>{const on=b.dataset.um===w._mode;b.style.background=on?MC_SEL:"transparent";b.style.color=on?"var(--color-text)":"color-mix(in srgb,var(--color-text) 45%,transparent)";});
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
  if(body)body.innerHTML='<div style="padding:16px;font-size:12px;color:color-mix(in srgb,var(--color-text) 50%,transparent)">Loading…</div>';
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
  const h=cacheGet("mc_uc_h30");if(h)fixHeaderTotals(h);
  usageWidgets.forEach(setup);
  // Header KPI skeletons: if a Usage widget is present it fills them via render()->fixHeaderTotals;
  // otherwise (or if that fetch stalls) drop back to the server-embedded value so nothing stays loading.
  if(!usageWidgets.length)mcHeaderFallback();else setTimeout(mcHeaderFallback,4000);
  renderHeaderLimits();                                 // Claude session/week limits in the Overview header
  if(_wired)return; _wired=true;
  // refresh when the dashboard becomes visible again (e.g. back from Configure) or is restored from cache.
  // These are non-forcing, so within the cache window they repaint from cache (content stays put).
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshAll();});
  window.addEventListener("pageshow",e=>{if(e.persisted)refreshAll();});
  window.addEventListener("focus",()=>refreshAll());
  setInterval(()=>{if(!document.hidden)refreshAll(true);},1800000);   // auto-refresh every 30 min (forces a fresh fetch)
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
