import test from 'node:test';
import assert from 'node:assert/strict';
import {getSnapshot,matches,DURATION} from '../dist/matches.js';
import {makeProjection} from '../dist/pocket-renderer.js';

test('all 22 players stay uniquely numbered and inside the pitch through every scene',()=>{
  for(const scene of Object.keys(matches))for(let t=0;t<=DURATION;t+=.2){
    const snapshot=getSnapshot(scene,t);
    assert.equal(snapshot.players.length,22);
    assert.equal(new Set(snapshot.players.map(p=>p.team+':'+p.number)).size,22);
    for(const p of snapshot.players)assert.ok(p.x>=0&&p.x<=105&&p.y>=0&&p.y<=68,`${scene}/${t}: player ${p.number} left the field`);
  }
});
test('completed passes arrive at the documented receiver, not a disconnected animation',()=>{
  for(const [id,scene] of Object.entries(matches))for(const event of scene.events.filter(e=>e.type==='pass')){
    const number=Number(event.title.split('→')[1].trim()),snapshot=getSnapshot(id,event.at);
    const receiver=snapshot.players.find(p=>p.team==='blue'&&p.number===number);
    assert.ok(receiver,`${id}: receiver is missing`);
    assert.ok(Math.hypot(receiver.x-snapshot.ball[0],receiver.y-snapshot.ball[1])<1,`${id}: pass misses receiver`);
  }
});
test('seeking backward removes later evidence and goals',()=>{
  assert.equal(getSnapshot('counter',24).goaled,true);
  const before=getSnapshot('counter',5);
  assert.equal(before.goaled,false);assert.equal(before.passes,0);assert.deepEqual(before.events.map(e=>e.id),['C01']);
  assert.equal(getSnapshot('counter',11).passes,2);
  assert.equal(getSnapshot('press',24).backwards,2);
});
test('substitution preserves 11 players and the completed outfield shape is 3–2–5',()=>{
  const before=getSnapshot('shape',2),after=getSnapshot('shape',24);
  assert.ok(before.players.some(p=>p.team==='blue'&&p.number===11));
  assert.ok(!after.players.some(p=>p.team==='blue'&&p.number===11));
  assert.ok(after.players.some(p=>p.team==='blue'&&p.number===17));
  const field=after.players.filter(p=>p.team==='blue'&&p.number!==1);
  assert.deepEqual([field.filter(p=>p.x<40).length,field.filter(p=>p.x>=40&&p.x<60).length,field.filter(p=>p.x>=60).length],[3,2,5]);
});
test('projected world coordinates meet all four illustrated field corners',()=>{
  const corners=[[925,330],[1527,537],[1204,782],[486,503]],project=makeProjection(corners);
  [[0,0],[105,0],[105,68],[0,68]].forEach((point,index)=>{const screen=project(...point);assert.ok(Math.hypot(screen[0]-corners[index][0],screen[1]-corners[index][1])<1e-8);});
});
