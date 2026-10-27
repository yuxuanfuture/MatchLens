"""Deterministic football metrics with explicit units, coverage and evidence."""
import math
from backend.review_state import OFFICIAL_TYPES


def distance(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


class FootballAnalytics:
    def __init__(self, tools):
        self.tools = tools

    def frames(self, start, end):
        self.tools._window(start, end)
        return sorted((r for r in self.tools._records if r["record_type"] == "tracking" and start <= r["event_time_ms"] <= end),key=lambda r:r['event_time_ms'])

    def player_metrics(self, player_id, start_ms, end_ms):
        if player_id not in self.tools._roster:
            raise ValueError("Unknown player")
        travelled, peak, last, evidence = 0., 0., None, []
        for frame in self.frames(start_ms, end_ms):
            position = next((p for p in frame.get("players") or [] if p["player_id"] == player_id), None)
            if position is None:
                last = None
                continue
            if last and frame.get("period", 2) == last[0].get("period", 2):
                dt = (frame["event_time_ms"] - last[0]["event_time_ms"]) / 1000
                if 0 < dt <= 1:
                    d = distance(position, last[1])
                    travelled += d
                    peak = max(peak, d / dt)
                    evidence.extend([last[0]["id"], frame["id"]])
            last = frame, position
        coverage = self.tools._coverage("tracking", start_ms, end_ms)
        events = [e for e in self.tools.query_events(start_ms, end_ms)["events"]
                  if e.get("player_id") == player_id]
        passes = [e for e in events if e["type"] == "pass"]
        complete = sum(e.get("outcome") == "complete" for e in passes)
        return {"player": self.tools._roster[player_id], "window_ms": [start_ms, end_ms],
                "distance_m": round(travelled, 2) if coverage["complete"] and evidence else None,
                "observed_distance_m": round(travelled, 2),
                "peak_sampled_speed_mps": round(peak, 2) if evidence else None,
                "speed_threshold_mps": 7, "sprint_threshold_reached": peak >= 7,
                "passes": len(passes), "completed_passes": complete,
                "pass_accuracy_pct": round(100 * complete / len(passes), 1) if passes else None,
                "shots": sum(e["type"] == "shot" for e in events),
                "goals": sum(e["type"] == "goal" for e in events),
                "tackles": sum(e["type"] == "tackle" for e in events),
                "evidence_ids": [e["id"] for e in events], "tracking_evidence_ids": list(dict.fromkeys(evidence))[-24:],
                "coverage": coverage, "method": "Sum of observed sample-to-sample distances; peak sampled speed, not instantaneous peak"}

    def pass_quality(self, event_id):
        event = self.tools.get_evidence([event_id])["records"][0]
        if event.get("type") != "pass":
            raise ValueError("Pass event required")
        start = event.get("start_time_ms", event["event_time_ms"])
        frames = [f for f in self.frames(max(0, start - 1000), start) if f.get("players")]
        length = distance(event["position"], event["end_position"]) if event.get("position") and event.get("end_position") else None
        opponents, lane, near = [], None, None
        if frames and length is not None:
            opponents = [p for p in frames[-1]["players"] if self.tools._roster.get(p["player_id"], {}).get("team_id") != event["team_id"]]
            a, b = event["position"], event["end_position"]
            near = min((distance(a, p) for p in opponents), default=None)
            lane = 0
            for p in opponents:
                t = ((p["x"] - a["x"]) * (b["x"] - a["x"]) + (p["y"] - a["y"]) * (b["y"] - a["y"])) / max(length ** 2, .001)
                if .05 < t < .95 and distance(p, {"x": a["x"] + t * (b["x"] - a["x"]), "y": a["y"] + t * (b["y"] - a["y"])}) < 3:
                    lane += 1
        rating = None if length is None or near is None else min(5, 1 + int(length >= 15) + int(length >= 30) + int(near < 3) + min(lane, 1))
        return {"event_id": event_id, "distance_m": round(length, 2) if length is not None else None,
                "outcome": event.get("outcome", "unknown"), "difficulty_1_to_5": rating,
                "difficulty_label": "heuristic, not learned or calibrated probability", "lane_defenders": lane,
                "nearest_defender_m": round(near, 2) if near is not None else None,
                "method": "1 + distance>=15m + distance>=30m + defender<3m + any defender within 3m of lane, capped at 5",
                "evidence_ids": [event_id] + ([frames[-1]["id"]] if frames else [])}

    def speeds(self, start_ms, end_ms):
        frames = self.frames(start_ms, end_ms)
        restarts = [e["event_time_ms"] for e in self.tools.query_events(start_ms, end_ms, event_types=["kickoff", "period_start"])["events"]]
        samples = []
        for a, b in zip(frames, frames[1:]):
            dt = (b["event_time_ms"] - a["event_time_ms"]) / 1000
            if any(a["event_time_ms"] <= t <= b["event_time_ms"] for t in restarts):
                continue
            if a.get("ball") and b.get("ball") and 0 < dt <= 1 and a.get("period", 2) == b.get("period", 2):
                samples.append({"time_ms": b["event_time_ms"], "speed_mps": round(distance(a["ball"], b["ball"]) / dt, 2),
                                "evidence_ids": [a["id"], b["id"]]})
        shots = []
        visible = {r["id"]: r for r in self.tools._records}
        for event in self.tools.query_events(start_ms, end_ms, event_types=["shot_end", "save", "goal"])["events"]:
            shot = visible.get(event.get("shot_id"))
            if not shot or any(s["shot_id"] == shot["id"] for s in shots) or not shot.get("position") or not event.get("position"):
                continue
            dt = (event["event_time_ms"] - shot["event_time_ms"]) / 1000
            if dt > 0:
                shots.append({"shot_id": shot["id"], "speed_mps": round(distance(shot["position"], event["position"]) / dt, 2),
                              "evidence_ids": [shot["id"], event["id"]], "method": "Observed completed flight average, not launch or peak speed"})
        current = bool(samples and end_ms-samples[-1]["time_ms"] <= 1000 and self.tools._coverage("tracking", end_ms, end_ms)["complete"])
        return {"window_ms": [start_ms, end_ms], "ball_speed_mps": samples[-1]["speed_mps"] if current else None,
                "peak_sampled_ball_speed_mps": max((s["speed_mps"] for s in samples), default=None),
                "ball_evidence_ids": samples[-1]["evidence_ids"] if current else [], "shot_speeds": shots,
                "ball_sample_time_ms": samples[-1]["time_ms"] if current else None,
                "coverage": self.tools._coverage("tracking", start_ms, end_ms),
                "method": "2D average sampled motion; unavailable across gaps; no inference of unobserved shot outcome"}

    def intelligence(self, start_ms, end_ms, team_id="A"):
        self.tools._team(team_id)
        events = self.tools.query_events(start_ms, end_ms)["events"]
        duration = max((end_ms - start_ms) / 1000, .001)
        teams = {}
        for team in self.tools._directions:
            group = [e for e in events if e["team_id"] == team]
            passes = [e for e in group if e["type"] == "pass"]
            teams[team] = {"passes": len(passes), "completed_passes": sum(e.get("outcome") == "complete" for e in passes),
                "pass_accuracy_pct": round(100 * sum(e.get("outcome") == "complete" for e in passes) / len(passes), 1) if passes else None,
                "shots": sum(e["type"] == "shot" for e in group), "tackles": sum(e["type"] == "tackle" for e in group),
                "recoveries": sum(e["type"] == "recovery" for e in group), "goals": sum(e["type"] == "goal" for e in group),
                "pressure": self.tools.calculate_metric("pressure_event_count", team, start_ms, end_ms)["value"],
                "passes_per_minute": round(len(passes) * 60 / duration, 2)}
        changes = [e for e in events if e["type"] == "recovery"]
        previous_start = max(0, start_ms - (end_ms - start_ms))
        previous_end = max(previous_start, start_ms - 1)
        pressure_before = self.tools.calculate_metric("pressure_event_count", team_id, previous_start, previous_end)
        pressure_now = self.tools.calculate_metric("pressure_event_count", team_id, start_ms, end_ms)
        complete = self.tools._coverage("events", start_ms, end_ms)["complete"]
        turnover_rate=len(changes)*60/duration
        rhythm = "unknown" if not complete else "frequent_turnovers" if len(changes)>=3 and turnover_rate>=6 else "sustained_sequence" if max(t["completed_passes"] for t in teams.values()) >= 4 and not changes else "mixed"
        observed_frames = [f for f in self.frames(start_ms, end_ms) if f.get("possession_team_id")]
        possession = {t: round(100 * sum(f["possession_team_id"] == t for f in observed_frames) / len(observed_frames), 1) if observed_frames else None for t in teams}
        elapsed={t:0 for t in teams}
        frames=self.frames(start_ms,end_ms)
        for left,right in zip(frames,frames[1:]):
            dt=right['event_time_ms']-left['event_time_ms'];owner=left.get('possession_team_id')
            if owner in elapsed and 0<dt<=1000 and left.get('period')==right.get('period') and self.tools._coverage('tracking',left['event_time_ms'],right['event_time_ms'])['complete']:
                elapsed[owner]+=dt
        observed=sum(elapsed.values())
        chain={t:0 for t in teams};longest={t:0 for t in teams}
        for e in events:
            if e['type'] in {'pressure','formation_change','substitution','period_start'} | OFFICIAL_TYPES:continue
            for t in teams:
                if e['team_id']!=t or (e['type']=='pass' and e.get('outcome')!='complete'):chain[t]=0
            if e['type']=='pass' and e.get('outcome')=='complete':
                chain[e['team_id']]+=1;longest[e['team_id']]=max(longest[e['team_id']],chain[e['team_id']])
        for t in teams:
            teams[t]['longest_observed_pass_chain']=longest[t]
            teams[t]['final_third_entries']=None if self.tools._direction_at(t,start_ms) is None else sum(bool(e['type'] in {'pass','carry'} and e['team_id']==t and e.get('position') and e.get('end_position') and
                ((e['position']['x']<70<=e['end_position']['x']) if self.tools._direction_at(t,e['event_time_ms'])==1 else (e['position']['x']>35>=e['end_position']['x']))) for e in events)
        return {"window_ms": [start_ms, end_ms], "teams": teams, "possession_sample_pct": possession,
                "possession_time_pct":{t:round(100*elapsed[t]/observed,1) if observed else None for t in teams},'possession_observed_ms':observed,
                "possession_method": "time-weighted observed intervals up to 1 second; no bridging gaps; sample share retained separately",
                "rhythm": rhythm, "turnovers": len(changes), "turnovers_per_minute":round(turnover_rate,2),
                "rhythm_method": "Heuristic: >=3 observed turnovers and >=6/minute = frequent_turnovers; >=4 completed passes and no turnovers = sustained_sequence",
                "pressure_change": {"before": pressure_before, "after": pressure_now,
                    "delta": None if pressure_now["value"] is None or pressure_before["value"] is None else pressure_now["value"] - pressure_before["value"]},
                "coverage": {c: self.tools._coverage(c, start_ms, end_ms) for c in self.tools._metadata["channels"]},
                "evidence_ids": [e["id"] for e in events], "speeds": self.speeds(start_ms, end_ms)}
