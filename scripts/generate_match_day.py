"""Reproducible event/position simulation including turnovers, goals and substitutes."""
import argparse
import copy
import json
import math
import random
from pathlib import Path
try:
    from scripts.generate_match_fixtures import BASE, NUMBERS
except ModuleNotFoundError:
    from generate_match_fixtures import BASE, NUMBERS

ROOT = Path(__file__).resolve().parents[1]


class Simulator:
    def __init__(self, seed=83):
        self.rng = random.Random(seed)
        self.t = 0
        self.period = 1
        self.direction = {"A": 1, "U": -1}
        self.positions = {f"{team}{number}": {"x": float(x), "y": float(y)} for team in BASE for number, (x, y) in zip(NUMBERS, BASE[team])}
        self.owner = "U4"
        self.ball = dict(self.positions[self.owner])
        self.possession = "U"
        self.events = []
        self.frames = []
        self.subbed = False
        self.roster = [{"id": f"{team}{number}", "team_id": team, "shirt_number": number,
                        "name": f"{'Atlas' if team == 'A' else 'Union'} {number}", "starter": True}
                       for team in BASE for number in NUMBERS]
        self.roster += [{"id": "A17", "team_id": "A", "shirt_number": 17, "name": "Atlas 17", "starter": False}]
        self.frame()

    def record(self, record_type, identifier, time, **fields):
        return {"schema_version": "1.1", "record_type": record_type, "id": identifier,
                "match_id": "match-day", "event_time_ms": time, "observed_at_ms": time + 80,
                "source": "synthetic_simulator", **fields}

    def frame(self):
        self.frames.append(self.record("tracking", f"t{len(self.frames):06}", self.t, period=self.period,
            sample_interval_ms=500, status="available", possession_team_id=self.possession,
            ball={**self.ball, "owner_id": self.owner},
            players=[{"player_id": p, **xy} for p, xy in self.positions.items()]))

    def emit(self, kind, player=None, position=None, **fields):
        player = player or self.owner or "A9"
        result = self.record("event", f"e{len(self.events):05}", self.t, type=kind, period=self.period,
                            player_id=player, team_id=player[0], position=copy.deepcopy(position or self.positions[player]),
                            position_status="observed", **fields)
        self.events.append(result)
        if kind in {"kickoff", "substitution", "period_start", "tackle"}:
            # A discrete state change at a sample boundary replaces that sample;
            # the stream must not show the outgoing player after substitution.
            if self.frames and self.frames[-1]["event_time_ms"] == self.t:
                self.frames.pop()
            self.frame()
        return result

    def advance(self, seconds, targets=None, ball_target=None, receiver=None):
        steps = max(1, math.ceil(seconds * 2))
        initial = copy.deepcopy(self.positions)
        ball_start = dict(self.ball)
        previous_owner = self.owner
        if ball_target is not None:
            self.owner = None
        for step in range(1, steps + 1):
            fraction = step / steps
            for player, target in (targets or {}).items():
                self.positions[player] = {k: round(initial[player][k] + fraction * (target[k] - initial[player][k]), 3) for k in ("x", "y")}
            if ball_target is not None:
                self.ball = {k: round(ball_start[k] + fraction * (ball_target[k] - ball_start[k]), 3) for k in ("x", "y")}
                if step == steps:
                    self.owner = receiver
                    if receiver:
                        self.possession = receiver[0]
            elif previous_owner:
                self.ball = dict(self.positions[previous_owner])
            self.t += 500
            self.frame()

    def move(self, player, x, y, speed=5):
        target = {"x": max(1., min(104., x)), "y": max(1., min(67., y))}
        distance = math.dist(tuple(self.positions[player].values()), tuple(target.values()))
        self.advance(max(.5, distance / speed), {player: target})

    def carry(self, x, y, speed=5):
        player, start, origin = self.owner, self.t, dict(self.ball)
        self.move(player, x, y, speed)
        self.emit("carry", player, origin, start_time_ms=start, end_position=dict(self.ball))

    def pass_to(self, receiver, intercepted_by=None):
        actor, start, origin = self.owner, self.t, dict(self.ball)
        actual = intercepted_by or receiver
        target = dict(self.positions[actual])
        seconds = math.dist(tuple(origin.values()), tuple(target.values())) / 16
        self.advance(max(.5, seconds), ball_target=target, receiver=actual)
        e = self.emit("pass", actor, origin, start_time_ms=start, end_position=target,
                      receiver_id=receiver, outcome="incomplete" if intercepted_by else "complete")
        if intercepted_by:
            self.emit("interception", actual, previous_team_id=actor[0], pass_id=e["id"])
            self.emit("recovery", actual, previous_team_id=actor[0], mechanism="interception")
            self.emit("possession_change", actual, previous_team_id=actor[0])

    def pressure(self, defender):
        opponent = self.owner
        self.move(defender, self.ball["x"] - 2 * self.direction[defender[0]], self.ball["y"])
        self.emit("pressure", defender, opponent_id=opponent, opponent_position=dict(self.ball),
                  distance_m=round(math.dist(tuple(self.positions[defender].values()), tuple(self.ball.values())), 3))

    def tackle(self, defender):
        previous, opponent = self.possession, self.owner
        self.move(defender, self.ball["x"], self.ball["y"], 7.5)
        self.owner, self.possession = defender, defender[0]
        tackle = self.emit("tackle", defender, opponent_id=opponent, outcome="won")
        self.emit("recovery", defender, previous_team_id=previous, tackle_id=tackle["id"])
        self.emit("possession_change", defender, previous_team_id=previous)

    def shoot(self, goal=False):
        team = self.owner[0]
        quota = 14 if team == 'A' else 11
        # Spread opportunities across match time rather than exhausting every
        # shot in the opening half and leaving the remaining match uneventful.
        allowance = min(quota, 1 + int(self.t / 5400000 * quota))
        if sum(e['type']=='shot' and e['team_id']==team for e in self.events) >= allowance:
            self.pass_to(team+'6')
            return
        scored = sum(e['type']=='goal' and e['team_id']==team for e in self.events)
        goal = goal and scored < (2 if team=='A' else 1) and (scored == 0 or self.t >= 3600000)
        actor, team = self.owner, self.owner[0]
        opponent = "U" if team == "A" else "A"
        keeper = opponent + "1"
        goal_x = 105 if self.direction[team] == 1 else 0
        self.move(keeper, 99 if goal_x == 105 else 6, 34)
        shot = self.emit("shot", actor)
        target = {"x": float(goal_x), "y": 34.} if goal else dict(self.positions[keeper])
        duration = max(.5, math.dist(tuple(self.ball.values()), tuple(target.values())) / 24)
        self.advance(duration, ball_target=target, receiver=None if goal else keeper)
        self.emit("shot_end", actor, target, shot_id=shot["id"])
        if goal:
            self.emit("goal", actor, target, shot_id=shot["id"])
            self.kickoff(opponent)
        else:
            self.emit("save", keeper, target, outcome="held", shot_id=shot["id"])

    def kickoff(self, team):
        player = team + "6"
        self.owner = None
        self.move(player, 52.5, 34)
        self.owner, self.possession, self.ball = player, team, dict(self.positions[player])
        self.emit("kickoff", player)

    def press_sequence(self, escape=False):
        if self.owner[0] != "U":
            self.tackle("U5")
        if self.owner != "U5":
            self.pass_to("U5")
        forward = self.direction["U"]
        x = lambda value: value if forward == -1 else 105 - value
        self.carry(x(77), 17)
        self.move("U4", x(83), 29)
        self.pressure("A7")
        self.pass_to("U4")
        self.move("U2", x(89), 21)
        self.pressure("A9")
        self.pass_to("U2")
        self.pressure("A7")
        if escape:
            self.move("U6", x(69), 34)
            self.pass_to("U6")
            self.carry(x(49), 34, 7.5)
            self.move("U9", x(30), 31)
            self.pass_to("U9")
        else:
            self.tackle("A7")
            self.move("A9", x(91), 34)
            self.pass_to("A9")
            self.shoot(goal=False)

    def counter_sequence(self, goal=False, attacking_team=None):
        team = self.owner[0]
        if attacking_team and team == attacking_team:
            self.tackle(('U' if team=='A' else 'A')+'8')
            team = self.owner[0]
        defender = ("A" if team == "U" else "U") + "8"
        self.tackle(defender)
        team = defender[0]
        direction = self.direction[team]
        self.carry(max(8, min(97, self.ball["x"] + 10 * direction)), 30, 7.5)
        self.move(team + "10", 65 if direction == 1 else 40, 26)
        self.pass_to(team + "10")
        self.move(team + "9", 90 if direction == 1 else 15, 34)
        self.pass_to(team + "9")
        self.shoot(goal=goal)

    def substitute(self):
        if self.owner == "A11":
            self.pass_to("A6")
        position = self.positions.pop("A11")
        self.positions["A17"] = position
        self.emit("substitution", "A17", player_out_id="A11", player_in_id="A17")
        self.emit("formation_change", "A17", formation_before="4-3-3", formation_after="3-2-5")
        slots = [(8, 34), (28, 14), (28, 34), (28, 54), (49, 23), (49, 45),
                 (76, 7), (79, 20), (84, 34), (79, 48), (76, 61)]
        active = [p for p in self.positions if p.startswith("A")]
        targets = {p: {"x": x if self.direction["A"] == 1 else 105 - x, "y": y}
                   for p, (x, y) in zip(active, slots)}
        self.advance(14, targets)
        self.subbed = True

    def build(self, duration_seconds):
        end = duration_seconds * 1000
        cycle = 0
        while self.t < end:
            if self.period == 1 and self.t >= end / 2:
                self.period = 2
                self.direction = {"A": -1, "U": 1}
                # Halftime is a discontinuity, never counted as running distance.
                self.positions = {p: {"x": 105 - xy["x"], "y": 68 - xy["y"]} for p, xy in self.positions.items()}
                self.ball = dict(self.positions[self.owner]) if self.owner else {"x": 52.5, "y": 34.}
                self.emit("period_start", team_directions=self.direction)
            if not self.subbed and self.t >= end * 2 / 3:
                self.substitute()
            if cycle % 7 == 0:
                self.press_sequence(escape=cycle % 14 != 0)
            elif cycle % 7 == 1:
                self.counter_sequence(goal=cycle % 3 == 1, attacking_team="A" if cycle % 2 else "U")
            else:
                for _ in range(self.rng.randint(4, 8)):
                    candidates = [p for p in self.positions if p[0] == self.owner[0] and p != self.owner and not p.endswith("1")]
                    target = self.rng.choice(candidates)
                    interceptor = self.rng.choice([p for p in self.positions if p[0] != self.owner[0] and not p.endswith("1")]) if self.rng.random() < .18 else None
                    self.pass_to(target, interceptor)
                    if self.t >= end:
                        break
                    if self.rng.random() < .3:
                        self.carry(self.ball["x"] + self.direction[self.owner[0]] * 5, self.ball["y"])
            self.advance(2)
            cycle += 1
        self.emit("full_time")
        metadata = self.record("metadata", "meta-day", 0, pitch={"length_m": 105, "width_m": 68, "coordinates": "metres"},
            period=1, match_clock_start_ms=0, initial_score={"A": 0, "U": 0}, initial_possession_team_id="U",
            teams=[{"id": "A", "name": "Atlas", "attack_direction_x": 1}, {"id": "U", "name": "Union", "attack_direction_x": -1}],
            roster=self.roster, channels={"events": "available", "event_positions": "available", "tracking": "available", "pressure": "available"},
            scheduled_duration_ms=end, observation_scope="full_match" if duration_seconds >= 5400 else "excerpt")
        metadata["observed_at_ms"] = 0
        return [metadata] + sorted(self.events + self.frames, key=lambda r: (r["observed_at_ms"], r["record_type"] == "tracking", r["id"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=83)
    parser.add_argument("--seconds", type=int, default=5400)
    parser.add_argument("--output", type=Path, default=ROOT / "data/streams/match-day.jsonl")
    args = parser.parse_args()
    rows = Simulator(args.seed).build(args.seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    print(json.dumps({"file": str(args.output), "records": len(rows), "duration_ms": rows[-1]["event_time_ms"],
                      "events": len([r for r in rows if r["record_type"] == "event"])}))
