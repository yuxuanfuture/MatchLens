import unittest
from tests.test_harness import ScriptedModel,final,story,verdict,ROOT
from backend.fixture_tools import FixtureStream
from backend.harness import Harness

class AgentRuntimeTests(unittest.TestCase):
 def test_recap_runs_specialist_and_independent_review_with_scoped_memory(self):
  snapshot=FixtureStream(ROOT/'data/streams/stream-01.jsonl').snapshot(68000)
  model=ScriptedModel([('recap',final({'report':'Atlas regained possession then shot.','evidence_ids':['e018','e022']})),('coordinator',final(story())),('verifier',verdict())])
  harness=Harness(model,snapshot,history=[{'at_ms':53000,'text':'No shot yet'},{'at_ms':90000,'text':'Future must not leak'}])
  result=harness.run('Summarize observed play',kind='recap')
  self.assertEqual(result['status'],'publish')
  self.assertEqual(result['kind'],'recap')
  self.assertIn('No shot yet',model.seen[0][1]['content'])
  self.assertNotIn('Future must not leak',str(model.seen))
  self.assertEqual(model.steps,[])

if __name__=='__main__':unittest.main()

class CancellationAndBudgetTests(unittest.TestCase):
 def test_cancelled_run_makes_no_provider_call(self):
  snapshot=FixtureStream(ROOT/'data/streams/stream-01.jsonl').snapshot(68000)
  model=ScriptedModel([])
  result=Harness(model,snapshot,cancelled=lambda:True).run('Investigate')
  self.assertEqual(result['reason'],'cancelled')
  self.assertEqual(result['usage']['model_calls'],0)

 def test_approval_budget_survives_gate_reload(self):
  import tempfile,json,importlib
  from unittest.mock import patch
  from pathlib import Path
  from backend import api_policy
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'policy.json'
   path.write_text(json.dumps({'enabled':True,'approved_provider':'test','approval_note':'unit test only','max_requests':1}))
   with patch.object(api_policy,'POLICY_PATH',path):api_policy.require_model_permission('test')
   api_policy._used = 0  # A reset process counter must not reset the persisted grant.
   with patch.object(api_policy,'POLICY_PATH',path):
    with self.assertRaises(api_policy.APIBlocked):api_policy.require_model_permission('test')

class PublicationTests(unittest.TestCase):
 def test_unreferenced_quantity_cannot_reach_verifier(self):
  snapshot=FixtureStream(ROOT/'data/streams/stream-01.jsonl').snapshot(68000)
  from tests.test_harness import IGNORE
  model=ScriptedModel([('coordinator',final(story('Atlas recorded 9999 shots.'))),('coordinator',IGNORE)])
  h=Harness(model,snapshot);result=h.run('Investigate')
  self.assertEqual(result['status'],'ignore')
  self.assertTrue(any('quantity' in r.get('error','') for r in h.trace))

 def test_media_clock_progress_does_not_cancel_investigations_but_seek_does(self):
  from backend.server import Session
  s=Session('stream-01');s.control({'seek_ms':50000});epoch=s.epoch
  s.control({'media_time_ms':50250});self.assertEqual(s.epoch,epoch)
  s.control({'media_time_ms':30000});self.assertGreater(s.epoch,epoch)

class ServiceRecapTests(unittest.TestCase):
 def test_recap_service_publishes_verified_model_result_and_discards_after_seek(self):
  from backend.server import Session,Journal,investigate
  journal=Journal(':memory:');session=Session('stream-01',journal=journal);session.control({'seek_ms':68000})
  model=ScriptedModel([('recap',final({'report':'A shot after a regain.','evidence_ids':['e018','e022']})),('coordinator',final(story())),('verifier',verdict())])
  result=investigate(session,session.store.snapshot(68000,False),session.epoch,session.prefs,'recap',model)
  self.assertEqual(result['status'],'publish');self.assertEqual(session.make_recap()['source'],'model_harness')
  session.control({'seek_ms':0});self.assertEqual(session.make_recap()['source'],'offline_facts');journal.close()
