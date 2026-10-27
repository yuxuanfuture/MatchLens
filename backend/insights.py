"""Evidence-linked, multilingual offline publisher. No model calls and no fixture labels.

The harness can replace the narrative after an independently verified investigation.
Numbers, coordinates and overlays always come from deterministic tools.
"""
import hashlib
import json
from backend.i18n import LANGUAGES, text, display_name
from backend.review_state import review_state, confirmed_goal_cues, presentation_evidence


DEFAULTS = {"language": "zh", "mode": "fan", "role": "fan", "focus_team": "A",
            "focus_player": None, "metric": "overview"}


def preferences(value, roster):
    result = {**DEFAULTS, **value}
    allowed = {"language": set(LANGUAGES), "mode": {"fan", "analyst"},
               "role": {"fan", "coach", "commentator"}, "focus_team": {"A", "U"},
               "metric": {"overview", "pressure", "passing", "speed"}}
    if set(value) - set(DEFAULTS):
        raise ValueError("Unknown preference")
    for key, choices in allowed.items():
        if result[key] not in choices:
            raise ValueError(f"Invalid {key}")
    if result["focus_player"] and result["focus_player"] not in roster:
        raise ValueError("Unknown focus player")
    return result


def clock(ms):
    return f"{ms // 60000:02}:{ms // 1000 % 60:02}"


