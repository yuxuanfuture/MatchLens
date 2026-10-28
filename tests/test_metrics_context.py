import copy,unittest
from backend.fixture_tools import FixtureStream,MatchTools
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class MetricsContextTests(unittest.TestCase):
 def test_possession_uses_observed_duration_not_sampling_density(self):
  source=FixtureStream(ROOT/'data/streams/stream-01.jsonl');metadata=copy.deepcopy(source._records[0]);rows=[metadata]
  for i,(t,team) in enumerate([(0,'A'),(100,'A'),(200,'A'),(1000,'U'),(1500,'U')]):
   rows.append({'id':f'tx{i}','record_type':'tracking','event_time_ms':t,'observed_at_ms':t,'match_id':metadata['match_id'],'players':[],'ball':None,'possession_team_id':team,'period':1})
  value=MatchTools(rows,1500).get_match_intelligence(0,1500)
  self.assertEqual(value['possession_time_pct'],{'A':66.7,'U':33.3})
  self.assertEqual(value['possession_observed_ms'],1500)
