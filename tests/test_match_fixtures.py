import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.fixture_tools import FixtureStream
from scripts.generate_match_fixtures import DEFAULT_SEED, ROOT, build_stream, with_missing_channels, write_fixtures
from scripts.validate_match_fixtures import validate_records


class FixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = ROOT / "data" / "streams"
        cls.rows = {key: [json.loads(line) for line in (cls.directory / f"{key}.jsonl").read_text().splitlines()]
                    for key in ("stream-01", "stream-02", "stream-03")}
        cls.expected = json.loads((ROOT / "evals" / "fixture_expectations.json").read_text())

    def snapshot(self, key="stream-01", time=68000):
        return FixtureStream(self.directory / f"{key}.jsonl").snapshot(time)

    def test_all_streams_have_valid_geometry_identity_and_timing(self):
        for key, rows in self.rows.items():
            self.assertEqual(validate_records(rows), [], key)
            self.assertEqual(sum(r["record_type"] == "tracking" for r in rows), 181)

    def test_generator_reproduces_checked_in_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            generated = write_fixtures(temp, DEFAULT_SEED)
            for item in generated["cases"]:
                original = (ROOT / item["stream"]).read_bytes()
                rebuilt = (Path(temp) / item["stream"]).read_bytes()
                self.assertEqual(original, rebuilt)
                self.assertEqual(hashlib.sha256(rebuilt).hexdigest(), item["sha256"])

    def test_another_seed_changes_positions_without_breaking_physics(self):
        changed = build_stream("regain", DEFAULT_SEED + 1)
        self.assertNotEqual(changed, self.rows["stream-01"])
        self.assertEqual(validate_records(changed), [])

    def test_positive_and_negative_have_identical_visible_prefix(self):
        left = [r for r in self.rows["stream-01"] if r["observed_at_ms"] <= 53000]
        right = [r for r in self.rows["stream-02"] if r["observed_at_ms"] <= 53000]
        self.assertEqual(left, right)
        for key in ("stream-01", "stream-02"):
            self.assertEqual(self.snapshot(key, 53000).calculate_metric("recovery_count", "A", 40000, 53000)["value"], 0)

    def test_expected_metrics_are_computed_from_each_stream(self):
        mapping = {"union_backward_passes": ("backward_pass_count", "U"),
                   "atlas_pressure_events": ("pressure_event_count", "A"),
                   "atlas_recoveries": ("recovery_count", "A"), "atlas_shots": ("shot_count", "A"),
                   "regain_to_shot_seconds": ("regain_to_shot_seconds", "A"), "goals": ("goal_count", "A")}
        for key, expected in self.expected["cases"].items():
            tools = self.snapshot(key)
            for assertion, (metric, team) in mapping.items():
                with self.subTest(stream=key, metric=metric):
                    self.assertEqual(tools.calculate_metric(metric, team, 40000, 68000)["value"], expected[assertion])
            high = tools.calculate_metric("high_recovery_count", "A", 40000, 68000)["value"]
            self.assertEqual(None if high is None else high > 0, expected["high_regain"])

    def test_missing_channels_preserve_actions_but_do_not_become_zero(self):
        tools = self.snapshot("stream-03")
        for metric, team in [("pressure_event_count", "A"), ("backward_pass_count", "U"), ("high_recovery_count", "A")]:
            result = tools.calculate_metric(metric, team, 40000, 68000)
            self.assertIsNone(result["value"])
            self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(tools.calculate_metric("regain_to_shot_seconds", "A", 40000, 68000)["value"], 7.0)
        self.assertEqual(tools.calculate_metric("pressure_event_count", "A", 65000, 68000)["value"], 0)

    def test_missing_version_is_only_an_observation_mask(self):
        self.assertEqual(with_missing_channels(self.rows["stream-01"]), self.rows["stream-03"])
        masked = [r for r in self.rows["stream-03"] if r["record_type"] == "tracking" and r["status"] == "unavailable"]
        self.assertEqual(len(masked), 58)

    def test_future_windows_and_future_evidence_are_rejected(self):
        tools = self.snapshot(time=53000)
        for method in (lambda: tools.query_events(40000, 68000),
                       lambda: tools.get_player_context("A7", 40000, 68000),
                       lambda: tools.calculate_metric("recovery_count", "A", 40000, 68000),
                       lambda: tools.get_evidence(["e018"])):
            with self.assertRaises(ValueError):
                method()

    def test_event_is_not_visible_until_it_arrives(self):
        before = self.snapshot(time=56000)
        after = self.snapshot(time=56080)
        self.assertEqual(before.calculate_metric("recovery_count", "A", 40000, 56000)["value"], 0)
        self.assertEqual(after.calculate_metric("recovery_count", "A", 40000, 56080)["value"], 1)

    def test_shot_does_not_reveal_its_future_outcome(self):
        tools = self.snapshot(time=63080)
        shots = tools.query_events(60000, 63080, event_types=["shot"])["events"]
        self.assertEqual(len(shots), 1)
        self.assertNotIn("outcome", shots[0])
        self.assertNotIn("end_position", shots[0])
        self.assertEqual(tools.query_events(60000, 63080, event_types=["save"])["events"], [])
        self.assertEqual(tools.get_match_state()["score"], {"A": 0, "U": 0})

    def test_direction_is_relative_to_the_team_and_missing_positions_stay_unknown(self):
        tools = self.snapshot("stream-02")
        union = next(t for t in tools.get_match_state()["teams"] if t["id"] == "U")
        self.assertEqual(union["own_goal_x_m"], 105)
        self.assertEqual(union["opponent_goal_x_m"], 0)
        backward, forward = tools.get_evidence(["e014", "e017"])["records"]
        self.assertEqual(backward["derived"]["attacking_progress_m"], -6)
        self.assertEqual(backward["derived"]["direction_in_team_frame"], "backward")
        self.assertEqual(forward["derived"]["attacking_progress_m"], 14)
        self.assertEqual(forward["derived"]["direction_in_team_frame"], "forward")
        self.assertAlmostEqual(forward["derived"]["travel_distance_m"], (14 ** 2 + 10 ** 2) ** .5, places=3)
        self.assertNotEqual(forward["derived"]["travel_distance_m"], forward["derived"]["attacking_progress_m"])
        missing = self.snapshot("stream-03").get_evidence(["e014"])["records"][0]
        self.assertNotIn("derived", missing)

    def test_pass_origin_and_receiver_match_tracking(self):
        for key in ("stream-01", "stream-02"):
            frames = {r["event_time_ms"]: r for r in self.rows[key] if r["record_type"] == "tracking"}
            for event in self.rows[key]:
                if event.get("type") != "pass":
                    continue
                for time, player_id, position in [(event["start_time_ms"], event["player_id"], event["position"]),
                                                  (event["event_time_ms"], event["receiver_id"], event["end_position"])]:
                    actual = next(p for p in frames[time]["players"] if p["player_id"] == player_id)
                    self.assertAlmostEqual(actual["x"], position["x"], places=2)
                    self.assertAlmostEqual(actual["y"], position["y"], places=2)

    def test_possession_chain_is_consistent(self):
        for rows in self.rows.values():
            owner, team = "U4", "U"
            for event in sorted((r for r in rows if r["record_type"] == "event"), key=lambda e: (e["event_time_ms"], e["id"])):
                if event["type"] in {"carry", "pass", "shot"}:
                    self.assertEqual(event["player_id"], owner)
                    self.assertEqual(event["team_id"], team)
                    if event["type"] == "pass":
                        owner = event["receiver_id"]
                elif event["type"] == "recovery":
                    self.assertEqual(event["previous_team_id"], team)
                    self.assertNotEqual(event["team_id"], team)
                    owner, team = event["player_id"], event["team_id"]
                elif event["type"] == "save":
                    owner, team = event["player_id"], event["team_id"]

    def test_returned_tool_data_cannot_mutate_the_snapshot(self):
        tools = self.snapshot()
        events = tools.query_events(40000, 68000)["events"]
        events[0]["team_id"] = "tampered"
        self.assertNotEqual(tools.query_events(40000, 68000)["events"][0]["team_id"], "tampered")

    def test_validator_rejects_corruption(self):
        rows = copy.deepcopy(self.rows["stream-01"])
        rows[-1]["id"] = rows[0]["id"]
        rows[-1]["players"][0]["x"] = 150
        rows[1]["ground_truth"] = "answer"
        messages = validate_records(rows)
        self.assertTrue(any("Duplicate" in message for message in messages))
        self.assertTrue(any("outside pitch" in message for message in messages))
        self.assertTrue(any("answer-bearing" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