def publish(tools, prefs=None, playback=None):
    p = preferences(prefs or {}, tools._roster)
    now = playback['position_ms'] if playback else tools.as_of_ms
    start = max(0, now - 30000)
    team = p["focus_team"]
    t = lambda key, **values: text(p["language"], key, **values)
    state = tools.get_match_state()
    review = review_state(tools._records)
    if playback:
        state['match_clock_ms'] = playback['match_clock_ms']
    events = tools.query_events(start, now)["events"]
    facts = tools.get_match_intelligence(start, now, team)
    own = facts["teams"][team]
    name = next(t["name"] for t in state["teams"] if t["id"] == team)
    focus = tools.get_player_metrics(p["focus_player"], start, now) if p["focus_player"] else None
    recent = [e for e in events if e["team_id"] == team]
    refs = [e["id"] for e in recent]
    window = f"{clock(state['match_clock_start_ms'] + start)}–{clock(state['match_clock_ms'])}"
    title = t('story.rhythm_title', v0=name)
    fan = t('story.rhythm_fan')
    analyst = t('story.rhythm_stats', v0=name, v1=own['completed_passes'], v2=own['passes'], v3=own['shots'])
    topic = "rhythm"
    if facts["rhythm"] == "frequent_turnovers":
        title = t('story.turnover_title')
        fan = t('story.turnover_fan')
        analyst += t('story.turnover_stats', v0=facts['turnovers'])
    elif facts["rhythm"] == "sustained_sequence":
        fan = t('story.sustained_fan')
    regain = tools.calculate_metric("regain_to_shot_seconds", team, start, now)
    pressures = [e for e in recent if e["type"] == "pressure"]
    if regain["value"] is not None:
        topic, title = "transition", t('story.transition_title')
        fan = t('story.transition_fan', v0=name)
        analyst = t('story.transition_stats', v0=regain['value'])
        refs = regain["evidence_ids"] + [e["id"] for e in pressures]
        if pressures:
            analyst += t('story.pressure_caveat')
    elif pressures:
        topic, title = "pressure", t('story.pressure_title')
        fan = t('story.pressure_fan')
        analyst = t('story.pressure_stats', v0=name, v1=len(pressures))
        refs = [e["id"] for e in pressures]
    special = [e for e in recent if e["type"] in {"goal", "substitution", "formation_change"}]
    changes = [e for e in recent if e["type"] == "formation_change" and now-e["event_time_ms"] >= 20000]
    if changes:
        change = changes[-1]
        at = change["event_time_ms"]
        comparison = tools.compare_windows("shot_count", team, [max(0, at-20000), at-1], [at, at+19999])
        topic, title = "shape_followup", t('story.shape_title')
        fan = t('story.shape_fan')
        analyst = t('story.shape_stats', v0=comparison['before']['value'], v1=comparison['after']['value'])
        refs = [change["id"]] + comparison["before"]["evidence_ids"] + comparison["after"]["evidence_ids"]
    if special and now - special[-1]["event_time_ms"] < 15000:
        e = special[-1]
        refs = [e["id"]]
        topic = e["type"]
        if topic == "goal":
            title = t('story.goal_title')
            fan = t('story.goal_fan', v0=tools._roster[e['player_id']]['name'], v1=state['score']['A'], v2=state['score']['U'])
            analyst = fan + t('story.goal_confirmed')
        else:
            title = t('story.change_title')
            fan = t('story.change_fan')
            analyst = t('story.change_stats')
            formation = [x for x in recent if x["type"] == "formation_change"]
            if formation:
                analyst += f" {formation[-1]['formation_before']} → {formation[-1]['formation_after']}."
                refs += [formation[-1]["id"]]
    last_pass = next((e for e in reversed(recent) if e["type"] == "pass"), None)
    quality = tools.get_pass_quality(last_pass["id"]) if last_pass else None
    if p["metric"] == "passing":
        topic, title = "passing", t('story.passing_title', v0=name)
        accuracy = own["pass_accuracy_pct"]
        fan = t('story.passing_fan', v0=own['passes'], v1=own['completed_passes'])
        analyst = fan
        if quality:
            analyst += t('story.passing_details', v0=quality['distance_m'], v1=quality['difficulty_1_to_5'])
        refs = [e["id"] for e in recent if e["type"] == "pass"]
    elif p["metric"] == "speed":
        topic, title = "speed", t('story.speed_title')
        speed = facts["speeds"]["ball_speed_mps"]
        fan = t('story.speed_fan')
        analyst = t('story.speed_stats', v0=speed)
        refs = facts["speeds"]["ball_evidence_ids"]
    elif p["metric"] == "pressure":
        topic, title = "pressure", t('story.pressure_change_title', v0=name)
        change = facts["pressure_change"]
        fan = t('story.pressure_change_fan')
        analyst = t('story.pressure_change_stats', v0=change['before']['window_ms'], v1=change['before']['value'], v2=change['after']['value'])
        refs = change["before"]["evidence_ids"] + change["after"]["evidence_ids"]
    if focus:
        topic, title = "player", t('story.player_title', v0=focus['player']['name'])
        fan = t('story.player_fan', v0=focus['completed_passes'], v1=focus['shots'])
        analyst = fan + t('story.player_stats', v0=focus['observed_distance_m'], v1=focus['peak_sampled_speed_mps'])
        refs = focus["evidence_ids"] + focus["tracking_evidence_ids"]
    if review['phase'] != 'none':
        phase = review['phase']
        topic, title = f'review_{phase}', t(f'review.{phase}.title')
        player = tools._roster.get(review.get('subject_player_id'), {}).get('name')
        team_name = next((x['name'] for x in state['teams'] if x['id'] == review.get('subject_team_id')), None)
        fan = t(f'review.{phase}.body', player=player, team=team_name, a=state['score']['A'], u=state['score']['U'])
        analyst = fan + ' ' + t('review.analysis_note')
        refs = review['evidence_ids']
    missing = [k for k, c in facts["coverage"].items() if not c["complete"]]
    if missing:
        names = {"event_positions": t('story.coverage_event_positions'), "tracking": t('story.coverage_tracking'), "pressure": t('story.coverage_pressure'), "events": t('story.coverage_events')}
        channels = ", ".join(names.get(k,k) for k in missing)
        limitation = t('story.coverage_caveat', v0=channels)
        fan += limitation
        analyst += limitation
    if p["role"] == "commentator":
        fan = f"{clock(state['match_clock_ms'])} · {fan}"
        analyst = f"{clock(state['match_clock_ms'])} · {analyst}"
    elif p["role"] == "coach":
        analyst += t('story.coach_caveat')
    frames = [r for r in tools._records if r["record_type"] == "tracking"]
    latest = max(frames, key=lambda r: r["event_time_ms"], default=None)
    tracking_ok = bool(latest and latest.get("players") and now - latest["event_time_ms"] <= 1500
                       and state["current_coverage"]["tracking"]["complete"])
    overlays = []
    for e in events:
        age = now - e["event_time_ms"]
        if e["type"] == "pressure" and e.get("position") and age <= 7000:
            overlays.append({"kind": "pressure", "position": e["position"], "intensity": 1-age/7000, "evidence_id": e["id"]})
        if e["type"] in {"pass", "carry"} and e.get("position") and e.get("end_position") and age <= 10000:
            overlays.append({"kind": "route", "from": e["position"], "to": e["end_position"], "team_id": e["team_id"], "evidence_id": e["id"]})
    overlays.extend(confirmed_goal_cues(tools._records, tools.as_of_ms, playback))
    substitutions = [e for e in events if e["type"] == "substitution"]
    for e in substitutions:
        overlays.append({"kind": "substitution", "at_ms": e["event_time_ms"], "player_id": e["player_in_id"], "evidence_id": e["id"]})
    refs = list(dict.fromkeys(refs))[-40:]
    story = {"topic": topic, "title": title, "fan_text": fan, "analyst_text": analyst,
             "evidence_ids": refs, "window_ms": [start, now], "window_label": window,
             "source": "offline_facts", "display_at_ms": now, "expires_at_ms": now + 8000}
    story["id"] = hashlib.sha256(json.dumps([story, p], sort_keys=True).encode()).hexdigest()[:16]
    return {"schema_version": "1.0", "as_of_ms": tools.as_of_ms, "mode": "offline_facts", "preferences": p,
            **({'playback': playback} if playback else {}),
            'review': review,
            "state": state, "story": story, "facts": facts, "focus": focus, "pass_quality": quality,
            "tracking": presentation_evidence([latest], review)[0] if tracking_ok else None, "tracking_available": tracking_ok,
            "overlays": overlays, "events": events[-40:],
            "evidence_records": presentation_evidence(tools.get_evidence(refs)["records"], review) if refs else [],
            "pipeline": ["ingest", "interpret", "explain", "render", "personalize"],
            "model_calls": 0}


