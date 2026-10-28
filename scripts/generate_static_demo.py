"""Generate deterministic browser-demo snapshots from the real offline publisher."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.api_policy import policy_status
from backend.i18n import LANGUAGES
from backend.server import Session


STREAM = ROOT / "data/streams/stream-04.jsonl"
OUTPUT = ROOT / "dist/demo-data"
INTERVAL_MS = 500


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def snapshot_payload(session: Session, position_ms: int, index: int) -> dict:
    receive_time = session.playback_config["receive_offset_ms"] + position_ms
    payload = session.control({"seek_ms": receive_time})
    payload.update(
        session_id="static-demo",
        source_mode="static_demo",
        playing=False,
        speed=1,
        epoch=0,
        sequence=index,
        agent_status="locked",
    )
    return payload


def generate_language(language: str, positions: list[int]) -> dict:
    session = Session("stream-04", {"language": language})
    snapshots = [
        snapshot_payload(session, position, index)
        for index, position in enumerate(positions)
    ]
    recaps = {}
    for team in ("A", "U"):
        recap_session = Session("stream-04", {"language": language, "focus_team": team})
        items = []
        for position in positions:
            receive_time = recap_session.playback_config["receive_offset_ms"] + position
            recap_session.control({"seek_ms": receive_time})
            items.append(recap_session.make_recap())
        recaps[team] = items
    return {"language": language, "snapshots": snapshots, "recaps": recaps}


def main() -> None:
    if policy_status()["enabled"]:
        raise SystemExit("Static demo generation requires the model API policy to remain disabled.")
    rows = [json.loads(line) for line in STREAM.read_text(encoding="utf-8").splitlines() if line]
    metadata = rows[0]
    duration = metadata["scheduled_duration_ms"]
    positions = list(range(0, duration + 1, INTERVAL_MS))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "records.json").write_text(compact(rows) + "\n", encoding="utf-8")
    for language in LANGUAGES:
        (OUTPUT / f"{language}.json").write_text(
            compact(generate_language(language, positions)) + "\n", encoding="utf-8"
        )
    manifest = {
        "schema_version": "matchlens.static-demo/1.0",
        "stream": "stream-04",
        "languages": list(LANGUAGES),
        "interval_ms": INTERVAL_MS,
        "duration_ms": duration,
        "receive_offset_ms": 80,
        "snapshots": len(positions),
        "source_sha256": hashlib.sha256(STREAM.read_bytes()).hexdigest(),
    }
    (OUTPUT / "manifest.json").write_text(compact(manifest) + "\n", encoding="utf-8")
    print(compact(manifest))


if __name__ == "__main__":
    main()
