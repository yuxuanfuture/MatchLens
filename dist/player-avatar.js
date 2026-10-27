const TAU = Math.PI * 2;
const playerKey = player => player.id ?? `${player.team}:${player.number}`;
const hasPosition = point => Array.isArray(point) && point.length >= 2 && point.every(Number.isFinite);

// Facing is presentation state only; it never changes tracking or match events.
export class PlayerFacing {
  constructor() { this.angles = new Map(); }

  update(snapshot, delta, reduced = false) {
    const key = `${snapshot.sessionId ?? snapshot.sceneId}:${snapshot.epoch ?? 0}`;
    const reset = key !== this.key || snapshot.time < this.time;
    if (reset) this.angles.clear();
    const animate = !reset && !reduced && snapshot.playing;
    const blend = animate ? 1 - Math.exp(-18 * Math.max(0, delta)) : 1;
    const present = new Set();
    for (const player of snapshot.players) {
      const id = playerKey(player);
      present.add(id);
      let angle = this.angles.get(id);
      let target = angle ?? (player.team === 'blue' ? 0 : Math.PI);
      if (hasPosition(snapshot.ball)) {
        const dx = snapshot.ball[0] - player.x, dy = snapshot.ball[1] - player.y;
        // A ball at the player's feet has no reliable bearing: keep the last one.
        if (Math.hypot(dx, dy) > .35) target = Math.atan2(dy, dx);
      }
      angle ??= target;
      const turn = Math.atan2(Math.sin(target - angle), Math.cos(target - angle));
      this.angles.set(id, (angle + turn * blend) % TAU);
    }
    for (const id of this.angles.keys()) if (!present.has(id)) this.angles.delete(id);
    this.key = key;
    this.time = snapshot.time;
  }

  get(player) { return this.angles.get(playerKey(player)) ?? 0; }
}

const models = new Map();
const BOX_FACES = [
  {axis:0, sign:1, corners:[1,3,7,5]}, {axis:0, sign:-1, corners:[0,4,6,2]},
  {axis:1, sign:1, corners:[2,6,7,3]}, {axis:1, sign:-1, corners:[0,1,5,4]},
  {axis:2, sign:1, corners:[4,5,7,6]}, {axis:2, sign:-1, corners:[0,2,3,1]},
];

// A small voxel model supplies real front, side and back views under the same
// pitch projection. Rotating a flat sprite would tip the player onto the grass.
function playerModel(team, number) {
  const key = `${team}:${number}`;
  if (models.has(key)) return models.get(key);
  const faces = [];
  const shirt = team === 'blue' ? [48,150,245] : [250,105,67];
  const skin = [255,190,119], hair = [100,58,34], white = [255,247,220], boots = [35,48,65];
  const box = (center, size, color) => {
    const surfaces = {};
    const vertices = Array.from({length:8}, (_, i) => center.map((v, axis) => v + ((i >> axis) & 1 ? .5 : -.5) * size[axis]));
    for (const {axis, sign, corners} of BOX_FACES) {
      const normal = [0,0,0]; normal[axis] = sign;
      const middle = [...center]; middle[axis] += sign * size[axis] / 2;
      const face = {vertices:corners.map(i=>vertices[i]), normal, center:middle, color};
      faces.push(face);
      if (axis === 1) surfaces[sign === 1 ? 'front' : 'back'] = face;
    }
    return surfaces;
  };
  const patch = (surface, left, bottom, width, height, front, color) => {
    (surface.decals ??= []).push({vertices:[[left,front,bottom],[left+width,front,bottom],[left+width,front,bottom+height],[left,front,bottom+height]],
      normal:[0,1,0], center:[left+width/2,front,bottom+height/2], color});
  };
  for (const side of [-1,1]) {
    const step = side * .035;
    box([side*.105,step+.055,.045],[.15,.25,.09],boots);
    box([side*.105,step,.16],[.125,.135,.18],shirt);
    box([side*.105,step,.245],[.13,.14,.035],white);
    box([side*.105,step,.295],[.13,.14,.07],skin);
    box([side*.105,step,.385],[.185,.21,.14],white);
    box([side*.235,-step,.60],[.13,.17,.22],shirt);
    box([side*.245,-step,.50],[.135,.175,.035],white);
    box([side*.25,-step+.025,.435],[.125,.15,.10],skin);
    box([side*.25,-step+.045,.385],[.13,.17,.08],skin);
  }
  const jersey = box([0,0,.585],[.36,.245,.30],shirt);
  box([0,0,.755],[.14,.15,.08],skin);
  const head = box([0,0,.895],[.37,.325,.30],skin);
  box([0,-.01,1.055],[.39,.35,.065],hair);
  box([0,-.15,.925],[.385,.06,.235],hair);
  box([-.17,-.025,1.005],[.055,.285,.09],hair);
  box([.17,-.025,1.005],[.055,.285,.09],hair);
  box([-.10,.145,1.025],[.17,.08,.085],hair);
  box([.035,.145,1.045],[.10,.08,.045],hair);
  box([0,.185,.865],[.065,.06,.06],skin);
  box([-.205,-.01,.875],[.055,.09,.10],skin);
  box([.205,-.01,.875],[.055,.09,.10],skin);
  patch(head.front,-.112,.924,.064,.025,.164,hair);
  patch(head.front,.048,.924,.064,.025,.164,hair);
  patch(head.front,-.098,.867,.038,.055,.165,[39,30,25]);
  patch(head.front,.060,.867,.038,.055,.165,[39,30,25]);
  patch(head.front,-.095,.900,.014,.020,.166,white);
  patch(head.front,.063,.900,.014,.020,.166,white);
  patch(head.front,-.055,.805,.11,.025,.164,[100,44,28]);
  patch(head.front,-.022,.805,.052,.010,.165,[229,113,81]);
  patch(jersey.front,-.10,.705,.20,.026,.124,white);
  for (const sign of [-1,1]) {
    const surface = sign === 1 ? jersey.front : jersey.back;
    (surface.decals ??= []).push({center:[0,sign*.124,.59], number:String(number), sign});
  }
  models.set(key, faces);
  return faces;
}

