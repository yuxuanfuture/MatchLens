import { clamp } from './matches.js';
import {t, language, applyTranslations, errorText, displayName} from './i18n.js';
import { LiveClient, toSnapshot } from './live-client.js';
import { StadiumRenderer } from './pocket-renderer.js?v=football';
import { REPLAY_STREAMS, playbackView, receiveTime, evidenceVisible } from './replay-view.js';

const $ = id => document.getElementById(id);
const moduleNames = ['slogan','commentary','notebook'];
const modules = Object.fromEntries(moduleNames.map(name=>[name,document.querySelector(`[data-module="${name}"]`)]));
const roles = ['fan','coach','commentator'], sizes = ['compact','regular','wide'];
const storageKey = 'matchlens-pocket-layout-v1';
let preferences = {role:'fan',mode:'fan',layouts:{}};
let storageAvailable = true;
try {
  const stored = JSON.parse(localStorage.getItem(storageKey));
  if(stored && roles.includes(stored.role) && ['fan','analyst'].includes(stored.mode) && stored.layouts && typeof stored.layouts==='object' && !Array.isArray(stored.layouts)) preferences=stored;
} catch { storageAvailable=false; }
let payload=null;
const audience={language:'zh',focus_team:'A',focus_player:null,metric:'overview',...(preferences.audience||{})};
audience.language=language();
const streams=REPLAY_STREAMS;
const requestedScene=new URLSearchParams(location.search).get('scene');
const state = {scene:streams.includes(requestedScene)?requestedScene:streams[0],time:0,playing:false,mode:preferences.mode,role:preferences.role,arranging:false};
const renderer = new StadiumRenderer($('stadium'));
const client=new LiveClient(value=>{payload=value;state.time=playbackView(value).position_ms/1000;state.playing=value.playing;updateUI();},message=>toast(message),{translate:t});
function audiencePrefs(){return {...audience,mode:state.mode,role:state.role};}
let previousFrame=performance.now(),lastContent='',lastClock='',toastTimer,drag=null,zIndex=1;
let evidenceScope='',evidenceRequest=0;
function clearEvidence(){evidenceRequest++;$('raw-evidence').textContent='';}

