from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Sequence

import cv2

from .types import AIReviewRequest, AIResultKind, AlarmEvent, Detection, EventState, FIRE_CLASSES
from .debug_telemetry import NullTelemetry


@dataclass
class _Event:
    event_id: str
    state: EventState
    review_id: int
    last_hit: float
    last_review_capture: float
    last_evidence_capture: float
    evidence_paths: Dict[int, Path] = field(default_factory=dict)
    in_flight: bool = False
    local_detection_gone: bool = False
    classes: tuple = ()
    max_confidence: float = 0.0


class FireEventManager:
    def __init__(self, config, reviewer, evidence_store, alarm_service, minimum_confidence: float, logger, telemetry=None):
        self.config=config; self.reviewer=reviewer; self.store=evidence_store; self.alarms=alarm_service
        self.minimum_confidence=minimum_confidence; self.logger=logger; self.telemetry=telemetry or NullTelemetry()
        self._hits=deque(); self._event: Optional[_Event]=None; self._counter=0

    @property
    def state(self): return self._event.state if self._event else EventState.IDLE

    def process_frame(self, detections: Sequence[Detection], raw_frame, annotated_frame, now_monotonic: float, captured_at) -> None:
        qualifying=[d for d in detections if d.class_name.lower() in FIRE_CLASSES and d.confidence >= self.minimum_confidence]
        hit=bool(qualifying)
        cutoff=now_monotonic-self.config.trigger_window_seconds
        while self._hits and self._hits[0] < cutoff:self._hits.popleft()
        if not self._event and hit:self._hits.append(now_monotonic)
        self.telemetry.update(detector={"hit": hit, "hit_count": len(self._hits),
                                       "trigger_min_hits": self.config.trigger_min_hits,
                                       "classes": sorted({d.class_name.lower() for d in qualifying}),
                                       "max_confidence": max((d.confidence for d in qualifying), default=0.0)},
                              event={"state": self.state.value, "event_id": self._event.event_id if self._event else ""})
        if hit and not self._event:
            self.telemetry.event("yolo_hit", ", ".join(f"{d.class_name} {d.confidence:.2f}" for d in qualifying),
                                 hit_count=len(self._hits), trigger_min_hits=self.config.trigger_min_hits)
        if (self._event and not hit and self._event.in_flight and
                now_monotonic - self._event.last_hit >= self.config.event_clear_seconds):
            self._event.local_detection_gone = True
        self._consume_results(captured_at)
        if self._event:
            if hit:
                self._event.last_hit=now_monotonic
                self._event.classes=tuple(sorted({d.class_name.lower() for d in qualifying}))
                self._event.max_confidence=max(d.confidence for d in qualifying)
            elif now_monotonic - self._event.last_hit >= self.config.event_clear_seconds:
                if self._event.in_flight:
                    self._event.local_detection_gone=True
                else:
                    self._reset()
                    return
            if not self._event or self._event.local_detection_gone:
                return
            if self._event.state == EventState.AI_REJECTED and hit and not self._event.in_flight and now_monotonic-self._event.last_review_capture >= self.config.review_interval_seconds:
                self._capture_review(raw_frame,annotated_frame,now_monotonic,captured_at,"review")
            elif self._event.state in (EventState.ALARMED_FIRE,EventState.ALARMED_SMOKE,EventState.AI_FAILED) and hit and now_monotonic-self._event.last_evidence_capture >= self.config.evidence_interval_seconds:
                self._save_evidence(annotated_frame,now_monotonic,captured_at,"periodic")
            return
        if not hit:return
        if len(self._hits) >= self.config.trigger_min_hits:
            self._counter+=1
            event_id=f"fire_{captured_at.strftime('%Y%m%d_%H%M%S_%f')}_{self._counter:03d}"
            self._event=_Event(event_id,EventState.AI_REVIEWING,0,now_monotonic,now_monotonic,now_monotonic,
                               classes=tuple(sorted({d.class_name.lower() for d in qualifying})),max_confidence=max(d.confidence for d in qualifying))
            self._hits.clear(); self._capture_review(raw_frame,annotated_frame,now_monotonic,captured_at,"initial")

    def _metadata(self,status="pending"):
        e=self._event
        return {"local_detection":{"classes":list(e.classes),"max_confidence":e.max_confidence,"trigger_hits":self.config.trigger_min_hits,"window_seconds":self.config.trigger_window_seconds},"ai_review":{"status":status}}

    def _capture_review(self,raw,annotated,now,captured_at,capture_type):
        e=self._event;e.review_id+=1
        ok,encoded=cv2.imencode('.jpg',raw,[cv2.IMWRITE_JPEG_QUALITY,90])
        if not ok:raise RuntimeError('failed to encode AI review JPEG')
        path=self.store.save(e.event_id,e.review_id,capture_type,captured_at,annotated,self._metadata())
        jpeg_bytes=encoded.tobytes()
        self.telemetry.write_jpeg_bytes("latest_ai_upload.jpg", jpeg_bytes)
        self.telemetry.update(event={"state": e.state.value, "event_id": e.event_id, "review_id": e.review_id,
                                     "evidence_path": str(path), "capture_type": capture_type},
                              ai={"state": "queued", "attempt": 0, "result": "", "error": ""})
        self.telemetry.event("captured", f"Evidence captured: {path}", event_id=e.event_id, review_id=e.review_id,
                             evidence_path=str(path), capture_type=capture_type)
        self.telemetry.event("ai_upload", "Unannotated image queued for real AI upload", event_id=e.event_id, review_id=e.review_id)
        request=AIReviewRequest(e.event_id,e.review_id,jpeg_bytes,captured_at)
        if not self.reviewer.submit(request):raise RuntimeError('AI reviewer rejected an expected task')
        e.evidence_paths[e.review_id]=path;e.in_flight=True;e.state=EventState.AI_REVIEWING;e.last_review_capture=now;e.last_evidence_capture=now

    def _save_evidence(self,annotated,now,captured_at,capture_type):
        e=self._event
        path=self.store.save(e.event_id,e.review_id,capture_type,captured_at,annotated,self._metadata("not_requested"));e.last_evidence_capture=now
        self.telemetry.update(event={"evidence_path": str(path), "capture_type": capture_type})
        self.telemetry.event("evidence", f"Periodic evidence saved: {path}", evidence_path=str(path), capture_type=capture_type)

    def _consume_results(self,captured_at):
        for result in self.reviewer.poll():
            e=self._event
            if not e or result.event_id != e.event_id or result.review_id != e.review_id:
                self.logger.warning('Ignoring stale AI result event=%s review=%s',result.event_id,result.review_id);continue
            e.in_flight=False; path=e.evidence_paths.get(result.review_id)
            update={"ai_review":{"status":"completed" if result.success else "failed","attempts":result.attempts,"result":result.result.value if result.result else None,"confidence":result.confidence,"reason":result.reason,"error":result.error}}
            if path:self.store.update_metadata(path,update)
            alarm=None
            if result.success and result.result == AIResultKind.CONFIRMED_FIRE:
                e.state=EventState.ALARMED_FIRE;alarm=("confirmed_fire",result.reason,result.confidence,self.alarms.report_confirmed_fire)
            elif result.success and result.result == AIResultKind.SUSPECTED_SMOKE:
                e.state=EventState.ALARMED_SMOKE;alarm=("suspected_smoke",result.reason,result.confidence,self.alarms.report_suspected_smoke)
            elif result.success:
                e.state=EventState.AI_REJECTED
            else:
                e.state=EventState.AI_FAILED;alarm=("ai_unavailable",result.error or "AI服务失效，需人工介入",None,self.alarms.report_ai_unavailable)
            self.telemetry.update(event={"state": e.state.value, "event_id": e.event_id})
            if alarm:
                kind,reason,confidence,method=alarm
                sent=method(AlarmEvent(e.event_id,kind,captured_at,reason,confidence,str(path) if path else None,e.local_detection_gone))
                self.telemetry.update(alarm={"state": "triggered" if sent else "duplicate", "type": kind, "reason": reason})
                self.telemetry.event("alarm", f"{kind}: {reason}", alarm_type=kind, sent=sent)
            if e.local_detection_gone:self._reset()

    def _reset(self):
        previous=self._event.event_id if self._event else ""
        self._event=None;self._hits.clear()
        self.telemetry.update(event={"state": EventState.IDLE.value, "event_id": ""}, detector={"hit_count": 0})
        if previous:self.telemetry.event("event_cleared", f"Event cleared: {previous}", event_id=previous)
    def drain_results(self, captured_at) -> None:
        self._consume_results(captured_at)

    def close(self):self.reviewer.close()
