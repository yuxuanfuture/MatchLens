# MatchLens Pocket Stadium

<p align="center">
  <strong>English</strong> ·
  <a href="README.zh-CN.md">简体中文</a> ·
  <a href="README.fr.md">Français</a> ·
  <a href="README.es.md">Español</a> ·
  <a href="README.ar.md">العربية</a>
</p>

**Watch MatchLens — the walkthrough shows the offline experience; API-backed agents
use the same interface.**

https://github.com/user-attachments/assets/7c19dc86-b2b1-4d1c-8126-0246e06f65e4

<h3 align="center">
  <a href="https://yuxuanfuture.github.io/MatchLens/">▶ Open Interactive Demo</a>
</h3>

<p align="center">Runs in the browser with synthetic scenarios; no server or API key required.</p>

[![CI](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml)

MatchLens turns observed football events into evidence-linked explanations and a
personalized miniature stadium. The same facts become concise storytelling for fans,
quantified context for analysts, and synchronized cues for broadcast overlays.

## Two ways to run

MatchLens is a runnable evidence and agent framework, not only a rendered product
walkthrough.

| Mode | What runs |
| --- | --- |
| **Offline** | Deterministic event processing, analytics, evidence, replay, localization, and UI. No model or API key is required. |
| **API-backed multi-agent** | DeepSeek or local Ollama drives the Coordinator and optional specialist roles; deterministic tools remain the source of numerical facts, and an independent Verifier reviews each candidate. |

Both modes use the same frozen observation window, evidence contract, Pocket Stadium,
and stale-result checks. A model can investigate and explain the match, but it cannot
invent records, advance the replay clock, or bypass the configured request budget.

## Why MatchLens

Football data is easy to count but hard to explain. MatchLens keeps each claim tied
to the event or tracking records that support it, respects what was observable at
that moment, and exposes uncertainty instead of filling gaps with invented facts.

The interface adapts one evidence stream for Fan and Analyst modes, English by
default plus Simplified Chinese, French, Spanish, and Arabic, followed teams or
players, a replayable Pocket Stadium, and a transparent broadcast overlay.

## Highlights

- **Evidence first:** explanations link back to received records and deterministic
  metrics; missing data remains missing rather than becoming zero.
- **Replay aware:** event time and arrival time are kept separate, so a replay cannot
  reveal a future goal or VAR decision.
- **Audience aware:** Fan and Analyst modes share facts but differ in language,
  density, focus, and presentation.
- **Multi-agent ready:** an optional bounded system can delegate investigation,
  verify claims independently, and discard stale results.
- **Portable demo:** the main experience runs locally with Python and a modern
  browser, without a frontend build step.

## Quick start: offline

Requirements: Python 3.13 and a modern browser. Node.js 22 is needed only for the
browser-side test suite.

### macOS or Linux

```bash
python3 -m backend.server --port 43128
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start-matchlens-windows.ps1
```

Open <http://127.0.0.1:43128/?lang=en>. The local service must remain running because
it provides the event stream, evidence APIs, and replay controls.

## Connect a model provider

The repository includes adapters for the official DeepSeek API and a loopback Ollama
service. The checked-in policy intentionally fails closed, so adding a key alone does
not make a request. To activate API-backed investigations:

1. Configure the provider locally: keep a DeepSeek key in the Git-ignored
   `.env.local`, or start an Ollama model on `127.0.0.1`.
2. Create an explicit, bounded provider grant in `config/model-policy.json`.
3. Start the server for continuous event-batched investigations, or run
   `scripts/run_harness.py` against a frozen stream snapshot.

See **[Model API setup](docs/MODEL_API_SETUP.md)** for working DeepSeek and Ollama
commands, the policy fields, budget behavior, and shutdown steps. Secrets never enter
the browser, prompts, traces, or committed files.

## Demo

The primary scenario is a 120-second added-time sequence: a clean tackle launches a
counterattack, a one-on-one finish is flagged offside, VAR progresses to an on-field
review, and the goal is awarded only after the final decision becomes observable.

Try switching between Fan and Analyst modes, changing language, following a player,
opening **See the evidence**, generating a recap, and seeking backward to confirm that
future outcomes disappear.

## Multi-agent system

The product does not require a model to run. When the fail-closed model policy is
explicitly enabled, the same frozen evidence tools can be used by a bounded
multi-agent investigation system:

![MatchLens multi-agent system architecture](docs/architecture/multi-agent-system-v3.svg)

Only the coordinator may delegate. Every non-empty candidate receives an independent
review, all numerical claims must come from deterministic tools, and results from an
old seek, preference state, or evidence window are discarded. DeepSeek and local
Ollama adapters are optional; the checked-in policy disables model calls by default.

## Verification

Run the complete offline acceptance suite:

```bash
python3 scripts/offline_acceptance.py
```

It validates the synthetic fixtures, runs the Python tests, and runs the browser-side
Node tests without making a model API request. GitHub Actions runs the same acceptance
path on every push and pull request.

## Project structure

| Path | Purpose |
| --- | --- |
| `backend/` | Event service, deterministic analytics, evidence tools, optional agent harness, and local video workers |
| `dist/` | Pocket Stadium, renderer, localization, data tools, and broadcast overlay |
| `data/` | Reproducible synthetic streams, manifests, and audio cue plans |
| `evals/` | Fixture expectations and clearly labelled historical evaluation runs |
| `scripts/` | Dataset generation, validation, environment setup, and acceptance commands |
| `tests/` | Python and browser-side regression tests |
| `docs/` and `case-design/` | Engineering contracts, setup guides, limitations, and scenario rationale |

## Documentation

- [Multi-agent design](docs/HARNESS_PLAN.zh-CN.md)
- [Model API setup](docs/MODEL_API_SETUP.md)
- [Event stream and broadcast overlay](docs/STREAM_AND_OVERLAY.md)
- [Synthetic data contract](data/README.md)
- [Offline acceptance guide](docs/OFFLINE_ACCEPTANCE.zh-CN.md)
- [Optional local video inference](docs/WINDOWS_VIDEO.zh-CN.md)
- [Engineering boundaries](docs/ENGINEERING_ACCEPTANCE.zh-CN.md)
- [Submission overview](SUBMISSION.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Boundaries and license

- All clubs, players, events, positions, and scores are fictional synthetic data.
- No Premier League footage, official data feed, club crest, or production partnership
  is included or claimed.
- The optional video path is offline preprocessing, not demonstrated real-time
  broadcast inference; anonymous tracks require explicit roster binding.
- The public repository excludes model weights, third-party source recordings, the
  generated crowd soundtrack, and machine-specific virtual environments.

The original MatchLens code is available for hackathon inspection, evaluation, and
testing under the repository's source-available [LICENSE](LICENSE). Third-party
components remain under their own licenses.
