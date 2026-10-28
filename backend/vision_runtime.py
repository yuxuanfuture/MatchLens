"""Platform-specific local vision paths; the original macOS environment is kept."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
VISION_ENV = ROOT / (".venv-vision-windows" if WINDOWS else ".venv-vision")
VISION_PYTHON = VISION_ENV / ("Scripts/python.exe" if WINDOWS else "bin/python")
DEFAULT_DEVICE = "cpu" if WINDOWS else "mps"


def resolve_device(device="auto"):
    return DEFAULT_DEVICE if device == "auto" else device
