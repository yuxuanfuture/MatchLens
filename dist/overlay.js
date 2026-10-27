import {t, language, applyTranslations, addLanguagePicker, errorText} from './i18n.js';
import {LiveClient} from './live-client.js';
import {playbackView,receiveTime} from './replay-view.js';
const $=id=>document.getElementById(id),params=new URLSearchParams(location.search),sid=params.get('session');
document.body.classList.toggle('transparent',params.get('transparent')==='1');
let value=null,busy=false,url=null,lastSync=-1,received=performance.now();
$('view').value=params.get('mode')==='analyst'?'analyst':'fan';
const client=new LiveClient(v=>{value=v;received=performance.now();$('status').textContent=t('overlay.status',{seconds:(playbackView(v).position_ms/1000).toFixed(1),mode:t(v.mode==='model_harness'?'status.agent':'status.offline')});},e=>$('status').textContent=e,{translate:t});
if(sid)client.attach(sid).then(()=>client.control({preferences:{language:language()}})).catch(e=>$('status').textContent=errorText(e));else $('status').textContent=t('overlay.open_from');
$('media').onchange=()=>{if(url)URL.revokeObjectURL(url);const file=$('media').files[0];if(!file)return;url=URL.createObjectURL(file);$('video').src=url;lastSync=-1;client.control({playing:false});};
$('copy').onclick=async()=>{const link=new URL(location.href);link.searchParams.set('transparent','1');link.searchParams.set('mode',$('view').value);link.searchParams.set('lang',language());try{await navigator.clipboard.writeText(link.href);$('status').textContent=t('overlay.copied');}catch{$('status').textContent=link.href;}};
async function synchronize(){
 if(!url||!value||busy)return;
 const at=receiveTime(value,$('video').currentTime+Number($('offset').value||0));
 if(Math.abs(at-lastSync)<150)return;
 busy=true;lastSync=at;await client.control({media_time_ms:at,playing:false});busy=false;
}
$('video').addEventListener('seeked',()=>{lastSync=-1;synchronize();});
setInterval(synchronize,250);
function draw(){
 const story=value?.story;let now=playbackView(value).position_ms;
 if(value?.playing)now+=(performance.now()-received)*value.speed;
 if(url)now=($('video').currentTime+Number($('offset').value||0))*1000;
 const visible=!!story&&value.preferences.language===language()&&now>=story.display_at_ms&&now<story.expires_at_ms&&performance.now()-received<10000;
 $('cue').hidden=!visible;
 if(visible){const windowLabel=document.createElement('bdi');windowLabel.dir='ltr';windowLabel.textContent=story.window_label;$('source').replaceChildren(document.createTextNode(`MatchLens · ${t(value.mode==='model_harness'?'status.agent':'status.offline')} · `),windowLabel);$('title').textContent=story.title;$('text').textContent=story[$('view').value==='fan'?'fan_text':'analyst_text'];$('refs').textContent=$('view').value==='analyst'?story.evidence_ids.join(' · '):'';}
 requestAnimationFrame(draw);
}draw();

document.body.dataset.pageTitle='ui.broadcast';addLanguagePicker($('toolbar'));applyTranslations();
document.addEventListener('matchlens:language',()=>{if(sid)client.control({preferences:{language:language()}});else $('status').textContent=t('overlay.open_from');});