const dot = (a,b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2];

export function drawPlayerAvatar(ctx, player, {project, angle, size, lift = 0}) {
  const origin = project(player.x,player.y);
  const px = project(player.x+1,player.y), py = project(player.x,player.y+1);
  const sx = [px[0]-origin[0],px[1]-origin[1]], sy = [py[0]-origin[0],py[1]-origin[1]];
  const unit = Math.max(Math.hypot(...sx),Math.hypot(...sy),.001);
  const c = Math.cos(angle), s = Math.sin(angle);
  const right = [(s*sx[0]-c*sy[0])/unit,(s*sx[1]-c*sy[1])/unit];
  const forward = [(c*sx[0]+s*sy[0])/unit,(c*sx[1]+s*sy[1])/unit];
  const determinant = right[0]*forward[1]-forward[0]*right[1];
  const sign = Math.sign(determinant) || 1;
  const camera = [-forward[0]*sign,right[0]*sign,Math.abs(determinant)];
  const scale = size * .84;
  const point = ([r,f,h]) => [origin[0]+(r*right[0]+f*forward[0])*scale,origin[1]+lift+(r*right[1]+f*forward[1]-h)*scale];
  const visible = playerModel(player.team,player.number).filter(face=>dot(face.normal,camera)>.001);
  visible.sort((a,b)=>dot(a.center,camera)-dot(b.center,camera));
  const paint = face => {
    if (face.number !== undefined) {
      const [x,y] = point(face.center);
      ctx.save();
      ctx.transform(right[0]*scale*face.sign,right[1]*scale*face.sign,0,scale,x,y);
      ctx.font = '900 .18px Nunito, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = '#fff9e7'; ctx.fillText(face.number,0,0);
      ctx.restore();
      return;
    }
    const [nr,nf,nh] = face.normal;
    const worldX = nr*s+nf*c, worldY = -nr*c+nf*s;
    const shade = .88 + nh*.20 - worldX*.08 - worldY*.12;
    ctx.fillStyle = `rgb(${face.color.map(v=>Math.round(Math.min(255,v*shade))).join(',')})`;
    ctx.beginPath();
    face.vertices.forEach((vertex,i)=>{const p=point(vertex);i?ctx.lineTo(...p):ctx.moveTo(...p);});
    ctx.closePath(); ctx.fill();
    // Paint markings with their surface so the face itself cannot hide them.
    for (const decal of face.decals ?? []) paint(decal);
  };
  for (const face of visible) paint(face);
}
