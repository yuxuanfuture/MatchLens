import test from 'node:test';
import assert from 'node:assert/strict';
import { toSnapshot } from '../dist/live-client.js';
import { celebrationCopy } from '../dist/goal-celebration-copy.js';
import { celebrationPose } from '../dist/goal-effects.js';

function moment(seconds, phase = 'none') {
  return {
    session_id:'celebration-test', epoch:0, playing:false, speed:1,
    as_of_ms:seconds*1000+80,
    playback:{position_ms:seconds*1000, duration_ms:120000, receive_offset_ms:80},
    state:{score:{A:0,U:phase==='awarded'?1:0},
      teams:[{id:'A',name:'Atlas',attack_direction_x:1},{id:'U',name:'Union',attack_direction_x:-1}],
      roster:[{id:'U9',name:'Union 9',team_id:'U',shirt_number:9}]},
    review:{phase,subject_team_id:'U',subject_player_id:'U9',
      observed_at_ms:phase==='awarded'?115080:90080,evidence_ids:phase==='awarded'?['g001','d002']:['s002']},
    evidence_records:phase==='awarded'?[{id:'g001',type:'goal',team_id:'U',player_id:'U9',event_time_ms:90000,observed_at_ms:115080}]:[],
    overlays:[],events:[]
  };
}

test('celebration follows the received ruling, with a short pending reaction and a five-second confirmation',()=>{
  assert.equal(toSnapshot(moment(89)).celebration,null);
  const pending=toSnapshot(moment(90.2,'pending')).celebration;
  assert.equal(pending.kind,'pending');
  assert.equal(pending.team,'coral');
  assert.equal(toSnapshot(moment(90.5,'flagged')).celebration,null);
  for(const phase of ['checking','review_requested','reviewing','awaiting_decision'])
    assert.equal(toSnapshot(moment(114.9,phase)).celebration,null);
  const confirmed=toSnapshot(moment(115.25,'awarded')).celebration;
  assert.equal(confirmed.kind,'confirmed');
  assert.equal(confirmed.age,.25);
  assert.equal(confirmed.goalX,0);
  assert.equal(confirmed.playerName,'Union 9');
  assert.equal(confirmed.teamName,'Union');
  assert.equal(toSnapshot(moment(119.8,'awarded')).celebration.kind,'confirmed');
  assert.equal(toSnapshot(moment(120,'awarded')).celebration,null);
});

test('paused, rewound, and newly opened replays cannot keep an old celebration running',()=>{
  const paused=moment(116,'awarded');
  assert.equal(toSnapshot(paused,undefined,20).celebration.age,1);
  const playing={...paused,playing:true};
  assert.ok(Math.abs(toSnapshot(playing,undefined,.3).celebration.age-1.3)<1e-9);
  assert.equal(toSnapshot(playing,undefined,20).celebration.age,1.5);
  assert.equal(toSnapshot({...moment(92,'checking'),epoch:1},undefined,.2).celebration,null);
  assert.equal(toSnapshot({...moment(0),session_id:'new-session'},undefined,.2).celebration,null);
  const unreceived=moment(114.9,'awarded');
  assert.equal(toSnapshot(unreceived).celebration,null);
});

test('confirmed effects use the scoring team and its actual attacking goal',()=>{
  const payload=moment(116,'awarded');
  payload.state.teams[1].attack_direction_x=1;
  assert.equal(toSnapshot(payload).celebration.goalX,105);
  payload.evidence_records[0].team_id='A';
  payload.state.teams[0].attack_direction_x=-1;
  const cue=toSnapshot(payload).celebration;
  assert.equal(cue.team,'blue');
  assert.equal(cue.goalX,0);
});

test('celebration text follows all five interface languages and the received score',()=>{
  const cue=toSnapshot(moment(116,'awarded')).celebration;
  const expected={en:'GOAL!',zh:'进球有效！',fr:'BUT !',es:'¡GOL!',ar:'هدف!'};
  for(const [language,headline] of Object.entries(expected)){
    const copy=celebrationCopy(cue,language);
    assert.equal(copy.headline,headline);
    assert.equal(copy.score,'0 – 1');
    assert.ok(copy.title.includes('Union'));
    assert.ok(copy.body.includes('Union 9'));
    assert.doesNotMatch(copy.body,/undefined|\{\w+\}/);
  }
});

test('only the scoring side cheers, and reduced motion keeps a still raised-arm pose',()=>{
  const cue=toSnapshot(moment(116,'awarded')).celebration;
  const scorer={id:'U9',number:9,team:'coral'},opponent={id:'A9',number:9,team:'blue'};
  assert.deepEqual(celebrationPose(cue,opponent,false),{lift:0,armsRaised:0});
  assert.ok(celebrationPose(cue,scorer,false).armsRaised>.7);
  const still=celebrationPose(cue,scorer,true);
  assert.equal(still.lift,0);
  assert.deepEqual(celebrationPose({...cue,age:4.8},scorer,true),still);
});
