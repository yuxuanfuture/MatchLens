const FACE_CORNERS=[[1,3,7,5],[0,4,6,2],[2,6,7,3],[0,1,5,4],[4,5,7,6],[0,2,3,1]];
const CAMERA=[-.5,.86,.3736];
const dot=(a,b)=>a.reduce((sum,value,i)=>sum+value*b[i],0);
const identity=point=>point;
const colors={suit:[45,51,60],lapel:[65,72,80],shirt:[255,248,226],skin:[246,184,114],
  hair:[103,62,35],dark:[30,36,43],blue:[37,123,187],lightBlue:[79,164,211],mouth:[98,43,33]};

function meshBuilder() {
  const faces=[];
  function box(center,size,color,transform=identity){
    const vertices=Array.from({length:8},(_,i)=>transform(center.map((v,axis)=>v+(((i>>axis)&1)-.5)*size[axis])));
    for(const corners of FACE_CORNERS){
      const points=corners.map(i=>vertices[i]);
      const a=points[1].map((v,i)=>v-points[0][i]),b=points[2].map((v,i)=>v-points[0][i]);
      const cross=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
      const length=Math.hypot(...cross),normal=cross.map(v=>v/length);
      if(dot(normal,CAMERA)<=0)continue;
      const center=points[0].map((_,i)=>points.reduce((sum,p)=>sum+p[i],0)/4);
      faces.push({points,normal,center,color});
    }
  }
  return {faces,box};
}

function portraitMesh(pose){
  const {faces,box}=meshBuilder();
  const upper=([x,y,z])=>[x+Math.max(0,z-.42)*pose.lean,y,z];
  const head=([x,y,z])=>{
    const c=Math.cos(pose.headTilt),s=Math.sin(pose.headTilt),h=z-.81;
    const r=x*c+h*s,up=-x*s+h*c;
    const yaw=pose.headTurn,cy=Math.cos(yaw),sy=Math.sin(yaw);
    return upper([r*cy-y*sy,r*sy+y*cy,up+.81]);
  };
  const bodyBox=(center,size,color)=>box(center,size,color,upper);
  const headBox=(center,size,color)=>box(center,size,color,head);
  for(const side of [-1,1]){
    box([side*.105,.025,.05],[.16,.27,.10],colors.dark);
    box([side*.105,0,.25],[.145,.17,.34],colors.suit);
    box([side*.105,.091,.28],[.022,.012,.24],colors.lapel);
  }
  bodyBox([0,0,.59],[.39,.26,.37],colors.suit);
  bodyBox([0,.136,.63],[.18,.018,.27],colors.shirt);
  bodyBox([0,.151,.64],[.045,.019,.23],colors.dark);
  bodyBox([-.13,.143,.67],[.06,.035,.18],colors.lapel);
  bodyBox([.13,.143,.67],[.06,.035,.18],colors.lapel);
  bodyBox([.13,.166,.61],[.056,.01,.03],colors.shirt);
  bodyBox([0,0,.81],[.14,.15,.09],colors.skin);

  // Separate upper arms and forearms let the same hands explain, listen and cheer.
  for(const side of [-1,1]){
    const angle=side<0?pose.leftArm:pose.rightArm;
    const bend=side<0?pose.leftElbow:pose.rightElbow;
    const shoulder=[side*.235,0,.72],upperLength=.20,foreLength=.235;
    const at=(pivot,angle)=> ([x,y,z])=>upper([
      pivot[0]+x*Math.cos(angle)-side*z*Math.sin(angle),pivot[1]+y,
      pivot[2]+side*x*Math.sin(angle)+z*Math.cos(angle)]);
    const elbow=[shoulder[0]+side*upperLength*Math.sin(angle),0,shoulder[2]-upperLength*Math.cos(angle)];
    box([0,0,-upperLength/2],[.13,.18,upperLength+.015],colors.suit,at(shoulder,angle));
    const fore=at(elbow,angle+bend);
    box([0,0,-.085],[.12,.17,.18],colors.suit,fore);
    box([0,0,-.185],[.123,.173,.035],colors.shirt,fore);
    box([0,.012,-foreLength],[.13,.15,.075],colors.skin,fore);
    if(pose.palmOpen){
      box([0,.012,-foreLength-.055],[.13,.12,.045],colors.skin,fore);
      box([-.077,.035,-foreLength],[.035,.08,.07],colors.skin,fore);
    }
  }

  headBox([0,0,.985],[.43,.35,.33],colors.skin);
  headBox([0,-.015,1.17],[.45,.38,.065],colors.hair);
  headBox([0,-.17,1.015],[.44,.05,.24],colors.hair);
  headBox([-.19,-.01,1.105],[.055,.34,.11],colors.hair);
  headBox([.19,-.01,1.115],[.055,.34,.09],colors.hair);
  headBox([-.11,.17,1.135],[.20,.05,.075],colors.hair);
  headBox([.045,.17,1.157],[.10,.05,.035],colors.hair);
  headBox([0,.205,.975],[.065,.07,.062],colors.skin);

  const surprised=pose.expression==='surprised',happy=pose.expression==='happy';
  const eyeHeight=(surprised?.075:.055)*(1-pose.blink*.94);
  for(const side of [-1,1]){
    const x=side*.105;
    headBox([x,.181,1.018],[.066,.009,eyeHeight],colors.shirt);
    headBox([x+.009,.188,1.013],[.032,.008,eyeHeight*.84],colors.dark);
    const browZ=1.075+(surprised?.025:0)+(pose.expression==='puzzled'&&side>0?.025:0);
    headBox([x,.184,browZ],[.083,.015,.022],colors.hair);
  }
  const mouthHeight=surprised?.085:.018+pose.talk*.055;
  headBox([0,.181,.90],[happy?.15:.09,.011,mouthHeight],colors.mouth);
  if(happy||pose.talk>.25)headBox([0,.189,.90+mouthHeight*.24],[happy?.12:.065,.008,mouthHeight*.25],colors.shirt);
  if(pose.talk>.65)headBox([0,.189,.90-mouthHeight*.28],[.06,.008,.015],[216,110,86]);

  // Headset and boom stay attached to the head in every pose.
  headBox([0,-.035,1.225],[.47,.09,.045],colors.dark);
  headBox([0,-.038,1.25],[.44,.085,.025],colors.blue);
  for(const side of [-1,1]){
    headBox([side*.245,-.035,1.12],[.045,.085,.20],colors.dark);
    headBox([side*.25,-.02,.995],[.07,.20,.18],colors.dark);
    headBox([side*.287,-.02,.995],[.043,.16,.14],colors.blue);
    headBox([side*.31,-.02,1.02],[.008,.08,.08],colors.lightBlue);
  }
  headBox([-.267,.10,.958],[.027,.16,.027],colors.dark);
  headBox([-.17,.182,.942],[.20,.028,.028],colors.dark);
  headBox([-.068,.197,.942],[.06,.045,.045],colors.dark);
  return faces;
}

