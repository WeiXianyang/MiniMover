import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from voice_assistant.car_client import CarClient
from voice_assistant.hospital_guide import HospitalGuideConfig, HospitalGuideOrchestrator
from voice_assistant.medical_knowledge import MedicalKnowledgeBase


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class HospitalGuideTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.config_path = root / "hospital.json"
        write_json(self.config_path, {
            "hospital_name": "测试医院",
            "departments": [{
                "id": "internal_medicine",
                "name": "内科",
                "aliases": ["内科", "呼吸内科"],
                "floor": "二层",
                "directions": "到二层内科候诊区。",
                "navigation": {"enabled": True, "x": 1.2, "y": -3.4, "theta": 0.0},
            }],
        })
        self.kb_path = root / "knowledge.jsonl"
        self.kb_path.write_text(
            '{"text":"胸痛或呼吸不适需要根据症状就诊。"}\n'
            '{"text":"儿科为儿童提供门诊服务。"}\n', encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_retrieval_returns_limited_relevant_text(self):
        knowledge = MedicalKnowledgeBase.from_jsonl(self.kb_path)
        results = knowledge.search("胸痛", limit=1)
        self.assertEqual(results, ["胸痛或呼吸不适需要根据症状就诊。"])

    def test_memory_is_bounded_and_resettable(self):
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), Mock(), memory_turns=1,
        )
        guide.remember("第一问", "第一答")
        guide.remember("第二问", "第二答")
        self.assertEqual(guide.history(), [
            {"role": "user", "content": "第二问"},
            {"role": "assistant", "content": "第二答"},
        ])
        guide.reset()
        self.assertEqual(guide.history(), [])

    def test_navigation_requires_a_pending_department_and_confirmation(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )
        guide.handle("带我去内科")
        car.navigate_to.assert_not_called()
        guide.handle("好的")
        car.navigate_to.assert_called_once_with(1.2, -3.4, 0.0)

    def test_rejection_clears_pending_navigation(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )
        guide.handle("带我去内科")
        guide.handle("不用了")
        guide.handle("好的")
        car.navigate_to.assert_not_called()

    def test_emergency_message_never_starts_navigation_automatically(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )
        answer = guide.handle("我胸痛而且晕倒了")
        self.assertIn("急诊", answer)
        car.navigate_to.assert_not_called()


    def test_invalid_or_disabled_navigation_is_rejected(self):
        payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        payload["departments"][0]["navigation"]["enabled"] = False
        write_json(self.config_path, payload)
        config = HospitalGuideConfig.from_path(self.config_path)
        self.assertFalse(config.department("internal_medicine").navigation_enabled)

        payload["departments"].append(dict(payload["departments"][0]))
        write_json(self.config_path, payload)
        with self.assertRaises(ValueError):
            HospitalGuideConfig.from_path(self.config_path)


    def test_committed_template_configuration_loads_with_navigation_disabled(self):
        template = Path(__file__).resolve().parents[1] / "voice_assistant" / "data" / "hospital_guide_template.json"
        config = HospitalGuideConfig.from_path(template)
        self.assertFalse(config.department("emergency").navigation_enabled)
        self.assertFalse(config.department("pharmacy").navigation_enabled)


    def test_llm_receives_limited_history_and_evidence(self):
        llm = Mock()
        llm.answer.return_value = "guide reply"
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), llm, Mock(), memory_turns=1,
        )
        guide.handle("\u80f8\u75db")
        kwargs = llm.answer.call_args.kwargs
        self.assertIn("medical_evidence", kwargs["context"])
        self.assertLessEqual(len(kwargs["context"]["history"]), 2)
        self.assertIn("\u4e0d\u8bca\u65ad", kwargs["context"]["system_rules"])

    @patch("voice_assistant.car_client.request.urlopen")
    def test_car_client_posts_validated_navigation_payload(self, urlopen):
        response = Mock()
        response.read.return_value = b'{"code": 0}'
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        urlopen.return_value = response
        CarClient("http://127.0.0.1:6500").navigate_to(1.2, -3.4, 0.0)
        payload = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload, {"x": 1.2, "y": -3.4, "theta": 0.0})


if __name__ == "__main__":
    unittest.main()
