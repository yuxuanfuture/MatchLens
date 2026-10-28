import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { ReplayCrowdAudio } from '../dist/crowd-audio.js';

function harness(load = async () => ({ duration:120 })) {
  let now = 0;
  const sources = [];
  const context = {
    state:'suspended', currentTime:0, destination:{},
    async resume() { this.state='running'; },
    createBufferSource() {
      const source = { playbackRate:{value:1}, connect(){}, disconnect(){},
        start(when, offset, duration) { this.offset=offset; this.duration=duration; this.started=true; },
        stop() { this.stopped=true; } };
      sources.push(source); return source;
    }
  };
  const player = new ReplayCrowdAudio({createContext:()=>context, load, now:()=>now});
  return { player, sources, context, advance(seconds) { now+=seconds; context.currentTime+=seconds; } };
}
const snapshot = (seconds, overrides={}) => ({stream:'stream-04',session_id:'s1',epoch:0,
  playing:true,speed:1,review:{phase:seconds>=115?'awarded':'awaiting_decision'},
  playback:{position_ms:seconds*1000,duration_ms:120000,ended:false},...overrides});

test('sound follows presentation time and pauses without restarting on ordinary updates',async()=>{
  const h=harness();
  h.player.update(snapshot(72));
  assert.equal(h.sources.length,0,'no audio before a user gesture');
  await h.player.unlock();
  assert.equal(h.sources[0].offset,72);
  h.advance(.5);h.player.update(snapshot(72.5));
  assert.equal(h.sources.length,1,'normal server ticks must not replay the sound');
  h.player.update(snapshot(72.5,{playing:false}));
  assert.equal(h.sources[0].stopped,true);
  h.player.update(snapshot(72.5));
  assert.equal(h.sources.at(-1).offset,72.5);
});

test('seeking, fast-forward, muting and leaving this replay stop the old sound',async()=>{
  const h=harness();await h.player.unlock();h.player.update(snapshot(115));
  const goal=h.sources.at(-1);
  h.player.update(snapshot(30,{epoch:1}));
  assert.equal(goal.stopped,true);assert.equal(h.sources.at(-1).offset,30);
  h.player.update(snapshot(30,{epoch:1,speed:4}));
  assert.equal(h.sources.at(-1).stopped,true);assert.equal(h.player.status,'fast');
  h.player.update(snapshot(70,{epoch:1,speed:1}));
  assert.equal(h.sources.at(-1).offset,70);
  h.player.setEnabled(false);assert.equal(h.sources.at(-1).stopped,true);
  h.player.setEnabled(true);assert.equal(h.sources.at(-1).offset,70);
  h.player.update(snapshot(70,{stream:'imported'}));assert.equal(h.sources.at(-1).stopped,true);
  const count=h.sources.length;
  h.player.update(snapshot(120,{playback:{position_ms:120000,duration_ms:120000,ended:true}}));
  assert.equal(h.sources.length,count,'no start at or after the clip end');
});

test('loading and control races never revive stale audio, and hidden/disconnected pages are silent',async()=>{
  let finishLoad;
  const h=harness(()=>new Promise(resolve=>{finishLoad=resolve;}));
  h.player.update(snapshot(90));
  const loading=h.player.unlock();await Promise.resolve();
  const releaseFirst=h.player.hold(),releaseSecond=h.player.hold();
  h.player.update(snapshot(115,{epoch:1}));
  finishLoad({duration:120});await loading;
  assert.equal(h.sources.length,0,'a pending control keeps late audio loads silent');
  releaseFirst();assert.equal(h.sources.length,0);
  releaseSecond();assert.equal(h.sources[0].offset,115);
  releaseSecond();assert.equal(h.sources.length,1,'release is idempotent');
  h.player.setHidden(true);assert.equal(h.sources.at(-1).stopped,true);
  h.player.setHidden(false);assert.equal(h.sources.at(-1).offset,115);
  h.player.disconnect();assert.equal(h.sources.at(-1).stopped,true);
  h.player.update(snapshot(0,{epoch:2}));assert.equal(h.sources.at(-1).offset,0);
});

