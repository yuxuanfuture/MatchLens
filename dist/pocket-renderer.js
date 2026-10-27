import { clamp } from './matches.js';
import { BallRoll, drawFootball } from './football.js';

// Project the 105 × 68 metre data plane onto the four measured grass corners.
export function makeProjection(corners) {
  const [p0,p1,p2,p3] = corners;
  const dx1=p1[0]-p2[0],dx2=p3[0]-p2[0],dx3=p0[0]-p1[0]+p2[0]-p3[0];
  const dy1=p1[1]-p2[1],dy2=p3[1]-p2[1],dy3=p0[1]-p1[1]+p2[1]-p3[1];
  const determinant=dx1*dy2-dx2*dy1;
  const g=(dx3*dy2-dx2*dy3)/determinant,h=(dx1*dy3-dx3*dy1)/determinant;
  const a=p1[0]-p0[0]+g*p1[0],b=p3[0]-p0[0]+h*p3[0];
  const d=p1[1]-p0[1]+g*p1[1],e=p3[1]-p0[1]+h*p3[1];
  return (x,y) => {const u=x/105,v=y/68,k=g*u+h*v+1;return [(a*u+b*v+p0[0])/k,(d*u+e*v+p0[1])/k];};
}
const pitchProject = makeProjection([[925,330],[1527,537],[1204,782],[486,503]]);
const loadImage = src => new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error(`Could not load ${src}`));img.src=src;});
export class StadiumRenderer {
  constructor(canvas) {
    this.canvas=canvas;this.ctx=canvas.getContext('2d');this.blend=0;this.reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.ballRoll=new BallRoll();
    matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change',event=>{this.reduced=event.matches;});
    this.resize();new ResizeObserver(()=>this.resize()).observe(canvas);
  }
  async load() {
    [this.background,this.blue,this.coral]=await Promise.all(['stadium-roomy','player-blue','player-coral'].map(name=>loadImage(`./assets/${name}.png`)));
  }
  resize() {
    this.width=this.canvas.clientWidth;this.height=this.canvas.clientHeight;
    this.dpr=Math.min(devicePixelRatio||1,2);this.canvas.width=Math.round(this.width*this.dpr);this.canvas.height=Math.round(this.height*this.dpr);
  }
  polygon(points,fill,stroke,lineWidth=1) {
    const ctx=this.ctx;ctx.beginPath();points.forEach(([x,y],i)=>{const p=this.project(x,y);i?ctx.lineTo(...p):ctx.moveTo(...p);});ctx.closePath();if(fill){ctx.fillStyle=fill;ctx.fill();}if(stroke){ctx.strokeStyle=stroke;ctx.lineWidth=lineWidth;ctx.stroke();}
  }
  line(points,color,width=2,dash=[]) {
    const ctx=this.ctx;ctx.beginPath();points.forEach(([x,y],i)=>{const p=this.project(x,y);i?ctx.lineTo(...p):ctx.moveTo(...p);});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.stroke();ctx.setLineDash([]);
  }
  tile(x,y,color,alpha=1,size=5) {
    this.ctx.save();this.ctx.globalAlpha=alpha;this.polygon([[x,y],[x+size,y],[x+size,y+size],[x,y+size]],color,'#fff2a566',.6);this.ctx.restore();
  }
  route(from,to,progress=1) {
    const length=Math.hypot(to[0]-from[0],to[1]-from[1]),steps=Math.ceil(length/3.7);
    for(let i=0;i<steps*progress;i++){const p=i/steps;this.tile(from[0]+(to[0]-from[0])*p-1.4,from[1]+(to[1]-from[1])*p-1.4,'#ffdb4b',.65,2.8);}
    this.line([from,[from[0]+(to[0]-from[0])*progress,from[1]+(to[1]-from[1])*progress]],'#fffbc7',2,[5,6]);
  }
  render(snapshot,mode,delta) {
    if(!this.background)return;
    const ctx=this.ctx,w=this.width,h=this.height;
    const target=mode==='analyst'?1:0;this.blend=this.reduced?target:this.blend+(target-this.blend)*Math.min(1,delta*5);
    const goalAge=snapshot.goaled?snapshot.time-(snapshot.live?snapshot.goalAt:19.2):-1;
    const goalZoom=!this.reduced&&goalAge>=0?Math.sin(clamp(goalAge/4)*Math.PI)*.024:0;
    const mobile=w<=700;
    this.scale=w/1672*(1.13+this.blend*.045+goalZoom);
    this.offsetX=(w-1672*this.scale)*.92;
    this.offsetY=mobile?160:(h-941*this.scale)*.45-10-this.blend*12;
    this.project=(x,y)=>{const p=pitchProject(x,y);return [this.offsetX+p[0]*this.scale,this.offsetY+p[1]*this.scale];};
    ctx.setTransform(this.dpr,0,0,this.dpr,0,0);ctx.clearRect(0,0,w,h);
    ctx.fillStyle='#9edcf9';ctx.fillRect(0,0,w,h);
    ctx.drawImage(this.background,this.offsetX,this.offsetY,1672*this.scale,941*this.scale);
    const sky=ctx.createLinearGradient(0,this.offsetY,0,this.offsetY+110*this.scale);sky.addColorStop(0,'#9edcf9');sky.addColorStop(1,'#9edcf900');ctx.fillStyle=sky;ctx.fillRect(0,0,w,this.offsetY+110*this.scale);
    const bottom=this.offsetY+941*this.scale;
    if(bottom<h){const fade=ctx.createLinearGradient(0,bottom-20,0,bottom);fade.addColorStop(0,'#fff7e600');fade.addColorStop(1,'#fff7e6');ctx.fillStyle=fade;ctx.fillRect(0,bottom-20,w,21);ctx.fillStyle='#fff7e6';ctx.fillRect(0,bottom,w,h-bottom);}
    if(this.blend>.01){ctx.save();ctx.globalAlpha=this.blend;for(let x=0;x<=105;x+=7.5)this.line([[x,0],[x,68]],'#efffdc45',.8);for(let y=0;y<=68;y+=6.8)this.line([[0,y],[105,y]],'#efffdc45',.8);ctx.restore();}
    if(!snapshot.live&&snapshot.sceneId==='press') {
      const intensity=.18+.46*clamp(snapshot.time/14);
      for(let x=65;x<95;x+=5)for(let y=10;y<40;y+=5){const near=1-Math.hypot((x-80)/20,(y-25)/25)*.5;this.tile(x,y,'#ff6d39',intensity*near);}
    }
    if(!snapshot.live&&snapshot.sceneId==='shape'&&snapshot.time>=3) {
      const progress=clamp((snapshot.time-3)/7);
      for(let y=3;y<66;y+=13)this.polygon([[73,y],[94,y],[94,y+8],[73,y+8]],`rgba(157,224,211,${(.08+this.blend*.14)*progress})`,'#e4fff34d');
      if(this.blend>.1)for(const number of [2,4,5,3,7]){const player=snapshot.players.find(p=>p.team==='blue'&&p.number===number);this.line([[player.x-8,player.y],[player.x,player.y]],'#b4ffff',2,[4,5]);}
    }
    if(snapshot.live)for(const overlay of snapshot.overlays){
      if(overlay.kind==='pressure'){const {x,y}=overlay.position;for(let dx=-5;dx<=5;dx+=5)for(let dy=-5;dy<=5;dy+=5)this.tile(clamp(x+dx,0,100),clamp(y+dy,0,63),'#ff6d39',overlay.intensity*.5);}
      if(overlay.kind==='route')this.route([overlay.from.x,overlay.from.y],[overlay.to.x,overlay.to.y]);
    }
    for(const e of snapshot.scene.events){if((e.type==='pass'||e.type==='shot')&&e.from&&e.to){const progress=clamp((snapshot.time-(e.at-2))/2);if(progress>0)this.route(e.from,e.to,progress);}}
    const ordered=snapshot.players.map(p=>({...p,screen:this.project(p.x,p.y)})).sort((a,b)=>a.screen[1]-b.screen[1]);
    for(const player of ordered)this.player(player,snapshot);
    const ballSize=Math.max(6.5,9*this.scale);
    const roll=this.ballRoll.advance(snapshot,this.project,ballSize,this.reduced);
    if(snapshot.ball){const bp=this.project(...snapshot.ball);drawFootball(ctx,bp[0],bp[1],ballSize,roll);}
    if(goalAge>=0&&!this.reduced)this.celebrate(goalAge);
  }
  player(player,snapshot) {
    const ctx=this.ctx,[x,y]=player.screen;
    const size=(55+player.y*.11)*this.scale;
    const moving=snapshot.live||snapshot.time>0&&snapshot.time<19.2;
    const bob=this.reduced?0:(moving?Math.sin(snapshot.time*8+player.number)*1.2*this.scale:0);
    const bounce=snapshot.goaled&&player.team===(snapshot.live?snapshot.goalTeam:'blue')&&!this.reduced?Math.abs(Math.sin((snapshot.time-(snapshot.live?snapshot.goalAt:19.2))*6+player.number))*8*this.scale:0;
    const drop=player.drop*85*this.scale;
    ctx.fillStyle='#203e3533';ctx.beginPath();ctx.ellipse(x,y+1,size*.21,size*.065,0,0,Math.PI*2);ctx.fill();
    if(this.blend>.1){ctx.globalAlpha=this.blend*.85;ctx.strokeStyle=player.team==='blue'?'#9aeeff':'#ffc5a2';ctx.lineWidth=1.4;ctx.beginPath();ctx.ellipse(x,y,size*.25,size*.1,0,0,Math.PI*2);ctx.stroke();ctx.globalAlpha=1;}
    ctx.drawImage(player.team==='blue'?this.blue:this.coral,x-size*.5,y-size+bob-bounce-drop,size,size);
    ctx.font=`900 ${Math.max(7,10.3*this.scale)}px Nunito, sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.strokeStyle=player.team==='blue'?'#1c6795':'#a03922';ctx.lineWidth=2.2*this.scale;
    const numberY=y-size*.43+bob-bounce-drop;ctx.strokeText(String(player.number),x-size*.012,numberY);ctx.fillStyle='#fff';ctx.fillText(String(player.number),x-size*.012,numberY);
    if(snapshot.live&&(player.focused||this.blend>.5)){
      if(player.focused){ctx.strokeStyle='#fff294';ctx.lineWidth=3;ctx.beginPath();ctx.ellipse(x,y,size*.34,size*.13,0,0,Math.PI*2);ctx.stroke();}
      ctx.font=`800 ${Math.max(9,10*this.scale)}px Nunito, sans-serif`;ctx.fillStyle='#fffbed';ctx.strokeStyle='#173f38';ctx.lineWidth=3;
      ctx.strokeText(player.name,x,y-size-8);ctx.fillText(player.name,x,y-size-8);
    }
    if(player.number===17&&snapshot.sceneId==='shape'&&snapshot.time>=3&&snapshot.time<7){ctx.fillStyle='#fff5bb';ctx.font=`900 ${11*this.scale}px Nunito`;ctx.fillText('17 ON',x,y-size-14*this.scale);}
  }
  celebrate(age) {
    const ctx=this.ctx,origin=this.project(100,33);
    for(let i=0;i<46;i++){const angle=i*2.3999,speed=45+(i%7)*11,t=age%(2.8);const x=origin[0]+Math.cos(angle)*speed*t*this.scale,y=origin[1]-90*this.scale+Math.sin(angle)*speed*t*this.scale+22*t*t*this.scale;ctx.globalAlpha=clamp(1-t/3);ctx.fillStyle=['#ff7954','#ffe478','#9ae6f5','#fff8e9'][i%4];ctx.fillRect(x,y,Math.max(3,6*this.scale),Math.max(3,6*this.scale));}ctx.globalAlpha=1;
    for(let i=0;i<16;i++){const p=this.project(10+i*5.5,-4);const size=25*this.scale;const jump=Math.abs(Math.sin(age*7+i))*6*this.scale;ctx.drawImage(i%3?this.blue:this.coral,p[0]-size/2,p[1]-size-jump,size,size);}
  }
}
