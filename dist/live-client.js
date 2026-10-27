import { playbackView } from './replay-view.js';

export function toSnapshot(payload,formatName=value=>value) {
  const time = playbackView(payload).position_ms / 1000;
  const overlays = payload?.overlays || [];
  const goal = overlays.find(o => o.kind === 'goal');
  const roster = new Map((payload?.state.roster || []).map(p => [p.id, p]));
  const players = (payload?.tracking?.players || []).map(p => {
    const identity = roster.get(p.player_id);
    const substitution = overlays.find(o => o.kind === 'substitution' && o.player_id === p.player_id);
    return {id:p.player_id, name:formatName(identity?.name || p.player_id), number:identity?.shirt_number || 0,
      team:identity?.team_id === 'A' ? 'blue' : 'coral', x:p.x, y:p.y,
      drop:substitution ? Math.max(0, 1-(payload.as_of_ms-substitution.at_ms)/2000) : 0,
      focused:p.player_id === payload?.preferences.focus_player};
  });
  return {live:true, sceneId:'live', scene:{events:[]}, time, players,
    ball:payload?.tracking?.ball ? [payload.tracking.ball.x,payload.tracking.ball.y] : null,
    overlays, goaled:!!goal, goalAt:goal?.at_ms/1000, goalTeam:goal?.team_id==='A'?'blue':'coral',
    events:payload?.events || [], phase:{}, passes:0, backwards:0};
}

export class LiveClient {
  constructor(onUpdate,onError,options={}) {this.onUpdate=onUpdate;this.onError=onError;this.queue=Promise.resolve();this.generation=0;this.translate=options.translate||((key,values={})=>key==='error.request'?`Request failed (${values.status}).`:'Connection interrupted. Reconnecting.');}
  async json(path, body) {
    const response=await fetch(path,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
    const value=await response.json();if(!response.ok){const error=new Error(this.translate('error.request',{status:response.status}));error.localized=true;throw error;}return value;
  }
  accept(value,generation=this.generation) {
    if(generation!==this.generation || value.session_id!==this.id)return;
    if(this.current && (value.epoch<this.current.epoch || (value.epoch===this.current.epoch && value.sequence<this.current.sequence)))return;
    this.current=value;this.onUpdate(value);
  }
  async open(stream,preferences) {
    this.events?.close();const generation=++this.generation;this.current=null;
    const value=await this.json('/api/session',{stream,preferences});if(generation!==this.generation)return;
    this.id=value.session_id;this.accept(value,generation);
    this.events=new EventSource(`/api/stream?session=${this.id}`);
    this.events.onmessage=event=>this.accept(JSON.parse(event.data),generation);
    this.events.onerror=()=>this.onError(this.translate('status.reconnecting'));
  }
  async attach(id) {
    this.events?.close();const generation=++this.generation;this.current=null;this.id=id;
    const value=await this.json(`/api/state?session=${encodeURIComponent(id)}`);this.accept(value,generation);
    if(generation!==this.generation)return;
    this.events=new EventSource(`/api/stream?session=${encodeURIComponent(id)}`);
    this.events.onmessage=event=>this.accept(JSON.parse(event.data),generation);
    this.events.onerror=()=>this.onError(this.translate('status.reconnecting'));
  }
  control(command) {
    const generation=this.generation,id=this.id;if(!id)return Promise.resolve();
    this.queue=this.queue.catch(()=>{}).then(async()=>{
      if(generation!==this.generation)return;
      const value=await this.json('/api/control',{session:id,...command});this.accept(value,generation);
    }).catch(error=>this.onError(error.localized?error.message:this.translate('error.connection')));return this.queue;
  }
  recap() {return this.json(`/api/recap?session=${this.id}`);}
  evidence(ids) {return this.json(`/api/evidence?session=${this.id}&${ids.map(id=>`id=${encodeURIComponent(id)}`).join('&')}`);}
}
