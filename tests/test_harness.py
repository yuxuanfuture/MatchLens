"""Harness control tests using explicitly scripted doubles, NOT model evaluation."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.fixture_tools import FixtureStream
from backend.harness import Budget, Harness, ModelError, ModelOutputError, OllamaModel, ROLES

ROOT = Path(__file__).resolve().parents[1]


class ScriptedModel:
    provider = 'contract_test_double'
    model = 'scripted_actions_no_inference'
    def __init__(self, steps):
        self.steps = list(steps)
        self.seen = []

    def complete(self, messages, timeout):
        role, response = self.steps.pop(0)
        assert f"Role: {role}." in messages[0]["content"]
        self.seen.append(copy.deepcopy(messages))
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


def final(result):
    return {"action": "final", "result": result}


def tool(name, **arguments):
    return {"action": "tool", "name": name, "arguments": arguments}


def verdict(approved=True):
    return final({"approved": approved, "issues": [] if approved else ["The draft invents a goal."],
                  "evidence_ids": ["e022"]})


def story(text="Atlas shot after regaining possession.", evidence=None, facts=None):
    return {"status": "publish", "claims": [{"kind": "observation", "text": text,
             "evidence_ids": ["e018", "e022"] if evidence is None else evidence,
             "fact_ids": facts or []}], "fan_text": text, "analyst_text": text}


IGNORE = final({"status": "ignore", "claims": [], "fan_text": "", "analyst_text": ""})


class HarnessTests(unittest.TestCase):
    def make(self, steps, time=68000, stream="01", **options):
        model = ScriptedModel(steps)
        snapshot = FixtureStream(ROOT / "data" / "streams" / f"stream-{stream}.jsonl").snapshot(time)
        return Harness(model, snapshot, **options), model

    def test_multiple_specialists_share_facts_and_observation(self):
        steps = []
        for role in ("scout", "tactics", "audience"):
            steps += [("coordinator", {"action": "delegate", "role": role, "task": "Inspect the observed play."}),
                      (role, final({"report": "An Atlas shot is observed.", "evidence_ids": ["e022"]}))]
        steps += [("coordinator", tool("calculate_metric", metric="regain_to_shot_seconds", team_id="A", start_ms=40000, end_ms=68000)),
                  ("coordinator", final(story("Atlas shot seven seconds after regaining possession.", facts=["f001"]))),
                  ("verifier", tool("get_evidence", record_ids=["e018", "e022"])),
                  ("verifier", verdict())]
        harness, model = self.make(steps)
        result = harness.run("Investigate")
        self.assertEqual(result["status"], "publish")
        self.assertEqual(result["facts"]["f001"]["value"], 7)
        self.assertEqual([r["role"] for r in harness.reports], ["scout", "tactics", "audience"])
        self.assertTrue(all(row["as_of_ms"] == 68000 for row in harness.trace))
        all_context = "\n".join(message["content"] for conversation in model.seen for message in conversation)
        for forbidden in ("stream-01", "fixture_expectations", "press_regain_shot", "e026"):
            self.assertNotIn(forbidden, all_context)
        self.assertEqual(model.steps, [])

    def test_registry_does_not_require_all_specialists(self):
        harness, _ = self.make([("coordinator", final(story())), ("verifier", verdict())],
                               roles={r: ROLES[r] for r in ("coordinator", "verifier")})
        self.assertEqual(harness.run("Investigate")["status"], "publish")
        self.assertFalse(any(row["kind"] == "delegate" for row in harness.trace))

    def test_batch_metrics_share_fact_ids_and_do_not_expose_future(self):
        request = {"metric": "shot_count", "team_id": "A", "start_ms": 40000, "end_ms": 68000}
        harness, _ = self.make([
            ("coordinator", tool("calculate_metrics", requests=[request, {**request, "metric": "regain_to_shot_seconds"}])),
            ("coordinator", tool("calculate_metric", **request)),
            ("coordinator", tool("calculate_metrics", requests=[{**request, "end_ms": 90000}])),
            ("coordinator", IGNORE)])
        result = harness.run("Investigate")
        self.assertEqual(len(result["facts"]), 2)
        self.assertEqual(result["facts"]["f001"]["value"], 1)
        self.assertEqual(result["facts"]["f002"]["value"], 7)
        self.assertEqual(sum(row["kind"] == "tool_error" for row in harness.trace), 1)

    def test_future_tools_and_file_tools_are_rejected(self):
        harness, _ = self.make([
            ("coordinator", tool("query_events", start_ms=0, end_ms=68000)),
            ("coordinator", tool("read_file", path="evals/fixture_expectations.json")),
            ("coordinator", IGNORE)], time=53000)
        self.assertEqual(harness.run("Investigate")["status"], "ignore")
        errors = [row for row in harness.trace if row["kind"] == "tool_error"]
        self.assertEqual(len(errors), 2)
        self.assertIn("future", errors[0]["result"]["error"])

    def test_future_evidence_and_uncomputed_facts_cannot_publish(self):
        harness, _ = self.make([
            ("coordinator", final(story(evidence=["e026"]))),
            ("coordinator", final(story(facts=["f999"]))),
            ("coordinator", IGNORE)])
        self.assertEqual(harness.run("Investigate")["status"], "ignore")
        self.assertEqual(sum(r["kind"] == "validation_error" for r in harness.trace), 2)
        self.assertFalse(any(r["kind"] == "review_requested" for r in harness.trace))

    def test_excerpt_counts_cannot_be_presented_as_full_match_stats(self):
        harness, _ = self.make([("coordinator", final(story("Union全场没有射门。"))), ("coordinator", IGNORE)])
        self.assertEqual(harness.run("Investigate")["status"], "ignore")
        self.assertTrue(any(r["kind"] == "validation_error" and "excerpt" in r["error"] for r in harness.trace))

    def test_scope_guard_allows_an_explicit_limitation(self):
        harness, _ = self.make([("coordinator", final(story("Atlas射门被扑出；片段不能代表全场表现。"))), ("verifier", verdict())])
        self.assertEqual(harness.run("Investigate")["status"], "publish")

    def test_regain_does_not_establish_tackle_or_causality(self):
        harness, _ = self.make([
            ("coordinator", final(story("A7完成抢断。"))),
            ("coordinator", final(story("压迫迫使对手丢球。"))), ("coordinator", IGNORE)])
        self.assertEqual(harness.run("Investigate")["status"], "ignore")
        self.assertEqual(sum(r["kind"] == "validation_error" for r in harness.trace), 2)

    def test_tackle_guard_allows_explaining_the_missing_mechanism(self):
        harness, _ = self.make([("coordinator", final(story("Atlas夺回球权，但无法确认是否通过抢断。"))), ("verifier", verdict())])
        self.assertEqual(harness.run("Investigate")["status"], "publish")

    def test_exact_revised_candidate_gets_reviewed_again(self):
        harness, _ = self.make([
            ("coordinator", final(story("Atlas scored."))), ("verifier", verdict(False)),
            ("coordinator", final(story("Atlas shot; the keeper saved it."))), ("verifier", verdict())])
        result = harness.run("Investigate")
        self.assertEqual(result["fan_text"], "Atlas shot; the keeper saved it.")
        drafts = [r["candidate"]["fan_text"] for r in harness.trace if r["kind"] == "review_requested"]
        self.assertEqual(drafts, ["Atlas scored.", "Atlas shot; the keeper saved it."])

    def test_repeated_rejection_degrades_without_publishing_draft(self):
        harness, _ = self.make([
            ("coordinator", final(story("Atlas scored."))), ("verifier", verdict(False)),
            ("coordinator", final(story("Atlas scored."))), ("verifier", verdict(False))])
        result = harness.run("Investigate")
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["reason"], "review_rejected_twice")
        self.assertEqual(result["claims"], [])
        self.assertEqual(result["fan_text"], "")

    def test_missing_metric_stays_null_in_shared_facts(self):
        candidate = story("Pressure coverage is unavailable in this interval.", evidence=[], facts=["f001"])
        candidate["status"] = "insufficient_evidence"
        candidate["claims"][0]["kind"] = "limitation"
        harness, _ = self.make([
            ("coordinator", tool("calculate_metric", metric="pressure_event_count", team_id="A", start_ms=40000, end_ms=68000)),
            ("coordinator", final(candidate)), ("verifier", verdict())], stream="03")
        result = harness.run("Investigate")
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertIsNone(result["facts"]["f001"]["value"])
        self.assertEqual(result["facts"]["f001"]["status"], "insufficient_data")

    def test_model_failure_has_honest_fallback(self):
        harness, _ = self.make([("coordinator", ModelError("endpoint unavailable"))])
        result = harness.run("Investigate")
        self.assertEqual(result["mode"], "basic_facts_only")
        self.assertEqual(result["state"]["score"], {"A": 0, "U": 0})
        self.assertEqual(result["usage"]["model_calls"], 1)
        self.assertFalse(any(r["kind"] == "review" for r in harness.trace))

    def test_invalid_model_json_has_only_one_retry_per_role(self):
        for responses, status in [([ModelOutputError("empty JSON"), IGNORE], "ignore"),
                                  ([ModelOutputError("empty JSON"), ModelOutputError("empty JSON")], "degraded")]:
            with self.subTest(status=status):
                harness, model = self.make([("coordinator", response) for response in responses])
                self.assertEqual(harness.run("Investigate")["status"], status)
                self.assertEqual(harness.model_calls, 2)
                self.assertEqual(model.steps, [])

    def test_global_budget_includes_specialist_calls(self):
        harness, _ = self.make([
            ("coordinator", {"action": "delegate", "role": "tactics", "task": "Inspect"}),
            ("tactics", tool("get_match_state"))], budget=Budget(model_calls=2))
        result = harness.run("Investigate")
        self.assertEqual(result["reason"], "model_call_budget")
        self.assertEqual(result["usage"]["model_calls"], 2)
        self.assertEqual(result["usage"]["tool_calls"], 1)

    def test_ollama_adapter_uses_json_inference_protocol(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({"message": {"content": json.dumps(IGNORE)}}).encode()
        with patch("backend.harness.require_model_permission"), patch("backend.harness.urllib.request.urlopen", return_value=response) as send:
            result = OllamaModel("already-installed").complete([{"role": "user", "content": "test"}], 5)
        request = send.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/chat")
        self.assertEqual(body["format"], "json")
        self.assertFalse(body["stream"])
        self.assertEqual(result, IGNORE)


if __name__ == "__main__":
    unittest.main()
