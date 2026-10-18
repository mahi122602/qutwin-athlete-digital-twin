import {createWorld} from './world.js';

const $=id=>document.getElementById(id);
const forms={account:$('account-form'),body:$('body-form'),health:$('health-form'),login:$('login-form')};
const smooth=v=>{const x=Math.max(0,Math.min(1,v));return x*x*(3-2*x);};
const standalone=window.parent===window;
const inspectMode=new URLSearchParams(location.search).has('inspect');
let parentOrigin='*';
try{if(document.referrer)parentOrigin=new URL(document.referrer).origin;}catch{}
function streamlit(type,payload={}){
  if(!standalone)window.parent.postMessage({isStreamlitMessage:true,type,...payload},parentOrigin);
}
function frameHeight(){
  let h=window.innerHeight;
  try{h=Math.max(h,window.parent.innerHeight);}catch{}
  streamlit('streamlit:setFrameHeight',{height:Math.max(h,640)});
}
let theme='dawn',reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
try{theme=localStorage.getItem('qutwin_auth_theme')==='dusk'?'dusk':'dawn';}catch{}
let world=null,page='arrive',poseKey='wide',journey=null,pending=false,initialised=false;
let draft={},role='Athlete',lastResponse='',initialPage='Login',worldReady=false;
const seenResponses=new Set();

function setTheme(value){
  theme=value;document.documentElement.dataset.theme=theme;
  $('theme').innerHTML=theme==='dawn'?'☀ <span>Dawn</span>':'☾ <span>Dusk</span>';
  $('theme').setAttribute('aria-label',theme==='dawn'?'Switch to dusk theme':'Switch to dawn theme');
  try{localStorage.setItem('qutwin_auth_theme',theme);}catch{}
  world?.setTheme(theme);
}
function setReduced(value){
  reduced=value;$('motion').setAttribute('aria-pressed',String(reduced));
  $('motion').textContent=reduced?'Motion reduced':'Reduce motion';
}
setTheme(theme);setReduced(reduced);
$('theme').addEventListener('click',()=>setTheme(theme==='dawn'?'dusk':'dawn'));
$('motion').addEventListener('click',()=>setReduced(!reduced));

