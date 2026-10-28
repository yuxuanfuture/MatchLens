# Local feed and rendering contracts

Run `python3 -m backend.server --port 43128`. All endpoints accept only the local origin. The browser cannot provide an API key or change the model policy.

## Event source

Use `data/streams/stream-01.jsonl` as a complete example. Every record has `schema_version`, `record_type`, `id`, `match_id`, `event_time_ms`, `observed_at_ms`. Coordinates are in metres on a 105 × 68 pitch. Metadata includes A/U team names and attack direction, roster IDs/names/shirt numbers, initial score, match clock origin and per-channel coverage. Event IDs remain stable across retransmission. Future event time and future arrival time are both hidden.

`POST /api/session` accepts `{records:[metadata,...],live:false,preferences:{...}}` for a replay, or `{records:[metadata],live:true}` for continuous ingestion. `POST /api/ingest` accepts `{session,records:[...],received_at_ms}`. It validates the entire batch before changing state. Identical IDs are idempotent; conflicting IDs, unknown actors and impossible coordinates are rejected. Missing channels require coverage records, not fabricated zero counts.

```bash
python3 scripts/push_stream.py data/streams/stream-01.jsonl --speed 16
```

This emits actual arrival batches and prints a viewer URL. Local connection failures retry the same IDs safely. It never invokes a model itself; the server's independently approved policy controls any harness scheduling.

## Observation and control

- `GET /api/state?session=...`: current frozen payload, preferences, story, statistics, coverage, coordinates, evidence and API lock status.
- `GET /api/stream?session=...`: SSE, monotonic epoch/sequence; keepalives plus state heartbeat.
- `POST /api/control`: `{session,seek_ms?,media_time_ms?,playing?,speed?,preferences?}`. A seek invalidates old investigations. Small forward video-clock updates do not. Speeds: 1/4/16/60.
- `GET /api/recap?session=...`: evidence recap. After model authorization, starts a bounded recap investigation; `agent_status` reports progress. Re-fetch after completion for the reviewed text.
- `GET /api/evidence?session=...&id=e018&id=e022`: visible original records.

## Broadcast cues

`GET /api/overlay?session=...` returns `schema_version: matchlens.overlay/1.0`, epoch, sequence, source and an explicit clock `{basis:source_media_ms,time_ms,match_clock_offset_ms,playing,speed}`. Every cue has ID, kind, start/end milliseconds and evidence IDs. Narrative cues provide both Fan and Analyst text; shape cues contain metre-coordinate geometry.

Open `/overlay.html?session=...` to add a local video and a media offset. The player clock drives the event session. Use `transparent=1&mode=fan` for an OBS browser source. A producer or another player must drive that session's clock. Stale cues expire; backward seeks use a new epoch. This is an interoperable browser/JSON output, not a claimed integration with Microsoft's rendering partner.

## Local vision jobs

`POST /api/video/upload` with raw bytes → upload ID. Max 250 MB, 8 uploads per server session. `/api/video/start` accepts `{upload_id,config}`; one worker runs at a time. `/api/video/status?job=...`, `/api/video/cancel`, `/api/video/detections?job=...`, `/api/video/records?job=...`, and `/api/video/session` expose progress, cancellation, observed output and a normal replay session.

The worker is a separate Python process with network connections disabled. Dependencies and pinned model weights are installed explicitly using `python3 scripts/setup_vision.py`; no runtime download, training, or model endpoint. Default device is Apple MPS; set `device:"cpu"` or `"0"` for another supported environment. Configure at most 600 seconds and 5–25 sampled frames per second. The source media timestamps are retained even when sampling is slower than the frame rate. All outputs are local under `run-output/video-jobs/`.


Vision configuration supports `auto_pitch:true` (default), `image_points` and `pitch_points` (at least four non-collinear corresponding anchors), `camera_motion:true`, `ball_confidence:0.4`, and optional `identities:{"3":{"name":"Known player","number":7}}`. Optional `team_directions:{"A":1,"U":-1}` confirms which end each team attacks; optional `initial_score:{"A":0,"U":0}` confirms the score. The A/U team assignment comes from local jersey-colour clustering, so confirm it against detections before binding identities or directions. Without direction/score metadata, state marks them unconfirmed and directional statistics/shot classification are withheld. Automatic pitch detection uses pinned local landmark weights; it does not call an external service. Cuts, invalid geometry and missing ball observations interrupt measurements. Well-observed flights may preserve a pass hypothesis across at most 240 ms of occlusion, with speed left null. Inferred event/pressure coverage remains incomplete even when positional observations exist.
