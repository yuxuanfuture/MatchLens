# MatchLens Live

MatchLens Live turns a stream of synthetic, football-realistic events into explainable match intelligence, broadcast-ready overlays, and audience-specific narratives.

The repository is intentionally self-contained for reliable judging and recording. The default demo uses deterministic, evidence-grounded narrative fixtures so it works without secrets or network access. Its agent adapter contract is designed for a Microsoft Foundry or Microsoft Agent Framework backend before final submission.

## What the demo proves

- **Ingest** — replays structured passes, shots, pressures, turnovers, substitutions, and match metadata as a live stream.
- **Interpret** — updates possession, expected goals, pressure state, momentum, and spatial context.
- **Explain** — promotes only meaningful match-state changes and attaches evidence to every claim.
- **Render** — presents synchronized output as a broadcast-style overlay on a 2.5D tactical pitch.
- **Personalize** — switches between analyst and fan narratives, team/player focus, and English/Chinese output.

## Demo scenarios

1. **High press** — a 23-second pressing sequence creates a high-value regain and goal.
2. **Counter attack** — a defensive corner becomes a four-action goal in nine seconds.
3. **Momentum swing** — a substitution changes the attacking shape and produces an equaliser.

All clubs, players, event sequences, scores, and metrics are fictional and synthetic.

## Run locally

No package installation is required.

```bash
python3 -m http.server 43127 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:43127/`.

## Recording controls

- Click **Auto Director** to run all three scenarios in a record-ready sequence.
- Press `Space` to play or pause.
- Press `D` to toggle Auto Director.
- Press `R` to reset the current scene.
- Use the full-screen button before recording.

The interface is designed for a 16:9 capture at 1440×900 or 1920×1080.

## Architecture

```text
Synthetic event scenarios
          ↓
Live replay / ingestion engine
          ↓
Deterministic match-state calculations
          ↓
Signal → Context → Audience → Verifier pipeline
          ↓
Evidence-grounded insight JSON
          ↓
2.5D pitch + broadcast overlay + event trace
```

## Project structure

```text
dist/
  index.html             Product UI
  styles.css             Responsive broadcast visual system
  app.js                 Replay, stats, personalization, animation
  data/scenarios.js      Three synthetic match event streams
docs/
  FOUNDRY_INTEGRATION.md Agent endpoint contract
  VIDEO_SCRIPT.md        Sub-two-minute recording plan
SUBMISSION.md            Draft English project submission
```

## Synthetic data model

Each event contains a match clock, actor, event type, start and end coordinates, outcome, pressure state, momentum, and optional football-specific values such as xG, speed, or score.

```json
{
  "minute": 62,
  "second": 27,
  "team": "home",
  "type": "shot",
  "player": "H9",
  "start": [92, 34],
  "end": [101, 35],
  "success": true,
  "xg": 0.44,
  "pressure": 0.18,
  "momentum": 94,
  "score": [1, 0]
}
```

Coordinates use a 105×68 metre pitch. The visualization maps these coordinates into the SVG scene at runtime.

## Microsoft integration path

The final agent service should run server-side so credentials never reach the browser. See [`docs/FOUNDRY_INTEGRATION.md`](docs/FOUNDRY_INTEGRATION.md) for the request/response contract and grounding requirements.

Recommended Microsoft components:

- Microsoft Foundry for model and agent management
- Microsoft Agent Framework for role orchestration and handoffs
- Azure Functions or Azure Container Apps for the insight API
- Azure Cosmos DB or Fabric for event/state persistence
- Application Insights for latency, failures, and traceability

## Integrity and rights

- No Premier League footage, club marks, player likenesses, or third-party music are included.
- No real match feed is represented as synthetic.
- Numeric statistics are computed from the structured event stream, not invented by a language model.
- Narrative claims expose their supporting metrics and event references.
- Do not commit secrets. Use server-side environment variables for Foundry credentials.

