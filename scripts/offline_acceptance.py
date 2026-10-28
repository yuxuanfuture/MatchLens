"""Run reproducible offline checks without making a model API request."""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api_policy import policy_status
from backend.vision_runtime import VISION_PYTHON


def executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def run_check(command: list[str], folder: Path, index: int, *, optional=False):
    start = time.monotonic()
    run = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    log = folder / f"check-{index}.log"
    log.write_text(run.stdout + run.stderr, encoding="utf-8")
    row = {
        "command": command,
        "passed": run.returncode == 0,
        "optional": optional,
        "seconds": round(time.monotonic() - start, 2),
        "log": str(log),
    }
    print(json.dumps(row), flush=True)
    return row


if policy_status()["enabled"]:
    raise SystemExit("Offline acceptance requires the model API policy to remain disabled.")

folder = ROOT / ("run-output/acceptance-windows" if os.name == "nt" else "run-output/acceptance")
folder.mkdir(parents=True, exist_ok=True)
python = str(VISION_PYTHON) if executable(VISION_PYTHON) else sys.executable

core_tests = [
    str(path.relative_to(ROOT))
    for path in sorted((ROOT / "tests").glob("test_*.py"))
    if path.name != "test_vision.py"
]
javascript_tests = [str(path.relative_to(ROOT)) for path in sorted((ROOT / "tests").glob("*.test.mjs"))]
commands = [
    [python, "-X", "utf8", "scripts/validate_match_fixtures.py"],
    [python, "-X", "utf8", "scripts/validate_stream_04.py"],
    [python, "-X", "utf8", "-m", "unittest", "-v", *core_tests],
]
if not shutil.which("node"):
    raise SystemExit("Node.js is required to run the browser-side acceptance tests.")
commands.append(["node", "--test", *javascript_tests])

results = [run_check(command, folder, index) for index, command in enumerate(commands, 1)]

vision_probe = subprocess.run(
    [python, "-c", "import cv2, numpy"],
    cwd=ROOT,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
if vision_probe.returncode == 0:
    results.append(
        run_check(
            [python, "-X", "utf8", "-m", "unittest", "-v", "tests/test_vision.py"],
            folder,
            len(results) + 1,
            optional=True,
        )
    )
    vision_status = "tested"
else:
    vision_status = "skipped_optional_dependencies_not_installed"
    print(json.dumps({"vision": vision_status}), flush=True)

required_results = [row for row in results if not row["optional"]]
report = {
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "type": "offline_engineering_acceptance",
    "model_api_enabled": False,
    "real_model_quality": "not_evaluated_without_explicit_owner_authorization",
    "vision_tests": vision_status,
    "checks": results,
    "passed": all(row["passed"] for row in required_results),
}
vision = ROOT / (
    "run-output/vision-windows-smoke/summary.json"
    if os.name == "nt"
    else "run-output/vision-acceptance/summary.json"
)
if vision.exists():
    report["local_vision_smoke"] = {
        key: value
        for key, value in json.loads(vision.read_text(encoding="utf-8")).items()
        if key != "roster"
    }

report_path = folder / "report.json"
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(report_path)
raise SystemExit(0 if report["passed"] else 1)
