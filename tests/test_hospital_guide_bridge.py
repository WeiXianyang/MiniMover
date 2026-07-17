import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask

from hospital_guide_bridge import register_hospital_guide_bridge


class RecordingNavigator:
    def __init__(self):
        self.goals = []

    def navigate_to(self, x, y, theta):
        self.goals.append((x, y, theta))
        return {"code": 0, "msg": "started"}


class RecordingLlm:
    def __init__(self):
        self.contexts = []

    def answer(self, text, context=None):
        self.contexts.append(context)
        return "这是一般健康教育信息，请结合现场医护意见。"


class HospitalGuideBridgeTests(unittest.TestCase):
    def _write_config(self, directory, enabled=False):
        path = Path(directory) / "guide.json"
        path.write_text(json.dumps({
            "hospital_name": "测试医院",
            "departments": [{
                "id": "internal_medicine",
                "name": "内科",
                "aliases": ["内科", "发热"],
                "floor": "二层",
                "directions": "请沿右侧通道前往。",
                "navigation": {"enabled": enabled, "x": 1.2, "y": -0.4, "theta": 0.0},
            }],
        }, ensure_ascii=False), encoding="utf-8")
        return path

    def _create_client(self, directory, enabled=False, on_guide_event=None):
        config_path = self._write_config(directory, enabled=enabled)
        kb_path = Path(directory) / "kb.jsonl"
        kb_path.write_text(json.dumps({"text": "健康教育问题应遵循现场医护人员指导。"}, ensure_ascii=False) + "\n", encoding="utf-8")
        telemetry_path = Path(directory) / "runtime.json"
        self.navigator = RecordingNavigator()
        self.llm = RecordingLlm()
        app = Flask(__name__)
        self.bridge = register_hospital_guide_bridge(
            app,
            config_path=config_path,
            knowledge_path=kb_path,
            telemetry_path=telemetry_path,
            navigation_client=self.navigator,
            llm_client=self.llm,
            on_guide_event=on_guide_event,
        )
        return app.test_client(), telemetry_path

    def test_rejects_empty_final_text(self):
        with TemporaryDirectory() as directory:
            client, _ = self._create_client(directory)
            response = client.post("/api/hospital-guide/turn", json={"text": "  "})
        self.assertEqual(400, response.status_code)
        self.assertEqual(1, response.get_json()["code"])

    def test_department_match_creates_real_pending_confirmation_and_telemetry(self):
        with TemporaryDirectory() as directory:
            client, telemetry_path = self._create_client(directory)
            response = client.post("/api/hospital-guide/turn", json={"text": "我要去内科"})
            payload = response.get_json()
            snapshot = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, payload["code"])
        self.assertIn("需要我带您去内科吗", payload["data"]["reply"])
        self.assertEqual("WAITING_CONFIRMATION", snapshot["session"]["state"])
        self.assertEqual("internal_medicine", snapshot["session"]["pending_department"]["id"])
        self.assertEqual("department_matched", snapshot["events"][-1]["type"])

    def test_department_match_emits_only_minimal_guide_event(self):
        events = []
        with TemporaryDirectory() as directory:
            client, _ = self._create_client(
                directory,
                on_guide_event=events.append,
            )
            client.post("/api/hospital-guide/turn", json={"text": "\u6211\u8981\u53bb\u5185\u79d1"})
        self.assertEqual([
            {"type": "department_matched", "department_id": "internal_medicine"},
        ], events)
        self.assertEqual([], self.navigator.goals)

    def test_bridge_can_replace_the_guide_event_handler(self):
        events = []
        with TemporaryDirectory() as directory:
            client, _ = self._create_client(directory)
            self.bridge.set_guide_event_handler(events.append)
            client.post("/api/hospital-guide/turn", json={"text": "\u6211\u8981\u53bb\u5185\u79d1"})
        self.assertEqual([
            {"type": "department_matched", "department_id": "internal_medicine"},
        ], events)

    def test_disabled_department_confirmation_does_not_send_navigation(self):
        with TemporaryDirectory() as directory:
            client, telemetry_path = self._create_client(directory, enabled=False)
            client.post("/api/hospital-guide/turn", json={"text": "去内科"})
            response = client.post("/api/hospital-guide/turn", json={"text": "确认"})
            snapshot = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(200, response.status_code)
        self.assertEqual([], self.navigator.goals)
        self.assertEqual("not_configured", snapshot["navigation"]["status"])
        self.assertEqual("navigation_not_configured", snapshot["events"][-1]["type"])

    def test_confirmed_enabled_department_uses_injected_navigation_client_once(self):
        with TemporaryDirectory() as directory:
            client, telemetry_path = self._create_client(directory, enabled=True)
            client.post("/api/hospital-guide/turn", json={"text": "去内科"})
            response = client.post("/api/hospital-guide/turn", json={"text": "好的，带我去"})
            snapshot = json.loads(telemetry_path.read_text(encoding="utf-8"))
        self.assertEqual(200, response.status_code)
        self.assertEqual([(1.2, -0.4, 0.0)], self.navigator.goals)
        self.assertEqual("started", snapshot["navigation"]["status"])
        self.assertEqual("navigation_started", snapshot["events"][-1]["type"])

    def test_confirmed_navigation_emits_event_only_after_client_accepts_goal(self):
        events = []
        with TemporaryDirectory() as directory:
            client, _ = self._create_client(
                directory,
                enabled=True,
                on_guide_event=events.append,
            )
            client.post("/api/hospital-guide/turn", json={"text": "\u6211\u8981\u53bb\u5185\u79d1"})
            client.post("/api/hospital-guide/turn", json={"text": "\u597d\u7684\uff0c\u5e26\u6211\u53bb"})
        self.assertEqual([(1.2, -0.4, 0.0)], self.navigator.goals)
        self.assertEqual([
            {"type": "department_matched", "department_id": "internal_medicine"},
            {"type": "navigation_started", "department_id": "internal_medicine"},
        ], events)

    def test_bridge_reset_invalidates_an_old_navigation_confirmation(self):
        events = []
        with TemporaryDirectory() as directory:
            client, _ = self._create_client(
                directory,
                enabled=True,
                on_guide_event=events.append,
            )
            client.post("/api/hospital-guide/turn", json={"text": "\u6211\u8981\u53bb\u5185\u79d1"})
            self.bridge.reset()
            client.post("/api/hospital-guide/turn", json={"text": "\u597d\u7684\uff0c\u5e26\u6211\u53bb"})
        self.assertEqual([], self.navigator.goals)
        self.assertEqual([
            {"type": "department_matched", "department_id": "internal_medicine"},
        ], events)

    def test_knowledge_query_passes_retrieved_shortmedkg_evidence_to_llm(self):
        with TemporaryDirectory() as directory:
            client, _ = self._create_client(directory)
            response = client.post("/api/hospital-guide/turn", json={"text": "健康教育有什么建议"})
        self.assertEqual(200, response.status_code)
        self.assertIn("健康教育问题", self.llm.contexts[-1]["medical_evidence"][0])


if __name__ == "__main__":
    unittest.main()