function preset(role,mode) {
  return {
    slogan:{x:0,y:0,visible:role!=='commentator',size:'regular'},
    commentary:{x:0,y:1,visible:true,size:role==='commentator'?'wide':'regular'},
    notebook:{x:1,y:1,visible:mode==='analyst'||role==='coach',size:'regular'}
  };
}
function layout() {
  const key=`${state.role}:${state.mode}`;
  const defaults=preset(state.role,state.mode);
  const saved=preferences.layouts[key];
  const clean={};
  for(const name of moduleNames) {
    const item=saved?.[name]||defaults[name];
    clean[name]={x:Number.isFinite(item.x)?clamp(item.x):defaults[name].x,y:Number.isFinite(item.y)?clamp(item.y):defaults[name].y,visible:typeof item.visible==='boolean'?item.visible:defaults[name].visible,size:sizes.includes(item.size)?item.size:'regular'};
  }
  preferences.layouts[key]=clean;
  return clean;
}
function save() {
  preferences.role=state.role;preferences.mode=state.mode;preferences.audience={...audience};
  try {localStorage.setItem(storageKey,JSON.stringify(preferences));storageAvailable=true;} catch {storageAvailable=false;}
  $('save-state').textContent=t(storageAvailable?'ui.saved':'ui.unsaved');
}
function applyLayout() {
  const current=layout(),stage=$('module-stage');
  stage.classList.toggle('no-headline',!current.slogan.visible);
  for(const name of moduleNames){const node=modules[name],item=current[name];node.hidden=!item.visible;node.dataset.size=item.size;node.style.left=`${item.x*Math.max(0,stage.clientWidth-node.offsetWidth)}px`;node.style.top=`${item.y*Math.max(0,stage.clientHeight-node.offsetHeight)}px`;document.querySelector(`[data-visible="${name}"]`).checked=item.visible;document.querySelector(`[data-size="${name}"]`).value=item.size;}
  const mobile=innerWidth<=700;
  $('edit-layout').disabled=mobile;
  $('drag-hint').textContent=t(mobile?'ui.mobile_hint':'ui.drag_hint');
  $('role-select').value=state.role;
}
function toast(message) {clearTimeout(toastTimer);$('toast').textContent=message;$('toast').hidden=false;toastTimer=setTimeout(()=>$('toast').hidden=true,2600);}
function announce(message){$('announcer').textContent=message;}
function setMode(mode,announceChange=true) {
  const previousMode=state.mode;
  state.mode=mode;document.body.dataset.mode=mode;
  $('fan-mode').setAttribute('aria-pressed',String(mode==='fan'));$('analyst-mode').setAttribute('aria-pressed',String(mode==='analyst'));
  updateHeadings();
  lastContent='';updateUI();applyLayout();save();
  if(previousMode!==mode&&!matchMedia('(prefers-reduced-motion: reduce)').matches)for(const node of Object.values(modules))if(!node.hidden)node.animate([{opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}],{duration:320,easing:'ease-out'});
  if(announceChange)client.control({preferences:audiencePrefs()});
  if(announceChange)announce(t('toast.mode',{mode:t('mode.'+mode)}));
}
function setArranging(value) {state.arranging=value;document.body.classList.toggle('arranging',value);$('arrange-tip').hidden=!value;if(value){closePanel('layout');modules[Object.keys(layout()).find(name=>layout()[name].visible)]?.querySelector('.drag-handle').focus();}}
function closePanel(name,restore=false) {$(name+'-panel').hidden=true;$(name==='layout'?'arrange-button':'evidence-button').setAttribute('aria-expanded','false');if(restore)$(name==='layout'?'arrange-button':'evidence-button').focus();}
function openPanel(name) {closePanel(name==='layout'?'evidence':'layout');$(name+'-panel').hidden=false;$(name==='layout'?'arrange-button':'evidence-button').setAttribute('aria-expanded','true');$('close-'+name).focus();if(name==='evidence')updateEvidence();}
function setPlaying(value){client.control({playing:value});}
function seek(time){clearEvidence();client.control({seek_ms:receiveTime(payload,time)});}
async function setScene(id){if(audience.focus_player&&!/^[AU]\d+$/.test(audience.focus_player))audience.focus_player=null;clearEvidence();state.scene=id;payload=null;lastContent='';try{await client.open(id,audiencePrefs());for(const button of document.querySelectorAll('[data-scene]'))button.setAttribute('aria-pressed',String(button.dataset.scene===id));announce(t('toast.scene',{stream:id}));}catch(error){toast(errorText(error));$('runtime-status').textContent=t('error.connection');}}
function updateEvidence() {
  if(!payload)return;
  const records=[...new Map([...payload.events,...payload.evidence_records].map(e=>[e.id,e])).values()].sort((a,b)=>b.observed_at_ms-a.observed_at_ms||b.event_time_ms-a.event_time_ms);
  $('evidence-list').replaceChildren(...records.map(e=>{
    const li=document.createElement('li'),button=document.createElement('button'),stamp=document.createElement('span'),title=document.createElement('strong'),detail=document.createElement('small');
    const official=payload.state.officials?.find(person=>person.id===e.official_id);
    const actor=official?t('official.'+official.role):e.player_id||e.id;
    stamp.textContent=clock(payload.state.match_clock_start_ms+e.event_time_ms);title.textContent=`${t('event.'+(e.type||e.record_type))} · ${actor}`;detail.textContent=`${e.id} · ${e.position?`(${e.position.x}, ${e.position.y}) m`:t('ui.position_unavailable')}`;
    if(e.official_id||e.type==='goal')detail.textContent+=' · '+t('ui.received_at',{clock:clock(payload.state.match_clock_start_ms+e.observed_at_ms-playbackView(payload).receive_offset_ms)});
    button.append(stamp,title,detail);button.addEventListener('click',async()=>{
      if(!payload)return;
      const requested={session_id:payload.session_id,epoch:payload.epoch},request=++evidenceRequest;
      try{const result=await client.evidence([e.id]);if(request===evidenceRequest&&evidenceVisible(result.records[0],payload,requested))$('raw-evidence').textContent=JSON.stringify(result.records[0],null,2);}
      catch(error){if(request===evidenceRequest)toast(errorText(error));}
    });li.append(button);return li;
  }));
}
function clock(ms){return `${String(Math.floor(ms/60000)).padStart(2,'0')}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`;}
function updateHeadings() {
  $('hero-title').textContent=t(state.mode==='fan'?'hero.fan_title':'hero.analyst_title');
  $('hero-subtitle').textContent=t(state.mode==='fan'?'hero.fan_subtitle':'hero.analyst_subtitle');
}
function updateUI() {
  if(!payload)return toSnapshot(null);
  const scope=`${payload.session_id}:${payload.epoch}`;
  if(scope!==evidenceScope){evidenceScope=scope;clearEvidence();}
  const {story,state:match,facts,focus,pass_quality:quality}=payload;
  const view=playbackView(payload),phase=payload.review?.phase||'none';
  for(const team of match.teams){$(team.id==='A'?'team-a':'team-u').textContent=displayName(team.name);const option=$('team-select').querySelector(`option[value="${team.id}"]`);if(option)option.textContent=displayName(team.name);}
  for(const button of document.querySelectorAll('[data-scene]'))button.setAttribute('aria-pressed',String(button.dataset.scene===payload.stream));
  $('seek').max=String(view.duration_ms/1000);$('seek').value=String(view.position_ms/1000);$('seek').style.setProperty('--progress',`${view.position_ms/Math.max(1,view.duration_ms)*100}%`);
  $('seek').setAttribute('aria-valuetext',t('ui.seconds_observed',{clock:clock(view.match_clock_ms),seconds:Math.round(view.position_ms/1000)}));
  $('match-time').textContent=clock(view.match_clock_ms);$('score').textContent=match.score_known===false?'— : —':`${match.score.A} – ${match.score.U}`;
  const status=$('review-status');status.hidden=!payload.playback&&phase==='none';status.dataset.phase=view.ended?'ended':phase;
  status.textContent=view.ended?t('review.ended'):phase!=='none'?t(`review.${phase}.title`):payload.playback?t('review.added_time',{minutes:Math.floor(view.announced_added_time_ms/60000)}):'';
  const playKey=payload.playing?'ui.pause':'ui.play';$('play-button').setAttribute('data-i18n-aria-label',playKey);$('play-button').setAttribute('aria-label',t(playKey));$('play-button').innerHTML=`<i class="ph-bold ph-${payload.playing?'pause':'play'}" aria-hidden="true"></i>`;
  $('scene-label').textContent=t('status.received',{stream:payload.stream,count:payload.received_records});
  const mode=t(payload.mode==='model_harness'?'status.agent':'status.offline');
  $('runtime-status').textContent=mode+' · '+t(payload.policy.enabled?'status.authorized':'status.locked')+(payload.tracking_available?'':' · '+t('status.missing'));
  $('chapter-a').textContent=payload.playback?t('ui.playback_progress',{position:clock(view.position_ms),duration:clock(view.duration_ms)}):t('ui.observed_only');$('chapter-b').textContent=story.window_label;$('chapter-c').textContent=t('ui.evidence_linked');
  const windowLabel=document.createElement('bdi');windowLabel.dir='ltr';windowLabel.textContent=story.window_label;$('commentary-kicker').replaceChildren(document.createTextNode(mode+' · '),windowLabel);
  const storyReady=payload.preferences.language===language();
  $('commentary-title').textContent=storyReady?story.title:t('status.updating');$('commentary-body').textContent=storyReady?story[state.mode==='fan'?'fan_text':'analyst_text']:'';
  $('commentary-evidence').replaceChildren(...(state.mode==='analyst'?story.evidence_ids.slice(0,3):[]).map(id=>{const span=document.createElement('span');span.textContent=id;return span;}));
  const own=facts.teams[audience.focus_team];
  $('play-state-note').hidden=match.in_play!==false;
  $('play-state-note').textContent=view.ended?t('review.ended'):t(phase==='awarded'?'review.stopped':'review.paused');
  $('tactic-value').textContent=focus?displayName(focus.player.name):t(quality&&audience.metric==='passing'?'stats.pass_quality':'stats.match_pulse');
  $('tactical-body').textContent=focus?t('stats.player',{distance:focus.observed_distance_m,speed:focus.peak_sampled_speed_mps??'—'}):t('stats.team',{accuracy:own.pass_accuracy_pct??'—',speed:facts.speeds.ball_speed_mps??'—'});
  $('stat-a').textContent=focus?focus.completed_passes:own.completed_passes;$('stat-a-label').textContent=t('stats.completed');
  const shotSpeed=facts.speeds.shot_speeds.at(-1)?.speed_mps;
  $('stat-b').textContent=audience.metric==='speed'?(shotSpeed??'—'):(focus?focus.shots:own.shots);$('stat-b-label').textContent=t(audience.metric==='speed'?'stats.shot_speed':'stats.shots');
  $('focus-note').textContent=focus?t(focus.sprint_threshold_reached?'stats.sprint':'stats.following'):(quality?t('stats.latest_pass',{distance:quality.distance_m??'—',difficulty:quality.difficulty_1_to_5??'—'}):'');
  const playerKey=payload.stream+':'+language();
  if($('player-select').dataset.stream!==playerKey){$('player-select').replaceChildren(new Option(t('ui.all_players'),''),...match.roster.map(p=>new Option(`${displayName(p.name)} #${p.shirt_number}`,p.id)));$('player-select').dataset.stream=playerKey;$('player-select').value=audience.focus_player||'';}
  if(!$('evidence-panel').hidden&&lastContent!==story.id)updateEvidence();lastContent=story.id;
  return toSnapshot(payload,displayName);
}

