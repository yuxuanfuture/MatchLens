import json
import string
import threading
import urllib.request
import unittest
from pathlib import Path

from backend.fixture_tools import FixtureStream
from backend.insights import publish, recap
from backend.server import AppServer

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ('en', 'zh', 'fr', 'es', 'ar')


class LocalizationTests(unittest.TestCase):
    def test_default_language_is_english(self):
        tools = FixtureStream(ROOT / 'data/streams/stream-01.jsonl').snapshot(68000)
        self.assertEqual(publish(tools)['preferences']['language'], 'en')

    def test_http_language_switch_preserves_time_role_and_evidence(self):
        server = AppServer(('127.0.0.1', 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, body=None):
            payload = json.dumps(body).encode('utf-8') if body is not None else None
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path, payload, {'Content-Type': 'application/json'})
            with opener.open(req, timeout=5) as response:
                return json.load(response)

        try:
            initial = request('/api/session', {'stream': 'stream-01', 'preferences': {'language': 'en', 'role': 'coach', 'mode': 'analyst'}})
            sid = initial['session_id']
            baseline = request('/api/control', {'session': sid, 'seek_ms': 68000, 'playing': False})
            texts = []
            for code in LANGUAGES:
                result = request('/api/control', {'session': sid, 'preferences': {'language': code}})
                self.assertEqual(result['as_of_ms'], 68000)
                self.assertEqual(result['preferences']['role'], 'coach')
                self.assertEqual(result['preferences']['mode'], 'analyst')
                self.assertEqual(result['facts'], baseline['facts'])
                self.assertEqual(result['story']['evidence_ids'], baseline['story']['evidence_ids'])
                self.assertEqual(result['model_calls'], 0)
                report = request('/api/recap?session=' + sid)
                self.assertEqual(report['preferences']['language'], code)
                texts.append(report['text'])
            self.assertEqual(len(set(texts)), 5)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_five_complete_catalogs_preserve_template_arguments(self):
        catalogs = {language: json.loads((ROOT / 'dist/locales' / f'{language}.json').read_text(encoding='utf-8')) for language in LANGUAGES}
        fields = lambda value: {field for _, field, _, _ in string.Formatter().parse(value) if field is not None}
        for language, catalog in catalogs.items():
            self.assertEqual(set(catalog), set(catalogs['en']), language)
            for key, value in catalog.items():
                self.assertIsInstance(value, str, (language, key))
                self.assertTrue(value.strip(), (language, key))
                self.assertEqual(fields(value), fields(catalogs['en'][key]), (language, key))

    def test_language_changes_text_without_changing_match_facts(self):
        tools = FixtureStream(ROOT / 'data/streams/stream-01.jsonl').snapshot(68000)
        baseline = publish(tools, {'language': 'en'})
        titles = []
        for language in LANGUAGES:
            for role in ('fan', 'coach', 'commentator'):
                result = publish(tools, {'language': language, 'role': role})
                self.assertEqual(result['facts'], baseline['facts'])
                self.assertEqual(result['story']['evidence_ids'], baseline['story']['evidence_ids'])
                self.assertEqual(result['as_of_ms'], 68000)
                self.assertEqual(result['model_calls'], 0)
            titles.append(result['story']['title'])
        self.assertEqual(len(set(titles)), 5)

    def test_every_metric_missing_data_and_recaps_use_requested_language(self):
        titles = {'fr': 'Une récupération mène à un tir', 'es': 'Una recuperación acaba en disparo', 'ar': 'استعادة الكرة تتحول إلى تسديدة'}
        for language, title in titles.items():
            tools = FixtureStream(ROOT / 'data/streams/stream-01.jsonl').snapshot(68000)
            self.assertEqual(publish(tools, {'language': language})['story']['title'], title)
            for metric in ('overview', 'passing', 'pressure', 'speed'):
                self.assertEqual(publish(tools, {'language': language, 'metric': metric})['preferences']['language'], language)
            missing = publish(FixtureStream(ROOT / 'data/streams/stream-03.jsonl').snapshot(58000), {'language': language})
            self.assertFalse(missing['tracking_available'])
            self.assertNotIn('Coverage gaps', missing['story']['fan_text'])
            self.assertNotIn('数据缺口', missing['story']['fan_text'])
            report = recap(tools, {'language': language})
            self.assertNotIn('Recap so far', report['text'])
            self.assertNotIn('截至当前', report['text'])
            self.assertEqual(report['counts']['goal'], 0)


if __name__ == '__main__':
    unittest.main()
