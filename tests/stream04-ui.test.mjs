import test from 'node:test';
import assert from 'node:assert/strict';
import { REPLAY_STREAMS, playbackView, receiveTime, evidenceVisible } from '../dist/replay-view.js';
import { toSnapshot } from '../dist/live-client.js';
import { BallRoll } from '../dist/football.js';

test('third slot opens stream 04 with 120 source seconds and correct seek conversion', () => {
  assert.deepEqual(REPLAY_STREAMS, ['stream-01', 'stream-02', 'stream-04', 'match-day']);
  const payload={as_of_ms:80,duration_ms:120080,state:{match_clock_ms:5400000,roster:[]},
    playback:{position_ms:0,duration_ms:120000,receive_offset_ms:80,match_clock_ms:5400000}};
  assert.equal(playbackView(payload).duration_ms,120000);
  assert.equal(receiveTime(payload,0),80);
  assert.equal(receiveTime(payload,120),120080);
  assert.equal(receiveTime(payload,150),120080);
  assert.equal(receiveTime(payload,-1),80);
  assert.equal(toSnapshot(payload).time,0);
  assert.equal(receiveTime({as_of_ms:1000,duration_ms:90080,state:{}},42),42000);
});

test('confirmation uses presentation time, independently of the old shot time', () => {
  const payload={as_of_ms:117080,state:{roster:[]},playback:{position_ms:117000,duration_ms:120000,receive_offset_ms:80},
    overlays:[{kind:'goal',at_ms:115000,event_time_ms:90000,team_id:'U'}]};
  const snapshot=toSnapshot(payload);
  assert.equal(snapshot.time-snapshot.goalAt,2);
  assert.equal(snapshot.goalTeam,'coral');
  assert.equal(snapshot.goaled,true);
});

test('evidence responses from a previous seek or case cannot reappear',()=>{
  const record={match_id:'match-04',event_time_ms:115000,observed_at_ms:115080};
  const requested={session_id:'session-04',epoch:1};
  const current={...requested,as_of_ms:115080,state:{match_id:'match-04'}};
  assert.equal(evidenceVisible(record,current,requested),true);
  assert.equal(evidenceVisible(record,{...current,epoch:2},requested),false);
  assert.equal(evidenceVisible(record,{...current,session_id:'session-01'},requested),false);
  assert.equal(evidenceVisible(record,{...current,as_of_ms:92080},requested),false);
});

test('football rolls on movement and freezes when paused, still, or reduced motion',()=>{
  const roll=new BallRoll(),project=(x,y)=>[x,y];
  const frame={ball:[0,0],time:0,sessionId:'04',epoch:1,playing:true};
  roll.advance(frame,project,10);
  const moved=roll.advance({...frame,ball:[10,0],time:.5},project,10);
  assert.notEqual(moved,0);
  for(let i=0;i<60;i++)assert.equal(roll.advance({...frame,ball:[10,0],time:1+i/60},project,10),moved);
  assert.equal(roll.advance({...frame,ball:[20,0],time:2,playing:false},project,10),moved);
  assert.equal(roll.advance({...frame,ball:[30,0],time:2.5},project,10,true),moved);
  assert.equal(roll.advance({...frame,ball:[100,0],time:90,epoch:2},project,10),0);
});
