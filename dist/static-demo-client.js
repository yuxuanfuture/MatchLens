const dataUrl = name => new URL(`./demo-data/${name}`, import.meta.url);
const clone = value => typeof structuredClone === 'function'
  ? structuredClone(value)
  : JSON.parse(JSON.stringify(value));
const clamp = (value,min,max)=>Math.max(min,Math.min(max,value));

export function staticDemoEnabled(locationObject=globalThis.location) {
  if(!locationObject)return false;
  const query=new URLSearchParams(locationObject.search||'');
  return query.get('demo')==='1'||String(locationObject.hostname||'').endsWith('.github.io');
}

export function playerFocus(records,player,asOfMs) {
  if(!player)return null;
  const visible=records.filter(row=>Math.max(row.event_time_ms,row.observed_at_ms)<=asOfMs);
  const events=visible.filter(row=>row.record_type==='event');
  const passes=events.filter(row=>row.type==='pass'&&row.player_id===player.id&&row.outcome==='complete');
  const shots=events.filter(row=>row.type==='shot'&&row.player_id===player.id);
  const samples=[];
  for(const frame of visible.filter(row=>row.record_type==='tracking')){
    const point=frame.players?.find(item=>item.player_id===player.id);
    if(point)samples.push({id:frame.id,time:frame.event_time_ms,x:point.x,y:point.y});
  }
  let distance=0,peak=null;
  for(let index=1;index<samples.length;index++){
    const previous=samples[index-1],current=samples[index];
    const travelled=Math.hypot(current.x-previous.x,current.y-previous.y);
    const seconds=(current.time-previous.time)/1000;
    distance+=travelled;
    if(seconds>0)peak=Math.max(peak??0,travelled/seconds);
  }
  return {
    player,
    completed_passes:passes.length,
    shots:shots.length,
    observed_distance_m:Math.round(distance*10)/10,
    peak_sampled_speed_mps:peak===null?null:Math.round(peak*10)/10,
    sprint_threshold_reached:(peak??0)>=7,
    evidence_ids:[...passes,...shots].map(row=>row.id),
    tracking_evidence_ids:samples.slice(-40).map(row=>row.id),
  };
}

export class StaticDemoClient {
  constructor(onUpdate,onError,options={}) {
    this.onUpdate=onUpdate;this.onError=onError;this.translate=options.translate||((key)=>key);
    this.queue=Promise.resolve();this.cache=new Map();this.preferences={};this.position=0;
    this.playing=false;this.speed=1;this.epoch=0;this.sequence=0;this.id='static-demo';
    this.frame=null;this.lastFrame=0;this.lastEmit=0;
  }
  async jsonFile(name) {
    if(this.cache.has(name))return this.cache.get(name);
    const response=await fetch(dataUrl(name));
    if(!response.ok)throw new Error(this.translate('error.request',{status:response.status}));
    const value=await response.json();this.cache.set(name,value);return value;
  }
  async prepare(language='en') {
    const [manifest,records,dataset]=await Promise.all([
      this.jsonFile('manifest.json'),this.jsonFile('records.json'),this.jsonFile(`${language}.json`),
    ]);
    this.manifest=manifest;this.records=records;this.dataset=dataset;
  }
  async open(stream,preferences={}) {
    this.stop();this.preferences={language:'en',mode:'fan',role:'fan',focus_team:'A',focus_player:null,metric:'overview',...preferences};
    await this.prepare(this.preferences.language);this.position=0;this.playing=false;this.speed=1;this.epoch++;
    this.emit();
  }
  async attach() {return this.open('stream-04',this.preferences);}
  index() {return clamp(Math.floor(this.position/this.manifest.interval_ms),0,this.dataset.snapshots.length-1);}
  build() {
    const payload=clone(this.dataset.snapshots[this.index()]);
    const position=Math.round(this.position),offset=this.manifest.receive_offset_ms;
    payload.session_id=this.id;payload.source_mode='static_demo';payload.playing=this.playing;
    payload.speed=this.speed;payload.epoch=this.epoch;payload.sequence=++this.sequence;
    payload.as_of_ms=offset+position;payload.preferences={...payload.preferences,...this.preferences};
    payload.playback={...payload.playback,position_ms:position,
      match_clock_ms:payload.state.match_clock_start_ms+position,
      ended:position>=this.manifest.duration_ms};
    payload.state.match_clock_ms=payload.playback.match_clock_ms;
    const person=payload.state.roster.find(item=>item.id===this.preferences.focus_player);
    payload.focus=playerFocus(this.records,person,payload.as_of_ms);
    return payload;
  }
  emit() {this.current=this.build();this.onUpdate(this.current);return this.current;}
  control(command={}) {
    this.queue=this.queue.catch(()=>{}).then(async()=>{
      if(command.preferences){
        const next={...this.preferences,...command.preferences};
        if(next.language!==this.preferences.language)await this.prepare(next.language);
        this.preferences=next;this.epoch++;
      }
      if(command.seek_ms!==undefined){this.position=clamp(command.seek_ms-this.manifest.receive_offset_ms,0,this.manifest.duration_ms);this.epoch++;}
      if(command.media_time_ms!==undefined){this.position=clamp(command.media_time_ms-this.manifest.receive_offset_ms,0,this.manifest.duration_ms);}
      if(command.speed!==undefined)this.speed=command.speed;
      if(command.playing!==undefined)this.playing=command.playing;
      if(this.position>=this.manifest.duration_ms)this.playing=false;
      const value=this.emit();this.playing?this.start():this.stop();return value;
    }).catch(error=>this.onError(error.message||this.translate('error.connection')));
    return this.queue;
  }
  start() {
    if(this.frame!==null||typeof requestAnimationFrame!=='function')return;
    this.lastFrame=performance.now();
    const tick=now=>{
      if(!this.playing){this.frame=null;return;}
      const elapsed=now-this.lastFrame;this.lastFrame=now;
      this.position=Math.min(this.manifest.duration_ms,this.position+elapsed*this.speed);
      if(now-this.lastEmit>=100||this.position>=this.manifest.duration_ms){this.lastEmit=now;this.emit();}
      if(this.position>=this.manifest.duration_ms){this.playing=false;this.emit();this.frame=null;return;}
      this.frame=requestAnimationFrame(tick);
    };
    this.frame=requestAnimationFrame(tick);
  }
  stop() {if(this.frame!==null&&typeof cancelAnimationFrame==='function')cancelAnimationFrame(this.frame);this.frame=null;}
  recap() {
    const team=this.preferences.focus_team==='U'?'U':'A';
    const value=clone(this.dataset.recaps[team][this.index()]);
    value.preferences={...value.preferences,...this.preferences};value.agent_status='locked';return Promise.resolve(value);
  }
  evidence(ids) {
    const allowed=new Set(this.current?.review?.evidence_ids||[]),wanted=new Set(ids);
    const records=this.records.filter(row=>wanted.has(row.id)&&Math.max(row.event_time_ms,row.observed_at_ms)<=this.current.as_of_ms)
      .map(row=>row.body_parts&&!allowed.has(row.id)?Object.fromEntries(Object.entries(row).filter(([key])=>key!=='body_parts')):row);
    return Promise.resolve({records:clone(records)});
  }
}
