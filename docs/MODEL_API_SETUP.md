# Model API setup

MatchLens runs offline by default, but the same evidence pipeline can be connected to
the official DeepSeek API or a local Ollama service. The provider drives the
Coordinator and any delegated specialist roles; it does not replace event ingestion,
metric calculation, evidence lookup, replay-time filtering, or final stale-result
checks.

## Before enabling a provider

Model access is fail-closed. Every provider request must pass
`config/model-policy.json`, and the request budget is counted across server restarts.
The browser cannot submit a key, select a provider, or change this policy.

Only enable a provider when you control the account or local model and accept the
resulting cost, data transfer, and latency. Use synthetic or otherwise authorized
match data.

## 1. Configure a provider

### DeepSeek

Copy the local environment template:

```bash
cp .env.example .env.local
```

Edit `.env.local` and set a new credential locally:

```dotenv
DEEPSEEK_MODEL=deepseek-flash
DEEPSEEK_API_KEY=your-new-key
```

`.env.local` is ignored by Git. The adapter sends the credential only to the official
`https://api.deepseek.com` endpoint and refuses credential-bearing redirects.

### Ollama

Start Ollama on its default loopback endpoint and make sure the selected model is
available. For example:

```bash
ollama serve
ollama pull qwen3:8b
```

Ollama remains subject to the same explicit authorization and request budget as a
remote provider. It is not a bypass for the policy gate.

## 2. Create a bounded authorization grant

Edit `config/model-policy.json`. Preserve any existing `blocked_key_sha256` entries
and set the fields below. This is a fragment to merge into the existing file, not a
replacement for the complete policy:

```json
{
  "enabled": true,
  "approved_provider": "deepseek",
  "approval_note": "I approve a bounded local evaluation run.",
  "grant_id": "local-evaluation-1",
  "max_requests": 20
}
```

Use `"approved_provider": "ollama"` for a local Ollama run. Merge these fields into
the existing policy file rather than deleting its revoked-key list.

`max_requests` counts provider HTTP requests, including delegated roles, verification,
and bounded retries; it is not the number of match investigations. Usage is recorded
in the Git-ignored `config/model-policy.usage.sqlite3`. Use a new `grant_id` only when
you intentionally authorize a new budget.

## 3. Run the framework

### Continuous server path

For DeepSeek:

```bash
python3 -m backend.server --port 43128
```

For Ollama, provide the local model name to the server process:

```bash
OLLAMA_MODEL=qwen3:8b python3 -m backend.server --port 43128
```

Open <http://127.0.0.1:43128/?lang=en>. The server batches important observations,
runs the bounded investigation against a frozen snapshot, and publishes only current,
reviewed results to the existing interface.

### One frozen snapshot

DeepSeek:

```bash
python3 scripts/run_harness.py data/streams/stream-01.jsonl \
  --provider deepseek --model deepseek-flash --as-of-ms 68000 \
  --output run-output/deepseek-result.json
```

Ollama:

```bash
python3 scripts/run_harness.py data/streams/stream-01.jsonl \
  --provider ollama --model qwen3:8b --as-of-ms 68000 \
  --output run-output/ollama-result.json
```

The CLI and server use the same policy gate, evidence tools, role budgets, structured
action protocol, and independent verification step.

## Disable model access

Return the policy to its fail-closed state by changing these fields in the existing
file:

```json
{
  "enabled": false,
  "approved_provider": null,
  "max_requests": 0
}
```

Preserve the remaining policy fields, remove the local credential when it is no longer
needed, and restart the server. Offline facts, replay, evidence, and the UI continue to
work without a provider.

## Operational boundaries

- Numerical claims must originate from registered deterministic tools.
- Missing channels remain missing rather than being converted to zero.
- Only the Coordinator may delegate, and all roles share one run budget.
- Every non-empty candidate receives an independent review and at most one revision.
- Timeline seeks, preference changes, and evidence-window changes invalidate older
  results.
- Traces contain actions, tool results, evidence references, latency, and usage—not
  credentials or private model reasoning.

For the role protocol and current limitations, see
[Multi-agent design](HARNESS_PLAN.zh-CN.md).
