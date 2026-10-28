"""Install a separate Windows vision environment, preserving the macOS paths."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.vision_runtime import VISION_ENV, VISION_PYTHON


def main():
    if os.name != "nt":
        raise SystemExit("This installer is for Windows. Use scripts/setup_vision.py on macOS.")
    if sys.version_info[:2] != (3, 13):
        raise SystemExit("Use Python 3.13 for this pinned Windows environment.")
    if not VISION_PYTHON.exists():
        venv.EnvBuilder(with_pip=True).create(VISION_ENV)
    lock = ROOT / "requirements-vision-windows.lock"
    installer = shutil.which("uv")
    if installer:
        command = [installer, "pip", "sync", "--python", str(VISION_PYTHON), str(lock)]
    else:
        subprocess.run([str(VISION_PYTHON), "-m", "ensurepip", "--upgrade"], check=True)
        command = [str(VISION_PYTHON), "-m", "pip", "install", "-r", str(lock)]
    subprocess.run(command, check=True)

    manifest = json.loads((ROOT / "config/vision-model.json").read_text(encoding="utf-8"))
    models = {"football-detector.pt": manifest, **manifest.get("additional_models", {})}
    for name, spec in models.items():
        destination = ROOT / "models" / name
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != spec["sha256"]:
                raise SystemExit(f"Checksum mismatch: {destination}. Existing model was kept.")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(".windows-download")
            if "drive.google.com" in spec["source"]:
                subprocess.run([str(VISION_PYTHON), "-m", "gdown", spec["source"], "-O", str(temporary)], check=True)
            else:
                with urllib.request.urlopen(spec["source"], timeout=60) as response, temporary.open("wb") as output:
                    shutil.copyfileobj(response, output)
            if hashlib.sha256(temporary.read_bytes()).hexdigest() != spec["sha256"]:
                raise SystemExit(f"Checksum mismatch: {name}; downloaded model was not installed.")
            temporary.replace(destination)
        print(f"Verified {name}", flush=True)
    print(f"Windows vision ready: {VISION_PYTHON}\nDefault device: CPU. macOS environment preserved.")


if __name__ == "__main__":
    main()
