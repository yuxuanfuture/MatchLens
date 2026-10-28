import unittest
from backend.server import Session
from backend.overlay import overlay_packet

class OverlayTests(unittest.TestCase):
 def test_overlay_has_expiry_clock_evidence_and_source(self):
  s=Session('stream-01');s.control({'seek_ms':68000})
  packet=overlay_packet(s.payload())
  self.assertEqual(packet['clock']['time_ms'],68000)
  self.assertEqual(packet['clock']['basis'],'source_media_ms')
  self.assertEqual(packet['source'],'offline_facts')
  self.assertTrue(all(c['start_ms']<=68000<c['end_ms'] for c in packet['cues']))
  self.assertTrue(all(c['evidence_ids'] for c in packet['cues'] if c['kind']!='narrative'))
  self.assertNotEqual(packet['cues'][0]['fan'],packet['cues'][0]['analyst'])
