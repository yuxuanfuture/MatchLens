"""Server-side model configuration. Secrets never enter model context or traces."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from backend.harness import ModelError, ModelOutputError
from backend.api_policy import APIBlocked, require_model_permission


def load_local_env(path):
    """Load only supported literal settings; process environment takes precedence."""
    allowed = {"MODEL_PROVIDER", "DEEPSEEK_API_KEY", "DEEPSEEK_MODEL"}
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or key not in allowed:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # Do not forward the Authorization header to a redirect destination.
        return None


class DeepSeekModel:
    provider = "deepseek"

    def __init__(self, api_key, model="deepseek-flash", base_url="https://api.deepseek.com"):
        if not isinstance(api_key, str) or not api_key.strip() or any(c in api_key for c in "\r\n"):
            raise ValueError("DEEPSEEK_API_KEY is missing or invalid")
        parsed = urllib.parse.urlsplit(base_url)
        if (parsed.scheme != "https" or parsed.netloc != "api.deepseek.com"
                or parsed.path.rstrip("/") not in {"", "/v1"} or parsed.query or parsed.fragment):
            raise ValueError("DeepSeek credentials may only be sent to the official HTTPS API endpoint")
        self._api_key = api_key.strip()
        self.model = model
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.last_usage = {}
        self.served_model = None

    def complete(self, messages, timeout):
        try:
            require_model_permission(self.provider, self._api_key)
        except APIBlocked as error:
            raise ModelError(str(error)) from None
        self.last_usage = {}
        review = any(message.get("role") == "system" and "\nRole: verifier." in message.get("content", "")
                     for message in messages)
        body = {"model": self.model, "messages": messages, "stream": False,
                "response_format": {"type": "json_object"},
                "thinking": {"type": "enabled" if review else "disabled"},
                "temperature": 0, "max_tokens": 8192 if review else 4096}
        if review:
            body["reasoning_effort"] = "low"
        request = urllib.request.Request(self.url, data=json.dumps(body, ensure_ascii=False).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self._api_key})
        try:
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
                raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ModelError("DeepSeek response exceeded 1 MB")
            envelope = json.loads(raw)
            choice = envelope["choices"][0]
            usage = envelope.get("usage", {})
            self.last_usage = {key: usage[key] for key in
                ("prompt_tokens", "completion_tokens", "total_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")
                if type(usage.get(key)) is int and usage[key] >= 0}
            self.served_model = envelope.get("model")
            if choice.get("finish_reason") != "stop":
                raise ModelOutputError("DeepSeek did not complete the JSON response")
            # Deliberately ignore reasoning_content and raw provider error bodies.
            result = json.loads(choice["message"]["content"])
            if not isinstance(result, dict):
                raise ModelOutputError("DeepSeek returned a non-object JSON action")
            return result
        except urllib.error.HTTPError as error:
            reasons = {400: "invalid request", 401: "authentication failed", 402: "insufficient balance",
                       403: "access denied", 429: "rate limited"}
            raise ModelError(f"DeepSeek HTTP {error.code}: {reasons.get(error.code, 'request failed')}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ModelError("DeepSeek endpoint unavailable or timed out") from None
        except (KeyError, IndexError, TypeError, ValueError):
            raise ModelOutputError("DeepSeek returned an invalid JSON action") from None
