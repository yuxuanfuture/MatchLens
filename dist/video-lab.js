import {t as translate, eventLabel, applyTranslations, addLanguagePicker, localizedError, errorText} from './i18n.js';
import {identities,detectPixels,TemporalEvents} from './video-detector.js';
const $=id=>document.getElementById(id),video=$('video'),canvas=$('preview'),ctx=canvas.getContext('2d',{willReadFrequently:true});
let generation=0,records=[],videoURL,outputURL;
const positions=identities.map((p,i)=>({id:p.id,x:i<11?8+(i%5)*12:98-(i%5)*12,y:7+Math.floor(i/5)*11}));
for(const [id,x,y] of [['A7',20,34],['A9',50,34],['U4',75,34],['U9',85,55],['A10',87,34]])Object.assign(positions.find(p=>p.id===id),{x,y});
const keys=[[0,20,34],[1.5,20,34],[3,50,34],[4,50,34],[5.4,75,34],[6.3,75,34],[7.3,85,55],[8,85,55],[9,87,34],[10,87,34],[11,104.7,34],[12,104.7,34]];
function drawSource(t){const source=$('source'),c=source.getContext('2d');c.fillStyle='#193723';c.fillRect(0,0,630,408);c.strokeStyle='#559066';c.lineWidth=1;c.strokeRect(1,1,628,406);c.beginPath();c.moveTo(315,0);c.lineTo(315,408);c.stroke();
  positions.forEach((p,i)=>{c.fillStyle=`rgb(${identities[i].rgb.join(',')})`;c.beginPath();c.arc(p.x*6,p.y*6,9,0,Math.PI*2);c.fill();});
  let a=keys[0],b=keys.at(-1);for(let i=1;i<keys.length;i++)if(t<=keys[i][0]){a=keys[i-1];b=keys[i];break;}
  const f=Math.max(0,Math.min(1,(t-a[0])/(b[0]-a[0])));c.fillStyle='#fff';c.beginPath();c.arc((a[1]+(b[1]-a[1])*f)*6,(a[2]+(b[2]-a[2])*f)*6,5,0,Math.PI*2);c.fill();
}
function load(blob){if(videoURL)URL.revokeObjectURL(videoURL);videoURL=URL.createObjectURL(blob);video.src=videoURL;$('analyze').disabled=false;$('download').href=videoURL;$('download').download='matchlens-calibrated.webm';$('download').hidden=false;}
$('generate').onclick=async()=>{try{
  $('generate').disabled=true;video.pause();const source=$('source');drawSource(0);
  const stream=source.captureStream(24);const type=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm','video/mp4'].find(t=>MediaRecorder.isTypeSupported(t));
  if(!type)throw localizedError('lab.unsupported');
  const recorder=new MediaRecorder(stream,{mimeType:type,videoBitsPerSecond:4000000}),chunks=[];
  recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
  const stopped=new Promise(resolve=>recorder.onstop=resolve);recorder.start();const started=performance.now();
  await new Promise(resolve=>{function frame(now){const t=(now-started)/1000;drawSource(t);$('status').textContent=translate('lab.generating',{seconds:Math.min(12,t).toFixed(1)});if(t<12)requestAnimationFrame(frame);else resolve();}requestAnimationFrame(frame);});
  recorder.stop();await stopped;stream.getTracks().forEach(t=>t.stop());video.onloadeddata=()=>analyze().catch(e=>$('status').textContent=errorText(e));load(new Blob(chunks,{type}));
}catch(error){$('status').textContent=errorText(error);}finally{$('generate').disabled=false;}};
$('file').onchange=()=>{const file=$('file').files[0];if(file){generation++;load(file);$('status').textContent=translate('lab.loaded');}};
async function analyze(){
  const run=++generation;video.pause();video.currentTime=0;records=[];$('events').replaceChildren();const temporal=new TemporalEvents();let frames=0,latest=-1,skipped=0;
  const metadata={schema_version:'1.1',record_type:'metadata',id:'video-meta',match_id:'video-lab',event_time_ms:0,observed_at_ms:0,source:'classical_vision_estimate',pitch:{length_m:105,width_m:68},teams:[{id:'A',name:'Atlas',attack_direction_x:1},{id:'U',name:'Union',attack_direction_x:-1}],roster:identities.map(({rgb,...p})=>p),match_clock_start_ms:0,initial_score:{A:0,U:0},initial_possession_team_id:'A',channels:{events:'available',tracking:'available',event_positions:'available',pressure:'unavailable'},observation_scope:'excerpt'};records.push(metadata);
  await video.play();
  function process(){if(run!==generation)return;const t=Math.round(video.currentTime*1000);
    if(t>latest){ctx.drawImage(video,0,0,630,408);const frame=detectPixels(ctx.getImageData(0,0,630,408).data,630,408);const result=temporal.update(frame,t);frames++;if(!frame.ball)skipped++;
      records.push({schema_version:'1.1',record_type:'tracking',id:`vt${frames}`,match_id:'video-lab',event_time_ms:t,observed_at_ms:t,source:'classical_vision_estimate',period:1,status:frame.ball?'estimated':'missing',players:frame.players,ball:frame.ball,possession_team_id:temporal.owner?.[0]||null});
      records.push(...result.events);for(const event of result.events){const li=document.createElement('li');li.textContent=`${(event.event_time_ms/1000).toFixed(2)}s · ${eventLabel(event.type)} · ${event.player_id}${event.receiver_id?' → '+event.receiver_id:''}${event.distance_m?' · '+event.distance_m+' m':''}`;$('events').append(li);}
      ctx.strokeStyle='#fff8a0';for(const p of frame.players){ctx.strokeRect(p.x*6-10,p.y*6-10,20,20);}if(frame.ball){ctx.strokeStyle='#fff';ctx.beginPath();ctx.arc(frame.ball.x*6,frame.ball.y*6,8,0,Math.PI*2);ctx.stroke();}
      $('metrics').textContent=translate('lab.metrics',{frames,players:frame.players.length,speed:result.speed_mps??'—',events:temporal.events.length,missing:skipped});
      $('status').textContent=translate('lab.processing',{seconds:video.currentTime.toFixed(1)});latest=t;
    }
    if(!video.ended&&!video.paused){if(video.requestVideoFrameCallback)video.requestVideoFrameCallback(process);else requestAnimationFrame(process);}else{$('status').textContent=translate('lab.complete',{events:temporal.events.length,frames});$('export').disabled=false;}
  }
  if(video.requestVideoFrameCallback)video.requestVideoFrameCallback(process);else requestAnimationFrame(process);
  video.onended=()=>{if(run===generation){$('status').textContent=translate('lab.complete',{events:temporal.events.length,frames});$('export').disabled=false;}};
}
$('analyze').onclick=()=>analyze().catch(e=>$('status').textContent=errorText(e));
$('export').onclick=()=>{if(outputURL)URL.revokeObjectURL(outputURL);outputURL=URL.createObjectURL(new Blob([records.map(r=>JSON.stringify(r)).join('\n')+'\n'],{type:'application/x-ndjson'}));const a=document.createElement('a');a.href=outputURL;a.download='matchlens-video-events.jsonl';a.click();};

document.body.dataset.pageTitle='lab.title';addLanguagePicker(document.querySelector('.toolbar'));applyTranslations();
