const clamp = value => Math.max(0,Math.min(1,value));

// Deterministic particles follow replay age: pausing or seeking never leaves a wall-clock animation behind.
export function drawGoalEffects(ctx, cue, {width, height, project, scale}) {
  if (!cue || cue.kind !== 'confirmed') return;
  const {age,team,goalX} = cue, fade = 1-clamp((age-3.6)/1.4);
  const colors = team==='coral'?['#fa6943','#ffce4a','#fff3bf','#f79b64']:['#3096f5','#ffce4a','#fff3bf','#9ae6f5'];
  ctx.save();
  // A brief ring marks the goal actually attacked, rather than a fixed end of the pitch.
  if (age<1.3) {
    const origin=project(goalX,34);
    ctx.globalAlpha=(1-age/1.3)*.7;
    ctx.strokeStyle=colors[1];ctx.lineWidth=4*scale;
    ctx.beginPath();ctx.ellipse(origin[0],origin[1],(12+age*65)*scale,(5+age*24)*scale,0,0,Math.PI*2);ctx.stroke();
  }
  // Keep the central pitch and bottom transport clear of confetti.
  ctx.beginPath();ctx.rect(0,145,width*.25,Math.max(0,height-315));ctx.rect(width*.75,145,width*.25,Math.max(0,height-315));ctx.clip();
  for (let side=0;side<2;side++) for (let i=0;i<94;i++) {
    const ageOffset=(i%13)*.045, t=age-ageOffset;
    if(t<0)continue;
    const seed=(i*37%101)/101, seed2=(i*61%97)/97;
    const x0=side?width*.94:width*.06, direction=side?-1:1;
    const x=x0+direction*(30+seed*width*.095)*t+Math.sin(t*3+i)*12*scale;
    const y=height*.64-(200+seed2*250)*scale*t+66*scale*t*t;
    const size=(4+seed*6)*scale;
    ctx.save();ctx.translate(x,y);ctx.rotate(t*(2+seed*5)+i);
    ctx.globalAlpha=fade*.94;ctx.fillStyle=colors[i%colors.length];
    ctx.fillRect(-size/2,-size/2,size*(.35+Math.abs(Math.cos(t*4+i))*.65),size*(i%5===0?3:1));
    ctx.restore();
  }
  ctx.restore();
}

export function celebrationPose(cue, player, reduced) {
  if (!cue || cue.team!==player.team) return {lift:0,armsRaised:0};
  const scorer=player.id===cue.playerId;
  const strength=cue.kind==='pending'?(scorer?1:.45):reduced?1:1-clamp((cue.age-4)/1);
  return {armsRaised:strength*(reduced ? .9 : .85+.1*Math.sin(cue.age*7+player.number)),
    lift:reduced?0:-Math.max(0,Math.sin(cue.age*8+player.number*.65))*(scorer?20:12)*strength};
}