test('a pause requested during loading stays silent when decoding finishes first',async()=>{
  let finishLoad;
  const h=harness(()=>new Promise(resolve=>{finishLoad=resolve;}));
  h.player.update(snapshot(5));const loading=h.player.unlock();await Promise.resolve();
  const release=h.player.hold();
  finishLoad({duration:120});await loading;
  assert.equal(h.sources.length,0,'the pending pause blocks a late decode');
  h.player.update(snapshot(5,{playing:false}));release();
  assert.equal(h.sources.length,0,'the completed pause must not revive the old playing state');
});

test('missing audio is recoverable and does not override the user mute choice',async()=>{
  let attempts=0;
  const h=harness(async()=>{if (++attempts===1)throw new Error('missing file');return {duration:120};});
  h.player.update(snapshot(90));
  const loading=h.player.unlock();h.player.setEnabled(false);await loading;
  assert.equal(h.player.status,'off');assert.equal(h.sources.length,0);
  h.player.setEnabled(true);await h.player.unlock();
  assert.equal(h.player.status,'on');assert.equal(h.sources.at(-1).offset,90);
});

test('the confirmation cheer cannot precede the received VAR decision',async()=>{
  const h=harness();await h.player.unlock();h.player.update(snapshot(114));
  assert.equal(h.sources[0].duration,1,'running audio must end before the confirmation cheer');
  h.advance(1.2);h.player.update(snapshot(115.2));
  assert.equal(h.sources[0].stopped,true);
  assert.equal(h.sources.at(-1).offset,115.2,'received confirmation opens the final cheer');

  let finishLoad;
  const late=harness(()=>new Promise(resolve=>{finishLoad=resolve;}));
  late.player.update(snapshot(114.8));
  const loading=late.player.unlock();await Promise.resolve();late.advance(.4);
  finishLoad({duration:120});await loading;
  assert.equal(late.sources.length,0,'a slow load cannot infer that VAR has confirmed');
  late.player.update(snapshot(115.2,{review:{phase:'awaiting_decision'}}));
  assert.equal(late.sources.length,0,'elapsed time alone cannot unlock the cheer');
  late.player.update(snapshot(115.2));assert.equal(late.sources.at(-1).offset,115.2);
});

test('the soundtrack covers 86 seconds, includes review chatter, and waits for goal confirmation',()=>{
  const plan=JSON.parse(readFileSync(new URL('../data/stream-04-audio.json',import.meta.url)));
  const records=readFileSync(new URL('../data/streams/stream-04.jsonl',import.meta.url),'utf8').trim().split('\n').map(JSON.parse);
  const goal=records.find(row=>row.type==='goal');
  const celebrations=plan.cues.filter(cue=>cue.source==='07');
  assert.equal(celebrations[0].start,90);
  assert.equal(celebrations[1].start,(goal.observed_at_ms-80)/1000);
  assert.equal(celebrations[1].start,115);
  assert.deepEqual(Object.keys(plan.sources).sort(),['01','02','04','05','06','07']);
  const murmur=plan.cues.find(cue=>cue.source==='06');
  const reviewStarted=records.find(row=>row.type==='var'&&row.stage==='on_field_review_started');
  const reviewCompleted=records.find(row=>row.type==='var'&&row.stage==='on_field_review_completed');
  assert.equal(murmur.start,(reviewStarted.observed_at_ms-80)/1000);
  assert.equal(murmur.end,(reviewCompleted.observed_at_ms-80)/1000);
  assert.equal(murmur.fade_out,2,'discussion fades through 112–114 seconds');
  assert.ok(murmur.gain_from<=.3&&murmur.gain_to<=.3,'discussion stays well below the goal cheer');
  let covered=0;
  for(let tenth=0;tenth<1200;tenth++){
    const time=tenth/10+.05;
    const audible=plan.cues.some(cue=>time>=cue.start&&time<cue.end);
    if(audible)covered++;
    if((time>=95&&time<104)||(time>=114&&time<115))assert.equal(audible,false,'quiet before review and before the final decision');
    if(time>=104&&time<114)assert.equal(audible,true,'review has low conversation');
  }
  assert.equal(covered,860);
  assert.equal(plan.audible_seconds,86);
  assert.equal(plan.cues.find(cue=>cue.source==='04').start,72);
  assert.equal(plan.cues.find(cue=>cue.source==='05').start,92);
});
