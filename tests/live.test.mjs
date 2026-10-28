import test from 'node:test';
import assert from 'node:assert/strict';
import {toSnapshot,LiveClient} from '../dist/live-client.js';
import {detectPixels,TemporalEvents,palette,identities} from '../dist/video-detector.js';

test('missing tracking produces no invented players or ball',()=>{
  const snapshot=toSnapshot({as_of_ms:58000,state:{roster:[]},tracking:null,overlays:[],preferences:{}});
  assert.deepEqual(snapshot.players,[]);assert.equal(snapshot.ball,null);assert.equal(snapshot.goaled,false);
});
test('observed substitutions, identities and goal team reach renderer',()=>{
  const snapshot=toSnapshot({as_of_ms:1200,state:{roster:[{id:'U17',team_id:'U',shirt_number:17,name:'Test 17'}]},preferences:{focus_player:'U17'},tracking:{players:[{player_id:'U17',x:50,y:30}],ball:{x:40,y:32}},overlays:[{kind:'substitution',player_id:'U17',at_ms:1000},{kind:'goal',team_id:'U',at_ms:1100}]});
  assert.equal(snapshot.players[0].number,17);assert.equal(snapshot.players[0].focused,true);assert.equal(snapshot.players[0].drop,.9);assert.equal(snapshot.goalTeam,'coral');assert.equal(snapshot.goalAt,1.1);
});
test('client discards stale seeks and previous-stream updates',()=>{
  const accepted=[];const c=new LiveClient(v=>accepted.push(v),()=>{});c.id='current';c.generation=2;
  c.accept({session_id:'current',epoch:2,sequence:10});c.accept({session_id:'current',epoch:1,sequence:999});c.accept({session_id:'old',epoch:5,sequence:1000});c.accept({session_id:'current',epoch:2,sequence:9});
  assert.equal(accepted.length,1);
});
test('vision detects identities and ball from pixel buffers only',()=>{
  const width=320,height=200,data=new Uint8ClampedArray(width*height*4);
  for(let i=0;i<data.length;i+=4){data.set([25,55,35,255],i);}
  const dot=(x,y,rgb)=>{for(let dy=-4;dy<=4;dy++)for(let dx=-4;dx<=4;dx++)data.set([...rgb,255],((y+dy)*width+x+dx)*4);};
  palette.forEach((rgb,i)=>dot(12+(i%11)*26,20+Math.floor(i/11)*45,rgb));dot(150,140,[255,255,255]);
  const frame=detectPixels(data,width,height);assert.equal(frame.players.length,22);assert.ok(Math.abs(frame.ball.x-150/width*105)<.3);assert.deepEqual(frame.players.map(p=>p.player_id),identities.map(p=>p.id));
});
const frame=x=>({ball:{x,y:34},players:[{player_id:'A7',x:10,y:34},{player_id:'A9',x:40,y:34},{player_id:'U4',x:70,y:34}]});
test('temporal vision infers complete pass and interception without event labels',()=>{
  const d=new TemporalEvents();let t=0;for(const x of [10,10,20,30,40,40,40,50,60,70,70,70])d.update(frame(x),t+=100);
  assert.deepEqual(d.events.map(e=>e.type),['pass','pass','interception','recovery','possession_change']);
  assert.equal(d.events[0].outcome,'complete');assert.equal(d.events[1].outcome,'incomplete');assert.equal(d.events[0].distance_m,30);
});
test('vision never invents a completed pass across missing pixels or time gaps',()=>{
  const d=new TemporalEvents();d.update(frame(10),0);d.update(frame(10),100);d.update(frame(20),200);d.update({ball:null,players:[]},300);d.update(frame(40),400);d.update(frame(40),500);assert.equal(d.events.length,0);
  d.update(frame(50),600);d.update(frame(70),1600);d.update(frame(70),1700);assert.equal(d.events.length,0);
});
test('shot extraction reports completed flight but never asserts a goal',()=>{
  const d=new TemporalEvents();for(let i=0;i<12;i++){const x=i<2?87:Math.min(104,87+(i-1)*2);d.update({ball:{x,y:34},players:[{player_id:'A10',x:87,y:34}]},i*100);}
  assert.deepEqual(d.events.map(e=>e.type),['shot','shot_end']);assert.equal(d.events[1].shot_id,d.events[0].id);assert.ok(d.events[0].event_time_ms<d.events[1].event_time_ms);
});
