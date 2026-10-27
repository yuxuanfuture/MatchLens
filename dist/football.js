// A vector football stays crisp at every stadium scale and needs no emoji font.
export function drawFootball(ctx, x, y, radius, angle) {
  ctx.save();
  ctx.fillStyle='#183d3540';ctx.beginPath();ctx.ellipse(x+2,y+2,radius*1.15,radius*.4,0,0,Math.PI*2);ctx.fill();
  ctx.translate(x,y-radius);ctx.rotate(angle);ctx.scale(radius,radius);
  ctx.beginPath();ctx.arc(0,0,1,0,Math.PI*2);ctx.fillStyle='#fffdf3';ctx.fill();
  ctx.strokeStyle='#183b36';ctx.lineWidth=.08;ctx.stroke();ctx.clip();
  const patch=(cx,cy,r,turn)=>{
    ctx.beginPath();
    for(let i=0;i<5;i++){const a=turn+i*Math.PI*2/5;const px=cx+Math.cos(a)*r,py=cy+Math.sin(a)*r;i?ctx.lineTo(px,py):ctx.moveTo(px,py);}
    ctx.closePath();ctx.fillStyle='#20332f';ctx.fill();
  };
  ctx.strokeStyle='#60736a';ctx.lineWidth=.045;
  for(let i=0;i<5;i++){
    const a=-Math.PI/2+i*Math.PI*2/5;
    ctx.beginPath();ctx.moveTo(Math.cos(a)*.32,Math.sin(a)*.32);ctx.lineTo(Math.cos(a)*.93,Math.sin(a)*.93);ctx.stroke();
    patch(Math.cos(a)*.98,Math.sin(a)*.98,.33,a+Math.PI);
  }
  patch(0,0,.39,-Math.PI/2);
  const shade=ctx.createRadialGradient(-.3,-.4,.1,.2,.25,1.3);
  shade.addColorStop(0,'#ffffff35');shade.addColorStop(.55,'#ffffff00');shade.addColorStop(1,'#15342955');
  ctx.fillStyle=shade;ctx.fillRect(-1,-1,2,2);ctx.restore();
}

export class BallRoll {
  constructor(){this.previous=null;this.angle=0;}
  advance(snapshot, project, radius, reduced=false){
    const ball=snapshot.ball;
    if(!ball){this.previous=null;return this.angle;}
    const key=`${snapshot.sessionId||snapshot.sceneId}:${snapshot.epoch||0}`;
    const old=this.previous;
    const reset=old&&(old.key!==key||snapshot.time<old.time);
    if(reset)this.angle=0;
    const playing=snapshot.playing??!snapshot.live;
    if(old&&!reset&&playing&&!reduced){
      const a=project(...old.ball),b=project(...ball);
      const dx=b[0]-a[0],dy=b[1]-a[1];
      this.angle+=Math.hypot(dx,dy)/radius*(dx<0?-1:1);
    }
    this.previous={key,ball:[...ball],time:snapshot.time};
    return this.angle;
  }
}
