"""Transport and secret-boundary checks; no external model calls."""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.harness import ModelError
from backend.model_providers import DeepSeekModel, NoRedirect, load_local_env


class ProviderTests(unittest.TestCase):
    def setUp(self):
        guard = patch("backend.model_providers.require_model_permission")
        guard.start()
        self.addCleanup(guard.stop)

    def reply(self, content='{"action":"final","result":{}}', finish="stop"):
        return {"model": "deepseek-flash", "choices": [{"finish_reason": finish,
                "message": {"content": content, "reasoning_content": "must not be logged"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
                          "untrusted_extra": "must not be logged"}}

    def test_authenticated_json_request_and_sanitized_usage(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(self.reply()).encode()
        model = DeepSeekModel("unit-test-secret")
        with patch("backend.model_providers.urllib.request.build_opener", return_value=opener):
            result = model.complete([{"role": "user", "content": "Return a JSON action"}], 5)
        request = opener.open.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer unit-test-secret")
        self.assertNotIn("unit-test-secret", request.data.decode())
        self.assertEqual(body["model"], "deepseek-flash")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertEqual(model.last_usage, {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120})
        self.assertNotIn("reasoning_content", result)

    def test_http_failure_does_not_echo_provider_body_or_secret(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError("https://api.deepseek.com", 401,
            "unit-test-secret", {}, io.BytesIO(b'unit-test-secret'))
        with patch("backend.model_providers.urllib.request.build_opener", return_value=opener):
            with self.assertRaises(ModelError) as caught:
                DeepSeekModel("unit-test-secret").complete([], 5)
        self.assertEqual(str(caught.exception), "DeepSeek HTTP 401: authentication failed")

    def test_verifier_uses_low_effort_without_exposing_private_reasoning(self):
        opener = MagicMock()
        opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(self.reply()).encode()
        with patch("backend.model_providers.urllib.request.build_opener", return_value=opener):
            result = DeepSeekModel("unit-test-secret").complete([{"role": "system", "content": "Rules\nRole: verifier."}], 5)
        body = json.loads(opener.open.call_args.args[0].data)
        self.assertEqual(body["thinking"], {"type": "enabled"})
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertNotIn("must not be logged", json.dumps(result))

    def test_truncated_or_empty_response_fails_closed(self):
        for content, finish in [("", "stop"), ('{"action":', "length"), ("[]", "stop")]:
            with self.subTest(content=content):
                opener = MagicMock()
                opener.open.return_value.__enter__.return_value.read.return_value = json.dumps(self.reply(content, finish)).encode()
                with patch("backend.model_providers.urllib.request.build_opener", return_value=opener):
                    with self.assertRaises(ModelError):
                        DeepSeekModel("unit-test-secret").complete([], 5)

    def test_credentials_cannot_be_redirected_or_sent_to_another_host(self):
        for url in ("http://api.deepseek.com", "https://example.com", "https://api.deepseek.com@other.invalid", "https://api.deepseek.com/?token=x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                DeepSeekModel("unit-test-secret", base_url=url)
        self.assertIsNone(NoRedirect().redirect_request(None, None, None, None, None, "https://example.com"))

    def test_env_is_literal_allowlisted_and_does_not_override_process(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"MODEL_PROVIDER": "ollama"}, clear=True):
            path = Path(folder) / ".env.local"
            path.write_text('MODEL_PROVIDER=deepseek\nDEEPSEEK_API_KEY="literal-$(unused)"\nHOME=/unused\n')
            load_local_env(path)
            self.assertEqual(os.environ["MODEL_PROVIDER"], "ollama")
            self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "literal-$(unused)")
            self.assertNotIn("HOME", os.environ)


if __name__ == "__main__":
    unittest.main()
