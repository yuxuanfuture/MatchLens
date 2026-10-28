"""Independent public-artifact checks for the approved 120-second case."""
from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from backend.fixture_tools import FixtureStream
from scripts.validate_stream_04 import validate_records


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "data" / "streams" / "stream-04.jsonl"


class Stream04Tests(unittest.TestCase):
    def load_rows(self):
        self.assertTrue(ARTIFACT.is_file(), "Generate data/streams/stream-04.jsonl first")
        return [json.loads(line) for line in ARTIFACT.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_goal_is_only_confirmed_after_final_decision_arrives(self):
        rows = self.load_rows()
        goals = [row for row in rows if row.get("type") == "goal"]
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["event_time_ms"], 90000)
        self.assertEqual(goals[0]["observed_at_ms"], 115080)
        for cutoff, count in ((90080, 0), (92080, 0), (115079, 0), (115080, 1), (120080, 1)):
            with self.subTest(cutoff=cutoff):
                visible = [row for row in goals if row["event_time_ms"] <= cutoff and row["observed_at_ms"] <= cutoff]
                self.assertEqual(len(visible), count)

    def test_public_artifact_satisfies_independent_contract(self):
        errors = validate_records(self.load_rows())
        self.assertEqual(errors, [], "\n".join(errors))

    def test_open_play_uses_backfield_and_both_wings_without_a_central_pile(self):
        frame = next(row for row in self.load_rows()
                     if row["record_type"] == "tracking" and row["event_time_ms"] == 22000)
        players = [p for p in frame["players"] if p["player_id"] not in {"A1", "U1"}]
        self.assertGreaterEqual(sum(p["x"] < 45 for p in players), 4)
        self.assertGreaterEqual(sum(p["y"] < 12 for p in players), 4)
        self.assertGreaterEqual(sum(p["y"] > 56 for p in players), 3)
        for index, player in enumerate(players):
            for other in players[index + 1:]:
                self.assertGreaterEqual(math.hypot(player["x"] - other["x"], player["y"] - other["y"]),
                                        4.5, f'{player["player_id"]}/{other["player_id"]} overlap at 90:22')

    def test_existing_snapshot_reader_counts_only_the_confirmed_goal(self):
        stream = FixtureStream(ARTIFACT)
        for cutoff, expected in ((90080, 0), (92080, 0), (115079, 0), (115080, 1), (120080, 1)):
            with self.subTest(cutoff=cutoff):
                snapshot = stream.snapshot(cutoff)
                self.assertEqual(snapshot.get_match_state()["score"], {"A": 0, "U": expected})
                value = snapshot.calculate_metric("goal_count", "U", 0, min(cutoff, 120000))
                self.assertEqual(value["value"], expected)

    def test_generator_cli_reproduces_bytes_in_two_independent_roots(self):
        expected = ARTIFACT.read_bytes()
        self.assertNotIn(b"\r\n", expected, "JSONL bytes must remain reproducible across Windows and Unix")
        with tempfile.TemporaryDirectory() as directory:
            for name in ("first", "second"):
                destination = Path(directory) / name
                result = subprocess.run(
                    [sys.executable, "-X", "utf8", str(ROOT / "scripts" / "generate_stream_04.py"), "--root", str(destination)],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                generated = destination / "data" / "streams" / "stream-04.jsonl"
                self.assertEqual(generated.read_bytes(), expected)

    def assert_rejected(self, rows, fragment):
        errors = validate_records(rows)
        self.assertTrue(any(fragment in error for error in errors), "\n".join(errors))

    def test_intercepted_pass_cannot_become_a_success(self):
        rows = self.load_rows()
        next(row for row in rows if row["id"] == "e006")["outcome"] = "complete"
        self.assert_rejected(rows, "incorrect completion outcome")

    def test_incomplete_pass_cannot_give_a7_the_ball(self):
        rows = self.load_rows()
        frame = next(row for row in rows if row["record_type"] == "tracking" and row["event_time_ms"] == 18000)
        frame["ball"]["owner_id"] = "A7"
        self.assert_rejected(rows, "incomplete pass must not be delivered to A7")

    def test_completed_pass_must_reach_the_named_receiver(self):
        rows = self.load_rows()
        frame = next(row for row in rows if row["record_type"] == "tracking" and row["event_time_ms"] == 85500)
        receiver = next(player for player in frame["players"] if player["player_id"] == "U9")
        receiver["y"] += 2
        self.assert_rejected(rows, "completed pass misses its receiver")

    def test_all_22_players_are_required_in_every_frame(self):
        rows = self.load_rows()
        frame = next(row for row in rows if row["record_type"] == "tracking")
        frame["players"] = [p for p in frame["players"] if p["player_id"] != "A11"]
        self.assert_rejected(rows, "every frame must contain 22")

    def test_a_defender_cannot_teleport(self):
        rows = self.load_rows()
        frame = next(row for row in rows if row["record_type"] == "tracking" and row["event_time_ms"] == 84000)
        next(p for p in frame["players"] if p["player_id"] == "A4")["x"] = 90
        self.assert_rejected(rows, "exceeds 11 m/s")

    def test_review_time_cannot_count_as_live_possession(self):
        rows = self.load_rows()
        frame = next(row for row in rows if row["record_type"] == "tracking" and row["event_time_ms"] == 104000)
        frame["possession_team_id"] = "U"
        self.assert_rejected(rows, "VAR/celebration time must not be live football possession")

    def test_earlier_events_cannot_reference_the_final_decision(self):
        rows = self.load_rows()
        row = next(row for row in rows if row.get("type") == "pressure")
        final = next(row for row in rows if row.get("type") == "decision" and row.get("outcome") == "goal_awarded")
        row["evidence_ids"] = [final["id"]]
        self.assert_rejected(rows, "reveals a record not yet received")

    def test_missing_evidence_is_rejected(self):
        rows = self.load_rows()
        next(row for row in rows if row.get("type") == "pressure")["evidence_ids"] = ["missing-record"]
        self.assert_rejected(rows, "missing referenced record")

    def test_official_cannot_impersonate_a_player(self):
        rows = self.load_rows()
        flag = next(row for row in rows if row.get("type") == "offside_flag")
        flag.update(player_id="U9", team_id="U")
        self.assert_rejected(rows, "officials must not impersonate")

    def test_official_must_have_the_correct_role(self):
        for identifier, wrong_official in (("o001", "R1"), ("d002", "AR1"), ("v002", "R1")):
            with self.subTest(identifier=identifier):
                rows = self.load_rows()
                next(row for row in rows if row["id"] == identifier)["official_id"] = wrong_official
                self.assert_rejected(rows, "incorrect official role")

    def test_declared_official_roles_must_be_preserved(self):
        rows = self.load_rows()
        rows[0]["officials"][0]["role"] = "assistant_referee"
        self.assert_rejected(rows, "incorrect official role")

    def test_official_subject_must_belong_to_the_stated_team(self):
        rows = self.load_rows()
        next(row for row in rows if row["id"] == "o001")["subject_team_id"] = "A"
        self.assert_rejected(rows, "official subject/team mismatch")

    def test_official_positions_must_be_explicitly_unavailable(self):
        rows = self.load_rows()
        next(row for row in rows if row["id"] == "o001").update(
            position_status="observed", position={"x": 50, "y": 0})
        self.assert_rejected(rows, "official position must be null/unavailable")

    def test_illegal_body_part_position_breaks_offside_evidence(self):
        rows = self.load_rows()
        frame = next(row for row in rows if row["record_type"] == "tracking" and row["event_time_ms"] == 83000)
        frame["body_parts"]["U9"]["head"]["x"] = 32
        self.assert_rejected(rows, "U9 must be 0.6 m behind")

    def test_clean_sliding_tackle_needs_contact_and_no_foul_facts(self):
        for missing in ("ball_contact", "foul"):
            with self.subTest(missing=missing):
                rows = self.load_rows()
                tackle = next(row for row in rows if row.get("type") == "tackle")
                tackle.pop(missing)
                self.assert_rejected(rows, "ball-contact evidence" if missing == "ball_contact" else "no-foul fact")

    def test_duplicate_confirmation_cannot_add_a_second_goal(self):
        rows = self.load_rows()
        goal_index = next(i for i, row in enumerate(rows) if row.get("type") == "goal")
        duplicate = dict(rows[goal_index], id="duplicate-confirmation")
        rows.insert(goal_index + 1, duplicate)
        self.assert_rejected(rows, "confirmed goal count must be 1")

    def test_shot_release_cannot_include_the_future_outcome(self):
        rows = self.load_rows()
        next(row for row in rows if row.get("type") == "shot")["outcome"] = "goal"
        self.assert_rejected(rows, "release must not contain its future result")

    def test_var_stage_cannot_be_omitted(self):
        rows = self.load_rows()
        rows = [row for row in rows if row.get("stage") != "on_field_review_completed"]
        self.assert_rejected(rows, "five approved stages")

    def test_var_cannot_review_the_flag_time_instead_of_the_release(self):
        rows = self.load_rows()
        evidence = next(row for row in rows if row.get("stage") == "evidence_ready")
        evidence["evidence_event_time_ms"] = 90500
        self.assert_rejected(rows, "83-second release")


if __name__ == "__main__":
    unittest.main()
