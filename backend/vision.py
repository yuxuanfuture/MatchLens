"""Local pretrained detection → tracks → calibrated motion → football events.

No model API, training or download occurs in this module. Dependencies and weights
are installed explicitly by the setup command. Metric coordinates require a
calibration; uncalibrated footage still produces detections but no invented metres.
"""
import contextlib
import importlib
import json
import math
import os
import socket
import time
from pathlib import Path
from backend.vision_runtime import resolve_device


@contextlib.contextmanager
def network_disabled():
    original=socket.socket.connect
    def denied(*args,**kwargs):raise RuntimeError('Vision inference is offline; network connections are disabled')
    socket.socket.connect=denied
    try:yield
    finally:socket.socket.connect=original


class PitchCalibration:
    def __init__(self,image_points,pitch_points):
        import cv2
        import numpy as np
        a,b=np.asarray(image_points,dtype=float),np.asarray(pitch_points,dtype=float)
        if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=2 or len(a)<4 or not np.isfinite(a).all() or not np.isfinite(b).all():raise ValueError('At least four finite corresponding points are required')
        if np.any(b<0) or np.any(b[:,0]>105) or np.any(b[:,1]>68):raise ValueError('Pitch anchors must be in metres')
        if abs(cv2.contourArea(cv2.convexHull(a.astype('float32'))))<16 or abs(cv2.contourArea(cv2.convexHull(b.astype('float32'))))<4:raise ValueError('Calibration points must span an area')
        self.matrix,mask=cv2.findHomography(a,b,cv2.RANSAC,1)
        if self.matrix is None or np.linalg.cond(self.matrix)>1e9:raise ValueError('Degenerate calibration')
        residual=np.linalg.norm(cv2.perspectiveTransform(a[None].astype('float32'),self.matrix)[0]-b,axis=1)
        if max(residual)>2:raise ValueError('Calibration residual exceeds 2 metres')
        self.residual_m=float(max(residual))

    def map(self,point):
        x,y=point;h=self.matrix;z=h[2,0]*x+h[2,1]*y+h[2,2]
        if abs(z)<1e-8:return None
        return (float((h[0,0]*x+h[0,1]*y+h[0,2])/z),float((h[1,0]*x+h[1,1]*y+h[1,2])/z))


def calibration_from_keypoints(xy,confidence):
    """Roboflow 32-landmark order, expressed on our physical 105×68m pitch.

    Penalty-arc intersections use circle geometry, not goal-area width. RANSAC
    excludes bad keypoints; four non-collinear inliers are the minimum.
    """
    import numpy as np
    import cv2
    arc=math.sqrt(9.15**2-5.5**2)
    vertices=[(0,y) for y in [0,13.84,24.84,43.16,54.16,68]]
    vertices += [(5.5,24.84),(5.5,43.16),(11,34),(16.5,13.84),(16.5,34-arc),(16.5,34+arc),(16.5,54.16)]
    vertices += [(52.5,0),(52.5,24.85),(52.5,43.15),(52.5,68)]
    vertices += [(88.5,13.84),(88.5,34-arc),(88.5,34+arc),(88.5,54.16),(94,34),(99.5,24.84),(99.5,43.16)]
    vertices += [(105,y) for y in [0,13.84,24.84,43.16,54.16,68]]+[(43.35,34),(61.65,34)]
    selected=[i for i,c in enumerate(confidence) if c>=.6 and i<32]
    if len(selected)<4:return None
    a=np.asarray([xy[i] for i in selected],dtype='float32');b=np.asarray([vertices[i] for i in selected],dtype='float32')
    h,mask=cv2.findHomography(a,b,cv2.RANSAC,1.5)
    if h is None or mask is None or mask.sum()<4:return None
    try:
        valid=mask.ravel()==1
        value=PitchCalibration(a[valid].tolist(),b[valid].tolist());value.landmarks=int(valid.sum())
        return value
    except ValueError:return None


