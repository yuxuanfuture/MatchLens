import { playbackView } from './replay-view.js';

async function loadSoundtrack(context) {
  const response = await fetch(new URL('./audio/stream-04-crowd.mp3', import.meta.url));
  if (!response.ok) throw new Error('Crowd soundtrack unavailable');
  return context.decodeAudioData(await response.arrayBuffer());
}

// One continuous soundtrack uses the same presentation clock as the stadium.
export class ReplayCrowdAudio {
  constructor({createContext=()=>new AudioContext(), load=loadSoundtrack,
    now=()=>performance.now()/1000, onStatus=()=>{}, enabled=true}={}) {
    Object.assign(this,{createContext,load,now,onStatus,enabled});
    this.source=null;this.snapshot=null;this.context=null;this.buffer=null;
    this.status=null;this.receivedAt=0;this.loading=null;this.failed=false;
    this.holds=0;this.hidden=false;this.disconnected=false;
  }

  update(payload) {
    this.snapshot=payload;this.receivedAt=this.now();this.disconnected=false;this.reconcile();
  }

  async unlock() {
    if (!this.enabled) return;
    try {
      this.failed=false;
      this.context ||= this.createContext();
      await this.context.resume();
      if (!this.buffer) {
        this.loading ||= this.load(this.context);
        this.setStatus(this.enabled?'loading':'off');
        this.buffer=await this.loading;
      }
      this.reconcile();
    } catch {
      this.loading=null;this.failed=true;this.stop();this.reconcile();
    }
  }

  stop() {
    if (this.source) {this.source.stop();this.source.disconnect();this.source=null;}
  }

  setStatus(value) {
    if (this.status!==value) {this.status=value;this.onStatus(value);}
  }

  setEnabled(value) {this.enabled=!!value;this.reconcile();}

  // Pending controls can overlap; releasing one must not resume another's audio.
  hold() {
    this.holds++;this.stop();let released=false;
    return ()=>{if (!released) {released=true;this.holds--;this.reconcile();}};
  }

  setHidden(value) {this.hidden=value;this.reconcile();}
  disconnect() {this.disconnected=true;this.stop();}

  reconcile() {
    const payload=this.snapshot,view=playbackView(payload);
    this.setStatus(!this.enabled?'off':this.failed?'unavailable':payload?.speed>1?'fast':this.loading&&!this.buffer?'loading':'on');
    if (this.holds || this.hidden || this.disconnected || !this.enabled || payload?.stream!=='stream-04' || !payload.playback ||
      !payload.playing || view.ended || !this.buffer || this.context?.state!=='running') {
      this.stop();return;
    }
    if (payload.speed!==1) {this.stop();return;}
    // Never let a running source or a late decode reveal the VAR outcome early.
    const confirmed=payload.review?.phase==='awarded';
    const duration=Math.min(view.duration_ms/1000,this.buffer.duration,confirmed?Infinity:115);
    const position=Math.min(duration,view.position_ms/1000+this.now()-this.receivedAt);
    if (position>=duration) {this.stop();return;}
    const scope=`${payload.session_id}:${payload.epoch}`;
    const drift=this.source?Math.abs(this.startedAtPosition+this.context.currentTime-this.startedAt-position):Infinity;
    if (!this.source || scope!==this.scope || duration!==this.sourceEnd || drift>.35) {
      this.stop();
      this.source=this.context.createBufferSource();this.source.buffer=this.buffer;
      this.source.connect(this.context.destination);this.source.start(0,position,duration-position);
      this.startedAt=this.context.currentTime;this.startedAtPosition=position;this.scope=scope;this.sourceEnd=duration;
    }
  }
}
