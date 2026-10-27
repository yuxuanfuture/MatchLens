"""Acceptance at the replay session/API boundary for the approved slot 03 design."""
import unittest
import copy
import json
import threading
import urllib.request
from pathlib import Path

from backend.server import Session, AppServer
from backend.ingestion import validate_stream, validate_record
from backend.overlay import overlay_packet


class Stream04UITests(unittest.TestCase):
    def test_120_second_playback_starts_and_finishes_with_all_players(self):
        session = Session('stream-04')
        initial = session.payload()
        self.assertEqual(initial['playback']['duration_ms'], 120000)
        self.assertEqual(initial['playback']['position_ms'], 0)
        self.assertEqual(initial['state']['match_clock_ms'], 5400000)
        self.assertEqual(initial['as_of_ms'], 80)
        self.assertEqual(len(initial['tracking']['players']), 22)
        final = session.control({'seek_ms': 120080})
        self.assertEqual(final['playback']['position_ms'], 120000)
        self.assertEqual(final['state']['match_clock_ms'], 5520000)
        self.assertEqual(final['tracking']['event_time_ms'], 120000)
        self.assertEqual(final['state']['score'], {'A': 0, 'U': 1})

    def test_official_progress_and_score_rewind_together(self):
        session = Session('stream-04')
        expected = ((72080, 'none', 0), (90080, 'pending', 0),
                    (90580, 'flagged', 0), (92080, 'checking', 0),
                    (99080, 'review_requested', 0), (104080, 'reviewing', 0),
                    (114080, 'awaiting_decision', 0), (115079, 'awaiting_decision', 0),
                    (115080, 'awarded', 1), (92080, 'checking', 0))
        for cutoff, phase, goals in expected:
            with self.subTest(cutoff=cutoff):
                data = session.control({'seek_ms': cutoff})
                self.assertEqual(data['review']['phase'], phase)
                self.assertEqual(data['state']['score'], {'A': 0, 'U': goals})
                self.assertNotIn('g001', data['review']['evidence_ids'] if not goals else [])
                if goals:
                    self.assertIn('g001', data['review']['evidence_ids'])

    def test_confirmed_goal_is_fresh_and_global_in_all_languages(self):
        for language in ('zh', 'en', 'fr', 'es', 'ar'):
            with self.subTest(language=language):
                session = Session('stream-04', {'language': language, 'focus_team': 'A', 'metric': 'passing'})
                before = session.control({'seek_ms': 115079})
                self.assertFalse(any(o['kind'] == 'goal' for o in before['overlays']))
                data = session.control({'seek_ms': 115080})
                self.assertEqual(data['story']['topic'], 'review_awarded')
                self.assertTrue(data['story']['title'])
                self.assertIn('d002', data['story']['evidence_ids'])
                cue = next(o for o in data['overlays'] if o['kind'] == 'goal')
                self.assertEqual((cue['at_ms'], cue['end_ms']), (115000, 119000))
                self.assertEqual(cue['event_time_ms'], 90000)
                self.assertFalse(any(o['kind'] == 'goal' for o in session.control({'seek_ms': 119080})['overlays']))

    def test_import_accepts_officials_and_rejects_wrong_identity(self):
        rows = [json.loads(line) for line in (Path(__file__).resolve().parents[1] / 'data/streams/stream-04.jsonl').read_text(encoding='utf-8').splitlines()]
        validate_stream(rows)
        flag = next(row for row in rows if row.get('type') == 'offside_flag')
        for changes in ({'official_id': 'R1'}, {'subject_team_id': 'A'},
                        {'player_id': 'U9', 'team_id': 'U'},
                        {'position_status': 'observed', 'position': {'x': 50, 'y': 0}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_record({**copy.deepcopy(flag), **changes}, rows[0])

    def test_var_is_dead_ball_and_broadcast_uses_source_time(self):
        session = Session('stream-04')
        for cutoff in (104080, 116080, 120080):
            data = session.control({'seek_ms': cutoff})
            self.assertIsNone(data['state']['possession_team_id'])
            self.assertIs(data['state']['in_play'], False)
        packet = overlay_packet(session.control({'seek_ms': 115080}))
        self.assertEqual(packet['clock']['time_ms'], 115000)
        cue = next(c for c in packet['cues'] if c['kind'] == 'goal')
        self.assertEqual((cue['start_ms'], cue['end_ms']), (115000, 119000))
        self.assertIn('d002', cue['evidence_ids'])

    def test_body_part_detail_waits_for_received_var_evidence(self):
        session = Session('stream-04', {'focus_team': 'A', 'focus_player': 'A9', 'metric': 'speed'})
        early = session.control({'seek_ms': 83080})
        frame = next(r for r in early['evidence_records'] if r['id'] == 't166')
        self.assertNotIn('body_parts', frame)
        review = session.control({'seek_ms': 99080})
        frame = next(r for r in review['evidence_records'] if r['id'] == 't166')
        self.assertIn('body_parts', frame)

    def test_http_evidence_rewind_and_static_cache_contract(self):
        server = AppServer(('127.0.0.1', 0))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{server.server_port}'

        def request(path, body=None):
            data = json.dumps(body).encode() if body is not None else None
            req = urllib.request.Request(base+path, data, {'Content-Type': 'application/json'})
            with opener.open(req, timeout=5) as response:
                return json.load(response)

        try:
            with opener.open(base+'/pocket.js', timeout=5) as response:
                self.assertEqual(response.headers['Cache-Control'], 'no-cache')
            created = request('/api/session', {'stream': 'stream-04'})
            sid = created['session_id']
            request('/api/control', {'session': sid, 'seek_ms': 83080})
            early = request('/api/evidence?session='+sid+'&id=t166')
            self.assertNotIn('body_parts', early['records'][0])
            request('/api/control', {'session': sid, 'seek_ms': 115080})
            confirmed = request('/api/evidence?session='+sid+'&id=t166&id=d002')
            self.assertIn('body_parts', confirmed['records'][0])
            self.assertEqual(confirmed['records'][1]['outcome'], 'goal_awarded')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_cached_model_story_cannot_bypass_review_detail_timing(self):
        session = Session('stream-04')
        session.control({'seek_ms': 83080})
        fake = {'status': 'publish', 'as_of_ms': 83080, 'fan_text': 'Test',
                'analyst_text': 'Test analysis', 'claims': [{'evidence_ids': ['t166']}],
                'usage': {'model_calls': 0}, 'facts': {}}
        self.assertTrue(session.model_result(session.epoch, 83080, fake))
        data = session.payload()
        self.assertEqual(data['mode'], 'model_harness')
        self.assertNotIn('body_parts', data['evidence_records'][0])


if __name__ == '__main__':
    unittest.main()
