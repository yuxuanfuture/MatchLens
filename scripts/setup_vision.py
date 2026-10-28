"""Explicit dependency/weight installation. Runtime inference never downloads."""
import hashlib,json,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
subprocess.run(['uv','venv',str(ROOT/'.venv-vision'),'--python','3.13'],check=True) if not (ROOT/'.venv-vision').exists() else None
subprocess.run(['uv','pip','sync','--python',str(ROOT/'.venv-vision/bin/python'),str(ROOT/'requirements-vision.lock')],check=True)
manifest=json.loads((ROOT/'config/vision-model.json').read_text());target=ROOT/'models/football-detector.pt';target.parent.mkdir(exist_ok=True)
if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=manifest['sha256']:
 temporary=target.with_suffix('.download')
 with urllib.request.urlopen(manifest['source'],timeout=60) as response,temporary.open('wb') as output:
  while chunk:=response.read(1_048_576):output.write(chunk)
 if hashlib.sha256(temporary.read_bytes()).hexdigest()!=manifest['sha256']:raise SystemExit('Model checksum mismatch; file was not installed')
 temporary.replace(target)
for filename,extra in manifest.get('additional_models',{}).items():
 destination=ROOT/'models'/filename
 if not destination.exists() or hashlib.sha256(destination.read_bytes()).hexdigest()!=extra['sha256']:
  temporary=destination.with_suffix('.download')
  subprocess.run([str(ROOT/'.venv-vision/bin/gdown'),extra['source'],'-O',str(temporary)],check=True)
  if hashlib.sha256(temporary.read_bytes()).hexdigest()!=extra['sha256']:raise SystemExit('Additional model checksum mismatch')
  temporary.replace(destination)
print('Vision ready. Pinned weights verified; no training or model API call.')