def recap(tools, prefs=None):
    p = preferences(prefs or {}, tools._roster)
    t = lambda key, **values: text(p["language"], key, **values)
    state = tools.get_match_state()
    all_events = tools.query_events(0, tools.as_of_ms)["events"]
    team = p["focus_team"]
    events = [e for e in all_events if e["team_id"] == team and
              (not p["focus_player"] or p["focus_player"] in {e.get("player_id"), e.get("receiver_id"), e.get("player_in_id"), e.get("player_out_id")})]
    milestones, counts = [], {"pass": 0, "shot": 0, "goal": 0, "tackle": 0}
    for e in events:
        kind = e["type"]
        if kind in counts:
            counts[kind] += 1
        if kind in {"goal", "substitution", "formation_change"} or (kind == "shot" and counts[kind] == 1) or (kind == "pass" and counts[kind] % 50 == 0):
            labels = {"goal": t("event.goal"), "substitution": t("event.substitution"),
                      "formation_change": t("event.formation_change"), "shot": t("recap.first_shot"),
                      "pass": t("recap.pass_number", count=counts['pass'])}
            milestones.append({"time_ms": e["event_time_ms"], "match_clock": clock(e["event_time_ms"]+state["match_clock_start_ms"]),
                "text": f"{display_name(p['language'], tools._roster[e['player_id']]['name'])} · {labels[kind]}", "evidence_ids": [e["id"]]})
    fulltime = any(e["type"] == "full_time" for e in all_events)
    scope = t("recap.scope_full" if fulltime else "recap.scope_sofar")
    score = t("recap.score", a=state['score']['A'], u=state['score']['U']) if state['score_known'] else t("recap.score_unknown")
    recap_text = t("recap.body", scope=scope, score=score, passes=counts['pass'], shots=counts['shot'], goals=counts['goal'], tackles=counts['tackle'])
    turning_points = []
    for shot in (e for e in events if e["type"] == "shot"):
        before = [e for e in all_events if max(0, shot["event_time_ms"]-30000) <= e["event_time_ms"] < shot["event_time_ms"]]
        regain = next((e for e in reversed(before) if e["type"] == "recovery" and e["team_id"] == team), None)
        if regain and not any(e["event_time_ms"] > regain["event_time_ms"] and e["team_id"] != team and e["type"] in {"recovery", "save", "pass", "carry"} for e in before):
            seconds = (shot["event_time_ms"]-regain["event_time_ms"])/1000
            turning_points.append({"time_ms": shot["event_time_ms"], "evidence_ids": [regain["id"], shot["id"]],
                "text": t("recap.turning", seconds=seconds)})
    coverage = tools._coverage("events", 0, tools.as_of_ms)
    if not coverage["complete"]:
        recap_text += t("recap.gaps")
    return {"as_of_ms": tools.as_of_ms, "scope": "full_time" if fulltime else "so_far", "source": "offline_facts",
            "preferences": p, "text": recap_text, "counts": counts, "milestones": milestones,
            "window_ms": [0, tools.as_of_ms], "turning_points": turning_points[-8:], "coverage": coverage,
            "evidence_ids": [e["id"] for e in events if e["type"] in counts]}
