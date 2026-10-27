"""Generate stream-04 alone; no model calls, downloads or older-fixture writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.stream_04_scene import NUMBERS, PRESSURES, actions, ball_at, build_paths, interpolate


def point(value):
    return {"x": round(value[0], 3), "y": round(value[1], 3)}


def record(kind, identifier, time, *, observed=None, **fields):
    return {"schema_version": "1.2", "record_type": kind, "id": identifier,
            "match_id": "match-04", "event_time_ms": time,
            "observed_at_ms": time + (0 if kind == "metadata" else 80) if observed is None else observed,
            "source": "synthetic_simulator", **fields}


def player_event(identifier, time, kind, player, position, **fields):
    return record("event", identifier, time, type=kind, player_id=player,
                  team_id=player[0], period=2, position=point(position),
                  position_status="observed", **fields)


def official_event(identifier, time, kind, official, subject, **fields):
    return record("event", identifier, time, type=kind, official_id=official,
                  player_id=None, team_id=None, subject_player_id=subject,
                  subject_team_id=subject[0], period=2, position=None,
                  position_status="unavailable", **fields)


def metadata():
    return record("metadata", "meta-04", 0,
        pitch={"length_m":105,"width_m":68,"coordinates":"metres"},
        period=2, match_clock_start_ms=5400000,
        initial_score={"A":0,"U":0}, initial_possession_team_id="A",
        announced_added_time_ms=120000, scheduled_duration_ms=120000,
        observation_scope="segment",
        teams=[{"id":"A","name":"Atlas","attack_direction_x":1},
               {"id":"U","name":"Union","attack_direction_x":-1}],
        roster=[{"id":f"{team}{number}","team_id":team,"shirt_number":number,
                 "name":f"{'Atlas' if team == 'A' else 'Union'} {number}",
                 "position_role":"goalkeeper" if number == 1 else "outfield"}
                for team in ("A","U") for number in NUMBERS],
        officials=[{"id":"R1","role":"referee"},
                   {"id":"AR1","role":"assistant_referee"},
                   {"id":"VAR1","role":"video_assistant_referee"}],
        channels={"events":"available","event_positions":"available",
                  "tracking":"available","pressure":"available"})


def action_events(sequence):
    records = []
    carry_count = 0
    for item in sequence:
        if item.kind in {"hold", "loose", "shot"}:
            continue
        if item.kind == "pass":
            records.append(player_event(f"e{item.number:03}", item.end, "pass",
                item.actor, item.origin, start_time_ms=item.start,
                end_position=point(item.target), receiver_id=item.receiver,
                outcome=item.outcome, **item.extra))
        else:
            carry_count += 1
            fields = {key:value for key,value in item.extra.items() if key != "actor_end_position"}
            fields.update(start_time_ms=item.start,
                          end_position=point(item.extra.get("actor_end_position",item.target)))
            if item.outcome == "lost_control":
                fields.update(outcome="lost_control", ball_end_position=point(item.target))
            records.append(player_event(f"c{carry_count:03}", item.end, "carry",
                                        item.actor, item.origin, **fields))
    return records


def control_events():
    records = [player_event("a001",18000,"interception","U7",(73,22.5),
                           opponent_id="A8",pass_id="e006",outcome="won")]
    controls = [(18500,"U7",(73,22.5),"A","a001"),
                (45500,"A6",(70,32),"U","c016"),
                (72500,"U4",(93,32),"A","a010")]
    for index,(time,player,position,previous,cause) in enumerate(controls,1):
        identifier = f"r{index:03}"
        records.append(player_event(identifier,time,"recovery",player,position,
                                     previous_team_id=previous,evidence_ids=[cause]))
        records.append(player_event(f"q{index:03}",time,"possession_change",player,position,
                                     previous_team_id=previous,
                                     evidence_ids=[identifier],outcome="controlled"))
    records.append(player_event("a010",72000,"tackle","U4",(94,31),
                   start_time_ms=71000,opponent_id="A9",outcome="won",
                   technique="sliding",foul=False,
                   ball_contact={"first_contact_ms":72000,"contact_order":"ball_first",
                                 "position":point((94,31))}))
    records.append(official_event("d000",72000,"decision","R1","U4",
                   outcome="play_on",reason="fair_challenge",evidence_ids=["a010"]))
    return records


def scoring_and_review_events():
    return [
        player_event("s001",89500,"shot","U9",(7,38)),
        player_event("s002",90000,"shot_end","U9",(0,34),shot_id="s001",
                     outcome="ball_in_net",goal_status="pending",
                     line_crossing={"goal_line_x":0,"whole_ball":True,
                                    "between_posts":True,"below_crossbar":True}),
        official_event("o001",90500,"offside_flag","AR1","U9",
                       reason="suspected_offside",evidence_ids=["e025","s002"]),
        official_event("d001",92000,"decision","R1","U9",
                       outcome="goal_disallowed",reason="offside",provisional=True,
                       evidence_ids=["o001","s002"]),
        official_event("v001",92000,"var","VAR1","U9",stage="check_started",
                       evidence_ids=["d001","e025","s002"]),
        official_event("v002",99000,"var","VAR1","U9",stage="evidence_ready",
                       evidence_event_time_ms=83000,evidence_ids=["t166","e025"],
                       measurements={"attacker_nearest_body_x":33.6,
                                     "second_last_opponent_nearest_body_x":33.0}),
        official_event("v003",99000,"var","R1","U9",stage="on_field_review_requested",
                       evidence_ids=["v002"]),
        official_event("v004",104000,"var","R1","U9",stage="on_field_review_started",
                       evidence_ids=["v003"]),
        official_event("v005",114000,"var","R1","U9",stage="on_field_review_completed",
                       evidence_ids=["v004","v002"]),
        official_event("d002",115000,"decision","R1","U9",
                       outcome="goal_awarded",reason="offside_not_confirmed",
                       provisional=False,supersedes="d001",
                       evidence_ids=["v005","v002","s002"]),
        record("event","g001",90000,observed=115080,type="goal",player_id="U9",team_id="U",
               period=2,position=point((0,34)),position_status="observed",
               shot_id="s001",decision_id="d002",evidence_ids=["s002","d002"]),
    ]


def build_stream():
    sequence = actions()
    paths = build_paths(sequence)
    records = [metadata(), *action_events(sequence), *control_events()]
    for index,(time,player,opponent) in enumerate(PRESSURES,1):
        position = interpolate(paths[player],time)
        opposing = interpolate(paths[opponent],time)
        records.append(player_event(f"p{index:03}",time,"pressure",player,position,
                       opponent_id=opponent,opponent_position=point(opposing),
                       distance_m=round(math.dist(position,opposing),3)))
    records.extend(scoring_and_review_events())
    for index,time in enumerate(range(0,120001,500)):
        position,owner,possession,state,in_play = ball_at(sequence,paths,time)
        players = [{"player_id":player,**point(interpolate(track,time))}
                   for player,track in paths.items()]
        extra = {}
        if time == 83000:
            extra["body_parts"] = {
                player["player_id"]:{"head":point((player["x"]-.2,player["y"])),
                    "torso":point((player["x"],player["y"])),
                    "left_foot":point((player["x"]-.4,player["y"]-.1)),
                    "right_foot":point((player["x"]+.2,player["y"]+.1))}
                for player in players}
        records.append(record("tracking",f"t{index:03}",time,sample_interval_ms=500,
            status="available",possession_team_id=possession,
            ball={**point(position),"owner_id":owner},players=players,
            in_play=in_play,ball_state=state,**extra))
    records.sort(key=lambda row:(row["observed_at_ms"],row["record_type"] == "tracking"))
    return records


def write_stream(root=ROOT):
    root = Path(root)
    rows = build_stream()
    path = root/"data/streams/stream-04.jsonl"
    path.parent.mkdir(parents=True,exist_ok=True)
    payload = "".join(json.dumps(row,ensure_ascii=False,separators=(",",":"))+"\n" for row in rows)
    path.write_text(payload,encoding="utf-8",newline="\n")
    manifest = {"schema_version":"1.2","stream":"data/streams/stream-04.jsonl",
        "duration_ms":120000,"tracking_hz":2,"records":len(rows),
        "record_types":dict(Counter(row["record_type"] for row in rows)),
        "sha256":hashlib.sha256(payload.encode("utf-8")).hexdigest()}
    (root/"data/stream-04-manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    args = parser.parse_args()
    print(json.dumps(write_stream(args.root),ensure_ascii=False,indent=2))
