import copy
import unittest
from pathlib import Path
from backend.fixture_tools import FixtureStream
from backend.server import Session, ROOT


class LiveIngestTests(unittest.TestCase):
    def test_live_source_accepts_batches_atomically_and_updates_score(self):
        source=FixtureStream(ROOT/'data/streams/match-day.jsonl')._records
        metadata=copy.deepcopy(source[0])
        session=Session.from_records([metadata],live=True)
        goal=copy.deepcopy(next(r for r in source if r.get('type')=='goal'))
        session.ingest([goal],goal['observed_at_ms'])
        result=session.payload()
        self.assertEqual(result['state']['score'][goal['team_id']],1)
        self.assertEqual(result['source_mode'],'live')
        self.assertEqual(session.ingest([goal],goal['observed_at_ms'])['accepted'],0)
        count=result['received_records']
        invalid={**goal,'id':'invalid','player_id':'unknown'}
        valid={**goal,'id':'new-goal'}
        with self.assertRaises(ValueError): session.ingest([valid,invalid],goal['observed_at_ms'])
        self.assertEqual(session.payload()['received_records'],count)
        session.control({'seek_ms':0})
        self.assertEqual(sum(session.payload()['state']['score'].values()),0)


if __name__=='__main__': unittest.main()

class ControlAtomicityTests(unittest.TestCase):
 def test_invalid_control_does_not_partially_seek(self):
  s=Session('stream-01');before=s.payload()
  with self.assertRaises(ValueError):s.control({'seek_ms':60000,'speed':123})
  after=s.payload();self.assertEqual(after['as_of_ms'],before['as_of_ms']);self.assertEqual(after['epoch'],before['epoch'])
