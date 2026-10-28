"""Build paired, football-consistent replay fixtures. No model training is involved."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = 20261027
NUMBERS = [1, 2, 4, 5, 3, 6, 8, 10, 7, 9, 11]
BASE = {
    "A": [(6, 34), (24, 10), (23, 26), (23, 44), (24, 59), (42, 32),
          (43, 51), (55, 22), (62, 13), (68, 36), (59, 58)],
    "U": [(99, 34), (77, 13), (64, 20), (68, 45), (50, 57), (54, 31),
          (43, 45), (45, 16), (46, 8), (43, 31), (32, 50)],
}


def action(kind, start, end, actor, origin, target, receiver=None):
    return {"kind": kind, "start": int(start * 1000), "end": int(end * 1000),
            "actor": actor, "origin": origin, "target": target, "receiver": receiver}


def actions(branch):
    sequence = [
        action("carry", 0, 3, "U4", (64, 20), (62, 22)),
        action("pass", 3, 4.5, "U4", (62, 22), (54, 31), "U6"),
        action("carry", 4.5, 8, "U6", (54, 31), (50, 34)),
        action("pass", 8, 9.5, "U6", (50, 34), (43, 45), "U8"),
        action("carry", 9.5, 13, "U8", (43, 45), (40, 46)),
        action("pass", 13, 14.5, "U8", (40, 46), (50, 57), "U3"),
        action("carry", 14.5, 19, "U3", (50, 57), (56, 58)),
        action("pass", 19, 21, "U3", (56, 58), (68, 45), "U5"),
        action("carry", 21, 25, "U5", (68, 45), (70, 41)),
        action("pass", 25, 27, "U5", (70, 41), (73, 21), "U4"),
        action("carry", 27, 33, "U4", (73, 21), (75, 19)),
        action("pass", 33, 35, "U4", (75, 19), (77, 13), "U2"),
        action("carry", 35, 41, "U2", (77, 13), (77, 16)),
        action("pass", 42, 44, "U2", (77, 16), (83, 29), "U4"),
        action("pass", 47, 49, "U4", (83, 29), (89, 21), "U5"),
        action("carry", 49, 53, "U5", (89, 21), (84, 24)),
    ]
    if branch == "escape":
        sequence += [
            action("pass", 53, 54.5, "U5", (84, 24), (70, 34), "U6"),
            action("carry", 54.5, 59, "U6", (70, 34), (56, 35)),
            action("pass", 59, 61, "U6", (56, 35), (36, 31), "U9"),
            action("carry", 61, 66, "U9", (36, 31), (25, 30)),
            action("pass", 67, 69, "U9", (25, 30), (20, 50), "U11"),
            action("carry", 69, 75, "U11", (20, 50), (18, 48)),
            action("pass", 78, 80, "U11", (18, 48), (30, 38), "U8"),
        ]
    else:
        sequence += [
            action("carry", 53, 56, "U5", (84, 24), (80, 25)),
            action("recovery", 56, 56, "A7", (80, 25), (80, 25)),
            action("carry", 56, 59, "A7", (80, 25), (83, 27)),
            action("pass", 59, 60.5, "A7", (83, 27), (88, 34), "A9"),
            action("carry", 60.5, 63, "A9", (88, 34), (91, 34)),
            action("shot", 63, 63.4, "A9", (91, 34), (99, 34), "U1"),
            action("save", 63.4, 63.4, "U1", (99, 34), (99, 34)),
            action("pass", 70, 72, "U1", (99, 34), (90, 13), "U2"),
            action("carry", 72, 78, "U2", (90, 13), (87, 13)),
            action("pass", 78, 80, "U2", (87, 13), (75, 28), "U6"),
        ]
    return sequence


def interpolate(points, time):
    ordered = sorted(points.items())
    previous_time, previous = ordered[0]
    for next_time, following in ordered[1:]:
        if time <= next_time:
            fraction = (time - previous_time) / (next_time - previous_time)
            return tuple(a + (b - a) * max(0, fraction) for a, b in zip(previous, following))
        previous_time, previous = next_time, following
    return previous


def build_paths(sequence, branch):
    paths = {f"{team}{number}": {0: position}
             for team in BASE for number, position in zip(NUMBERS, BASE[team])}
    anchors = {"U1": (99, 34), "U2": (87, 13), "U4": (86, 31), "U5": (84, 24),
               "U3": (66, 57), "U6": (68, 34), "U8": (53, 45), "U10": (57, 16),
               "U7": (60, 8), "U9": (43, 31), "U11": (32, 50)}
    for player, track in paths.items():
        x, y = track[0]
        track[53000] = anchors.get(player, (x + (0 if player == "A1" else 11), y))
    paths["A7"].update({35000: (70, 14), 41000: (74.7, 16), 44000: (78, 19),
                         49000: (82, 21), 52000: (82.9, 23), 53000: (83, 24)})
    paths["A9"].update({35000: (73, 31), 46000: (80.8, 29), 49000: (83, 31), 53000: (83, 32)})
    if branch == "escape":
        paths["A7"][56000] = (73, 27)
        paths["A9"][59000] = (62, 32)
    for item in sequence:
        actor = paths[item["actor"]]
        actor[item["start"]] = item["origin"]
        if item["kind"] in {"carry", "recovery", "save"}:
            actor[item["end"]] = item["target"]
        if item["receiver"]:
            paths[item["receiver"]][item["end"]] = item["target"]
    for track in paths.values():
        track[90000] = track[max(track)]
    return paths


def ball_at(sequence, time):
    position, owner, possession = (64, 20), "U4", "U"
    for item in sequence:
        if time < item["start"]:
            break
        duration = item["end"] - item["start"]
        fraction = min(1, (time - item["start"]) / duration) if duration else 1
        position = tuple(a + (b - a) * fraction for a, b in zip(item["origin"], item["target"]))
        possession = item["actor"][0]
        if item["kind"] in {"pass", "shot"}:
            owner = item["receiver"] if time >= item["end"] else None
            if owner:
                possession = owner[0]
        else:
            owner = item["actor"]
        if time < item["end"]:
            break
    return position, owner, possession


def build_stream(branch, seed=DEFAULT_SEED):
    rng = random.Random(seed)
    y_offset = round(rng.uniform(-1, 1), 2)

    def point(value):
        return {"x": round(value[0], 3), "y": round(value[1] + y_offset, 3)}

    def record(kind, identifier, time, **fields):
        return {"schema_version": "1.0", "record_type": kind, "id": identifier,
                "match_id": "match-01", "event_time_ms": time,
                "observed_at_ms": time + (0 if kind == "metadata" else 80),
                "source": "synthetic_simulator", **fields}

    sequence = actions(branch)
    paths = build_paths(sequence, branch)
    records = [record("metadata", "meta-01", 0,
        pitch={"length_m": 105, "width_m": 68, "coordinates": "metres"},
        period=2, match_clock_start_ms=62 * 60 * 1000, initial_score={"A": 0, "U": 0},
        teams=[{"id": "A", "name": "Atlas", "attack_direction_x": 1},
               {"id": "U", "name": "Union", "attack_direction_x": -1}],
        roster=[{"id": f"{team}{number}", "team_id": team, "shirt_number": number,
                 "name": f"{'Atlas' if team == 'A' else 'Union'} {number}"}
                for team in BASE for number in NUMBERS],
        initial_possession_team_id="U",
        channels={"events": "available", "event_positions": "available",
                  "tracking": "available", "pressure": "available"})]
    for index, item in enumerate(sequence, 1):
        kind = item["kind"]
        # A shot is known when kicked. Its future end point/outcome is not published.
        time = item["start"] if kind == "shot" else item["end"]
        fields = {"type": kind, "team_id": item["actor"][0], "player_id": item["actor"],
                  "period": 2, "position": point(item["origin"]),
                  "position_status": "observed"}
        if kind in {"pass", "carry"}:
            fields.update(start_time_ms=item["start"], end_position=point(item["target"]))
        if kind == "pass":
            fields.update(receiver_id=item["receiver"], outcome="complete")
        elif kind == "recovery":
            fields.update(previous_team_id="U")
        elif kind == "save":
            fields.update(outcome="held")
        records.append(record("event", f"e{index:03}", time, **fields))
    for index, (time, actor, opponent) in enumerate([(41000, "A7", "U2"), (46000, "A9", "U4"), (52000, "A7", "U5")], 1):
        position, opposing = interpolate(paths[actor], time), interpolate(paths[opponent], time)
        records.append(record("event", f"p{index:03}", time, type="pressure", period=2,
            team_id="A", player_id=actor, opponent_id=opponent, position=point(position),
            opponent_position=point(opposing), position_status="observed",
            distance_m=round(math.dist(position, opposing), 3)))
    for index, time in enumerate(range(0, 90001, 500)):
        position, owner, possession = ball_at(sequence, time)
        records.append(record("tracking", f"t{index:03}", time,
            sample_interval_ms=500, status="available", possession_team_id=possession,
            ball={**point(position), "owner_id": owner},
            players=[{"player_id": player, **point(interpolate(track, time))}
                     for player, track in paths.items()]))
    records.sort(key=lambda row: (row["observed_at_ms"], row["record_type"] == "tracking", row["id"]))
    return records


def with_missing_channels(records):
    result = []
    for original in records:
        row = copy.deepcopy(original)
        time = row["event_time_ms"]
        if 35000 <= time < 64000:
            if row.get("type") == "pressure":
                continue
            if row["record_type"] == "tracking":
                row.update(status="unavailable", ball=None, players=None, possession_team_id=None)
            elif row["record_type"] == "event":
                for field in ("position", "end_position", "opponent_position", "distance_m"):
                    if field in row:
                        row[field] = None
                row["position_status"] = "unavailable"
        result.append(row)
    for time, status in [(35000, "unavailable"), (64000, "available")]:
        result.append({"schema_version": "1.0", "record_type": "coverage", "id": f"q{time}",
            "match_id": "match-01", "event_time_ms": time, "observed_at_ms": time + 80,
            "source": "synthetic_simulator", "status": status,
            "channels": ["tracking", "pressure", "event_positions"],
            "reason": "feed_status_update"})
    result.sort(key=lambda row: (row["observed_at_ms"], row["record_type"] == "tracking", row["id"]))
    return result


def write_fixtures(root=ROOT, seed=DEFAULT_SEED):
    root = Path(root)
    folder = root / "data" / "streams"
    folder.mkdir(parents=True, exist_ok=True)
    positive = build_stream("regain", seed)
    streams = {"stream-01": positive, "stream-02": build_stream("escape", seed),
               "stream-03": with_missing_channels(positive)}
    manifest = {"version": "1.0", "seed": seed, "purpose": "inference replay and evaluation; not training",
                "duration_ms": 90000, "tracking_hz": 2, "cases": []}
    for key, records in streams.items():
        content = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in records)
        path = folder / f"{key}.jsonl"
        path.write_text(content, encoding="utf-8", newline="\n")
        manifest["cases"].append({"stream": f"data/streams/{key}.jsonl", "records": len(records),
                                  "events": sum(row["record_type"] == "event" for row in records),
                                  "sha256": hashlib.sha256(content.encode()).hexdigest()})
    (root / "data" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    # These labels live outside the runtime stream and must never enter model context.
    expected = {
        "purpose": "offline assertions only; never supply to an inference tool or prompt",
        "observation_time_ms": 68000,
        "window_ms": [40000, 68000],
        "cases": {
            "stream-01": {"case": "press_regain_shot", "union_backward_passes": 2,
                "atlas_pressure_events": 3, "atlas_recoveries": 1, "atlas_shots": 1,
                "regain_to_shot_seconds": 7.0, "high_regain": True, "goals": 0,
                "allowed": ["Two backward passes precede an Atlas high regain.",
                            "A shot follows the regain by seven seconds and is saved.",
                            "The observed pressure is consistent with a pressing sequence; causality is an inference."],
                "forbidden": ["Atlas scored", "Pressure is proven to be the sole cause"]},
            "stream-02": {"case": "press_escaped", "union_backward_passes": 2,
                "atlas_pressure_events": 3, "atlas_recoveries": 0, "atlas_shots": 0,
                "regain_to_shot_seconds": None, "high_regain": False, "goals": 0,
                "allowed": ["Union retain possession after two backward passes and then advance.",
                            "There is no Atlas regain or shot in this observed window."],
                "forbidden": ["Atlas won the ball high", "Atlas created a shot from the press"]},
            "stream-03": {"case": "insufficient_spatial_evidence", "union_backward_passes": None,
                "atlas_pressure_events": None, "atlas_recoveries": 1, "atlas_shots": 1,
                "regain_to_shot_seconds": 7.0, "high_regain": None, "goals": 0,
                "allowed": ["Atlas regain possession and shoot seven seconds later.",
                            "Location and pressure evidence are unavailable for the relevant interval."],
                "forbidden": ["There was no pressure", "The regain was in the final third", "Two backward passes were forced"]},
        },
        "pre_divergence_check": {"observation_time_ms": 53000,
            "requirement": "stream-01 and stream-02 have identical visible records; do not predict the branch outcome"},
    }
    eval_folder = root / "evals"
    eval_folder.mkdir(parents=True, exist_ok=True)
    (eval_folder / "fixture_expectations.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--root", type=Path, default=ROOT)
    arguments = parser.parse_args()
    print(json.dumps(write_fixtures(arguments.root, arguments.seed), indent=2))
