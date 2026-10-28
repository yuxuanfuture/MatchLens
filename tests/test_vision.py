import unittest
from backend.vision import PitchCalibration, EventExtractor


class VisionTests(unittest.TestCase):
    def test_calibrated_video_tracks_produce_pass_distance_and_speed(self):
        calibration=PitchCalibration([[0,0],[1050,0],[1050,680],[0,680]],[[0,0],[105,0],[105,68],[0,68]])
        self.assertAlmostEqual(calibration.map([500,340])[0],50)
        detector=EventExtractor('test')
        rows=[]
        positions=[10,10,10,15,20,25,30,35,40,40,40,40]
        for i,x in enumerate(positions):
            rows.extend(detector.update(i*100,[{'player_id':'A7','x':10.,'y':34.},{'player_id':'A9','x':40.,'y':34.}],{'x':float(x),'y':34.},True))
        passes=[r for r in rows if r.get('type')=='pass']
        self.assertEqual(len(passes),1)
        self.assertEqual(passes[0]['player_id'],'A7')
        self.assertEqual(passes[0]['receiver_id'],'A9')
        self.assertAlmostEqual(passes[0]['distance_m'],30)
        self.assertGreater(passes[0]['average_speed_mps'],20)


if __name__=='__main__':unittest.main()

class VisionBoundaryTests(unittest.TestCase):
 def test_missing_ball_breaks_pass_chain(self):
  d=EventExtractor();people=[{'player_id':'A7','x':10,'y':34},{'player_id':'A9','x':40,'y':34}]
  rows=[]
  for t,x in [(0,10),(100,10),(200,10),(300,20),(400,None),(500,40),(600,40),(700,40)]:
   rows+=d.update(t,people,{'x':x,'y':34} if x is not None else None)
  self.assertFalse(any(r['type']=='pass' for r in rows))

 def test_shot_flight_does_not_invent_score(self):
  d=EventExtractor();rows=[]
  for i,x in enumerate([87,87,87,89,92,95,98,101,104]):rows+=d.update(i*100,[{'player_id':'A9','x':87,'y':34}],{'x':x,'y':34})
  self.assertEqual([r['type'] for r in rows],['shot','shot_end'])
  self.assertNotIn('outcome',rows[0]);self.assertEqual(rows[0]['observed_at_ms'],800)

 def test_degenerate_calibration_is_rejected(self):
  with self.assertRaises(ValueError):PitchCalibration([[0,0],[1,1],[2,2],[3,3]],[[0,0],[10,10],[20,20],[30,30]])

 def test_vision_inference_forbids_network(self):
  from backend.vision import network_disabled
  import socket
  with network_disabled(),socket.socket() as connection:
   with self.assertRaisesRegex(RuntimeError,'offline'):connection.connect(('127.0.0.1',11434))

class ShortOcclusionTests(unittest.TestCase):
 def test_well_observed_flight_survives_one_short_ball_occlusion(self):
  d=EventExtractor();rows=[];players=[{'player_id':'A7','x':10,'y':34},{'player_id':'A9','x':40,'y':34}]
  for i,x in enumerate([10,10,10,14,18,22,26,None,34,38,40,40,40]):
   rows+=d.update(i*100,players,{'x':x,'y':34} if x is not None else None)
  passes=[r for r in rows if r['type']=='pass'];self.assertEqual(len(passes),1)
  self.assertEqual(passes[0]['outcome'],'complete');self.assertTrue(passes[0]['short_occlusion'])
  self.assertEqual(passes[0]['distance_m'],30)
  self.assertIsNone(passes[0]['average_speed_mps'])

class AutomaticCalibrationTests(unittest.TestCase):
 def test_pitch_keypoints_recover_known_scale_and_reject_bad_landmarks(self):
  from backend.vision import calibration_from_keypoints
  points=[[0.,0.] for _ in range(32)];confidence=[0.]*32
  for i,point in {0:[0,0],5:[0,680],24:[1050,0],29:[1050,680],13:[525,0],30:[433.5,340],31:[616.5,340],8:[900,900]}.items():points[i]=point;confidence[i]=.95
  c=calibration_from_keypoints(points,confidence)
  self.assertIsNotNone(c);self.assertAlmostEqual(c.map([500,340])[0],50,places=3)
  self.assertAlmostEqual(c.map([500,340])[1],34,places=3)
  self.assertLess(c.landmarks,8)
 def test_confident_but_collinear_keypoints_do_not_establish_a_pitch(self):
  from backend.vision import calibration_from_keypoints
  points=[[0.,0.] for _ in range(32)];confidence=[0.]*32
  for i in [13,14,15,16]:points[i]=[500,i*10];confidence[i]=1
  self.assertIsNone(calibration_from_keypoints(points,confidence))

