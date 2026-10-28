// Authored demo data: all clubs, positions, timestamps and events are synthetic.
export const DURATION = 24;
export const clamp = (value, min = 0, max = 1) => Math.max(min, Math.min(max, value));
const lerp = (a, b, t) => a + (b - a) * t;
export function sampleTrack(track, time) {
  const next = track.findIndex(point => point[0] > time);
  if (next === 0) return track[0].slice(1);
  if (next === -1) return track.at(-1).slice(1);
  const a = track[next - 1], b = track[next];
  const p = clamp((time - a[0]) / (b[0] - a[0]));
  return [lerp(a[1], b[1], p), lerp(a[2], b[2], p)];
}
const blue = [[6,34],[23,9],[21,26],[21,44],[24,59],[39,32],[34,49],[48,25],[58,8],[61,39],[58,59]];
const coral = [[99,34],[80,10],[81,26],[83,44],[80,59],[67,20],[65,36],[66,52],[47,10],[45,34],[47,59]];
const numbers = [1,2,4,5,3,6,8,10,7,9,11];
const event = (id, at, type, title, detail, from, to) => ({ id, at, type, title, detail, from, to });
export const matches = {
  counter: {
    label: 'THE COUNTERATTACK · 83′', start: 83*60+10, score:[0,1],
    chapters:['THE REGAIN','THE BREAK','THE FINISH'],
    ball:[[0,33,49],[2,35,47],[4,39,42],[6,55,27],[8,61,27],[11,79,33],[16,88,33],[18,91,33],[19.2,104,34],[24,104,34]],
    tracks:{8:[[0,33,49],[2,35,47],[4,39,42],[6,42,40],[11,53,41],[18,69,41],[24,84,33]],10:[[0,48,25],[6,55,27],[8,61,27],[11,65,27],[18,76,25],[24,88,30]],9:[[0,61,39],[6,68,36],[11,79,33],[16,88,33],[18,91,33],[24,96,34]]},
    events:[event('C01',2,'regain','8 wins it back','Atlas regain possession in their own half.',null,[35,47]),event('C02',6,'pass','8 → 10','A forward pass reaches the central runner.',[39,42],[55,27]),event('C03',11,'pass','10 → 9','The second pass finds space behind the defence.',[61,27],[79,33]),event('C04',18,'shot','9 takes the shot','The striker shoots from inside the box.',[91,33],[104,34]),event('C05',19.2,'goal','Atlas equalise','A two-pass counterattack ends in a goal.',null,[104,34])],
    phases:[
      {at:0,kicker:'THE MOMENT BEFORE',fan:['One little spark. A whole new game.','Win it. Move it. Make it count.'],analyst:['Watch the space beyond the press.','Atlas have runners ready on both sides of midfield.']},
      {at:2,kicker:'THE REGAIN',fan:['They’ve got it. Now, go!','Look at all that space ahead.'],analyst:['The regain creates a running start.','Number 8 carries forward as 10 shows between the lines.']},
      {at:6,kicker:'THE BREAK',fan:['Two runners. One open road.','Follow the golden tiles toward goal.'],analyst:['A forward pass opens the middle.','Number 10 receives and looks for 9 beyond the back line.']},
      {at:11,kicker:'THE TURNING POINT',fan:['One pass, and they’re away.','Number 9 has room to make this count.'],analyst:['Two passes beat the defensive line.','Number 9 receives behind the defence and carries into the box.']},
      {at:19.2,kicker:'A LITTLE MOMENT OF MAGIC',fan:['That’s how you turn a game!','From winning it back to finding the net.'],analyst:['Regain → two passes → equaliser.','Five recorded events explain the counterattack.']}
    ]
  },
  press: {
    label:'THE HIGH PRESS · 62′',start:62*60+4,score:[0,0],chapters:['CLOSE THE SPACE','WIN IT BACK','TAKE THE SHOT'],
    ball:[[0,76,17],[2,78,17],[5,83,32],[7,83,32],[9,89,20],[12,84,23],[14,80,25],[16,81,25],[18,87,34],[21,91,34],[22.8,98,34],[24,98,34]],
    tracks:{7:[[0,65,11],[5,74,16],[9,81,19],[14,80,25],[18,84,23],[24,86,20]],9:[[0,68,36],[9,78,35],[14,82,34],[18,87,34],[21,91,34],[24,92,34]],10:[[0,58,24],[5,67,28],[9,74,30],[14,76,29],[24,81,30]]},
    events:[event('P01',5,'backward','Union pass backwards','Pressure forces the ball closer to Union’s goal.',[78,17],[83,32]),event('P02',9,'backward','A second backward pass','The ball is pushed back again as Atlas close in.',[83,32],[89,20]),event('P03',14,'regain','7 wins possession','Atlas regain the ball in the final third.',null,[80,25]),event('P04',18,'pass','7 → 9','A short forward pass finds the striker.',[81,25],[87,34]),event('P05',21,'shot','9 shoots','The regain becomes a shot inside seven seconds.',[91,34],[98,34]),event('P06',22.8,'save','The keeper holds it','Union’s goalkeeper stops the shot.',null,[98,34])],
    phases:[{at:0,kicker:'THE PRESS IS ON',fan:['Nowhere easy to go.','Watch the orange squares close in.'],analyst:['Three runners close the passing lanes.','Atlas commit 7, 9 and 10 to the high press.']},{at:5,kicker:'SQUEEZING THE SPACE',fan:['A little pressure goes a long way.','Union have to go backwards.'],analyst:['The first backward pass is forced.','The highlighted zone tracks the pressing trap.']},{at:9,kicker:'THE TRAP CLOSES',fan:['They’re getting closer…','Another backward pass. Another chance to pounce.'],analyst:['Two backward passes narrow the options.','Atlas continue to press on Union’s right side.']},{at:14,kicker:'THE TURNING POINT',fan:['Got it! Right where it matters.','Number 7 wins the ball near goal.'],analyst:['The high press produces a regain.','Number 7 wins it at x = 80 m in the attacking third.']},{at:22.8,kicker:'A CHANCE CREATED',fan:['So close. The keeper saves the day.','The press still turned pressure into a chance.'],analyst:['A high regain becomes a shot.','Two backward passes, one regain and one saved shot.']}]
  },
  shape: {
    label:'THE EXTRA RUNNER · 71′',start:71*60+2,score:[0,1],chapters:['NEW PLAYER','NEW SHAPE','NEW SPACE'],
    ball:[[0,31,34],[8,36,32],[10,40,31],[12,59,24],[15,64,23],[17,80,16],[20,83,16],[22,87,32],[24,87,32]],
    tracks:{6:[[0,31,34],[8,36,32],[10,40,31],[24,49,30]],10:[[0,48,25],[12,59,24],[15,64,23],[24,73,24]],11:[[0,58,59],[3,58,59],[6,56,57],[10,66,42],[17,80,16],[20,83,16],[24,85,18]],9:[[0,61,39],[12,77,35],[22,87,32],[24,87,32]]},
    events:[event('S01',3,'substitution','17 comes on for 11','Atlas introduce a fresh runner.',null,[58,59]),event('S02',12,'pass','6 → 10','The central midfielder finds a forward pass.',[40,31],[59,24]),event('S03',17,'pass','10 → 17','The new player receives in the right channel.',[64,23],[80,16]),event('S04',22,'pass','17 → 9','The cutback finds the striker in the box.',[83,16],[87,32])],
    phases:[{at:0,kicker:'A FRESH IDEA',fan:['A new face. A new possibility.','Watch what happens when number 17 arrives.'],analyst:['A substitution changes the attacking shape.','Atlas start in a 4–3–3 before adding an extra high runner.']},{at:3,kicker:'WELCOME TO THE GAME',fan:['Here comes a little extra energy.','Number 17 takes the stage.'],analyst:['17 replaces 11; the team reshapes.','The wing-backs advance as the back line becomes three.']},{at:10,kicker:'THE SHAPE SHIFTS',fan:['Look at all those new options.','Five blue shirts now stretch the defence.'],analyst:['Three behind. Five moving higher.','The grid marks the five attacking lanes as players move into position.']},{at:17,kicker:'THE TURNING POINT',fan:['The new kid finds the gap.','Number 17 is right where they need to be.'],analyst:['The substitute receives in a wide channel.','Two forward passes link the central base to the new runner.']},{at:22,kicker:'A NEW WAY THROUGH',fan:['And that’s why they made the change.','A fresh runner, a fresh route to goal.'],analyst:['The new shape creates a cutback.','Three completed passes connect 6 → 10 → 17 → 9.']}]
  }
};
export function getSnapshot(sceneId, time) {
  const scene = matches[sceneId];
  const t = clamp(time,0,DURATION), p = clamp(t/18);
  const shapeTargets = [[6,34],[79,60],[35,20],[32,34],[35,48],[49,39],[50,44],[71,24],[76,46],[87,32],[82,18]];
  const players = blue.map((position,index) => {
    const number = numbers[index];
    const target = sceneId === 'shape' ? shapeTargets[index] : [position[0]+(index ? 18 : 0),position[1]];
    const pos = scene.tracks[number] ? sampleTrack(scene.tracks[number],t) : position.map((v,i)=>lerp(v,target[i],p));
    return {team:'blue',number:sceneId==='shape'&&number===11&&t>=3?17:number,x:pos[0],y:pos[1],drop:sceneId==='shape'&&number===11?Math.max(0,1-(t-3)/1.1)*(t>=3&&t<4.1?1:0):0};
  }).concat(coral.map((position,index)=>({team:'coral',number:numbers[index],x:position[0]+(index?Math.min(10,100-position[0])*p:0),y:position[1],drop:0})));
  const events = scene.events.filter(e=>e.at<=t);
  const phase = scene.phases.filter(e=>e.at<=t).at(-1);
  return {sceneId,scene,time:t,players,ball:sampleTrack(scene.ball,t),events,phase,goaled:events.some(e=>e.type==='goal'),passes:events.filter(e=>e.type==='pass').length,backwards:events.filter(e=>e.type==='backward').length};
}
export function matchClock(scene,time) {
  const total = Math.floor(scene.start+time);
  return `${Math.floor(total/60)}:${String(total%60).padStart(2,'0')}`;
}
