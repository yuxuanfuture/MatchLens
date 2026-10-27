"""Validate authored replay fixtures without invoking a language model."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FORBIDDEN = {"phases", "label", "case", "ground_truth", "expected", "narrative", "commentary", "title", "description"}


def validate_records(rows):
    if rows and rows[0].get("schema_version") == "1.2" and rows[0].get("match_id") == "match-04":
        from scripts.validate_stream_04 import validate_records as validate_stream_04
        return validate_stream_04(rows)
    errors = []

    def check(condition, message):
        if not condition:
            errors.append(message)

    def scan(value, location):
        if isinstance(value, dict):
            for key, item in value.items():
                check(key not in FORBIDDEN, f"{location}: answer-bearing field {key}")
                scan(item, f"{location}.{key}")
            if "x" in value and "y" in value:
                x, y = value["x"], value["y"]
                check(all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (x, y)), f"{location}: non-numeric coordinate")
                if all(isinstance(v, (int, float)) for v in (x, y)):
                    check(0 <= x <= 105 and 0 <= y <= 68, f"{location}: position outside pitch")
        elif isinstance(value, list):
            for item in value:
                scan(item, location)

    if not rows or rows[0].get("record_type") != "metadata":
        return ["Missing initial metadata"]
    metadata = rows[0]
    roster = {p["id"]: p for p in metadata["roster"]}
    active = {p["id"] for p in roster.values() if p.get("starter", True)}
    check(len(roster) == len(metadata["roster"]), "Roster IDs must be unique")
    check(len(active) == 22, "Starting roster must contain 22 unique players")
    check(Counter(roster[p]["team_id"] for p in active) == {"A": 11, "U": 11}, "Each team must have 11 starters")
    check(len({r["id"] for r in rows}) == len(rows), "Duplicate record IDs")
    check(sum(r["record_type"] == "metadata" for r in rows) == 1, "Metadata must occur once")
    check(all(a["observed_at_ms"] <= b["observed_at_ms"] for a, b in zip(rows, rows[1:])), "Stream arrival order is not monotonic")
    last_frame = None
    for row in rows:
        scan(row, row["id"])
        check(row.get("schema_version") in {"1.0", "1.1"}, f"{row['id']}: invalid schema version")
        check(row.get("match_id") == metadata["match_id"], f"{row['id']}: wrong match identity")
        for key in ("event_time_ms", "observed_at_ms"):
            check(type(row[key]) is int and row[key] >= 0, f"{row['id']}: invalid {key}")
        check(row["event_time_ms"] <= row["observed_at_ms"], f"{row['id']}: received before occurrence")
        if row["record_type"] == "event":
            if row["type"] == "substitution":
                incoming, outgoing = row["player_in_id"], row["player_out_id"]
                check(incoming in roster and incoming not in active and outgoing in active, f"{row['id']}: invalid substitution")
                check(roster[incoming]["team_id"] == roster[outgoing]["team_id"], f"{row['id']}: substitution across teams")
                active.discard(outgoing)
                active.add(incoming)
            check(row["player_id"] in roster, f"{row['id']}: unknown actor")
            if row["player_id"] in roster:
                check(roster[row["player_id"]]["team_id"] == row["team_id"], f"{row['id']}: actor/team mismatch")
            check(row.get("position_status") in {"observed", "unavailable"}, f"{row['id']}: position status missing")
            check((row.get("position") is not None) == (row.get("position_status") == "observed"), f"{row['id']}: missingness not explicit")
            if row["type"] == "pass":
                check(row["receiver_id"] in roster, f"{row['id']}: unknown receiver")
                check(row["start_time_ms"] < row["event_time_ms"], f"{row['id']}: non-positive pass duration")
                if row["receiver_id"] in roster:
                    check(roster[row["receiver_id"]]["team_id"] == row["team_id"], f"{row['id']}: completed pass across teams")
                if row.get("position") and row.get("end_position"):
                    distance = math.dist(tuple(row["position"].values()), tuple(row["end_position"].values()))
                    check(distance / ((row["event_time_ms"] - row["start_time_ms"]) / 1000) <= 40, f"{row['id']}: excessive pass speed")
            if row["type"] == "shot":
                check("outcome" not in row and "end_position" not in row, f"{row['id']}: shot includes future outcome")
            if row["type"] == "pressure":
                distance = math.dist(tuple(row["position"].values()), tuple(row["opponent_position"].values()))
                check(abs(distance - row["distance_m"]) < .01 and distance <= 3, f"{row['id']}: pressure geometry inconsistent")
        elif row["record_type"] == "tracking":
            if row["status"] == "unavailable":
                check(row["players"] is None and row["ball"] is None, f"{row['id']}: hidden positions must be null")
                last_frame = None
                continue
            players = {p["player_id"]: p for p in row["players"]}
            check(len(row["players"]) == 22 and set(players) == active, f"{row['id']}: inconsistent tracking roster")
            if last_frame and row.get("period") == last_frame.get("period"):
                elapsed = (row["event_time_ms"] - last_frame["event_time_ms"]) / 1000
                previous = {p["player_id"]: p for p in last_frame["players"]}
                for player, p in players.items():
                    if player not in previous:
                        continue
                    old = previous[player]
                    speed = math.hypot(p["x"] - old["x"], p["y"] - old["y"]) / elapsed
                    check(speed <= 11, f"{row['id']}/{player}: implausible player speed {speed:.2f} m/s")
            ball = row["ball"]
            if ball["owner_id"]:
                owner = players.get(ball["owner_id"])
                check(owner is not None, f"{row['id']}: unknown ball owner")
                if owner:
                    check(math.hypot(ball["x"] - owner["x"], ball["y"] - owner["y"]) < .02, f"{row['id']}: owned ball detached from player")
            last_frame = row
    return errors


def validate_file(path):
    try:
        rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
        return validate_records(rows)
    except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
        return [f"Malformed stream: {error}"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    failures = 0
    for path in args.paths or sorted((ROOT / "data" / "streams").glob("*.jsonl")):
        problems = validate_file(path)
        print(f"{path.name}: {'FAIL' if problems else 'PASS'}")
        for problem in problems:
            print(f"  {problem}")
        failures += len(problems)
    raise SystemExit(1 if failures else 0)
