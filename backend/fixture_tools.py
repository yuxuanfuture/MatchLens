"""Model-independent, read-only tools for a frozen replay observation.

The harness creates a new snapshot as the clock advances. The model cannot advance
that clock, read fixture paths, access the generator, or inspect evaluation labels.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path


class FixtureStream:
    def __init__(self, path):
        self._records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
        if not self._records or self._records[0]["record_type"] != "metadata":
            raise ValueError("The stream must begin with metadata")

    def snapshot(self, observation_time_ms):
        if type(observation_time_ms) is not int or observation_time_ms < 0:
            raise ValueError("observation_time_ms must be a non-negative integer")
        visible = [row for row in self._records if row["observed_at_ms"] <= observation_time_ms
                   and row["event_time_ms"] <= observation_time_ms]
        return MatchTools(copy.deepcopy(visible), observation_time_ms)


class MatchTools:
    def __init__(self, visible_records, as_of_ms):
        self._records = visible_records
        self.as_of_ms = as_of_ms
        self._metadata = next(row for row in visible_records if row["record_type"] == "metadata")
        self._roster = {p["id"]: p for p in self._metadata["roster"]}
        self._directions = {t["id"]: t["attack_direction_x"] for t in self._metadata["teams"]}
        self._events = [r for r in visible_records if r["record_type"] == "event"]
        self._coverage_updates = {c:sorted((r for r in visible_records if r['record_type']=='coverage' and c in r['channels']),key=lambda r:r['event_time_ms']) for c in self._metadata['channels']}
        self._period_changes = sorted((r for r in self._events if r["type"] == "period_start"), key=lambda r: r["event_time_ms"])

    def _direction_at(self, team, time_ms):
        direction = None if self._metadata.get('direction_source') == 'unconfirmed' else self._directions[team]
        for row in self._period_changes:
            if row["event_time_ms"] <= time_ms:
                direction = row.get("team_directions", {}).get(team, direction)
        return direction

    def _window(self, start_ms, end_ms):
        if any(type(t) is not int for t in (start_ms, end_ms)) or not 0 <= start_ms <= end_ms <= self.as_of_ms:
            raise ValueError("Window must be within [0, the frozen observation time]; future access is unavailable")

    def _team(self, team_id):
        if team_id not in self._directions:
            raise ValueError("Unknown team_id")

    def _spatial_context(self, row):
        result = copy.deepcopy(row)
        if row.get("type") in {"pass", "carry"} and row.get("position") and row.get("end_position"):
            direction = self._direction_at(row["team_id"], row["event_time_ms"])
            progress = (row["end_position"]["x"] - row["position"]["x"]) * direction if direction is not None else None
            result["derived"] = {"attacking_progress_m": round(progress, 3) if progress is not None else None,
                "travel_distance_m": round(math.hypot(row["end_position"]["x"] - row["position"]["x"],
                                                     row["end_position"]["y"] - row["position"]["y"]), 3),
                "direction_in_team_frame": None if progress is None else "forward" if progress > 1 else "backward" if progress < -1 else "lateral",
                "calculation": "attacking_progress_m is signed goalward x displacement, NOT travel distance; travel_distance_m is Euclidean start-to-end distance; +/- 1 m lateral tolerance"}
        return result

    def query_events(self, start_ms, end_ms, team_id=None, event_types=None):
        self._window(start_ms, end_ms)
        if team_id is not None:
            self._team(team_id)
        events = [row for row in self._events if start_ms <= row["event_time_ms"] <= end_ms
                  and (team_id is None or row["team_id"] == team_id)
                  and (event_types is None or row["type"] in event_types)]
        return {"as_of_ms": self.as_of_ms, "window_ms": [start_ms, end_ms],
                "events": [self._spatial_context(row) for row in sorted(events, key=lambda row: (row["event_time_ms"], row["id"]))]}

    def _coverage(self, channel, start_ms, end_ms):
        status = self._metadata["channels"][channel]
        cursor, gaps = 0, []
        updates = self._coverage_updates[channel]
        for row in updates:
            change = row["event_time_ms"]
            if status != "available" and max(start_ms, cursor) < min(end_ms + 1, change):
                gaps.append([max(start_ms, cursor), min(end_ms, change - 1)])
            status, cursor = row["status"], change
        if status != "available" and max(start_ms, cursor) <= end_ms:
            gaps.append([max(start_ms, cursor), end_ms])
        return {"complete": not gaps, "missing_intervals_ms": gaps}

    def get_match_state(self):
        score = dict(self._metadata["initial_score"])
        possession = self._metadata["initial_possession_team_id"]
        # State transitions only need raw observed records, not an expensive
        # spatially enriched copy of every pass since kickoff on every tick.
        events = sorted(self._events,key=lambda row:(row['event_time_ms'],row['id']))
        for event in events:
            if event["type"] == "goal":
                score[event["team_id"]] += 1
            if event["type"] in {"carry", "pass", "recovery", "save", "interception", "tackle", "kickoff", "possession_change"}:
                possession = event["team_id"]
        latest = max((r for r in self._records if r['record_type'] == 'tracking'),
                     key=lambda r: r['event_time_ms'], default=None)
        live_state = {}
        if latest and 'in_play' in latest and latest.get('status') == 'available' and self.as_of_ms - latest['event_time_ms'] <= 1500:
            live_state['in_play'] = latest['in_play']
            possession = latest.get('possession_team_id') if latest['in_play'] else None
        teams = copy.deepcopy(self._metadata["teams"])
        length = self._metadata["pitch"]["length_m"]
        for team in teams:
            team["attack_direction_x"] = self._direction_at(team["id"], self.as_of_ms)
            if team['attack_direction_x'] is None:
                team.update(own_goal_x_m=None, opponent_goal_x_m=None, attacking_direction=None)
                continue
            forward_positive = team["attack_direction_x"] == 1
            team.update(own_goal_x_m=0 if forward_positive else length,
                        opponent_goal_x_m=length if forward_positive else 0,
                        attacking_direction="increasing_x" if forward_positive else "decreasing_x")
        return {"as_of_ms": self.as_of_ms, "match_id": self._metadata["match_id"],
                "observation_scope": self._metadata.get("observation_scope", "excerpt"), "observation_window_ms": [0, self.as_of_ms],
                "match_clock_start_ms": self._metadata["match_clock_start_ms"],
                "time_note": "Times are relative to stream start; add match_clock_start_ms for match clock. Statistics cover the queried window only.",
                "match_clock_ms": self._metadata["match_clock_start_ms"] + self.as_of_ms,
                "score": score, "score_known":self._metadata.get('score_source')!='unconfirmed',
                "direction_known": all(t['attack_direction_x'] is not None for t in teams), "possession_team_id": possession,
                **live_state, "officials": copy.deepcopy(self._metadata.get('officials', [])),
                "teams": teams, "roster": copy.deepcopy(self._metadata["roster"]),
                "current_coverage": {channel: self._coverage(channel, self.as_of_ms, self.as_of_ms)
                                     for channel in self._metadata["channels"]}}

    def get_player_context(self, player_id, start_ms, end_ms, limit=24):
        self._window(start_ms, end_ms)
        if player_id not in self._roster:
            raise ValueError("Unknown player_id")
        if type(limit) is not int or not 1 <= limit <= 40:
            raise ValueError("limit must be between 1 and 40")
        events = [e for e in self.query_events(start_ms, end_ms)["events"]
                  if player_id in (e.get("player_id"), e.get("receiver_id"), e.get("opponent_id"))]
        samples = []
        for row in self._records:
            if row["record_type"] == "tracking" and start_ms <= row["event_time_ms"] <= end_ms:
                position = next((p for p in row["players"] or [] if p["player_id"] == player_id), None)
                samples.append({"sample_id": row["id"], "event_time_ms": row["event_time_ms"],
                                "status": row["status"], "position": position})
        return {"as_of_ms": self.as_of_ms, "player": copy.deepcopy(self._roster[player_id]),
                "events": events, "samples": copy.deepcopy(samples[-limit:]),
                "samples_truncated": len(samples) > limit,
                "tracking_coverage": self._coverage("tracking", start_ms, end_ms)}

    def calculate_metric(self, metric, team_id, start_ms, end_ms):
        self._team(team_id)
        events = self.query_events(start_ms, end_ms, team_id)["events"]
        evidence, notes, status, value, unit = [], [], "available", None, "count"
        type_metrics = {"pass_count": "pass", "pressure_event_count": "pressure",
                        "recovery_count": "recovery", "shot_count": "shot", "goal_count": "goal"}
        if metric in type_metrics:
            selected = [e for e in events if e["type"] == type_metrics[metric]]
            evidence = [e["id"] for e in selected]
            channel = "pressure" if metric == "pressure_event_count" else "events"
            if self._coverage(channel, start_ms, end_ms)["complete"]:
                value = len(selected)
            else:
                status = "insufficient_data"
                notes.append(f"{channel} coverage is incomplete; absence of records is not evidence of zero")
        elif metric in {"backward_pass_count", "high_recovery_count", "pass_distance_total_m"}:
            kind = "recovery" if metric == "high_recovery_count" else "pass"
            selected = [e for e in events if e["type"] == kind]
            missing = [e for e in selected if e.get("position") is None or (kind == "pass" and e.get("end_position") is None)]
            if metric != 'pass_distance_total_m' and (self._direction_at(team_id,start_ms) is None or any(self._direction_at(team_id,e['event_time_ms']) is None for e in selected)):
                status = 'insufficient_data'
                notes.append('Attacking direction is unconfirmed; no forward/backward or attacking-third claim is available')
            elif missing:
                status = "insufficient_data"
                evidence = [e["id"] for e in missing]
                notes.append("Required event positions are unavailable; null must not be treated as zero")
            else:
                if metric == "backward_pass_count":
                    selected = [e for e in selected if (e["end_position"]["x"] - e["position"]["x"]) * self._direction_at(team_id, e["event_time_ms"]) < -1]
                    value = len(selected)
                    notes.append("Backward means more than 1 m toward the team's own goal")
                elif metric == "high_recovery_count":
                    selected = [e for e in selected if (e["position"]["x"] >= 70 if self._direction_at(team_id, e["event_time_ms"]) == 1 else e["position"]["x"] <= 35)]
                    value = len(selected)
                    notes.append("High regain means a recovery in the attacking third of the 105 m pitch")
                else:
                    unit = "metres"
                    value = round(sum(math.hypot(e["position"]["x"] - e["end_position"]["x"],
                                                e["position"]["y"] - e["end_position"]["y"]) for e in selected), 3)
                evidence = [e["id"] for e in selected]
        elif metric == "regain_to_shot_seconds":
            unit = "seconds"
            recoveries = [e for e in events if e["type"] == "recovery"]
            all_events = self.query_events(start_ms, end_ms)["events"]
            if recoveries:
                recovery = recoveries[-1]
                for e in all_events:
                    if e["event_time_ms"] <= recovery["event_time_ms"]:
                        continue
                    if e["team_id"] != team_id and e["type"] in {"recovery", "save", "pass", "carry"}:
                        break
                    if e["team_id"] == team_id and e["type"] == "shot":
                        value = (e["event_time_ms"] - recovery["event_time_ms"]) / 1000
                        evidence = [recovery["id"], e["id"]]
                        break
            if value is None:
                status = "not_observed"
                notes.append("No completed regain-to-shot sequence is observable in this window")
        else:
            raise ValueError("Unknown metric")
        channels = ["events"]
        if metric == "pressure_event_count":
            channels = ["pressure"]
        elif metric in {"backward_pass_count", "high_recovery_count", "pass_distance_total_m"}:
            channels.append("event_positions")
        return {"as_of_ms": self.as_of_ms, "metric": metric, "team_id": team_id,
                "window_ms": [start_ms, end_ms], "value": value, "unit": unit,
                "status": status, "evidence_ids": evidence, "notes": notes,
                "input_coverage": {channel: self._coverage(channel, start_ms, end_ms) for channel in channels}}

    def compare_windows(self, metric, team_id, before, after):
        left = self.calculate_metric(metric, team_id, *before)
        right = self.calculate_metric(metric, team_id, *after)
        delta = right["value"] - left["value"] if left["value"] is not None and right["value"] is not None else None
        return {"as_of_ms": self.as_of_ms, "before": left, "after": right, "delta": delta}

    def get_evidence(self, record_ids):
        if not isinstance(record_ids, list) or not 1 <= len(record_ids) <= 40:
            raise ValueError("Supply between 1 and 40 record IDs")
        available = {r["id"]: r for r in self._records}
        if any(identifier not in available for identifier in record_ids):
            raise ValueError("Some requested evidence is not observable at this snapshot")
        return {"as_of_ms": self.as_of_ms, "records": [self._spatial_context(available[i]) for i in record_ids]}

    def get_match_intelligence(self, start_ms, end_ms, team_id="A"):
        from backend.analytics import FootballAnalytics
        return FootballAnalytics(self).intelligence(start_ms, end_ms, team_id)

    def get_player_metrics(self, player_id, start_ms, end_ms):
        from backend.analytics import FootballAnalytics
        return FootballAnalytics(self).player_metrics(player_id, start_ms, end_ms)

    def get_pass_quality(self, event_id):
        from backend.analytics import FootballAnalytics
        return FootballAnalytics(self).pass_quality(event_id)

    def get_speed_metrics(self, start_ms, end_ms):
        from backend.analytics import FootballAnalytics
        return FootballAnalytics(self).speeds(start_ms, end_ms)

    def get_recap_context(self):
        from backend.insights import recap
        report = recap(self)
        return {**report, 'statistics': self.get_match_intelligence(0, self.as_of_ms)}
