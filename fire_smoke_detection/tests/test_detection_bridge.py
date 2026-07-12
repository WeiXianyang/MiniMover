import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fire_monitor.types import build_fire_detections

class BridgeTests(unittest.TestCase):
 def test_converts_only_fire_classes(self):
  rows=[(0,0,0,0,.81,0),(0,0,0,0,.72,1),(0,0,0,0,.95,2)]
  result=build_fire_detections(['fire','smoke','person'],rows)
  self.assertEqual([(x.class_name,round(x.confidence,2)) for x in result],[('fire',.81),('smoke',.72)])
if __name__=='__main__':unittest.main()
