"""Publish a JSONL fixture as real arrival batches into the local live endpoint."""
import argparse,json,time,urllib.request,urllib.parse
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('file',type=Path);p.add_argument('--base-url',default='http://127.0.0.1:43128');p.add_argument('--speed',type=float,default=16);a=p.parse_args()
url=urllib.parse.urlsplit(a.base_url)
if url.hostname not in {'localhost','127.0.0.1'} or url.scheme!='http' or a.speed<=0:p.error('Use a local HTTP server and positive speed')
def post(path,body):
 request=urllib.request.Request(a.base_url+path,json.dumps(body).encode(),{'Content-Type':'application/json'})
 for attempt in range(3):
  try:
   with urllib.request.urlopen(request,timeout=10) as response:return json.load(response)
  except OSError:
   if attempt==2:raise
   time.sleep(.5*2**attempt)
rows=[json.loads(line) for line in a.file.read_text().splitlines() if line.strip()];metadata=next(r for r in rows if r['record_type']=='metadata');created=post('/api/session',{'records':[metadata],'live':True});sid=created['session_id']
print(f'{a.base_url}/?session={sid}',flush=True)
start=time.monotonic();pending=sorted([r for r in rows if r is not metadata],key=lambda r:r['observed_at_ms']);i=0
while i<len(pending):
 now=int((time.monotonic()-start)*1000*a.speed);end=i
 while end<len(pending) and pending[end]['observed_at_ms']<=now and end-i<1000:end+=1
 if end>i:
  post('/api/ingest',{'session':sid,'records':pending[i:end],'received_at_ms':now});i=end
 else:time.sleep(.02)
print(json.dumps({'session':sid,'records':len(rows),'model_api_calls_from_producer':0}))
