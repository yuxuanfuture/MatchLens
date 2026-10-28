# MatchLens Pocket Stadium

[![CI](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml/badge.svg)](https://github.com/yuxuanfuture/MatchLens/actions/workflows/ci.yml)

MatchLens turns synthetic football events into evidence-linked match intelligence
and a personalized miniature stadium. It ingests events as they arrive, derives
deterministic football metrics, explains why a moment matters, renders synchronized
overlays, and adapts the same evidence for fans and analysts in five languages.

The default demo is fully offline. It does not require an API key, a model download,
an npm install, or a frontend build step.

## Demo scenario

The home page plays a 120-second added-time sequence at match time 90:00–92:00:

- Atlas builds an attack before a clean Union tackle.
- Union counters into a one-on-one and puts the ball in the net.
- An assistant raises the offside flag.
- VAR review progresses from the initial check to an on-field review.
- The goal is awarded only after the final decision arrives.

Useful replay positions are 72 seconds for the tackle, 86–90 seconds for the
counterattack and finish, 104 seconds for the on-field review, and 115 seconds for
the confirmed goal.

## Quick start

Requirements:

- Python 3.13 for the local service.
- A modern browser.
- Node.js 22 only if you want to run the JavaScript tests.

### macOS or Linux

```bash
python3 -m backend.server --port 43128
```

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\start-matchlens-windows.ps1
```

Open <http://127.0.0.1:43128/?lang=en>. Keep the terminal or background process
running. Opening `dist/index.html` directly cannot provide the event stream and
local APIs.

| Page | Local URL |
| --- | --- |
| Pocket Stadium | `http://127.0.0.1:43128/?lang=en` |
| Data and video tools | `http://127.0.0.1:43128/sources.html` |
| Broadcast overlay | `http://127.0.0.1:43128/overlay.html` |
| Service configuration | `http://127.0.0.1:43128/api/config` |

## What to try

1. Press **Replay** and seek through the tackle, counterattack, offside flag, VAR
   review, and confirmed goal.
2. Switch between Fan and Analyst modes. The fan receives a concise explanation;
   the analyst receives quantities, qualifications, and evidence identifiers.
3. Change language between English, Chinese, French, Spanish, and Arabic. Arabic
   uses right-to-left presentation without changing the underlying match facts.
4. Follow a club, player, role, or metric. The story, statistics, pitch highlight,
   and draggable module layout adapt to the selected audience.
5. Open **See the evidence** to inspect the observed records behind each claim.
6. Export the timed overlay JSON or open the transparent broadcast overlay.
7. Generate a recap of the observed interval. Seeking backward removes future
   goals, decisions, and evidence.

The crowd-audio controller is fault tolerant: a source clone runs silently when the
optional local soundtrack is absent. See [Optional soundtrack](#optional-soundtrack).

## Architecture

```text
synthetic JSONL arrival stream
            |
            v
EventStore -> frozen evidence + deterministic metrics
            |
            +-> offline fact publisher
            |
            +-> permission-gated multi-agent harness
                    coordinator / scout / tactics
                    verifier / audience / recap
            |
            v
timed story + evidence + coordinates + overlays
            |
            v
SSE -> Fan / Analyst UI + recap + broadcast output
```

The local server binds to `127.0.0.1` and requires a matching local origin for API
requests. Uploaded video and generated outputs stay under the ignored `run-output/`
directory.

## Microsoft and GitHub technology

This public source release uses the Microsoft-owned GitHub platform for repository
hosting, reviewable history, GitHub Actions continuous integration, and a GitHub CLI
release workflow. CI runs the reproducible offline acceptance suite on every push
and pull request.

The runtime agent harness is a custom, bounded orchestration implementation with
specialized roles, shared facts, explicit handoffs, independent verification,
failure recovery, request budgets, and stale-result cancellation.

Microsoft Foundry, Microsoft Agent Framework, and Azure are not integrated in this
version. The repository does not claim that they are. `docs/FOUNDRY_INTEGRATION.md`
is an integration contract for future work, not an implemented adapter.

## Model API policy

The checked-in policy is fail-closed: `config/model-policy.json` has model calls
disabled and a zero request budget. The offline demo remains functional in that
state.

Optional DeepSeek and local Ollama adapters exist for controlled evaluation. To use
one, the project owner must provide explicit authorization, configure a positive
request budget, and supply credentials locally. Credentials must never be committed.

Copy the template only when an authorized evaluation is required:

```bash
cp -n .env.example .env.local
```

Only `.env.local` or process environment variables may contain secrets. The browser
bundle does not receive provider credentials. See `backend/api_policy.py`,
`backend/model_providers.py`, and `docs/DEEPSEEK_SMOKE_TEST.zh-CN.md` for the exact
controls and test procedure.

## Optional local video inference

The basic stadium does not require computer-vision dependencies. The optional video
pipeline uses local Ultralytics, PyTorch, OpenCV, BoT-SORT, pitch calibration, and
checksum-verified detector weights.

Do not copy virtual environments between machines. Rebuild from the pinned files:

### macOS

Install `uv`, then run:

```bash
python3 scripts/setup_vision.py
./.venv-vision/bin/python -m backend.server --port 43128
```

### Windows

```powershell
py -3.13 scripts\setup_vision_windows.py
powershell -ExecutionPolicy Bypass -File .\start-video-windows.ps1
```

The setup scripts download dependencies and three detector weights, verify their
checksums, and store them in ignored local directories. Review the upstream license
terms before installation; see `THIRD_PARTY_NOTICES.md` and
`config/vision-model.json`.

This is an offline preprocessing path, not a claim of real-time broadcast-video
inference. Anonymous tracks require explicit roster binding before real names can be
shown. Projection speeds are estimates, and broad event-recall accuracy has not
been established.

## Optional soundtrack

The public source repository intentionally excludes the finished crowd soundtrack
and all source recordings. The local mix includes material whose license does not
permit redistribution as source assets.

The application degrades to silent replay when `dist/audio/stream-04-crowd.mp3` is
missing. If you have lawfully obtained the recordings and accepted their licenses,
you can rebuild the local soundtrack with:

```bash
python3 -m pip install -r requirements-audio.txt
python3 scripts/build_crowd_audio.py --source-dir /path/to/audio-sources
```

The cue plan and attribution links are in `data/stream-04-audio.json` and
`dist/audio/credits.html`. Do not commit the generated audio file.

## Verification

Run the complete source-repository acceptance suite without model calls:

```bash
python3 scripts/offline_acceptance.py
python3 scripts/api_acceptance.py
```

`offline_acceptance.py` validates all synthetic fixtures, runs the core Python
tests, and runs every browser-side Node test. Vision tests run automatically only
when a working optional vision environment is available; otherwise the report marks
them as skipped. Results are written to ignored files under `run-output/acceptance/`.

The API acceptance command is plan-only unless `--execute` is explicitly supplied.
Execution remains blocked while the checked-in policy is disabled.

## Evidence and limitations

- All clubs, players, positions, events, and scores are fictional synthetic data.
- No Premier League match footage, official data feed, club crest, or trademarked
  broadcast package is included.
- Names and shirt numbers come from the synthetic roster, not face recognition.
- Pass difficulty is a transparent heuristic, not a learned probability.
- Distance, speed, and possession use observed samples; missing frames remain
  missing rather than being silently interpolated.
- Sequence does not establish causation. Explanations preserve evidence windows and
  state explicit limitations.
- The current public demo uses deterministic offline explanations. Optional model
  quality and live latency are not claimed without a separately authorized run.

## Repository map

| Path | Purpose |
| --- | --- |
| `backend/` | Event ingestion, metrics, explanations, API policy, agent harness, local service, and optional vision worker |
| `dist/` | Browser application, renderer, overlay, localizations, fonts, icons, and generated visual assets |
| `data/` | Synthetic arrival streams, manifests, and audio cue plan |
| `evals/` | Fixture expectations and historical, clearly labelled evaluation artifacts |
| `scripts/` | Deterministic generators, validators, setup utilities, and acceptance commands |
| `tests/` | Python and browser-side regression tests |
| `docs/` | Engineering limits, contracts, setup notes, and design evidence |
| `case-design/` | Design rationale for the current 120-second scenario |

## License and third-party material

The original MatchLens code is publicly available for hackathon inspection,
evaluation, and testing under the repository's source-available `LICENSE`. Third-
party components remain under their own licenses. Review `THIRD_PARTY_NOTICES.md`
before redistributing or extending the project.
