"""Bounded, cancellable local video workers; no model service is used."""
import json
import os
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.vision_runtime import VISION_PYTHON, resolve_device

ROOT=Path(__file__).resolve().parents[1]

class VideoJobs:
 def __init__(self,root=None):
  self.root=Path(root or ROOT/'run-output/video-jobs');self.root.mkdir(parents=True,exist_ok=True)
  self.uploads={};self.jobs={};self.lock=threading.RLock();self.pool=ThreadPoolExecutor(max_workers=1)

 def upload(self,reader,length):
  if not 0<length<=250_000_000:raise ValueError('Video must be under 250 MB')
  with self.lock:
   if len(self.uploads)>=8:raise ValueError('Eight local uploads per server session; restart to begin another batch')
   identifier=uuid.uuid4().hex;path=self.root/identifier;path.mkdir()
   with (path/'source.video').open('wb') as handle:
    remaining=length
    while remaining:
     chunk=reader.read(min(remaining,1_048_576))
     if not chunk:raise ValueError('Upload interrupted')
     handle.write(chunk);remaining-=len(chunk)
   self.uploads[identifier]=path
   return {'upload_id':identifier,'bytes':length}

 def start(self,identifier,config):
  if not isinstance(config,dict):raise ValueError('Video configuration must be an object')
  if not VISION_PYTHON.is_file() or not os.access(VISION_PYTHON,os.X_OK) or any(not (ROOT/'models'/name).exists() for name in ['football-detector.pt','football-ball-detector.pt','football-pitch-detector.pt']):raise ValueError('Run scripts/setup_vision_windows.py on Windows, or scripts/setup_vision.py on macOS first')
  allowed={'image_points','pitch_points','identities','sample_fps','max_seconds','camera_motion','auto_pitch','initial_score','team_directions','match_clock_start_ms','device','ball_confidence'}
  if set(config)-allowed:raise ValueError('Unknown video setting')
  if not 5<=config.get('sample_fps',10)<=25 or not 1<=config.get('max_seconds',60)<=600:raise ValueError('Use 5–25 samples/second and 1–600 seconds')
  if config.get('device','auto') not in {'auto','cpu','mps','0'}:raise ValueError('Unsupported local device')
  config={**config,'device':resolve_device(config.get('device','auto'))}
  if 'team_directions' in config and (not isinstance(config['team_directions'],dict) or set(config['team_directions'])!={'A','U'} or any(type(v) is not int for v in config['team_directions'].values()) or set(config['team_directions'].values())!={1,-1}):raise ValueError('Provide opposite A/U directions, +1 or -1')
  if 'initial_score' in config and (not isinstance(config['initial_score'],dict) or set(config['initial_score'])!={'A','U'} or any(type(v) is not int or v<0 for v in config['initial_score'].values())):raise ValueError('Provide non-negative A/U initial scores')
  if not isinstance(config.get('identities',{}),dict):raise ValueError('Identities must map tracking numbers to names and shirt numbers')
  for identity in config.get('identities',{}).values():
   if not isinstance(identity,dict) or not isinstance(identity.get('name'),str) or not identity['name'].strip() or type(identity.get('number')) is not int or not 1<=identity['number']<=99:raise ValueError('Each identity needs a name and a shirt number from 1 to 99')
  with self.lock:
   if identifier not in self.uploads:raise ValueError('Unknown upload')
   if any(j['status'] in {'queued','running'} for j in self.jobs.values()):raise ValueError('A local video job is already running')
   job_id=uuid.uuid4().hex;folder=self.uploads[identifier]/job_id;folder.mkdir()
   (folder/'config.json').write_text(json.dumps({**config,'match_id':job_id}),encoding='utf-8')
   job={'job_id':job_id,'upload_id':identifier,'status':'queued','progress':{},'cancel':False,'folder':folder}
   self.jobs[job_id]=job;self.pool.submit(self._run,job)
   return self.status(job_id)

 def _run(self,job):
  source=self.uploads[job['upload_id']]/'source.video';folder=job['folder']
  env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['API_KEY','TOKEN','SECRET'])}
  env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8')
  cmd=[str(VISION_PYTHON),'-X','utf8','-u','-m','backend.vision',str(source),'--output',str(folder),'--config',str(folder/'config.json')]
  try:
   with self.lock:
    if job['cancel']:job['status']='cancelled';return
    job['status']='running'
    process=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    job['process']=process
   with (folder/'worker.log').open('w',encoding='utf-8') as log:
    for line in process.stdout:
     log.write(line)
     try:
      value=json.loads(line)
      if isinstance(value,dict):
       with self.lock:job['progress']=value
     except ValueError:pass
   code=process.wait()
   with self.lock:
    job.pop('process',None)
    job['status']='cancelled' if job['cancel'] else 'complete' if code==0 else 'failed'
    if code==0:job['summary']=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
    elif not job['cancel']:job['error']='Video worker failed. Check calibration, dependencies and the local worker.log.'
  except Exception:
   with self.lock:job.update(status='failed',error='Unable to run local vision worker')

 def status(self,identifier):
  with self.lock:
   job=self.jobs[identifier]
   return {k:v for k,v in job.items() if k not in {'folder','process','cancel'}}

 def cancel(self,identifier):
  with self.lock:
   job=self.jobs[identifier];job['cancel']=True
   if job.get('process'):job['process'].terminate()
   return self.status(identifier)

 def records(self,identifier):
  with self.lock:
   job=self.jobs[identifier]
   if job['status']!='complete':raise ValueError('Video job has not completed')
   return [json.loads(line) for line in (job['folder']/'events.jsonl').read_text(encoding='utf-8').splitlines()]

 def detections(self,identifier):
  with self.lock:
   job=self.jobs[identifier]
   if job['status']!='complete':raise ValueError('Video job has not completed')
   return [json.loads(line) for line in (job['folder']/'detections.jsonl').read_text(encoding='utf-8').splitlines()]

 def close(self):
  for identifier in list(self.jobs):self.cancel(identifier)
  self.pool.shutdown(wait=False,cancel_futures=True)
