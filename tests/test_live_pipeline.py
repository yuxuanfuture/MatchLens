"""Offline acceptance: real calculations, clocks, transport and API denial."""
import copy
import hashlib
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from backend import api_policy
from backend.fixture_tools import FixtureStream
from backend.harness import ModelError, OllamaModel
from backend.model_providers import DeepSeekModel
from backend.server import AppServer, EventStore, Session, Journal, ROOT
from backend.insights import publish, recap


class ApprovalTests(unittest.TestCase):
    def test_current_policy_blocks_all_model_network(self):
        self.assertFalse(api_policy.policy_status()["enabled"])
        with patch("urllib.request.build_opener") as opener, patch("urllib.request.urlopen") as request:
            for model in [DeepSeekModel("unused-test-key"), OllamaModel("test-only")]:
                with self.assertRaises(ModelError):
                    model.complete([], 1)
            opener.assert_not_called()
            request.assert_not_called()

    def test_revoked_credential_remains_blocked_even_with_later_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy.json"
            path.write_text(json.dumps({"enabled": True, "approved_provider": "deepseek", "approval_note": "test", "max_requests": 10,
                                        "blocked_key_sha256": [hashlib.sha256(b"revoked-test-key").hexdigest()]}))
            with patch.object(api_policy, "POLICY_PATH", path):
                with self.assertRaisesRegex(api_policy.APIBlocked, "revoked"):
                    api_policy.require_model_permission("deepseek", "revoked-test-key")

    def test_missing_policy_fails_closed(self):
        with patch.object(api_policy, "POLICY_PATH", Path("/nonexistent-policy")):
            with self.assertRaises(api_policy.APIBlocked):
                api_policy.require_model_permission("ollama")


class StreamTests(unittest.TestCase):
    def test_duplicate_late_future_and_conflicting_records(self):
        stream = FixtureStream(ROOT / "data/streams/stream-01.jsonl")
        store = EventStore()
        metadata = stream._records[0]
        self.assertTrue(store.ingest(metadata, 0))
        self.assertFalse(store.ingest(metadata, 0))
        later = copy.deepcopy(next(r for r in stream._records if r["record_type"] == "event"))
        later.update(event_time_ms=900, observed_at_ms=1100)
        store.ingest(later, 1100)
        self.assertEqual(len(store.snapshot(1000)._records), 1)
        self.assertEqual(len(store.snapshot(1100)._records), 2)
        with self.assertRaises(ValueError):
            store.ingest({**later, "type": "goal"}, 1100)
        with self.assertRaises(ValueError):
            store.ingest({**later, "id": "future", "observed_at_ms": 1200}, 1100)
        store.ingest({**later, "id": "clock_future", "event_time_ms": 5000}, 1100)
        self.assertNotIn("clock_future", [r["id"] for r in store.snapshot(1200)._records])

    def test_three_branches_differ_by_observed_evidence(self):
        results = [publish(FixtureStream(ROOT / f"data/streams/stream-{i:02}.jsonl").snapshot(68000)) for i in range(1,4)]
        self.assertEqual(results[0]["story"]["topic"], "transition")
        self.assertEqual(results[1]["story"]["topic"], "pressure")
        self.assertIn("Coverage gaps", results[2]["story"]["analyst_text"])
        missing = publish(FixtureStream(ROOT / "data/streams/stream-03.jsonl").snapshot(58000))
        self.assertFalse(missing["tracking_available"])
        self.assertIsNone(missing["facts"]["speeds"]["ball_speed_mps"])
        self.assertEqual(missing["overlays"], [])

    def test_seek_removes_future_goals_evidence_and_model_results(self):
        s = Session("match-day")
        goal = next(r for r in s.rows if r.get("type") == "goal")
        after = s.control({"seek_ms": goal["observed_at_ms"]})
        self.assertEqual(sum(after["state"]["score"].values()), 1)
        epoch = s.epoch
        before = s.control({"seek_ms": 1000})
        self.assertEqual(sum(before["state"]["score"].values()), 0)
        self.assertFalse(s.model_result(epoch, goal["observed_at_ms"], {"status": "publish", "claims": [{}]}))
        self.assertTrue(all(e["event_time_ms"] <= 1000 for e in before["events"]))
        self.assertNotIn(goal["id"], s.make_recap()["evidence_ids"])

    def test_preferences_change_content_and_invalidate_inflight_analysis(self):
        s = Session("stream-01")
        a = s.control({"seek_ms": 68000})
        epoch = s.epoch
        b = s.control({"preferences": {"focus_team": "U", "language": "en", "metric": "passing", "focus_player": "U4"}})
        self.assertNotEqual(a["story"]["fan_text"], b["story"]["fan_text"])
        self.assertEqual(b["focus"]["player"]["id"], "U4")
        self.assertIn("In this window", b["story"]["fan_text"])
        self.assertNotEqual(b["story"]["fan_text"], b["story"]["analyst_text"])
        self.assertFalse(s.model_result(epoch, 68000, {"status": "publish", "claims": [{}]}))

    def test_approved_test_double_uses_original_window_then_expires(self):
        # Synthetic result injected into the publication boundary, never an API.
        s = Session("stream-01")
        s.control({"seek_ms":68000})
        result = {"status":"publish", "as_of_ms":60000, "fan_text":"Test fan", "analyst_text":"Test analyst",
                  "claims":[{"evidence_ids":["p001"]}], "usage":{"model_calls":0}, "facts":{}}
        self.assertTrue(s.model_result(s.epoch,60000,result))
        published = s.payload()
        self.assertEqual(published['story']['window_ms'],[30000,60000])
        self.assertEqual(published['story']['source'],'model_harness')
        self.assertEqual(published['evidence_records'][0]['id'],'p001')
        s.at=90080
        self.assertEqual(s.payload()['story']['source'],'offline_facts')

    def test_all_published_refs_are_observable_without_network(self):
        with patch("socket.socket.connect", side_effect=AssertionError("network prohibited")):
            for stream in ["stream-01", "stream-02", "stream-03"]:
                session = Session(stream)
                for time in [1000, 53000, 58000, 68000, 90000]:
                    result = session.control({"seek_ms": time})
                    self.assertEqual(result["model_calls"], 0)
                    ids = result["story"]["evidence_ids"]
                    if ids:
                        records = session.store.snapshot(time, False).get_evidence(ids)["records"]
                        self.assertTrue(all(max(r["event_time_ms"], r["observed_at_ms"]) <= time for r in records))

    def test_persistent_journal_records_epoch_and_published_story(self):
        journal = Journal(":memory:")
        self.addCleanup(journal.db.close)
        s = Session("stream-01", journal=journal)
        s.control({"seek_ms": 68000})
        s.control({"seek_ms": 1000})
        rows = journal.db.execute("SELECT epoch,at,body FROM stories ORDER BY epoch").fetchall()
        self.assertEqual([(r[0],r[1]) for r in rows], [(1,68000),(2,1000)])
        self.assertEqual(json.loads(rows[0][2])["source"], "offline_facts")


class FullMatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stream = FixtureStream(ROOT / "data/streams/match-day.jsonl")
        cls.rows = cls.stream._records
        cls.end = max(r["observed_at_ms"] for r in cls.rows)

    def test_active_lineups_geometry_and_turnovers(self):
        from scripts.validate_match_fixtures import validate_records
        self.assertEqual(validate_records(self.rows), [])
        frames = [r for r in self.rows if r["record_type"] == "tracking"]
        self.assertGreaterEqual(self.end, 5400000)
        for frame in frames:
            self.assertEqual(len({p["player_id"] for p in frame["players"]}),22)
            self.assertTrue(all(0<=p["x"]<=105 and 0<=p["y"]<=68 for p in frame["players"]))
        events = [r for r in self.rows if r["record_type"] == "event"]
        self.assertTrue({"tackle","possession_change","substitution","period_start","goal","shot_end","full_time"} <= {e["type"] for e in events})
        sub = next(e for e in events if e["type"] == "substitution")
        before = self.stream.snapshot(sub["event_time_ms"]-1).get_player_context("A11",0,sub["event_time_ms"]-1)["samples"][-1]
        after = self.stream.snapshot(sub["event_time_ms"]+1000).get_player_context("A17",sub["event_time_ms"],sub["event_time_ms"]+1000)["samples"][-1]
        self.assertIsNotNone(before["position"])
        self.assertIsNotNone(after["position"])

    def test_score_recap_and_goal_evidence_agree(self):
        tools = self.stream.snapshot(self.end)
        score = Counter(e["team_id"] for e in self.rows if e.get("type") == "goal")
        self.assertEqual(tools.get_match_state()["score"], {team:score[team] for team in ["A","U"]})
        self.assertEqual({e['period'] for e in self.rows if e.get('type')=='shot'},{1,2})
        report = recap(tools)
        self.assertEqual(report["scope"], "full_time")
        self.assertGreater(len(report["turning_points"]), 0)
        self.assertTrue(all(m["time_ms"]<=self.end for m in report["milestones"]))

    def test_half_time_direction_and_speed_discontinuity(self):
        period = next(e for e in self.rows if e.get("type") == "period_start")
        tools = self.stream.snapshot(period["event_time_ms"]+5000)
        self.assertEqual(tools._direction_at("A", period["event_time_ms"]), -1)
        events = tools.query_events(period["event_time_ms"],tools.as_of_ms)["events"]
        for e in events:
            if e["type"] == "pass":
                self.assertAlmostEqual(e["derived"]["attacking_progress_m"],round(-(e["end_position"]["x"]-e["position"]["x"]),3))
        speed = tools.get_player_metrics("A7",period["event_time_ms"]-2000,tools.as_of_ms)
        self.assertLessEqual(speed["peak_sampled_speed_mps"] or 0,8)

    def test_pass_quality_accuracy_and_completed_shot_speed(self):
        shot_end = next(e for e in self.rows if e.get("type") == "shot_end")
        tools = self.stream.snapshot(shot_end["observed_at_ms"])
        speeds = tools.get_speed_metrics(0,tools.as_of_ms)["shot_speeds"]
        self.assertEqual(len(speeds),1)
        self.assertGreater(speeds[0]["speed_mps"],0)
        self.assertLessEqual(speeds[0]["speed_mps"],24.1)
        before = self.stream.snapshot(shot_end["event_time_ms"]-1)
        self.assertEqual(before.get_speed_metrics(0,before.as_of_ms)["shot_speeds"],[])
        event = next(e for e in self.rows if e.get("type") == "pass")
        q = tools.get_pass_quality(event["id"])
        self.assertGreater(q["distance_m"],0)
        self.assertIn(q["difficulty_1_to_5"],range(1,6))

    def test_simulation_is_reproducible_without_evaluation_labels(self):
        from scripts.generate_match_day import Simulator
        from scripts.validate_match_fixtures import validate_records
        first=Simulator(9).build(300)
        self.assertEqual(first,Simulator(9).build(300))
        self.assertNotEqual(first,Simulator(10).build(300))
        self.assertEqual(validate_records(first),[])


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.server = AppServer(("127.0.0.1",0))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def request(self,path,body=None):
        request=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body else None,
                                      headers={"Content-Type":"application/json"})
        return json.load(urllib.request.urlopen(request,timeout=5))

    def test_http_session_controls_sse_recap_and_policy(self):
        created=self.request('/api/session',{'stream':'stream-01'})
        sid=created['session_id']
        result=self.request('/api/control',{'session':sid,'seek_ms':68000,'preferences':{'language':'en'}})
        self.assertFalse(result['policy']['enabled'])
        self.assertEqual(result['story']['topic'],'transition')
        with urllib.request.urlopen(self.base+'/api/stream?session='+sid,timeout=5) as response:
            data=json.loads(response.readline().decode()[6:])
            self.assertEqual(data['as_of_ms'],68000)
        report=self.request('/api/recap?session='+sid)
        self.assertIn('Recap so far',report['text'])
        self.assertEqual(report['counts']['shot'],1)
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/control',{'session':sid,'seek_ms':999999999})

    def test_live_http_ingestion_reaches_overlay_and_recap_without_duplicate_goals(self):
        rows=FixtureStream(ROOT/'data/streams/match-day.jsonl')._records
        created=self.request('/api/session',{'records':[rows[0]],'live':True})
        sid=created['session_id'];goal=next(r for r in rows if r.get('type')=='goal')
        command={'session':sid,'records':[goal],'received_at_ms':goal['observed_at_ms']}
        self.assertEqual(self.request('/api/ingest',command)['accepted'],1)
        self.assertEqual(self.request('/api/ingest',command)['accepted'],0)
        state=self.request('/api/state?session='+sid)
        self.assertEqual(sum(state['state']['score'].values()),1)
        packet=self.request('/api/overlay?session='+sid)
        self.assertTrue(any(c['kind']=='goal' for c in packet['cues']))
        self.assertEqual(packet['clock']['basis'],'source_media_ms')
        self.assertFalse(state['policy']['enabled'])


if __name__ == '__main__':
    unittest.main()
