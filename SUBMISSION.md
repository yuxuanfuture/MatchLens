# MatchLens Live — Submission Draft

## Elevator pitch

MatchLens Live transforms synthetic football events into explainable, personalized match intelligence that is ready to sit alongside a live broadcast. Instead of reporting only what happened, it identifies meaningful shifts in pressure, transition, shape, and momentum; explains why each moment matters; grounds every narrative in event-level evidence; and adapts the same intelligence for analysts, casual fans, favourite teams, individual players, and multiple languages.

## The problem

Live football produces a constant stream of events, but raw events and statistics do not automatically become a story. Broadcasters and streaming platforms need timely context without sacrificing accuracy, while different fans need different levels of depth.

## The solution

MatchLens Live implements one end-to-end pipeline:

1. Replays synthetic, football-realistic events as a live feed.
2. Calculates match state, pressure, possession, expected goals, and momentum.
3. Detects moments that materially change the match.
4. Produces claim-level evidence and an explainable narrative.
5. Renders synchronized broadcast overlays.
6. Personalizes depth, focus, and language for each viewer.

## Microsoft technology

The product is designed around Microsoft Foundry and Microsoft Agent Framework. The production pipeline separates signal analysis, tactical context, audience adaptation, and factual verification into distinct agent responsibilities with shared structured state. Azure Functions or Azure Container Apps provide the low-latency API layer, with telemetry captured in Application Insights.

> Final submission note: replace this paragraph with the exact deployed services and model names after the Foundry endpoint is connected and verified.

## Why it is different

MatchLens treats explainability as part of the viewer experience. Every on-screen claim is accompanied by the underlying metrics or event reference, while deterministic calculations remain separate from narrative generation. The same match moment can therefore become a dense tactical explanation for an analyst or a clear, emotional story for a casual fan without changing the facts.

## Category

Best Multi-Agent System

## Data disclosure

All match data, teams, players, scores, events, and metrics shown in the demo are synthetic and fictional. The project contains no broadcast footage, club marks, player likenesses, or copyrighted music.

