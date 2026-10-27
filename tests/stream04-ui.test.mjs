import test from 'node:test';
import assert from 'node:assert/strict';
import { REPLAY_STREAMS, playbackView, receiveTime } from '../dist/replay-view.js';
import { toSnapshot } from '../dist/live-client.js';

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
