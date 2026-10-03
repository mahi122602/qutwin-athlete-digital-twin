"use strict";
let model={},paused=false;const $=id=>document.getElementById(id);const post=(type,extra={})=>parent.postMessage({isStreamlitMessage:true,type,...extra},"*");
function resize(){post("streamlit:setFrameHeight",{height:Math.ceil(document.documentElement.getBoundingClientRect().height)});}
function send(action,id){const value={action,nonce:globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random()}`};if(id!=null)value.upload_id=String(id);post("streamlit:setComponentValue",{value,dataType:"json"});}
function text(id,value){$(id).textContent=value??"";}
function buttonAction(el,action,id){el.onclick=()=>send(action,id);}
function render(m){model=m;text("welcome",`Welcome to your studio, ${m.name}.`);text("avatar",m.initials);text("badge",m.unread?String(m.unread):"");$("notifications").setAttribute("aria-label",m.errors.includes("notifications")?"Notifications — count unavailable":`Notifications, ${m.unread} unread`);
$("metrics").replaceChildren(...m.measurements.map(x=>{const d=document.createElement("div");d.className="metric";const v=document.createElement("strong");v.textContent=x.value;const u=document.createElement("span");u.className="unit";u.textContent=x.unit;const l=document.createElement("label");l.textContent=x.available?x.label:`${x.label} not recorded`;d.append(v,u,l);return d;}));
text("coach-status",m.coach_status);text("coach-text",m.coach_text);text("coach-link",m.coach_action+" ↗");buttonAction($("coach-link"),m.coach_route,m.latest_id);$("coach-nav").dataset.action=m.coach_route;
$("events-list").replaceChildren(...(m.events.length?m.events:["Choose your events"]).map(e=>{let d=document.createElement("span");d.className="event";d.textContent=e;return d;}));
const latest=m.uploads[0];text("last-title",latest?.title||"Your next chapter");text("last-date",latest?.date||"Add your first activity");buttonAction($("last"),latest?"activity":"upload",m.latest_id);
text("assessment-title",m.assessment);text("assessment-status",m.status);buttonAction($("assessment"),m.errors.includes("uploads")?"refresh":m.has_data?"insights":"upload",m.latest_id);text("note",m.note);text("note-link",m.errors.includes("uploads")?"Refresh ↻":m.has_data?"View details ↗":"Add activity ↗");buttonAction($("note-link"),m.errors.includes("uploads")?"refresh":m.has_data?"insights":"upload",m.latest_id);
const summary=m.summary||{groups:["High","Medium","Low"].map(level=>({level,items:[]})),unavailable:["Restart the app after replacing all update files to load the summary."],basis:"Summary unavailable",note:"Missing information is not classified as low risk."};
text("summary-basis",summary.basis+" · Fatigue, injury, recommendations and saved forecasting");text("summary-note",summary.note);
$("trail").replaceChildren(...summary.groups.map(g=>{
 const card=document.createElement("section");card.className="risk-card risk-"+g.level.toLowerCase();
 const heading=document.createElement("div");heading.className="risk-heading";
 const title=document.createElement("h3");title.textContent=g.level+" risk";
 const count=document.createElement("span");count.className="risk-count";count.textContent=g.items.length+ (g.items.length===1?" item":" items");heading.append(title,count);
 const sub=document.createElement("p");sub.className="risk-subtitle";sub.textContent={High:"Review first",Medium:"Needs review",Low:"Routine monitoring"}[g.level];card.append(heading,sub);
 if(!g.items.length){const empty=document.createElement("p");empty.className="risk-empty";empty.textContent="No available signals in this band. This does not rule out risk.";card.append(empty);}
 for(const item of g.items){const row=document.createElement("article");row.className="risk-item";
 const source=document.createElement("span");source.className="risk-source";source.textContent=item.source;
 const name=document.createElement("h4");name.textContent=item.title;
 const detail=document.createElement("p");detail.textContent=item.detail;row.append(source,name,detail);
 if(item.quote){const q=document.createElement("blockquote");q.textContent=item.quote;const caption=document.createElement("small");caption.textContent="Saved recommendation excerpt";row.append(caption,q);}
 const link=document.createElement("button");link.className="text-link";link.textContent=item.cta+" →";buttonAction(link,item.action,item.upload_id);row.append(link);card.append(row);}
 return card;
}));
$("summary-unavailable").replaceChildren();if(summary.unavailable.length){const title=document.createElement("strong");title.textContent="Not assessed / needs updating";const list=document.createElement("ul");for(const item of summary.unavailable){const li=document.createElement("li");li.textContent=item;list.append(li);}const link=document.createElement("button");link.className="text-link";link.textContent="Open forecasting →";buttonAction(link,"forecast");$("summary-unavailable").append(title,list,link);}
applyTheme(m.theme||"dawn");
setupCardMotion();
requestAnimationFrame(resize);}
document.querySelectorAll("[data-action]").forEach(b=>b.addEventListener("click",()=>{let a=b.dataset.action;if(b.hasAttribute("data-latest")&&!model.latest_id&&a!=="requests")a="upload";send(a,b.hasAttribute("data-latest")?model.latest_id:null);}));
function closeMenu(){ $("explore-menu").hidden=true;$("explore-toggle").setAttribute("aria-expanded","false");resize();}
$("explore-toggle").onclick=()=>{const hidden=!$("explore-menu").hidden;$("explore-menu").hidden=hidden;$("explore-toggle").setAttribute("aria-expanded",String(!hidden));resize();};document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!$("explore-menu").hidden){closeMenu();$("explore-toggle").focus();}});document.addEventListener("click",e=>{if(!e.target.closest(".explore"))closeMenu();});$("motion").onclick=()=>{paused=!paused;document.body.classList.toggle("paused",paused);text("motion",paused?"Resume motion":"Pause motion");};document.addEventListener("visibilitychange",()=>document.body.classList.toggle("paused",paused||document.hidden));window.addEventListener("message",e=>{if(e.source===parent&&e.data?.type==="streamlit:render"&&e.data.args?.model)render(e.data.args.model);});new ResizeObserver(()=>resize()).observe(document.body);post("streamlit:componentReady",{apiVersion:1});resize();

function applyTheme(theme){const dusk=theme==="dusk";document.documentElement.dataset.theme=dusk?"dusk":"dawn";$("theme-dial").setAttribute("aria-checked",String(dusk));text("theme-name",dusk?"Dusk":"Dawn");text("theme-hint",dusk?"Switch to dawn":"Switch to dusk");}
$("theme-dial").onclick=()=>{const theme=document.documentElement.dataset.theme==="dusk"?"dawn":"dusk";applyTheme(theme);post("streamlit:setComponentValue",{value:{action:"theme",theme,nonce:globalThis.crypto?.randomUUID?.()||`${Date.now()}-${Math.random()}`},dataType:"json"});};

// Pointer tilt is intentionally small; the cards retain their grid positions.
let cardObserver=null;
const motionPreference=window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : {matches:true};
const finePointer=window.matchMedia ? window.matchMedia("(hover: hover) and (pointer: fine)") : {matches:false};
function motionAllowed(){return !motionPreference.matches&&!document.hidden&&!document.body.classList.contains("paused");}
function resetCard(card){card.style.setProperty("--tilt-x","0deg");card.style.setProperty("--tilt-y","0deg");card.classList.remove("following-pointer");}
function setupCardMotion(){
 resetAllCards();
 if(cardObserver)cardObserver.disconnect();
 const cards=document.querySelectorAll(".risk-card");
 if(typeof IntersectionObserver!=="undefined"){
  cardObserver=new IntersectionObserver(entries=>{for(const entry of entries){if(entry.isIntersecting){if(motionAllowed())entry.target.classList.add("card-arrived");cardObserver.unobserve(entry.target);}}},{threshold:0.08});
 }
 cards.forEach((card,index)=>{
  card.style.setProperty("--reveal-delay",`${index*70}ms`);
  if(cardObserver)cardObserver.observe(card);
  let frame=0,rect=null;
  const clear=()=>{if(frame)cancelAnimationFrame(frame);frame=0;rect=null;resetCard(card);};
  card._resetMotion=clear;
  card.addEventListener("pointerenter",()=>{rect=card.getBoundingClientRect();});
  card.addEventListener("pointermove",event=>{
   if(!motionAllowed()||!finePointer.matches||event.pointerType==="touch"||card.matches(":focus-within")){clear();return;}
   if(!rect)rect=card.getBoundingClientRect();
   const x=Math.max(-1,Math.min(1,(event.clientX-rect.left)/Math.max(rect.width,1)*2-1));
   const y=Math.max(-1,Math.min(1,(event.clientY-rect.top)/Math.max(rect.height,1)*2-1));
   if(frame)cancelAnimationFrame(frame);
   frame=requestAnimationFrame(()=>{frame=0;card.style.setProperty("--tilt-x",`${(-y*2).toFixed(2)}deg`);card.style.setProperty("--tilt-y",`${(x*2.5).toFixed(2)}deg`);card.classList.add("following-pointer");});
  });
  card.addEventListener("pointerleave",clear);card.addEventListener("pointercancel",clear);card.addEventListener("focusin",clear);
 });
}
function resetAllCards(){document.querySelectorAll(".risk-card").forEach(card=>card._resetMotion?card._resetMotion():resetCard(card));}
if(motionPreference.addEventListener)motionPreference.addEventListener("change",resetAllCards);
window.addEventListener("scroll",resetAllCards,{passive:true});
document.addEventListener("visibilitychange",resetAllCards);
$("motion").addEventListener("click",resetAllCards);