function moveModule(name,left,top) {
  const stage=$('module-stage'),node=modules[name],availableX=Math.max(0,stage.clientWidth-node.offsetWidth),availableY=Math.max(0,stage.clientHeight-node.offsetHeight);
  const item=layout()[name];item.x=availableX?clamp(left/availableX):0;item.y=availableY?clamp(top/availableY):0;node.style.left=`${item.x*availableX}px`;node.style.top=`${item.y*availableY}px`;
}
for(const name of moduleNames){const node=modules[name],handle=node.querySelector('.drag-handle');
  handle.addEventListener('pointerdown',event=>{if(innerWidth<=700||event.button!==0)return;event.preventDefault();handle.focus();drag={name,x:event.clientX,y:event.clientY,left:node.offsetLeft,top:node.offsetTop,pointer:event.pointerId};handle.setPointerCapture(event.pointerId);node.classList.add('dragging');node.style.zIndex=String(++zIndex);});
  handle.addEventListener('pointermove',event=>{if(drag?.name!==name)return;moveModule(name,drag.left+event.clientX-drag.x,drag.top+event.clientY-drag.y);});
  const endDrag=()=>{if(drag?.name!==name)return;drag=null;node.classList.remove('dragging');save();};handle.addEventListener('pointerup',endDrag);handle.addEventListener('pointercancel',endDrag);handle.addEventListener('lostpointercapture',endDrag);
  handle.addEventListener('keydown',event=>{if(!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(event.key)||innerWidth<=700)return;event.preventDefault();const step=event.shiftKey?30:8;moveModule(name,node.offsetLeft+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),node.offsetTop+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0));save();});
}
for(const input of document.querySelectorAll('[data-visible]'))input.addEventListener('change',()=>{layout()[input.dataset.visible].visible=input.checked;applyLayout();save();});
for(const input of document.querySelectorAll('[data-size]'))input.addEventListener('change',()=>{layout()[input.dataset.size].size=input.value;applyLayout();save();});
for(const button of document.querySelectorAll('[data-hide]'))button.addEventListener('click',()=>{layout()[button.dataset.hide].visible=false;applyLayout();save();$('arrange-button').focus();toast(t('toast.hidden'));});
$('fan-mode').addEventListener('click',()=>setMode('fan'));$('analyst-mode').addEventListener('click',()=>setMode('analyst'));
$('arrange-button').addEventListener('click',()=>$('layout-panel').hidden?openPanel('layout'):closePanel('layout',true));
$('close-layout').addEventListener('click',()=>closePanel('layout',true));$('close-evidence').addEventListener('click',()=>closePanel('evidence',true));
$('evidence-button').addEventListener('click',()=>openPanel('evidence'));$('about-button').addEventListener('click',()=>openPanel('evidence'));
$('role-select').addEventListener('change',event=>{state.role=event.target.value;setMode(state.role==='fan'?'fan':'analyst');toast(t('toast.role',{role:t(state.role==='fan'?'mode.fan':'role.'+state.role)}));});
$('edit-layout').addEventListener('click',()=>setArranging(true));$('done-arranging').addEventListener('click',()=>{setArranging(false);$('arrange-button').focus();toast(t('toast.arranged'));});
$('reset-layout').addEventListener('click',()=>{preferences.layouts[`${state.role}:${state.mode}`]=preset(state.role,state.mode);applyLayout();save();toast(t('toast.reset'));});
$('replay-button').addEventListener('click',()=>{seek(0);setPlaying(true);});$('restart-button').addEventListener('click',()=>seek(0));
$('play-button').addEventListener('click',()=>{if(state.time>=playbackView(payload).duration_ms/1000)seek(0);setPlaying(!state.playing);});
$('seek').addEventListener('change',event=>{setPlaying(false);seek(event.target.value);});
for(const button of document.querySelectorAll('[data-scene]'))button.addEventListener('click',()=>setScene(button.dataset.scene));
document.addEventListener('keydown',event=>{if(event.key==='Escape'){if(!$('layout-panel').hidden)closePanel('layout',true);else if(!$('evidence-panel').hidden)closePanel('evidence',true);if(state.arranging){setArranging(false);$('arrange-button').focus();}}});
document.addEventListener('visibilitychange',()=>{if(document.hidden)setPlaying(false);});
window.addEventListener('resize',()=>{if(innerWidth<=700)setArranging(false);applyLayout();});
const observer=new ResizeObserver(()=>{if(!drag)applyLayout();});moduleNames.forEach(name=>observer.observe(modules[name]));
setMode(state.mode,false);applyLayout();
renderer.load().then(()=>{$('load-status').hidden=true;requestAnimationFrame(frame);}).catch(error=>{console.error(error);$('load-status').textContent=t('status.load_failed');});
function frame(now){const delta=Math.min((now-previousFrame)/1000,.06);previousFrame=now;renderer.render(toSnapshot(payload,displayName),state.mode,delta);requestAnimationFrame(frame);}
for(const [id,key] of [['team-select','focus_team'],['player-select','focus_player'],['metric-select','metric']])$(id).addEventListener('change',event=>{audience[key]=event.target.value||null;save();client.control({preferences:audiencePrefs()});});
$('speed-select').addEventListener('change',event=>client.control({speed:Number(event.target.value)}));
$('recap-button').addEventListener('click',async()=>{try{await client.control({playing:false});const recap=await client.recap();$('recap-text').textContent=recap.text+(recap.agent_status==='running'?' · '+t('status.reviewing'):'');if(recap.agent_status==='running')setTimeout(()=>{if($('recap-panel').open)$('recap-button').click();},1500);$('recap-list').replaceChildren(...[...recap.milestones,...recap.turning_points.map(p=>({...p,match_clock:clock(p.time_ms+(payload?.state.match_clock_start_ms||0))}))].sort((a,b)=>a.time_ms-b.time_ms).map(m=>{const li=document.createElement('li');li.textContent=`${m.match_clock} · ${m.text} · ${m.evidence_ids.join(', ')}`;return li;}));if(!$('recap-panel').open)$('recap-panel').showModal();}catch(error){toast(errorText(error));}});
$('close-recap').addEventListener('click',()=>$('recap-panel').close());
function download(value,name){const link=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export-overlay').addEventListener('click',()=>{if(payload)download({schema_version:payload.schema_version,as_of_ms:payload.as_of_ms,playback:payload.playback,review:payload.review,story:payload.story,overlays:payload.overlays},'matchlens-overlay.json');});
$('export-recap').addEventListener('click',async()=>{try{download(await client.recap(),'matchlens-recap.json');}catch(error){toast(errorText(error));}});
for(const [id,key] of [['language-select','language'],['team-select','focus_team'],['metric-select','metric']])$(id).value=audience[key];
$('broadcast').onclick=()=>{if(client.id)window.open(`./overlay.html?session=${client.id}&mode=${state.mode}&lang=${language()}`,'_blank','noopener');};
const attached=new URLSearchParams(location.search).get('session');
if(attached)client.attach(attached).then(()=>{Object.assign(audience,client.current.preferences,{language:language()});state.mode=audience.mode;setMode(state.mode,false);client.control({preferences:audiencePrefs()});}).catch(e=>toast(errorText(e)));else setScene(state.scene);

document.addEventListener('matchlens:language',async()=>{
  audience.language=language();updateHeadings();applyLayout();save();updateUI();
  if(!$('evidence-panel').hidden)updateEvidence();
  await client.control({preferences:audiencePrefs()});
  if($('recap-panel').open)$('recap-button').click();
});
applyTranslations();updateHeadings();applyLayout();save();