class CalibrationContinuityTests(unittest.TestCase):
 def test_adjacent_frame_refit_cannot_teleport_the_pitch(self):
  from backend.vision import stable_calibration
  old=PitchCalibration([[0,0],[1050,0],[1050,680],[0,680]],[[0,0],[105,0],[105,68],[0,68]])
  jumped=PitchCalibration([[0,0],[1050,0],[1050,680],[0,680]],[[20,0],[100,0],[100,68],[20,68]])
  selected=stable_calibration(old,jumped,[[200,200],[500,400],[800,300],[500,200]])
  self.assertAlmostEqual(selected.map([500,340])[0],50)

class PitchDetectionSelectionTests(unittest.TestCase):
 def test_invalid_high_confidence_pitch_cannot_hide_a_valid_second_detection(self):
  from backend.vision import select_pitch_calibration
  invalid={'xy':[[0,0]]*32,'confidence':[.99]*3+[0.]*29}
  points=[[0.,0.] for _ in range(32)];confidence=[0.]*32
  for i,point in {0:[0,0],5:[0,680],24:[1050,0],29:[1050,680],13:[525,0],30:[433.5,340]}.items():points[i]=point;confidence[i]=.9
  c=select_pitch_calibration([invalid,{'xy':points,'confidence':confidence}])
  self.assertIsNotNone(c);self.assertAlmostEqual(c.map([610,340])[0],61,places=5)

class RecordedVisionRegressionTests(unittest.TestCase):
 def test_actual_pretrained_tracks_yield_passes_without_fabricating_occluded_speed(self):
  import json
  from pathlib import Path
  fixture=json.loads((Path(__file__).parent/'fixtures/observed_ground_tracks.json').read_text());d=EventExtractor();events=[]
  for f in fixture['frames']:events+=d.update(f['time_ms'],f['players'],f['ball'])
  passes=[e for e in events if e['type']=='pass']
  self.assertEqual([e['event_time_ms'] for e in passes],[1840,4000,8560])
  self.assertEqual([e['distance_m'] for e in passes],[12.64,15.88,9.75])
  self.assertTrue(all(e['average_speed_mps'] is None for e in passes if e['short_occlusion']))
  self.assertFalse(any(e['type']=='goal' for e in events))

class UnknownDirectionTests(unittest.TestCase):
 def test_unknown_direction_preserves_distance_without_inventing_forward_or_shots(self):
  import json
  from pathlib import Path
  from backend.fixture_tools import FixtureStream,MatchTools
  tools=FixtureStream(Path(__file__).resolve().parents[1]/'data/streams/stream-01.jsonl').snapshot(68000)
  tools._metadata['direction_source']='unconfirmed';tools=MatchTools(tools._records,68000)
  state=tools.get_match_state()
  self.assertFalse(state['direction_known'])
  self.assertIsNone(state['teams'][0]['opponent_goal_x_m'])
  event=tools.query_events(0,68000,event_types=['pass'])['events'][0]
  self.assertGreater(event['derived']['travel_distance_m'],0)
  self.assertIsNone(event['derived']['attacking_progress_m'])
  for metric in ['backward_pass_count','high_recovery_count']:
   fact=tools.calculate_metric(metric,'A',0,68000)
   self.assertEqual(fact['status'],'insufficient_data');self.assertIsNone(fact['value'])
  self.assertIsNone(tools.get_match_intelligence(0,68000)['teams']['A']['final_third_entries'])
  d=EventExtractor(directions={});events=[]
  for i,x in enumerate([87,87,87,89,92,95,98,101,104]):events+=d.update(i*100,[{'player_id':'A9','x':87,'y':34}],{'x':x,'y':34})
  self.assertFalse(any(e['type']=='shot' for e in events))