def stable_calibration(previous,proposed,pixel_points):
    """Reject a refit inconsistent with motion-tracked pitch geometry."""
    if previous is None:return proposed
    if proposed is None:return previous
    errors=[]
    for point in pixel_points:
        old,new=previous.map(point),proposed.map(point)
        if old and new:errors.append(math.dist(old,new))
    if len(errors)<4 or sorted(errors)[len(errors)//2]>1.5:return previous
    previous.matrix=.9*previous.matrix/previous.matrix[2,2]+.1*proposed.matrix/proposed.matrix[2,2]
    previous.residual_m=proposed.residual_m
    return previous


def select_pitch_calibration(predictions):
    candidates=[calibration_from_keypoints(p['xy'],p['confidence']) for p in predictions]
    return max((c for c in candidates if c is not None),key=lambda c:(c.landmarks,-c.residual_m),default=None)


class EventExtractor:
    """Conservative temporal inference: gaps/cuts reset possession chains."""
    def __init__(self,match_id='video',directions=None):
        self.match_id=match_id;self.owner=None;self.candidate=None;self.since=0
        self.directions=dict(directions) if directions is not None else {'A':1,'U':-1}
        self.last=None;self.flight=None;self.sequence=0;self.pressure_at={};self.current_speed=None
        self.missing=False

    def record(self,kind,t,player,position,**fields):
        self.sequence+=1
        return {'schema_version':'1.1','record_type':'event','id':f've{self.sequence:06}',
                'match_id':self.match_id,'event_time_ms':t,'observed_at_ms':t,'source':'local_pretrained_vision',
                'type':kind,'player_id':player,'team_id':player[0], 'position':position,
                'position_status':'estimated' if position else 'unavailable','confidence_kind':'detector_and_temporal_rule',**fields}

    def reset(self):
        self.owner=None;self.flight=None;self.last=None;self.candidate=None;self.current_speed=None
        self.missing=False

    def update(self,t,players,ball,calibrated=True):
        events=[]
        if not calibrated:
            self.reset();return events
        distance=lambda a,b:math.hypot(a['x']-b['x'],a['y']-b['y'])
        if not ball:
            # Preserve a hypothesis only after several observed flight samples.
            # No coordinates or speed are interpolated through the occlusion.
            if self.flight and self.flight.get('observations',0)>=3 and t-self.flight['last_observed']<=240:
                self.flight['short_occlusion']=True;self.missing=True
                self.last=None;self.candidate=None;self.current_speed=None
            else:self.reset()
            return events
        if self.missing:
            f=self.flight;dt=(t-f['last_observed'])/1000 if f else 0
            if not f or not 0<dt<=.24 or distance(ball,f['last_ball'])/dt>65:self.reset()
            self.missing=False
        if self.last and not 0<t-self.last[0]<=500:self.reset()
        speed=distance(ball,self.last[1])/((t-self.last[0])/1000) if self.last else None
        if speed and speed>65:
            self.reset();return events
        self.current_speed=speed
        nearest=min(players,key=lambda p:distance(ball,p),default=None)
        # Acquisition needs proximity and a ball moving with that player's body,
        # or a settled ball. A pass crossing nearby must not switch possession.
        player_speed=0
        if nearest and self.last:
            old=self.last[2].get(nearest['player_id'])
            if old:player_speed=distance(nearest,old)/((t-self.last[0])/1000)
        candidate=nearest['player_id'] if nearest and distance(ball,nearest)<2.7 and (speed is None or speed<max(4,player_speed+3)) else None
        if candidate!=self.candidate:self.candidate=candidate;self.since=t
        if self.owner and candidate!=self.owner and not self.flight:
            self.flight={'player':self.owner,'position':self.last[1] if self.last else ball,'time':self.last[0] if self.last else t,'observations':0,'short_occlusion':False}
        if self.flight:
            self.flight['observations']+=1;self.flight['last_observed']=t;self.flight['last_ball']=ball
        if candidate and t-self.since>=100:
            if self.flight and candidate!=self.flight['player']:
                f=self.flight;length=distance(f['position'],ball);duration=(t-f['time'])/1000
                if length>4 and .1<duration<=8:
                    events.append(self.record('pass',t,f['player'],f['position'],start_time_ms=f['time'],end_position=ball,receiver_id=candidate,
                        outcome='complete' if candidate[0]==f['player'][0] else 'incomplete',distance_m=round(length,2),average_speed_mps=None if f['short_occlusion'] else round(length/duration,2),
                        short_occlusion=f['short_occlusion'],method='Inferred release and stable receipt; short occlusion explicitly retained, never an observed complete trajectory'))
                    if candidate[0]!=f['player'][0]:
                        for kind in ['interception','recovery','possession_change']:events.append(self.record(kind,t,candidate,ball,previous_team_id=f['player'][0]))
                elif length<=4 and candidate[0]!=f['player'][0]:
                    events.append(self.record('recovery',t,candidate,ball,previous_team_id=f['player'][0],mechanism='observed_proximity_change'))
                    events.append(self.record('possession_change',t,candidate,ball,previous_team_id=f['player'][0]))
            self.owner=candidate;self.flight=None
        if self.flight:
            f=self.flight
            if t-f['time']>8000:self.owner=None;self.flight=None
            elif not f['short_occlusion'] and 28<ball['y']<40 and ((self.directions.get(f['player'][0])==1 and f['position']['x']>75 and ball['x']>103) or (self.directions.get(f['player'][0])==-1 and f['position']['x']<30 and ball['x']<2)):
                shot=self.record('shot',f['time'],f['player'],f['position'],method='Goalward flight from final third; outcome unconfirmed')
                shot['observed_at_ms']=t
                events.extend([shot,self.record('shot_end',t,f['player'],ball,shot_id=shot['id'])]);self.owner=None;self.flight=None
        if self.owner:
            for p in players:
                if p['player_id'][0]!=self.owner[0] and distance(ball,p)<=3 and t-self.pressure_at.get(p['player_id'],-5000)>=3000:
                    events.append(self.record('pressure',t,p['player_id'],{'x':p['x'],'y':p['y']},opponent_id=self.owner,
                        opponent_position=ball,distance_m=round(distance(ball,p),3),method='Opponent within 3m of observed ball carrier'))
                    self.pressure_at[p['player_id']]=t
        self.last=(t,dict(ball),{p['player_id']:p for p in players})
        return events


class CameraMotion:
    def __init__(self):self.previous=None
    def update(self,frame,calibration,boxes):
        import cv2
        import numpy as np
        gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        if self.previous is None:self.previous=gray;return True
        mask=np.full_like(gray,255)
        for x1,y1,x2,y2 in boxes:cv2.rectangle(mask,(max(0,int(x1)-8),max(0,int(y1)-8)),(int(x2)+8,int(y2)+8),0,-1)
        old=cv2.goodFeaturesToTrack(self.previous,300,.01,12,mask=mask)
        okay=False
        if old is not None and len(old)>=12:
            new,status,_=cv2.calcOpticalFlowPyrLK(self.previous,gray,old,None)
            good=status.ravel()==1
            if good.sum()>=12:
                h,inliers=cv2.findHomography(new[good],old[good],cv2.RANSAC,3)
                if h is not None and inliers.mean()>.65 and np.isfinite(h).all() and .5<abs(np.linalg.det(h[:2,:2]))<2:
                    calibration.matrix=calibration.matrix@h
                    okay=True
        self.previous=gray
        return okay


def load_detector(path):
    """Only load pinned, locally present weights through torch's safe loader."""
    import hashlib
    import torch
    from unittest.mock import patch
    from ultralytics import YOLO,settings
    settings.update({'sync':False})
    path=Path(path)
    manifest=json.loads((Path(__file__).resolve().parents[1]/'config/vision-model.json').read_text(encoding='utf-8'))
    if path.name!='football-detector.pt':manifest=manifest.get('additional_models',{}).get(path.name,{})
    if hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['sha256']:raise ValueError('Model checksum mismatch')
    allowed=[]
    for name in torch.serialization.get_unsafe_globals_in_checkpoint(path):
        extra={'ultralytics.utils.loss.BboxLoss','ultralytics.utils.IterableSimpleNamespace','ultralytics.utils.tal.TaskAlignedAssigner','ultralytics.utils.loss.v8PoseLoss','ultralytics.utils.loss.KeypointLoss'}
        if not name.startswith(('torch.nn.modules.','ultralytics.nn.')) and name not in extra:raise ValueError('Unexpected checkpoint global: '+name)
        module,attribute=name.rsplit('.',1)
        allowed.append(getattr(importlib.import_module(module),attribute))
    original=torch.load
    def safe_load(*args,**kwargs):kwargs['weights_only']=True;return original(*args,**kwargs)
    with torch.serialization.safe_globals(allowed),patch('torch.load',safe_load):
        return YOLO(str(path))


def analyze_video(source,output,config,progress=lambda value:None):
    import cv2
    import numpy as np
    from collections import Counter
    root=Path(__file__).resolve().parents[1]
    device=resolve_device(config.get('device','auto'))
    capture=cv2.VideoCapture(str(source))
    if not capture.isOpened():raise ValueError('Video could not be decoded')
    fps=capture.get(cv2.CAP_PROP_FPS)
    if not math.isfinite(fps) or fps<=0:raise ValueError('Video frame rate unavailable')
    frames=int(capture.get(cv2.CAP_PROP_FRAME_COUNT));stride=max(1,round(fps/config.get('sample_fps',10)))
    calibration=PitchCalibration(config['image_points'],config['pitch_points']) if config.get('image_points') else None
    detector=load_detector(root/'models/football-detector.pt')
    ball_detector=load_detector(root/'models/football-ball-detector.pt')
    automatic=config.get('auto_pitch',not bool(calibration))
    pitch_detector=load_detector(root/'models/football-pitch-detector.pt') if automatic else None
    names=detector.names
    extract=EventExtractor(config.get('match_id','video-match'),config.get('team_directions',{}))
    motion=CameraMotion();calibration_valid=bool(calibration);roster={};teams={};centers=None
    records=[];raw=[];counter=Counter();index=0;started=time.monotonic();coverage_state=None
    stop_after=config.get('max_seconds',600)
    previous_ball=None;ball_pixel=None;last_pitch_ms=-1000
    while True:
        ok,frame=capture.read()
        if not ok:break
        t=round(index/fps*1000);index+=1
        if t>stop_after*1000:break
        if (index-1)%stride:continue
        results=detector.track(frame,persist=True,tracker='botsort.yaml',conf=.12,imgsz=int(config.get('image_size',1280)),device=device,verbose=False)[0]
        detections=[]
        for box in results.boxes:
            kind=names[int(box.cls.item())].lower();xy=box.xyxy[0].tolist();confidence=float(box.conf.item());track=int(box.id.item()) if box.id is not None else None
            detections.append({'class':kind,'box':xy,'confidence':round(confidence,4),'track':track})
            counter[kind]+=1
        # A ball is only a few pixels in a broadcast wide shot. Detect crops at
        # native resolution, separately from the player tracker (no fake ball IDs).
        h,w=frame.shape[:2];size=min(640,h,w)
        crops=[];origins=[]
        if ball_pixel:
            x=max(0,min(w-size,round(ball_pixel[0]-size/2)));y=max(0,min(h-size,round(ball_pixel[1]-size/2)))
            origins=[(x,y)]
        else:
            origins=list(dict.fromkeys((min(x,w-size),min(y,h-size)) for y in range(0,h,max(1,size-80)) for x in range(0,w,max(1,size-80))))
        crops=[frame[y:y+size,x:x+size] for x,y in origins]
        found=[]
        for (ox,oy),result in zip(origins,ball_detector.predict(crops,classes=[0],conf=config.get('ball_confidence',.4),imgsz=640,device=device,verbose=False)):
            for box in result.boxes:
                x1,y1,x2,y2=box.xyxy[0].tolist()
                found.append({'class':'ball','box':[x1+ox,y1+oy,x2+ox,y2+oy],'confidence':round(float(box.conf.item()),4),'track':None})
        detections.extend(found);counter['ball']+=len(found)
        if found:
            best=max(found,key=lambda d:d['confidence']);x1,y1,x2,y2=best['box'];ball_pixel=((x1+x2)/2,(y1+y2)/2)
        else:ball_pixel=None
        raw.append({'time_ms':t,'detections':detections})
        people=[d for d in detections if d['class'] in {'player','goalkeeper'} and d['track'] is not None and d['confidence']>=.3]
        if calibration and config.get('camera_motion',True):
            calibration_valid=motion.update(frame,calibration,[d['box'] for d in people]) and calibration_valid
            if not calibration_valid:calibration=None;extract.reset()
        if pitch_detector and (not calibration_valid or t-last_pitch_ms>=240):
            keypoints=pitch_detector.predict(frame,imgsz=640,conf=.25,device=device,verbose=False)[0].keypoints
            predictions=[{'xy':k.xy[0].tolist(),'confidence':k.conf[0].tolist()} for k in keypoints] if keypoints is not None else []
            proposed=select_pitch_calibration(predictions)
            calibration=stable_calibration(calibration,proposed,[[(d['box'][0]+d['box'][2])/2,d['box'][3]] for d in people])
            calibration_valid=calibration is not None
            last_pitch_ms=t;motion.previous=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        if not calibration_valid:extract.reset()
        colors=[]
        for d in people:
            x1,y1,x2,y2=d['box'];h,w=frame.shape[:2]
            crop=frame[max(0,int(y1+(y2-y1)*.15)):min(h,int(y1+(y2-y1)*.55)),max(0,int(x1+(x2-x1)*.2)):min(w,int(x2-(x2-x1)*.2))]
            if crop.size:
                lab=cv2.cvtColor(crop,cv2.COLOR_BGR2LAB).reshape(-1,3)
                color=np.median(lab,axis=0).astype(float)
            else:color=np.zeros(3)
            colors.append(color)
        if centers is None and len(colors)>=4:
            values=np.array(colors,dtype=np.float32)
            first=values[0];other=values[np.linalg.norm(values-first,axis=1).argmax()]
            centers=np.array([first,other])
            for _ in range(8):
                assignment=np.linalg.norm(values[:,None,:]-centers[None,:,:],axis=2).argmin(axis=1)
                centers=np.array([values[assignment==i].mean(axis=0) if (assignment==i).any() else centers[i] for i in range(2)])
        players=[]
        for d,color in zip(people,colors):
            track=d['track'];team=teams.get(track)
            if team is None:
                team='A' if centers is None or np.linalg.norm(color-centers[0])<=np.linalg.norm(color-centers[1]) else 'U';teams[track]=team
            pid=f'{team}v{track}';binding=config.get('identities',{}).get(str(track),{})
            roster[pid]={'id':pid,'team_id':team,'shirt_number':binding.get('number',0),'name':binding.get('name',f'Team {team} · track {track}'),'identity_source':'roster_binding' if binding else 'anonymous_track'}
            x1,y1,x2,y2=d['box'];point=calibration.map([(x1+x2)/2,y2]) if calibration_valid else None
            if point and 0<=point[0]<=105 and 0<=point[1]<=68:players.append({'player_id':pid,'x':round(point[0],3),'y':round(point[1],3),'confidence':d['confidence']})
        balls=[d for d in detections if d['class']=='ball' and d['confidence']>=config.get('ball_confidence',.4)]
        ball=None
        if balls and calibration_valid:
            # Continuity rejects isolated distant false positives; never bridge a gap.
            options=[]
            for b in balls:
                x1,y1,x2,y2=b['box'];point=calibration.map([(x1+x2)/2,(y1+y2)/2])
                if point and 0<=point[0]<=105 and 0<=point[1]<=68:
                    if previous_ball and math.dist(point,previous_ball[1])/max((t-previous_ball[0])/1000,.001)>65:continue
                    options.append((b['confidence'],point))
            if options:
                _,point=max(options);ball={'x':round(point[0],3),'y':round(point[1],3),'owner_id':None};previous_ball=t,point
        if ball is None:
            previous_ball=None;ball_pixel=None
        available=calibration_valid and ball is not None
        if available!=coverage_state:
            records.append({'schema_version':'1.1','record_type':'coverage','id':f'vc{index}','match_id':extract.match_id,'event_time_ms':t,'observed_at_ms':t,'source':'local_pretrained_vision','channels':['tracking','event_positions'],'status':'available' if available else 'unavailable'})
            coverage_state=available
        records.extend(extract.update(t,players,ball,calibration_valid))
        if ball:ball['owner_id']=extract.owner
        records.append({'schema_version':'1.1','record_type':'tracking','id':f'vt{index}','match_id':extract.match_id,'event_time_ms':t,'observed_at_ms':t,'source':'local_pretrained_vision','period':1,'status':'available' if available else 'unavailable','players':players if available else None,'ball':ball if available else None,'possession_team_id':extract.owner[0] if extract.owner else None})
        progress({'processed_ms':t,'total_ms':round(min(frames/fps,stop_after)*1000),'frames':len(raw),'detections':dict(counter),'events':extract.sequence,'calibration_valid':calibration_valid})
    capture.release()
    if not roster:raise ValueError('No football player tracks found; inspect detection confidence or input footage')
    metadata={'schema_version':'1.1','record_type':'metadata','id':'video-meta','match_id':extract.match_id,'event_time_ms':0,'observed_at_ms':0,'source':'local_pretrained_vision','pitch':{'length_m':105,'width_m':68},'teams':[{'id':'A','name':'Team A','attack_direction_x':config.get('team_directions',{}).get('A',1)},{'id':'U','name':'Team U','attack_direction_x':config.get('team_directions',{}).get('U',-1)}],'roster':list(roster.values()),'initial_score':config.get('initial_score',{'A':0,'U':0}),'direction_source':'user_supplied' if 'team_directions' in config else 'unconfirmed','score_source':'user_supplied' if 'initial_score' in config else 'unconfirmed','initial_possession_team_id':None,'match_clock_start_ms':config.get('match_clock_start_ms',0),'channels':{'events':'unavailable','tracking':'unavailable','event_positions':'unavailable','pressure':'unavailable'},'observation_scope':'excerpt','measurement_notes':'Local pretrained detections; identity requires roster binding; planar speeds require calibration; inferred events are incomplete; score is not inferred from a shot.'}
    rows=[metadata]+sorted(records,key=lambda r:(r['observed_at_ms'],r['record_type']=='tracking',r['id']))
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'events.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    (output/'detections.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in raw),encoding='utf-8')
    summary={'status':'complete' if calibration_valid else 'needs_calibration','frames':len(raw),'detections':dict(counter),'events':extract.sequence,'elapsed_seconds':round(time.monotonic()-started,2),'source':'local_pretrained_vision','model_api_calls':0,'calibrated':calibration_valid,'calibration_mode':'pretrained_landmarks' if automatic else 'manual_anchors','calibration_residual_m':calibration.residual_m if calibration else None,'metrics_method':'2D pitch projection; sampled average speed, not launch velocity','roster':metadata['roster']}
    summary['device']=device
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    return summary


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('video');parser.add_argument('--output',required=True);parser.add_argument('--config',required=True)
    args=parser.parse_args()
    os.environ.update(YOLO_AUTOINSTALL='false',YOLO_OFFLINE='true',DO_NOT_TRACK='1',YOLO_CONFIG_DIR=str(Path(args.output)/'yolo-config'))
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    with network_disabled():
        result=analyze_video(args.video,args.output,config,lambda p:print(json.dumps(p),flush=True))
    print(json.dumps(result,ensure_ascii=False),flush=True)
