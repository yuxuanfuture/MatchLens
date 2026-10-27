"""Independent, standard-library acceptance for the approved stream-04 artifact.

Expected facts come from case-design/120s-counterattack-var-design.zh-CN.md,
not from the generator. Validation is read-only and makes no model/network calls.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "data" / "streams" / "stream-04.jsonl"
ALLOWED_EVENTS = {
    "pass", "shot", "shot_end", "goal", "save", "carry", "tackle", "recovery",
    "interception", "possession_change", "pressure", "substitution",
    "formation_change", "kickoff", "period_start", "full_time",
    "offside_flag", "decision", "var",
}
OFFICIAL_EVENTS = {"offside_flag", "decision", "var"}
REFERENCE_KEYS = {
    "evidence_ids", "event_ids", "related_event_ids", "source_event_ids", "record_ids",
    "evidence_id", "event_id", "related_event_id", "source_event_id", "record_id",
    "pass_id", "shot_id", "shot_end_id", "decision_id", "final_decision_id",
    "initial_decision_id", "tracking_id", "frame_id", "trigger_event_id", "supersedes",
}
# id, passer, intended receiver, start, completion, source x/y, actual end x/y.
PASS_PLAN = (
    ("e001", "A4", "A5", 1000, 3000, (33, 25), (38, 43)),
    ("e002", "A5", "A3", 4000, 6000, (40, 44), (45, 55)),
    ("e003", "A3", "A6", 7000, 9000, (48, 54), (52, 36)),
    ("e004", "A6", "A2", 10000, 12000, (55, 34), (60, 13)),
    ("e005", "A2", "A8", 13000, 15000, (62, 15), (67, 28)),
    ("e006", "A8", "A7", 16500, 18000, (69, 27), (73, 22.5)),
    ("e007", "U7", "U9", 19500, 21000, (71, 24), (61, 30)),
    ("e008", "U9", "U8", 21500, 24000, (60, 31), (57, 44)),
    ("e009", "U8", "U3", 25000, 27000, (58, 46), (69, 55)),
    ("e010", "U3", "U5", 28000, 30000, (71, 54), (78, 44)),
    ("e011", "U5", "U4", 31000, 33000, (79, 42), (80, 27)),
    ("e012", "U4", "U6", 34000, 36000, (78, 28), (68, 33)),
    ("e013", "U6", "U10", 37000, 39000, (66, 32), (61, 23)),
    ("e014", "U10", "U2", 40000, 42000, (62, 21), (72, 12)),
    ("e015", "U2", "U6", 42500, 44500, (72, 14), (68, 31)),
    ("e016", "A6", "A10", 46500, 48000, (74, 32), (80, 28)),
    ("e017", "A10", "A9", 49000, 51000, (82, 28), (85, 32)),
    ("e018", "A9", "A8", 52000, 54000, None, (83, 43)),
    ("e019", "A8", "A7", 56000, 57000, (87, 44), (90, 46)),
    ("e020", "A7", "A10", 60000, 62000, (92, 44), (90, 34)),
    ("e021", "A10", "A7", 64000, 66000, (92, 32), (94, 42)),
    ("e022", "A7", "A9", 66000, 68000, (94, 42), (93, 31)),
    ("e023", "U4", "U6", 74000, 75500, (90, 32), (72, 38)),
    ("e024", "U6", "U10", 78000, 80000, (63, 36), (48, 29)),
    ("e025", "U10", "U9", 83000, 85500, (40, 31), (25, 34)),
)


def _check(errors, condition, message):
    if not condition:
        errors.append(message)


def _position(value):
    return (isinstance(value, dict)
            and all(type(value.get(key)) in (int, float) and math.isfinite(value[key]) for key in ("x", "y")))


def _distance(left, right):
    if not _position(left) or not _position(right):
        return math.inf
    return math.hypot(left["x"] - right["x"], left["y"] - right["y"])


def _near(value, expected, tolerance=.03):
    return _position(value) and math.dist((value["x"], value["y"]), expected) <= tolerance


def _references(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in REFERENCE_KEYS:
                if isinstance(child, str):
                    yield child
                elif isinstance(child, list):
                    for item in child:
                        if isinstance(item, str):
                            yield item
            if isinstance(child, (dict, list)):
                yield from _references(child)
    elif isinstance(value, list):
        for item in value:
            yield from _references(item)


def _coordinates(value, path="record"):
    if isinstance(value, dict):
        if "x" in value or "y" in value:
            yield path, value
        for key, child in value.items():
            yield from _coordinates(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _coordinates(child, f"{path}[{index}]")


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def _metadata_and_envelope(rows, errors):
    if not rows or not isinstance(rows[0], dict) or rows[0].get("record_type") != "metadata":
        errors.append("metadata: stream must begin with the single metadata record")
        return None, {}, {}, {}
    metadata = rows[0]
    roster_list = metadata.get("roster", [])
    roster = {p.get("id"): p for p in roster_list if isinstance(p, dict)}
    expected_players = {f"{team}{number}" for team in ("A", "U") for number in range(1, 12)}
    _check(errors, len(roster_list) == 22 and set(roster) == expected_players, "roster: exactly A1..A11 and U1..U11 are required")
    for identifier, player in roster.items():
        _check(errors, player.get("team_id") == identifier[:1], f"roster/{identifier}: team mismatch")
    _check(errors, {p for p, entry in roster.items() if entry.get("position_role") == "goalkeeper"} == {"A1", "U1"}, "roster: A1 and U1 must be the two declared goalkeepers")
    _check(errors, metadata.get("initial_score") == {"A": 0, "U": 0}, "metadata: initial score must be 0-0")
    _check(errors, metadata.get("period") == 2 and metadata.get("match_clock_start_ms") == 5400000, "metadata: period 2 must begin this excerpt at 90:00")
    _check(errors, metadata.get("announced_added_time_ms") == 120000, "metadata: announced minimum added time must be 120000 ms")
    _check(errors, metadata.get("initial_possession_team_id") == "A", "metadata: A must initially control the ball")
    _check(errors, metadata.get("pitch", {}).get("length_m") == 105 and metadata.get("pitch", {}).get("width_m") == 68, "metadata: pitch must be 105 by 68 metres")
    teams = {t.get("id"): t for t in metadata.get("teams", [])}
    _check(errors, set(teams) == {"A", "U"} and teams.get("A", {}).get("attack_direction_x") == 1 and teams.get("U", {}).get("attack_direction_x") == -1, "metadata: A/U attack directions must be +1/-1")
    _check(errors, all(metadata.get("channels", {}).get(c) == "available" for c in ("events", "event_positions", "tracking", "pressure")), "metadata: all four observation channels must be available")
    officials = {p.get("id"): p.get("role") for p in metadata.get("officials", []) if isinstance(p, dict)}
    _check(errors, bool(officials), "metadata: named officials are required")
    index = {}
    events = {}
    frames = {}
    last_arrival = -1
    meta_count = 0
    for ordinal, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"record {ordinal + 1}: expected an object")
            continue
        identifier = row.get("id")
        _check(errors, isinstance(identifier, str) and bool(identifier), f"record {ordinal + 1}: missing string id")
        _check(errors, identifier not in index, f"{identifier}: duplicate record id")
        index[identifier] = (ordinal, row)
        kind = row.get("record_type")
        _check(errors, kind in {"metadata", "event", "tracking"}, f"{identifier}: unsupported record type or unexpected coverage gap")
        _check(errors, row.get("schema_version") == "1.2", f"{identifier}: schema_version must be 1.2")
        _check(errors, row.get("match_id") == "match-04", f"{identifier}: match_id must be match-04")
        _check(errors, row.get("source") == "synthetic_simulator", f"{identifier}: source must explicitly identify synthetic data")
        occurred, arrived = row.get("event_time_ms"), row.get("observed_at_ms")
        if not all(type(t) is int for t in (occurred, arrived)):
            errors.append(f"{identifier}: event and arrival times must be integer milliseconds")
            continue
        _check(errors, 0 <= occurred <= 120000 and occurred <= arrived <= 120080, f"{identifier}: time outside the excerpt or received before occurrence")
        _check(errors, arrived >= last_arrival, f"{identifier}: records are not sorted by arrival time")
        last_arrival = arrived
        expected_arrival = 0 if kind == "metadata" else 115080 if row.get("type") == "goal" else occurred + 80
        _check(errors, arrived == expected_arrival, f"{identifier}: incorrect arrival delay")
        for path, position in _coordinates(row, str(identifier)):
            _check(errors, _position(position) and 0 <= position.get("x", -1) <= 105 and 0 <= position.get("y", -1) <= 68, f"{path}: invalid/out-of-pitch coordinate")
        if arrived < 115080:
            leaked = set(_keys(row)) & {"is_onside", "is_offside", "final_verdict", "ground_truth", "expected", "final_score"}
            _check(errors, not leaked, f"{identifier}: early answer-bearing fields {sorted(leaked)}")
        if kind == "metadata":
            meta_count += 1
            _check(errors, occurred == 0 and arrived == 0, "metadata: must arrive at time zero")
        elif kind == "tracking":
            _check(errors, occurred not in frames, f"{identifier}: duplicate tracking timestamp")
            frames[occurred] = row
        elif kind == "event":
            events[identifier] = row
            typ = row.get("type")
            _check(errors, typ in ALLOWED_EVENTS, f"{identifier}: unsupported event type {typ}")
            _check(errors, row.get("period") == 2, f"{identifier}: event period must be 2")
            if typ in OFFICIAL_EVENTS:
                _check(errors, row.get("player_id") is None and row.get("team_id") is None, f"{identifier}: officials must not impersonate a player/team")
                _check(errors, row.get("official_id") in officials, f"{identifier}: unknown official_id")
                if typ == "offside_flag":
                    required_role = "assistant_referee"
                elif typ == "var" and row.get("stage") in {"check_started", "evidence_ready"}:
                    required_role = "video_assistant_referee"
                else:
                    required_role = "referee"
                _check(errors, officials.get(row.get("official_id")) == required_role, f"{identifier}: incorrect official role for this event/stage")
                subject = row.get("subject_player_id")
                _check(errors, subject in roster, f"{identifier}: official event needs its subject player")
                _check(errors, subject in roster and row.get("subject_team_id") == roster.get(subject, {}).get("team_id"), f"{identifier}: official subject/team mismatch")
                _check(errors, row.get("position") is None and row.get("position_status") == "unavailable", f"{identifier}: official position must be null/unavailable")
            else:
                player = row.get("player_id")
                _check(errors, player in roster and row.get("team_id") == roster.get(player, {}).get("team_id"), f"{identifier}: actor/team mismatch")
                _check(errors, row.get("position_status") == "observed" and _position(row.get("position")), f"{identifier}: ordinary event needs an observed position")
    _check(errors, meta_count == 1, "metadata: exactly one record is required")
    for identifier, (ordinal, row) in index.items():
        for reference in _references(row):
            target = index.get(reference)
            _check(errors, target is not None, f"{identifier}: missing referenced record {reference}")
            if target:
                _check(errors, (target[1].get("observed_at_ms", math.inf), target[0]) <= (row.get("observed_at_ms", -1), ordinal), f"{identifier}: reference {reference} reveals a record not yet received")
    return metadata, roster, events, frames


def _pass_checks(events, frames, errors):
    passes = {key: row for key, row in events.items() if row.get("type") == "pass"}
    _check(errors, set(passes) == {p[0] for p in PASS_PLAN}, "passes: require exactly the 25 planned e001..e025 records")
    successful = Counter()
    for identifier, passer, receiver, start, end, origin, destination in PASS_PLAN:
        row = passes.get(identifier)
        if not row:
            continue
        _check(errors, row.get("player_id") == passer and row.get("receiver_id") == receiver, f"{identifier}: incorrect planned passer/receiver")
        _check(errors, row.get("start_time_ms") == start and row.get("event_time_ms") == end, f"{identifier}: incorrect planned pass times")
        _check(errors, row.get("outcome") == ("incomplete" if identifier == "e006" else "complete"), f"{identifier}: incorrect completion outcome")
        _check(errors, _distance(row.get("position"), row.get("end_position")) / ((end - start) / 1000) <= 40, f"{identifier}: implausible pass speed")
        if origin is not None:
            _check(errors, _near(row.get("position"), origin), f"{identifier}: incorrect release position")
        _check(errors, _near(row.get("end_position"), destination), f"{identifier}: incorrect actual end position")
        start_frame, end_frame = frames.get(start), frames.get(end)
        if start_frame and end_frame:
            start_players = {p.get("player_id"): p for p in start_frame.get("players", [])}
            end_players = {p.get("player_id"): p for p in end_frame.get("players", [])}
            _check(errors, _distance(start_frame.get("ball"), row.get("position")) <= .03 and _distance(start_players.get(passer), row.get("position")) <= .03, f"{identifier}: release does not join the ball/passer track")
            _check(errors, _distance(end_frame.get("ball"), row.get("end_position")) <= .03, f"{identifier}: ball does not reach the actual pass endpoint")
            if identifier != "e006":
                _check(errors, _distance(end_players.get(receiver), row.get("end_position")) <= .03, f"{identifier}: completed pass misses its receiver")
            else:
                _check(errors, end_frame.get("ball", {}).get("owner_id") != "A7" and _distance(end_players.get("A7"), row.get("end_position")) > .1, "e006: incomplete pass must not be delivered to A7")
        for time, frame in frames.items():
            if start <= time < end:
                _check(errors, frame.get("ball", {}).get("owner_id") is None, f"{identifier}/{time}: ball in flight has a player owner")
        if row.get("outcome") == "complete":
            successful[passer] += 1
    expected_passers = {f"{team}{number}" for team in ("A", "U") for number in range(2, 11)}
    _check(errors, set(successful) == expected_passers, "passes: all 18 planned non-goalkeepers must actually complete a pass")
    _check(errors, sum(successful.values()) == 24, "passes: exactly 24 successful passes are required")


def _tracking_checks(frames, roster, errors):
    _check(errors, set(frames) == set(range(0, 120001, 500)), "tracking: exactly 241 frames at 500 ms intervals are required")
    prior = None
    for time, frame in sorted(frames.items()):
        identifier = frame.get("id")
        players_list = frame.get("players", [])
        players = {p.get("player_id"): p for p in players_list if isinstance(p, dict)}
        _check(errors, len(players_list) == 22 and set(players) == set(roster), f"{identifier}: every frame must contain 22 unique roster players")
        _check(errors, frame.get("status") == "available" and frame.get("sample_interval_ms") == 500, f"{identifier}: tracking availability/cadence mismatch")
        _check(errors, type(frame.get("in_play")) is bool and frame.get("in_play") == (time < 90000), f"{identifier}: incorrect live/dead-ball status")
        ball = frame.get("ball")
        _check(errors, _position(ball), f"{identifier}: ball position is missing")
        if not isinstance(ball, dict):
            continue
        owner = ball.get("owner_id")
        if owner is not None:
            _check(errors, owner in players and _distance(ball, players.get(owner)) <= .03, f"{identifier}: owned ball is detached from its owner")
        if time < 18000 or 45500 <= time < 72000:
            expected_team = "A"
        elif 18500 <= time < 45000 or 72500 <= time < 89500:
            expected_team = "U"
        else:
            expected_team = None
        _check(errors, frame.get("possession_team_id") == expected_team, f"{identifier}: incorrect possession phase")
        state = frame.get("ball_state")
        if time in {18000, 45000, 72000}:
            _check(errors, owner is None and state == "loose", f"{identifier}: turnover must include the half-second loose-ball interval")
        elif 89500 <= time < 90000:
            _check(errors, owner is None and state == "shot_flight", f"{identifier}: shot flight must have no owner")
        elif time >= 90000:
            _check(errors, state == "dead" and frame.get("possession_team_id") is None, f"{identifier}: VAR/celebration time must not be live football possession")
        else:
            _check(errors, state in {"in_play", "pass_flight"}, f"{identifier}: unknown live ball_state {state}")
        if prior:
            elapsed = (time - prior[0]) / 1000
            for player, position in players.items():
                previous = prior[1].get(player)
                speed = _distance(position, previous) / elapsed if elapsed > 0 else math.inf
                _check(errors, speed <= 11.0001, f"{identifier}/{player}: player speed {speed:.3f} exceeds 11 m/s")
        prior = time, players
    for time, owner in ((0, "A4"), (18500, "U7"), (45500, "A6"), (72500, "U4")):
        if time in frames:
            _check(errors, frames[time].get("ball", {}).get("owner_id") == owner, f"tracking/{time}: expected confirmed owner {owner}")
    for time, expected in ((57000, (90, 46)), (87500, (13, 34)), (88500, (9.5, 39)), (89500, (7, 38))):
        if time in frames:
            player = "A7" if time == 57000 else "U9"
            positions = {p.get("player_id"): p for p in frames[time].get("players", [])}
            _check(errors, _near(positions.get(player), expected), f"tracking/{time}: {player} misses the planned attacking location")
    if 83000 in frames:
        start = {p.get("player_id"): p for p in frames[83000].get("players", [])}
        for time in (85500, 87500, 89500):
            if time not in frames:
                continue
            positions = {p.get("player_id"): p for p in frames[time].get("players", [])}
            for defender in ("A4", "A5"):
                _check(errors, positions.get(defender, {}).get("x", -1) > positions.get("U9", {}).get("x", math.inf), f"tracking/{time}: {defender} is ahead of the supposed breakaway attacker")
                if time == 89500:
                    _check(errors, _distance(start.get(defender), positions.get(defender)) > 5, f"tracking/{time}: {defender} is frozen rather than chasing")


def _body_part_coordinates(parts):
    result = []
    if isinstance(parts, dict):
        for name, value in parts.items():
            lower = name.lower()
            if any(token in lower for token in ("hand", "arm")):
                continue
            if any(token in lower for token in ("head", "torso", "foot", "feet", "shoulder", "knee")):
                if _position(value):
                    result.append(value)
                elif isinstance(value, list):
                    result.extend(p for p in value if _position(p))
    elif isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict):
                name = str(part.get("part", part.get("name", "")))
                result.extend(_body_part_coordinates({name: part.get("position", part)}))
    return result


def _offside_checks(frames, errors):
    frame = frames.get(83000)
    if not frame:
        return
    parts = frame.get("body_parts", {})
    if isinstance(parts, list):
        parts = {p.get("player_id"): p.get("parts", p.get("body_parts", p)) for p in parts if isinstance(p, dict)}
    _check(errors, isinstance(parts, dict), "offside: 83-second tracking needs player body_parts")
    if not isinstance(parts, dict):
        return
    relevant = [f"A{number}" for number in range(1, 12)] + ["U9"]
    nearest = {}
    centres = {p.get("player_id"): p for p in frame.get("players", [])}
    for player in relevant:
        player_parts = parts.get(player, {})
        names = list(player_parts) if isinstance(player_parts, dict) else [str(p.get("part", p.get("name", ""))) for p in player_parts if isinstance(p, dict)] if isinstance(player_parts, list) else []
        _check(errors, any("head" in name.lower() for name in names) and any("torso" in name.lower() for name in names) and any("foot" in name.lower() or "feet" in name.lower() for name in names), f"offside: {player} needs head, torso and foot measurements")
        points = _body_part_coordinates(player_parts)
        _check(errors, bool(points), f"offside: missing eligible body parts for {player}")
        _check(errors, all(_distance(point, centres.get(player)) <= 1.5 for point in points), f"offside: {player} body parts are detached from its sampled position")
        if points:
            nearest[player] = min(p["x"] for p in points)
    if len(nearest) != len(relevant):
        return
    ordered = sorted((nearest[p], p) for p in nearest if p.startswith("A"))
    _check(errors, ordered[0][1] == "A1" and abs(ordered[0][0] - 6) <= .01, "offside: goalkeeper evidence must be at x=6.0")
    _check(errors, ordered[1][1] == "A4" and abs(ordered[1][0] - 33) <= .01, "offside: independently sorted second-last defender must be A4 at x=33.0")
    _check(errors, abs(nearest["A5"] - 36) <= .01 and all(nearest[p] > 36 for p in nearest if p.startswith("A") and p not in {"A1", "A4", "A5"}), "offside: remaining defender body-part evidence is inconsistent")
    _check(errors, abs(nearest["U9"] - 33.6) <= .01 and abs(nearest["U9"] - ordered[1][0] - .6) <= .01, "offside: U9 must be 0.6 m behind the second-last defender at release")
    _check(errors, nearest["U9"] < frame.get("ball", {}).get("x", -1), "offside: ball/attacker geometry is inconsistent")


def _story_checks(events, frames, errors):
    event_list = list(events.values())
    by_type = lambda kind: [r for r in event_list if r.get("type") == kind]
    _check(errors, not any(r.get("type") in {"full_time", "kickoff", "substitution", "save"} for r in event_list), "story: excerpt must not contain full time, restart, substitution or a successful save")
    interceptions = by_type("interception")
    _check(errors, len(interceptions) == 1 and interceptions[0].get("player_id") == "U7" and interceptions[0].get("event_time_ms") == 18000, "turnover: U7 must intercept at 18 seconds")
    recoveries = by_type("recovery")
    possession_changes = by_type("possession_change")
    _check(errors, len(recoveries) == 3 and len(possession_changes) == 3, "turnover: require exactly three recoveries and three linked possession changes")
    for time, player, previous_team in ((18500, "U7", "A"), (45500, "A6", "U"), (72500, "U4", "A")):
        found = [r for r in by_type("recovery") if r.get("event_time_ms") == time and r.get("player_id") == player]
        _check(errors, len(found) == 1, f"turnover: require one recovery by {player} at {time}")
        changes = [r for r in possession_changes if r.get("event_time_ms") == time and r.get("player_id") == player]
        _check(errors, len(changes) == 1 and changes[0].get("previous_team_id") == previous_team, f"turnover: missing explicit possession change to {player} at {time}")
        if found and changes:
            _check(errors, found[0]["id"] in set(_references(changes[0])), f"turnover: {changes[0]['id']} must reference its recovery")
    tackles = by_type("tackle")
    _check(errors, len(tackles) == 1 and tackles[0].get("player_id") == "U4" and tackles[0].get("opponent_id") == "A9" and tackles[0].get("event_time_ms") == 72000 and _near(tackles[0].get("position"), (94, 31)), "tackle: U4 must tackle A9 in the box at 72 seconds")
    if tackles:
        tackle = tackles[0]
        text = json.dumps(tackle, ensure_ascii=False).lower()
        _check(errors, any(word in text for word in ("sliding", "slide")), "tackle: sliding technique must be explicit")
        _check(errors, tackle.get("outcome") in {"won", "successful", "complete"}, "tackle: successful outcome must be explicit")
        _check(errors, tackle.get("foul") is False, "tackle: no-foul fact must be explicit")
        contact = tackle.get("ball_contact", {})
        _check(errors, isinstance(contact, dict) and contact.get("first_contact_ms") == 72000 and contact.get("contact_order") == "ball_first" and _near(contact.get("position"), (94, 31)), "tackle: explicit first ball-contact evidence is required")
        frame = frames.get(72000, {})
        players = {p.get("player_id"): p for p in frame.get("players", [])}
        _check(errors, _distance(frame.get("ball"), tackle.get("position")) <= .03 and _distance(players.get("U4"), tackle.get("position")) <= .03, "tackle: contact must join the ball and tackler track")
        referee = [r for r in by_type("decision") if r.get("event_time_ms") == 72000 and r.get("outcome") == "play_on" and r.get("reason") == "fair_challenge" and tackle["id"] in set(_references(r))]
        _check(errors, len(referee) == 1, "tackle: require the referee's linked fair-challenge/play-on decision")
        recovery = next((r for r in recoveries if r.get("event_time_ms") == 72500), None)
        _check(errors, recovery is not None and _near(recovery.get("position"), (93, 32)) and tackle["id"] in set(_references(recovery)), "tackle: subsequent U4 recovery must preserve the loose-ball endpoint and link")
    for row in by_type("pressure"):
        frame = frames.get(row.get("event_time_ms"))
        if not frame:
            errors.append(f"{row.get('id')}: pressure requires a corresponding tracking sample")
            continue
        players = {p.get("player_id"): p for p in frame.get("players", [])}
        distance = _distance(players.get(row.get("player_id")), players.get(row.get("opponent_id")))
        _check(errors, distance <= 3 and _distance(row.get("position"), players.get(row.get("player_id"))) <= .03 and _distance(row.get("opponent_position"), players.get(row.get("opponent_id"))) <= .03 and abs(row.get("distance_m", math.inf) - distance) <= .02, f"{row.get('id')}: pressure must be supported by <=3 m tracking geometry")
    shots = by_type("shot")
    _check(errors, len(shots) == 1 and shots[0].get("player_id") == "U9" and shots[0].get("event_time_ms") == 89500, "shot: only U9 shoots, at 89.5 seconds")
    if shots:
        _check(errors, not ({"outcome", "end_position", "goal_status", "final_decision_id"} & set(shots[0])), "shot: release must not contain its future result")
    take_ons = [r for r in by_type("carry") if r.get("player_id") == "U9" and r.get("action") == "take_on" and r.get("opponent_id") == "A1"]
    _check(errors, len(take_ons) == 1 and take_ons[0].get("start_time_ms") == 87500 and take_ons[0].get("event_time_ms") == 88500 and take_ons[0].get("outcome") == "complete", "breakaway: U9 must explicitly beat A1 while retaining control")
    endings = by_type("shot_end")
    _check(errors, len(endings) == 1 and endings[0].get("event_time_ms") == 90000 and endings[0].get("outcome") == "ball_in_net", "shot_end: at 90 seconds only the ball-in-net observation is known")
    flags = by_type("offside_flag")
    _check(errors, len(flags) == 1 and flags[0].get("event_time_ms") == 90500 and flags[0].get("subject_player_id") == "U9", "offside_flag: delayed flag must concern U9 at 90.5 seconds")
    decisions = by_type("decision")
    initial = [r for r in decisions if r.get("event_time_ms") == 92000 and r.get("outcome") == "goal_disallowed"]
    final = [r for r in decisions if r.get("event_time_ms") == 115000 and r.get("outcome") == "goal_awarded"]
    _check(errors, len(initial) == 1 and initial[0].get("reason") == "offside", "decision: initial 92-second ruling must disallow the goal for offside")
    _check(errors, len(final) == 1, "decision: final goal-awarded ruling must occur at 115 seconds")
    if initial and final:
        _check(errors, final[0].get("supersedes") == initial[0].get("id"), "decision: final ruling must explicitly supersede the initial ruling")
    stages = {(r.get("event_time_ms"), r.get("stage")) for r in by_type("var")}
    expected_stages = {(92000, "check_started"), (99000, "evidence_ready"), (99000, "on_field_review_requested"), (104000, "on_field_review_started"), (114000, "on_field_review_completed")}
    _check(errors, stages == expected_stages, "VAR: require the five approved stages and timestamps")
    evidence = next((r for r in by_type("var") if r.get("stage") == "evidence_ready"), None)
    if evidence:
        references = set(_references(evidence))
        frame_id = frames.get(83000, {}).get("id")
        _check(errors, evidence.get("evidence_event_time_ms") == 83000 and {"e025", frame_id} <= references, "VAR: review evidence must reference the 83-second release and its body-part snapshot")
        values = evidence.get("measurements", {})
        _check(errors, values.get("attacker_nearest_body_x") == 33.6 and values.get("second_last_opponent_nearest_body_x") == 33.0, "VAR: reported measurements must match the independently checked body-part snapshot")
    goals = by_type("goal")
    _check(errors, len(goals) == 1 and goals[0].get("event_time_ms") == 90000 and goals[0].get("observed_at_ms") == 115080 and goals[0].get("player_id") == "U9", "goal: one 90-second goal may become known only at 115.08 seconds")
    if goals and final and shots:
        references = set(_references(goals[0]))
        _check(errors, {final[0]["id"], shots[0]["id"]} <= references, "goal: confirmation must reference the shot and final decision")
    for cutoff, expected in ((90080, 0), (92080, 0), (115079, 0), (115080, 1), (120080, 1)):
        visible = [r for r in goals if r.get("event_time_ms", math.inf) <= cutoff and r.get("observed_at_ms", math.inf) <= cutoff]
        _check(errors, len(visible) == expected, f"score/{cutoff}: confirmed goal count must be {expected}")


def validate_records(rows):
    """Return all observable contract failures; never alter the supplied records."""
    errors = []
    try:
        metadata, roster, events, frames = _metadata_and_envelope(rows, errors)
        if metadata is None:
            return errors
        _pass_checks(events, frames, errors)
        _tracking_checks(frames, roster, errors)
        _offside_checks(frames, errors)
        _story_checks(events, frames, errors)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, AttributeError) as error:
        errors.append(f"Malformed stream: {type(error).__name__}: {error}")
    return errors


def load_records(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_file(path=DEFAULT_PATH):
    try:
        return validate_records(load_records(path))
    except (OSError, ValueError) as error:
        return [f"Cannot read stream: {error}"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_PATH)
    args = parser.parse_args()
    errors = validate_file(args.path)
    print(f"{args.path.name}: {'FAIL' if errors else 'PASS'}")
    for error in errors:
        print(f"  {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
