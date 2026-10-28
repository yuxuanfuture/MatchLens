// A deliberately bounded classical-vision baseline: calibrated, fixed-camera,
// colour-coded synthetic pitches only. It does not recognise broadcast footage.
export const palette = [
  [230,45,45],[230,120,40],[220,190,35],[155,215,35],[60,210,60],[35,205,140],
  [40,195,215],[45,110,230],[95,55,220],[170,45,220],[220,40,150],
  [135,25,25],[140,70,25],[130,115,25],[85,130,25],[25,130,35],[25,125,85],
  [25,115,135],[25,65,140],[60,25,130],[105,25,135],[135,25,85]
];
const numbers=[1,2,3,4,5,6,7,8,9,10,11];
export const identities=palette.map((rgb,i)=>({id:`${i<11?'A':'U'}${numbers[i%11]}`,team_id:i<11?'A':'U',shirt_number:numbers[i%11],name:`${i<11?'Atlas':'Union'} ${numbers[i%11]}`,rgb}));
export function detectPixels(data,width,height) {
  const sums=Array.from({length:23},()=>({x:0,y:0,n:0}));
  const columns=Math.ceil(width/2),rows=Math.ceil(height/2),labels=new Uint8Array(columns*rows).fill(255),visited=new Uint8Array(labels.length);
  for(let y=0;y<height;y+=2)for(let x=0;x<width;x+=2){
    const at=(y*width+x)*4,r=data[at],g=data[at+1],b=data[at+2];
    let index=-1,best=42**2;
    if(r>232&&g>232&&b>232)index=22;
    else for(let i=0;i<palette.length;i++){
      const p=palette[i],d=(r-p[0])**2+(g-p[1])**2+(b-p[2])**2;
      if(d<best){best=d;index=i;}
    }
    if(index>=0)labels[Math.floor(y/2)*columns+Math.floor(x/2)]=index;
  }
  // Compression and antialiasing can create tiny islands matching another
  // identity. Keep the largest connected component, not a whole-image centroid.
  for(let seed=0;seed<labels.length;seed++){
    if(visited[seed]||labels[seed]===255)continue;
    const kind=labels[seed],stack=[seed],sum={x:0,y:0,n:0};visited[seed]=1;
    while(stack.length){const at=stack.pop(),x=at%columns,y=Math.floor(at/columns);sum.x+=x*2;sum.y+=y*2;sum.n++;
      for(const [nx,ny] of [[x-1,y],[x+1,y],[x,y-1],[x,y+1]]){if(nx<0||nx>=columns||ny<0||ny>=rows)continue;const next=ny*columns+nx;if(!visited[next]&&labels[next]===kind){visited[next]=1;stack.push(next);}}
    }
    if(sum.n>sums[kind].n)sums[kind]=sum;
  }
  const point=s=>s.n>=3?{x:s.x/s.n/width*105,y:s.y/s.n/height*68}:null;
  return {ball:point(sums[22]),players:sums.slice(0,22).flatMap((s,i)=>point(s)?[{player_id:identities[i].id,...point(s)}]:[])};
}
const d=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
export class TemporalEvents {
  constructor(){this.owner=null;this.candidate=null;this.stable=0;this.departure=null;this.previous=null;this.events=[];this.shotUntil=0;}
  update(frame,timeMs){
    const emitted=[];
    const emit=(type,player,extra={})=>{const event={schema_version:'1.1',match_id:'video-lab',record_type:'event',source:'classical_vision_estimate',id:`v${String(this.events.length).padStart(5,'0')}`,type,event_time_ms:timeMs,observed_at_ms:timeMs,player_id:player,team_id:player[0],position:frame.ball,position_status:'estimated',...extra};this.events.push(event);emitted.push(event);};
    if(!frame.ball){this.previous=null;this.owner=null;this.departure=null;this.stable=0;return {events:[],speed_mps:null};}
    if(this.previous && (timeMs<=this.previous.time || timeMs-this.previous.time>500)){
      this.owner=null;this.departure=null;this.previous=null;this.stable=0;
    }
    const speed=this.previous?d(frame.ball,this.previous.ball)/((timeMs-this.previous.time)/1000):null;
    const nearest=frame.players.map(p=>({...p,d:d(p,frame.ball)})).sort((a,b)=>a.d-b.d)[0];
    // A ball merely crossing a nearby player's colour region is not reception.
    // This baseline requires a settled ball for acquisition (stationary demo).
    const candidate=nearest&&nearest.d<2.8&&(speed===null||speed<3)?nearest.player_id:null;
    this.stable=candidate===this.candidate?this.stable+1:1;this.candidate=candidate;
    if(this.owner&&!candidate&&!this.departure)this.departure={player:this.owner,start:this.previous?.ball||frame.ball,time:this.previous?.time||timeMs};
    if(candidate&&this.stable>=2){
      if(this.departure&&candidate!==this.departure.player){
        const from=this.departure.player,length=d(this.departure.start,frame.ball),elapsed=(timeMs-this.departure.time)/1000;
        if(length>4&&elapsed>.1){
          emit('pass',from,{position:this.departure.start,start_time_ms:this.departure.time,end_position:frame.ball,receiver_id:candidate,outcome:from[0]===candidate[0]?'complete':'incomplete',distance_m:+length.toFixed(2),average_ball_speed_mps:+(length/elapsed).toFixed(2),method:'colour identity + settled reception + intervening free ball; estimated pass, not manual annotation'});
          if(from[0]!==candidate[0]){emit('interception',candidate,{previous_team_id:from[0]});emit('recovery',candidate,{previous_team_id:from[0]});emit('possession_change',candidate,{previous_team_id:from[0]});}
        }
      }
      this.owner=candidate;this.departure=null;
    }
    if(this.departure&&timeMs>this.shotUntil&&frame.ball.y>28&&frame.ball.y<40&&
      (this.departure.player[0]==='A'&&this.departure.start.x>75&&frame.ball.x>103 || this.departure.player[0]==='U'&&this.departure.start.x<30&&frame.ball.x<2)){
      const source=this.departure;const shotTime=source.time;
      emit('shot',source.player,{position:source.start,start_time_ms:shotTime,method:'estimated shot: observed trajectory from final third reaches goal-line region; outcome unconfirmed'});
      this.events.at(-1).event_time_ms=shotTime;
      const shot=this.events.at(-1);
      emit('shot_end',source.player,{shot_id:shot.id,position:frame.ball});
      this.shotUntil=timeMs+2000;this.departure=null;this.owner=null;
    }
    this.previous={ball:frame.ball,time:timeMs};
    return {events:emitted,speed_mps:speed===null?null:+speed.toFixed(2)};
  }
}
