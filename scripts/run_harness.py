"""Run an inference-only investigation against a frozen synthetic observation."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.fixture_tools import FixtureStream
from backend.harness import Harness, OllamaModel
from backend.model_providers import DeepSeekModel, load_local_env


def main():
    load_local_env(ROOT / ".env.local")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stream", type=Path, help="JSONL stream; only currently visible records reach the model")
    parser.add_argument("--as-of-ms", type=int, default=68000)
    parser.add_argument("--provider", choices=["offline", "ollama", "deepseek"], default="offline")
    parser.add_argument("--model", help="Model identifier; DeepSeek defaults to deepseek-flash")
    parser.add_argument("--base-url", help="Provider URL; defaults to its official or local endpoint")
    parser.add_argument("--language", choices=["zh", "en"], default="zh")
    parser.add_argument("--focus-team", default="A")
    parser.add_argument("--focus-player")
    parser.add_argument("--task", default="Investigate the recent visible play. Decide what matters and why; produce grounded Fan and Analyst explanations, or abstain when appropriate.")
    parser.add_argument("--trace", type=Path, help="Optional JSONL log of actions, evidence, reviews and latency; no private reasoning")
    parser.add_argument("--output", type=Path, help="Save result JSON here and print only a compact status")
    args = parser.parse_args()
    if args.provider == "offline":
        from backend.insights import publish
        result = publish(FixtureStream(args.stream).snapshot(args.as_of_ms),
                         {"language": args.language, "focus_team": args.focus_team, "focus_player": args.focus_player})
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output)
            print(json.dumps({"mode": result["mode"], "model_calls": 0, "output": str(args.output)}))
        else:
            print(output)
        return 0
    if args.provider == "deepseek":
        try:
            model = DeepSeekModel(os.environ.get("DEEPSEEK_API_KEY"),
                                 args.model or os.environ.get("DEEPSEEK_MODEL", "deepseek-flash"),
                                 args.base_url or "https://api.deepseek.com")
        except ValueError as error:
            parser.error(str(error))
    else:
        if not args.model:
            parser.error("--model is required for Ollama")
        model = OllamaModel(args.model, args.base_url or "http://127.0.0.1:11434")
    snapshot = FixtureStream(args.stream).snapshot(args.as_of_ms)
    harness = Harness(model, snapshot)
    result = harness.run(args.task, {"language": args.language, "focus_team": args.focus_team,
                                     "focus_player": args.focus_player})
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "usage": result["usage"], "output": str(args.output)}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.trace:
        args.trace.parent.mkdir(parents=True, exist_ok=True)
        args.trace.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in harness.trace), encoding="utf-8")
    return 2 if result["status"] == "degraded" else 0


if __name__ == "__main__":
    raise SystemExit(main())
