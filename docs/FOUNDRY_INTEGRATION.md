# Microsoft Foundry Integration Contract

The browser demo must never contain a model key. Connect it to a server-side Azure Function or Container App that owns the Microsoft Foundry credentials.

## Proposed endpoint

`POST /api/insight`

### Request

```json
{
  "trace_id": "TRC-6227-11",
  "viewer": {
    "audience": "analyst",
    "language": "en",
    "focus": "match"
  },
  "match_state": {
    "clock": "62:27",
    "score": [1, 0],
    "possession": [63, 37],
    "xg": [0.72, 0.0],
    "momentum": 94
  },
  "event_window": [
    {
      "event_id": "evt_006",
      "type": "interception",
      "player": "H7",
      "position": [70, 56]
    }
  ]
}
```

### Response

```json
{
  "status": "verified",
  "kicker": "WHY IT MATTERS",
  "headline": "The finish is the last step of a 23-second press",
  "narrative": "Northbridge score before Riverside complete a progressive pass after the pressure begins.",
  "confidence": 0.99,
  "evidence": [
    { "claim": "23-second press", "event_ids": ["evt_002", "evt_004", "evt_006", "evt_011"] },
    { "claim": "0 progressive passes", "metric": "progressive_passes", "value": 0 }
  ]
}
```

## Recommended agent responsibilities

### Signal Analyst

- Consumes only structured events and deterministic match-state metrics.
- Ranks candidate moments by change, rarity, and audience relevance.
- Does not write final viewer-facing language.

### Context Agent

- Compares the current window with the preceding match state.
- Identifies tactical explanations and milestones.
- Must reference exact input metrics or event IDs.

### Audience Agent

- Changes depth, terminology, language, and focus.
- Must not add new factual claims.

### Verifier

- Rejects unsupported claims.
- Returns claim-level evidence.
- Falls back to deterministic copy when verification fails or latency is too high.

## Latency budget

```text
event aggregation      50 ms
signal ranking        100 ms
context generation    700 ms
audience adaptation   350 ms
verification          350 ms
network/render        250 ms
----------------------------
target total        <1800 ms
```

## Required environment variables

Use the exact variable names supported by the chosen Microsoft Foundry SDK and deployment. Do not commit their values.

```text
AZURE_AI_PROJECT_ENDPOINT
AZURE_AI_MODEL_DEPLOYMENT_NAME
```

Prefer managed identity in Azure. If a local development credential is temporarily required, keep it in an untracked `.env.local` file and rotate it before making the repository public.

