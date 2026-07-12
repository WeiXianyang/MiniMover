import json
import logging
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from fire_monitor.alarm_service import LoggingAlarmService
from fire_monitor.types import AlarmEvent

class AlarmTests(unittest.TestCase):
 def test_records_and_deduplicates(self):
  with tempfile.TemporaryDirectory() as d:
   svc=LoggingAlarmService(Path(d),logging.getLogger('alarm-test'))
   event=AlarmEvent('fire_1','confirmed_fire',datetime.now(timezone.utc),'reason',.9,'x.jpg',False)
   self.assertTrue(svc.report_confirmed_fire(event)); self.assertFalse(svc.report_confirmed_fire(event))
   smoke=AlarmEvent('fire_1','suspected_smoke',datetime.now(timezone.utc),'smoke',.8,'x.jpg',False)
   failed=AlarmEvent('fire_2','ai_unavailable',datetime.now(timezone.utc),'需人工介入',None,'x.jpg',False)
   svc.report_suspected_smoke(smoke); svc.report_ai_unavailable(failed)
   lines=[json.loads(x) for x in (Path(d)/'alarms.jsonl').read_text(encoding='utf-8').splitlines()]
   self.assertEqual([x['alarm_type'] for x in lines],['confirmed_fire','suspected_smoke','ai_unavailable'])

if __name__=='__main__': unittest.main()