export class CommentatorPortrait {
  constructor(canvas){this.canvas=canvas;this.ctx=canvas.getContext('2d');}

  render(pose){
    if(!this.ctx)return;
    // Avoid repainting a frozen pose; the canvas has no independent animation clock.
    const key=JSON.stringify(pose);
    if(key===this.lastPose)return;
    this.lastPose=key;
    const ctx=this.ctx;
    ctx.setTransform(this.canvas.width/112,0,0,this.canvas.height/135,0,0);
    ctx.clearRect(0,0,112,135);
    ctx.fillStyle='#5d553b20';ctx.beginPath();ctx.ellipse(55,130,23,4,0,0,Math.PI*2);ctx.fill();
    const project=([x,y,z])=>[55+(.86*x+.5*y)*82,125+(-.3*x+.26*y-z)*82+pose.lift];
    const faces=portraitMesh(pose).sort((a,b)=>dot(a.center,CAMERA)-dot(b.center,CAMERA));
    for(const face of faces){
      const shade=.86+face.normal[2]*.18-face.normal[0]*.10+face.normal[1]*.05;
      ctx.fillStyle=`rgb(${face.color.map(value=>Math.round(Math.min(255,value*shade))).join(',')})`;
      ctx.beginPath();face.points.forEach((point,i)=>i?ctx.lineTo(...project(point)):ctx.moveTo(...project(point)));
      ctx.closePath();ctx.fill();
    }
    this.canvas.dataset.mood=pose.mood;
    this.canvas.parentElement.dataset.portraitReady='true';
  }
}