function clearFeedback(){document.querySelectorAll('.feedback').forEach(n=>{n.hidden=true;n.textContent='';});}
function message(text,target=page){
  const node=$(target)?.querySelector('.feedback');
  if(node){node.textContent=text;node.hidden=false;node.scrollIntoView({block:'nearest',behavior:'instant'});}
}
function steps(){
  document.querySelectorAll('.steps').forEach(nav=>{
    const active=Number(nav.dataset.step),labels=role==='Coach'?['Account','Review & save']:['Account','Body & sport','Health context','Review & save'];
    nav.replaceChildren();
    const step=role==='Coach'?(active===0?0:1):active;
    labels.forEach((label,i)=>{
      const item=document.createElement('div');item.className='step'+(i===step?' active':i<step?' done':'');
      if(i===step)item.setAttribute('aria-current','step');
      const number=document.createElement('span');number.className='step-number';number.textContent=i<step?'✓':String(i+1);
      const text=document.createElement('span');text.textContent=label;item.append(number,text);nav.append(item);
    });
  });
}
function setRole(value){
  role=value;world?.setRole(role);steps();
  $('role-caption').textContent=role==='Athlete'?'Athlete · Your journey starts here.':'Coach · Bring your team’s potential to life.';
  document.querySelectorAll('.coach-only').forEach(n=>n.hidden=role!=='Coach');
}
forms.account.querySelectorAll('[name=role]').forEach(input=>input.addEventListener('change',()=>setRole(input.value)));
steps();
function show(next,{focus=true,slide=false}={}){
  page=next;
  document.querySelectorAll('.screen').forEach(section=>{
    section.hidden=section.id!==page;section.classList.remove('travelling','panel-slide');
  });
  const section=$(page);
  if(slide)section.classList.add('panel-slide');
  $('journey-status').hidden=true;
  if(focus&&page!=='arrive')section.querySelector('h1')?.focus({preventScroll:true});
  if(page==='review')renderReview();
}
function navigate(next){
  if(journey||pending)return;
  clearFeedback();
  const target=next==='wide'?'arrive':next;
  const toPose=target==='arrive'?'wide':target==='reset'?'signin':target;
  if(!worldReady||reduced||poseKey===toPose){
    poseKey=toPose;world?.rig.setCamera(world.rig.poses[poseKey],0,false);show(target);return;
  }
  const morph=!['wide','signin'].includes(poseKey)&&!['wide','signin'].includes(toPose);
  const route=(poseKey==='signin'&&toPose!=='wide')||(toPose==='signin'&&poseKey!=='wide');
  let duration=morph?.8:route?9.2:toPose==='wide'?4.8:toPose==='signin'?5.8:theme==='dusk'?6:6.2;
  journey={from:poseKey,to:toPose,target,route:route?'route':'zoom',morph,duration,start:performance.now()/1000};
  // The scene remains visible. No opacity animation, dissolve, image exchange,
  // or transition overlay is applied to the environment.
  $(page).classList.add('travelling');
  $('journey-status').textContent=toPose==='wide'?'Returning to the landscape…':toPose==='signin'?'Travelling to the starting line…':'Travelling to your next chapter…';
  $('journey-status').hidden=false;
}
document.querySelectorAll('[data-go]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.go)));
$('brand-home').addEventListener('click',()=>navigate('wide'));
$('review-back').addEventListener('click',()=>navigate(role==='Coach'?'account':'health'));
$('success-signin').addEventListener('click',()=>{
  forms.login.elements['user_id'].value=draft.user_id||'';
  forms.login.querySelector(`[name="login-role"][value="${role}"]`).checked=true;
  navigate('signin');
});
document.querySelectorAll('.eye').forEach(button=>button.addEventListener('click',()=>{
  const input=button.parentElement.querySelector('input'),showing=input.type==='password';
  input.type=showing?'text':'password';button.setAttribute('aria-label',showing?'Hide password':'Show password');
}));
const notice=$('notice');$('open-notice').addEventListener('click',()=>notice.showModal());
document.querySelectorAll('.notice-close').forEach(b=>b.addEventListener('click',()=>notice.close()));
notice.addEventListener('click',e=>{if(e.target===notice)notice.close();});

function values(form){return Object.fromEntries(new FormData(form));}
forms.account.addEventListener('submit',event=>{
  event.preventDefault();clearFeedback();
  const valuesNow=values(forms.account);
  if(valuesNow.password!==valuesNow.confirm){message('Passwords do not match.');return;}
  if(new TextEncoder().encode(valuesNow.password).length>72){message('Use a password of at most 72 UTF-8 bytes.');return;}
  draft={...draft,...valuesNow,terms_accepted:forms.account.elements.terms_accepted.checked};
  navigate(role==='Athlete'?'body':'review');
});
forms.body.addEventListener('submit',event=>{
  event.preventDefault();clearFeedback();const data=values(forms.body);
  const birth=new Date(data.date_of_birth+'T00:00:00'),today=new Date();
  let age=today.getFullYear()-birth.getFullYear();
  if(today.getMonth()<birth.getMonth()||(today.getMonth()===birth.getMonth()&&today.getDate()<birth.getDate()))age--;
  if(!Number.isFinite(age)||age<10||age>80){message('Athlete accounts currently support ages 10–80.');return;}
  draft={...draft,...data};navigate('health');
});
forms.health.addEventListener('submit',event=>{
  event.preventDefault();draft={...draft,...values(forms.health),health_consent:forms.health.elements.health_consent.checked};navigate('review');
});
function renderReview(){
  const box=$('review-content');box.replaceChildren();
  const rows=[['↗','Your account',`${draft.name||''} · ${role}\n${draft.user_id||''}\n${draft.email||''}`,'account']];
  if(role==='Athlete'){
    rows.push(['◌','Body & sport',`${draft.sport||''}${draft.event_type?' · '+draft.event_type:''}\n${draft.height||''} cm · ${draft.weight||''} kg\n${draft.date_of_birth||''} · ${draft.gender||''}`,'body']);
    rows.push(['♡','Training context',`${draft.previous_injury||0} previous injuries\n${draft.injury_history||'No additional context provided.'}`,'health']);
  }else if(draft.specialisation)rows.push(['♧','Coaching',draft.specialisation,'account']);
  rows.forEach(([icon,title,copy,destination])=>{
    const row=document.createElement('div');row.className='review-row';
    const symbol=document.createElement('span');symbol.textContent=icon;
    const content=document.createElement('div'),heading=document.createElement('h3'),description=document.createElement('p');
    heading.textContent=title;description.textContent=copy;description.style.whiteSpace='pre-line';
    content.append(heading,description);
    const edit=document.createElement('button');edit.className='text-link';edit.textContent='Edit';edit.addEventListener('click',()=>navigate(destination));
    row.append(symbol,content,edit);box.append(row);
  });
}
function busy(value){
  pending=value;
  document.querySelectorAll('.screen button[type=submit],#save-account').forEach(button=>button.disabled=value);
  $('save-account').firstChild.textContent=value?'Saving your account… ':'Create my account ';
}
function submit(action,data){
  if(pending)return;
  if(standalone){message('Open this screen through Streamlit to use the account database.');return;}
  clearFeedback();busy(true);
  const nonce=crypto.randomUUID?.()||String(Date.now())+'-'+String(Math.random()).slice(2);
  streamlit('streamlit:setComponentValue',{value:{action,data,nonce,theme},dataType:'json'});
}
forms.login.addEventListener('submit',event=>{
  event.preventDefault();
  const data=values(forms.login);data.role=data['login-role'];delete data['login-role'];submit('login',data);
});
$('save-account').addEventListener('click',()=>submit('signup',{...draft,role}));

function response(value){
  if(!value||typeof value!=='object'||!value.nonce||seenResponses.has(value.nonce))return;
  seenResponses.add(value.nonce);lastResponse=value.nonce;busy(false);
  // Replace the component's submitted value with a credential-free acknowledgement.
  streamlit('streamlit:setComponentValue',{value:{action:'ack',nonce:value.nonce},dataType:'json'});
  if(value.ok){
    const uid=value.user_id;role=value.role||role;
    draft={user_id:uid,role};
    for(const form of [forms.account,forms.body,forms.health])form.reset();
    forms.account.querySelector(`[name=role][value="${role}"]`).checked=true;
    setRole(role);poseKey='success';show('success');
    world?.rig.setCamera(world.rig.poses.success,0,false);
  }else{
    forms.login.elements.password.value='';
    message(value.message||'Please try again.');
  }
}
window.addEventListener('message',event=>{
  if(event.source!==window.parent||event.data?.type!=='streamlit:render')return;
  if(parentOrigin!=='*'&&event.origin!==parentOrigin)return;
  const args=event.data.args||{};initialPage=args.initial_page||'Login';
  if(!initialised){
    initialised=true;
    if(initialPage==='Signup'){page='account';poseKey='account';show('account',{focus:false});}
    else if(initialPage==='Forgot Password'){page='reset';poseKey='signin';show('reset',{focus:false});}
  }
  response(args.response);frameHeight();
});
streamlit('streamlit:componentReady',{apiVersion:1});frameHeight();
window.addEventListener('resize',()=>{frameHeight();world?.resize(innerWidth,innerHeight);});

let lastFrame=0;
function update(milliseconds){
  requestAnimationFrame(update);
  if(!world||document.hidden||inspectMode)return;
  if(milliseconds-lastFrame<30)return;
  lastFrame=milliseconds;const now=milliseconds/1000;
  if(journey){
    const local=now-journey.start;
    if(local>=journey.duration){
      const next=journey.target;poseKey=journey.to;const slide=journey.morph;journey=null;
      world.rig.setCamera(world.rig.poses[poseKey],now,false);show(next,{slide});
    }else{
      let pose;
      if(journey.morph){
        const u=smooth(local/journey.duration),a=world.rig.poses[journey.from],b=world.rig.poses[journey.to];
        pose={pos:a.pos.clone().lerp(b.pos,u),look:a.look.clone().lerp(b.look,u),fov:a.fov};
      }else{
        pose=world.rig.flightPose(journey.from,journey.to,smooth((local-.55)/(journey.duration-1.1)),journey.route);
      }
      world.rig.setCamera(pose,now,false);
    }
  }else world.rig.setCamera(world.rig.poses[poseKey],now,!reduced);
  world.draw(now);
}
requestAnimationFrame(update);
try{
  world=await createWorld($('scene'),(n,total)=>$('loading-detail').textContent=`Loading the landscape · ${Math.min(99,Math.round(n/Math.max(1,total)*100))}%`);
  world.resize(innerWidth,innerHeight);world.setTheme(theme);world.setRole(role);
  world.rig.setCamera(world.rig.poses[poseKey],0,false);world.draw(0);
  worldReady=true;$('loader').hidden=true;
  $('scene').addEventListener('webglcontextlost',event=>{
    event.preventDefault();$('scene-warning').hidden=false;
    $('scene-warning').textContent='The animated environment paused. Refresh this page to resume it.';
  });
}catch(error){
  $('loader').hidden=true;$('fallback').hidden=false;$('scene').hidden=true;
  $('scene-warning').hidden=false;
  $('scene-warning').textContent='The animated environment could not load. You can still use the account forms.';
  // Report only a technical asset error, never form values or submitted data.
  console.error('QUTwin environment could not load:',error?.message||'Unknown scene error');
}
if(inspectMode){
  // Camera-only inspection interface. It has no account or authentication bypass.
  window.qutwinScene={
    get world(){return world;},
    get state(){return {page,poseKey,theme,role,travelling:Boolean(journey),ready:worldReady};},
    move:navigate,
    show(next){poseKey=next==='arrive'?'wide':next;journey=null;show(next);world?.rig.setCamera(world.rig.poses[poseKey],0,false);world?.draw(0);},
    theme:setTheme,
    renderPose(from,to,u,kind='zoom'){
      journey=null;const p=world.rig.flightPose(from,to,u,kind);world.rig.setCamera(p,0,false);world.draw(0);
    }
  };
}
