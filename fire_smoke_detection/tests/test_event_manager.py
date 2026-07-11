import logging
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from fire_monitor.config import FireMonitorConfig
from fire_monitor.event_manager import FireEventManager
from fire_monitor.types import AIReviewResult, AIResultKind, Detection, EventState

class Reviewer:
 def __init__(self): self.requests=[]; self.results=[]; self.busy=False
 def submit(self,r):
  if self.busy:return False
  self.busy=True; self.requests.append(r); return True
 def poll(self):
  x=self.results; self.results=[]
  if x:self.busy=False
  return x
 def close(self,join_timeout=1): self.busy=False
class Store:
 def __init__(self):self.saved=[];self.updated=[]
 def save(self,*args,**kw):
  p=Path(f"C:/fake/{args[0]}_{args[1]}_{args[2]}.jpg");self.saved.append((p,args,kw));return p
 def update_metadata(self,p,u):self.updated.append((p,u));return True
class Alarm:
 def __init__(self):self.fire=[];self.smoke=[];self.failed=[]
 def report_confirmed_fire(self,e):self.fire.append(e);return True
 def report_suspected_smoke(self,e):self.smoke.append(e);return True
 def report_ai_unavailable(self,e):self.failed.append(e);return True

def cfg():return FireMonitorConfig(ROOT,'https://x','/chat','k','m',30,2,2,5,10,30,60,10)

class EventManagerTests(unittest.TestCase):
 def setUp(self):
  self.r=Reviewer();self.s=Store();self.a=Alarm();self.m=FireEventManager(cfg(),self.r,self.s,self.a,.4,logging.getLogger('x'));self.frame=np.zeros((4,4,3),dtype=np.uint8);self.dt=datetime.now(timezone.utc)
 def hit(self,t,dets=None):self.m.process_frame(dets or [Detection('fire',.8)],self.frame,self.frame,t,self.dt)
 def trigger(self):
  for t in [0,.3,.6,.9,1.2]:self.hit(t)
 def test_trigger_requires_five_hits_in_window_and_counts_frame_once(self):
  for t in [0,.3,.6,.9]:self.hit(t,[Detection('fire',.8),Detection('smoke',.9)])
  self.assertEqual(self.m.state,EventState.IDLE);self.hit(1.2)
  self.assertEqual(self.m.state,EventState.AI_REVIEWING);self.assertEqual(len(self.r.requests),1);self.assertEqual(self.s.saved[0][1][2],'initial')
 def test_expired_and_irrelevant_hits_do_not_trigger(self):
  for t in [0,.5,1,1.5,2.1]:self.hit(t)
  self.assertEqual(self.m.state,EventState.IDLE)
  self.hit(2.2,[Detection('person',.9),Detection('fire',.2)]);self.assertEqual(self.m.state,EventState.IDLE)
 def test_ai_results_transition_and_alarm_once(self):
  self.trigger(); req=self.r.requests[-1];self.r.results=[AIReviewResult(req.event_id,req.review_id,True,1,AIResultKind.CONFIRMED_FIRE,.9,'fire')];self.hit(2)
  self.assertEqual(self.m.state,EventState.ALARMED_FIRE);self.assertEqual(len(self.a.fire),1);self.hit(3);self.assertEqual(len(self.a.fire),1)
 def test_no_fire_rereviews_at_thirty_seconds(self):
  self.trigger();req=self.r.requests[-1];self.r.results=[AIReviewResult(req.event_id,1,True,1,AIResultKind.NO_FIRE,.6,'no')];self.hit(2)
  self.hit(31.1);self.assertEqual(len(self.r.requests),1);self.hit(31.2);self.assertEqual(len(self.r.requests),2);self.assertEqual(self.s.saved[-1][1][2],'review')
 def test_failed_alarm_periodic_and_no_retry(self):
  self.trigger();req=self.r.requests[-1];self.r.results=[AIReviewResult(req.event_id,1,False,3,error='Timeout')];self.hit(2)
  self.assertEqual(self.m.state,EventState.AI_FAILED);self.assertEqual(len(self.a.failed),1);self.hit(61.1);self.assertEqual(len(self.s.saved),1);self.hit(61.2);self.assertEqual(len(self.s.saved),2);self.assertEqual(len(self.r.requests),1)
 def test_clear_after_ten_seconds(self):
  self.trigger();req=self.r.requests[-1];self.r.results=[AIReviewResult(req.event_id,1,True,1,AIResultKind.NO_FIRE,.5,'no')];self.hit(2)
  self.m.process_frame([],self.frame,self.frame,11.99,self.dt);self.assertNotEqual(self.m.state,EventState.IDLE)
  self.m.process_frame([],self.frame,self.frame,12.0,self.dt);self.assertEqual(self.m.state,EventState.IDLE)
 def test_inflight_disappearance_still_alarms_then_resets(self):
  self.trigger();req=self.r.requests[-1];self.m.process_frame([],self.frame,self.frame,11.2,self.dt);self.assertEqual(self.m.state,EventState.AI_REVIEWING)
  self.r.results=[AIReviewResult(req.event_id,1,True,1,AIResultKind.CONFIRMED_FIRE,.9,'fire')];self.m.process_frame([],self.frame,self.frame,12,self.dt)
  self.assertEqual(len(self.a.fire),1);self.assertTrue(self.a.fire[0].local_detection_gone);self.assertEqual(self.m.state,EventState.IDLE)
 def test_stale_result_ignored(self):
  self.trigger();self.r.results=[AIReviewResult('other',99,True,1,AIResultKind.CONFIRMED_FIRE,.9,'x')];self.hit(2);self.assertEqual(self.m.state,EventState.AI_REVIEWING);self.assertFalse(self.a.fire)

if __name__=='__main__':unittest.main()

