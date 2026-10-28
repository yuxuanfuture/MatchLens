# MatchLens Pocket Stadium — submission overview

## Elevator pitch

MatchLens transforms synthetic football events into evidence-linked match
intelligence and a personalized miniature stadium. It explains why a moment matters,
keeps uncertainty visible, and renders the same observed facts as concise fan
storytelling or quantified analyst insight in five languages.

## What we built

MatchLens provides one end-to-end pipeline:

1. **Ingest** synthetic passes, shots, tackles, possession changes, tracking
   samples, match metadata, and VAR decisions as arrival-ordered events.
2. **Interpret** the observed interval into deterministic football states and
   statistics without reading future events.
3. **Explain** pressure changes, transitions, chances, and decisions with explicit
   evidence identifiers and limitations.
4. **Render** a synchronized miniature stadium, timed JSON overlay, transparent
   broadcast view, animated commentator, and replay-aware recap.
5. **Personalize** language, role, club, player, metric, and draggable module layout
   so fans and analysts receive genuinely different presentations of the same facts.

The primary demo is a 120-second added-time sequence containing a clean tackle,
counterattack, one-on-one finish, offside flag, VAR review, and confirmed goal. The
score and celebration change only when the final decision becomes observable.

## Agentic design

The optional inference harness uses six specialized roles: coordinator, scout,
tactics, verifier, audience, and recap. Roles share frozen evidence, use bounded
tools, hand work to one another, and require independent review before publication.
Global request, tool, turn, and wall-clock budgets prevent runaway execution.
Results from an old seek, preference state, or evidence window are discarded.

The checked-in demo runs in deterministic offline mode, so judges can inspect the
complete product without an API key. Optional DeepSeek and local Ollama adapters are
present behind an explicit fail-closed authorization policy. Offline templates are
not represented as live model output.

## Microsoft and GitHub technology used

- Public GitHub repository for inspectable source and history.
- GitHub Actions for reproducible offline validation on every push and pull request.
- GitHub CLI for repository publication and release verification.

The runtime orchestration is custom. Microsoft Foundry, Microsoft Agent Framework,
and Azure are not integrated in this version and are not claimed.

## Technical implementation

- Python 3.13 local event service and standard-library HTTP/SSE transport.
- SQLite journals for local stories and persistent model-request budgets.
- Canvas-based browser renderer with no frontend build step.
- Deterministic synthetic datasets and arrival-time validators.
- Optional local PyTorch, Ultralytics, OpenCV, BoT-SORT, and pitch calibration path.
- English, Chinese, French, Spanish, and Arabic interfaces.
- Transparent overlay and machine-readable timed JSON export.

## Run and verify

```bash
python3 -m backend.server --port 43128
python3 scripts/offline_acceptance.py
```

Open `http://127.0.0.1:43128/?lang=en`. The repository README contains Windows
instructions, optional vision setup, the soundtrack policy, known limitations, and
the third-party notices.

## Boundaries

- All match data, clubs, players, events, and scores are fictional and synthetic.
- No Premier League footage, official feed, club marks, or production partnership is
  included or claimed.
- The optional video path is preprocessing rather than demonstrated real-time
  broadcast inference; broad event-recall accuracy is not claimed.
- The source repository omits third-party recordings, generated soundtrack bytes,
  model weights, and machine-specific virtual environments.
- Model quality and live latency are not claimed without a separately authorized
  evaluation run.

Repository: <https://github.com/yuxuanfuture/MatchLens>
