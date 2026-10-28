import { playbackView } from './replay-view.js';
import { goalCelebration } from './goal-celebration.js';

const clamp=value=>Math.max(0,Math.min(1,value));
const pulse=(age,duration)=>age>=0&&age<duration?Math.sin(Math.PI*age/duration):0;

function reaction(payload,time,view) {
  if(!payload)return {mood:'idle',age:0};
  const received=event=>event.observed_at_ms<=payload.as_of_ms;
  const events=(payload.events??[]).filter(received);
  const age=event=>time-(event.observed_at_ms-view.receive_offset_ms)/1000;
  const recent=(types,duration)=>events.filter(event=>types.includes(event.type)&&age(event)>=0&&age(event)<duration)
    .sort((a,b)=>b.observed_at_ms-a.observed_at_ms)[0];
  const review=received(payload.review??{})?payload.review:null;
  const phase=review?.phase??'none';
  if(['review_requested','reviewing','awaiting_decision'].includes(phase))return {mood:'listening',age:age(review)};
  if(['flagged','checking'].includes(phase))return {mood:'puzzled',age:age(review)};
  if(phase==='awarded')return {mood:'settled',age:age(review)};
  if(phase==='pending')return {mood:'hopeful',age:age(review)};
  const tackle=recent(['tackle','interception'],1.8);
  if(tackle&&tackle.outcome!=='lost')return {mood:'surprised',age:age(tackle)};
  const shot=recent(['shot'],1.2);
  if(shot)return {mood:'shot',age:age(shot)};
  const change=recent(['possession_change'],16);
  if(change&&age(change)<1.5)return {mood:'turnover',age:age(change)};

  const tracking=payload.tracking,ball=tracking?.ball;
  if(ball&&received(tracking)&&tracking.in_play!==false){
    const teamId=tracking.possession_team_id;
    const team=payload.state?.teams?.find(item=>item.id===teamId);
    const direction=team?.attack_direction_x;
    if(direction===1||direction===-1){
      const progress=x=>direction===1?x:105-x;
      const advanced=progress(ball.x),central=ball.y>13.8&&ball.y<54.2;
      const roster=new Map((payload.state?.roster??[]).map(player=>[player.id,player]));
      const opponents=(tracking.players??[]).filter(player=>roster.get(player.player_id)?.team_id!==teamId);
      const defendersAhead=opponents.filter(player=>roster.get(player.player_id)?.position_role!=='goalkeeper'&&progress(player.x)>advanced-1);
      if(advanced>78&&central&&ball.owner_id&&!defendersAhead.length)return {mood:'one-on-one',age:0};
      if(advanced>78&&central)return {mood:'attacking',age:0};
      if(change&&change.team_id===teamId&&change.position&&progress(change.position.x)<35&&advanced>progress(change.position.x)+2)
        return {mood:'counter',age:age(change)};
    }
  }
  const pass=recent(['pass','carry'],1.5);
  return {mood:'explaining',age:pass?age(pass):-1};
}

// Replay-derived rather than wall-clock timers: pause, seek and new sessions are deterministic.
export function commentatorPose(payload,{elapsed=0,reduced=false}={}) {
  const view=playbackView(payload);
  const time=Math.min(view.duration_ms/1000,view.position_ms/1000+(payload?.playing?clamp(elapsed/.5)*.5*(payload.speed||1):0));
  const cue=goalCelebration(payload,undefined,elapsed);
  const current=cue?{mood:cue.kind==='confirmed'?'celebrating':'hopeful',age:cue.age}:reaction(payload,time,view);
  const {mood,age}=current,animated=!reduced&&!!payload;
  const wave=animated?Math.sin(time*2.1):0;
  const gesture=animated?pulse(age,1.5):0;
  const blinkPhase=time%4.3;
  const pose={mood,expression:'calm',blink:animated?pulse(blinkPhase-3.9,.16):0,
    talk:animated&&time%3.7<2.3?.25+.55*Math.max(0,Math.sin(time*12)):0,
    headTilt:animated?.025*wave:0,headTurn:animated?.025*Math.sin(time*.7):0,
    lean:0,lift:animated?Math.sin(time*1.9)*.45:0,
    leftArm:.10,leftElbow:.05,rightArm:.28+gesture*.35,rightElbow:.55+gesture*.35,palmOpen:gesture>.2};
  if(mood==='idle'){pose.talk=0;return pose;}
  if(mood==='explaining')pose.headTilt+=gesture*.06;
  if(['attacking','counter','one-on-one','shot'].includes(mood)){
    pose.expression='focused';pose.lean=.055;pose.headTilt=-.055;
    pose.rightArm=.75;pose.rightElbow=.75;pose.palmOpen=true;
    if(mood==='counter'){pose.rightArm+=wave*.08;pose.lean=.035;}
    if(mood==='one-on-one'){pose.expression='surprised';pose.lean=.09;pose.talk=.7;pose.leftArm=.35;}
    if(mood==='shot'){pose.lean=.1;pose.talk=.18;pose.lift=0;pose.headTurn=0;}
  }
  if(['surprised','turnover','hopeful'].includes(mood)){
    const strength=reduced?1:.35+.65*pulse(age,mood==='hopeful'?.6:1.8);
    pose.expression=mood==='turnover'?'focused':'surprised';pose.talk=.8;
    pose.headTilt=-.07;pose.rightArm=.8+strength*.55;pose.rightElbow=.4;
    pose.leftArm=.25+strength*.4;pose.leftElbow=.4;pose.palmOpen=true;
  }
  if(['puzzled','listening'].includes(mood)){
    pose.expression=mood==='puzzled'?'puzzled':'focused';pose.talk=mood==='puzzled'?.15:0;
    pose.headTilt=-.09+(animated?.035*pulse(time%5,1):0);pose.headTurn=-.06;
    pose.leftArm=1.9;pose.leftElbow=1.8;pose.rightArm=mood==='puzzled'?.8:.12;
    pose.rightElbow=mood==='puzzled'?.45:.3;pose.palmOpen=mood==='puzzled';
  }
  if(mood==='celebrating'){
    pose.expression='happy';pose.talk=1;pose.palmOpen=true;pose.lean=0;
    pose.leftArm=2.55;pose.rightArm=2.55;pose.leftElbow=.08;pose.rightElbow=.08;
    pose.lift=animated?-Math.max(0,Math.sin(age*8))*5:0;
    pose.headTilt=animated?.05*Math.sin(age*7):0;
  }
  if(mood==='settled'){pose.expression='happy';pose.talk=0;pose.rightArm=.3;pose.rightElbow=.6;}
  return pose;
}
