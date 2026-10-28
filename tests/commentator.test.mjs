import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { commentatorPose } from '../dist/commentator-state.js';
import { CommentatorPortrait } from '../dist/commentator-avatar.js';

const records=readFileSync(new URL('../data/streams/stream-04.jsonl',import.meta.url),'utf8').trim().split(/\r?\n/).map(JSON.parse);
const metadata=records[0];
function moment(seconds, phase='none') {
  const asOf=seconds*1000+80, received=records.filter(record=>record.observed_at_ms<=asOf);
  const events=received.filter(record=>record.record_type==='event');
  const reviewId={pending:'s002',flagged:'o001',checking:'v001',review_requested:'v003',reviewing:'v004',awaiting_decision:'v005',awarded:'d002'}[phase];
  const ruling=events.find(event=>event.id===reviewId);
  return {session_id:'commentator-test',epoch:0,playing:false,speed:1,as_of_ms:asOf,
    playback:{position_ms:seconds*1000,duration_ms:120000,receive_offset_ms:80},
    state:{...metadata,score:{A:0,U:phase==='awarded'?1:0}},
    tracking:received.filter(record=>record.record_type==='tracking').at(-1),events,
    review:{phase,observed_at_ms:ruling?.observed_at_ms,subject_team_id:'U',subject_player_id:'U9',evidence_ids:phase==='awarded'?['d002','g001']:[]}};
}

test('the same commentator reacts to the received attack, tackle, counter and one-on-one',()=>{
  assert.equal(commentatorPose(moment(8)).mood,'explaining');
  assert.equal(commentatorPose(moment(60)).mood,'attacking');
  assert.equal(commentatorPose(moment(71.5)).mood,'attacking');
  assert.equal(commentatorPose(moment(72.3)).mood,'surprised');
  assert.equal(commentatorPose(moment(78)).mood,'counter');
  assert.equal(commentatorPose(moment(86.5)).mood,'one-on-one');
  assert.equal(commentatorPose(moment(89.7)).mood,'shot');
});

test('VAR stops excitement and confirmation alone triggers the full celebration',()=>{
  assert.equal(commentatorPose(moment(90.2,'pending')).mood,'hopeful');
  assert.equal(commentatorPose(moment(91,'flagged')).mood,'puzzled');
  assert.equal(commentatorPose(moment(95,'checking')).mood,'puzzled');
  for(const [time,phase] of [[100,'review_requested'],[108,'reviewing'],[114.5,'awaiting_decision']])
    assert.equal(commentatorPose(moment(time,phase)).mood,'listening');
  assert.equal(commentatorPose(moment(116,'awarded')).mood,'celebrating');
  assert.equal(commentatorPose(moment(120,'awarded')).mood,'settled');
});

test('pause, seek and a fresh session produce deterministic poses, without future reactions',()=>{
  const paused=moment(108,'reviewing');
  assert.deepEqual(commentatorPose(paused,{elapsed:30}),commentatorPose(paused));
  const playing={...paused,playing:true};
  assert.notDeepEqual(commentatorPose(playing,{elapsed:.2}),commentatorPose(playing));
  assert.deepEqual(commentatorPose(playing,{elapsed:30}),commentatorPose(playing,{elapsed:.5}));
  commentatorPose(moment(116,'awarded'));
  assert.deepEqual(commentatorPose({...moment(8),epoch:1}),commentatorPose(moment(8)));
  assert.deepEqual(commentatorPose({...moment(0),session_id:'new'}),commentatorPose(moment(0)));
  const beforeTackle=moment(71.5);
  beforeTackle.events=records.filter(record=>record.record_type==='event');
  assert.equal(commentatorPose(beforeTackle).mood,'attacking');
  const futureRuling={...moment(89),review:moment(116,'awarded').review};
  assert.notEqual(commentatorPose(futureRuling).mood,'celebrating');
  const futurePending={...moment(89.8),playing:true,review:moment(90.2,'pending').review};
  assert.notEqual(commentatorPose(futurePending,{elapsed:.4}).mood,'hopeful');
  assert.equal(commentatorPose(null).mood,'idle');
});

test('reduced motion keeps expressive static poses without blinking, speaking or bouncing',()=>{
  for(const [start,end,phase] of [[105,109,'reviewing'],[116,119,'awarded']]){
    const first=commentatorPose(moment(start,phase),{reduced:true});
    const later=commentatorPose(moment(end,phase),{reduced:true});
    assert.deepEqual(first,later);
    assert.equal(first.lift,0);
    assert.equal(first.blink,0);
  }
});

test('all poses fit the existing portrait space and a paused portrait does not repaint',()=>{
  let points=[],paints=0;
  const ctx={setTransform(){},clearRect(){points=[];paints++;},ellipse(){},beginPath(){},closePath(){},fill(){},
    moveTo(x,y){points.push([x,y]);},lineTo(x,y){points.push([x,y]);}};
  const canvas={width:224,height:270,dataset:{},parentElement:{dataset:{}},getContext:()=>ctx};
  const portrait=new CommentatorPortrait(canvas);
  for(const [time,phase] of [[8,'none'],[60,'none'],[72.3,'none'],[86.5,'none'],[90.2,'pending'],[95,'checking'],[108,'reviewing'],[116,'awarded']]){
    const pose=commentatorPose(moment(time,phase));
    portrait.render(pose);
    assert.ok(points.length>100);
    assert.ok(points.every(([x,y])=>Number.isFinite(x)&&Number.isFinite(y)&&x>=0&&x<=112&&y>=0&&y<=135),
      `${pose.mood}: ${JSON.stringify(points.filter(([x,y])=>x<0||x>112||y<0||y>135).slice(0,4))}`);
    const painted=paints;
    portrait.render(pose);
    assert.equal(paints,painted);
  }
});
