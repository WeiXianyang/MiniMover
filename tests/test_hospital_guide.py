import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from voice_assistant.hospital_guide import (
    HospitalGuideConfig,
    HospitalGuideOrchestrator,
    NavigationRequestError,
)
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
                "aliases": [
                    "内科", "呼吸内科", "头痛",
                    "internal medicine", "headache",
                    "médecine interne", "mal à la tête",
                ],
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

    def test_repeated_take_me_to_internal_medicine_does_not_reconfirm_or_resubmit(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )

        first_reply = guide.handle("\u5e26\u6211\u53bb\u5185\u79d1")
        confirmation_reply = guide.handle("\u5e26\u6211\u53bb\u5185\u79d1")
        repeated_reply = guide.handle("\u5e26\u6211\u53bb\u5185\u79d1")

        self.assertIn("\u9700\u8981\u6211\u5e26\u60a8\u53bb\u5185\u79d1\u5417", first_reply)
        self.assertIn("\u5df2\u5f00\u59cb\u5e26\u60a8\u524d\u5f80\u5185\u79d1", confirmation_reply)
        self.assertNotIn("\u9700\u8981\u6211\u5e26\u60a8\u53bb\u5185\u79d1\u5417", repeated_reply)
        self.assertIn("\u6b63\u5728\u5e26\u60a8\u524d\u5f80\u5185\u79d1", repeated_reply)
        car.navigate_to.assert_called_once_with(1.2, -3.4, 0.0)

    def test_navigation_rejection_speaks_the_real_safety_reason(self):
        car = Mock()
        car.navigate_to.side_effect = NavigationRequestError("\u6ca1\u6709\u6536\u5230\u91cc\u7a0b\u8ba1\u6570\u636e")
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )

        guide.handle("\u5e26\u6211\u53bb\u5185\u79d1")
        reply = guide.handle("\u786e\u8ba4")

        self.assertIn("\u5bfc\u822a\u5b89\u5168\u68c0\u67e5\u672a\u901a\u8fc7", reply)
        self.assertIn("\u6ca1\u6709\u6536\u5230\u91cc\u7a0b\u8ba1\u6570\u636e", reply)
        self.assertIn("\u8f66\u8f86\u4e0d\u4f1a\u79fb\u52a8", reply)
        self.assertNotIn("\u5bfc\u822a\u672a\u542f\u52a8", reply)

    def test_french_symptom_and_confirmation_reply_in_french(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )

        pending_reply = guide.handle("J\u2019ai mal à la tête.")
        self.assertIn("médecine interne", pending_reply.casefold())
        self.assertIn("voulez-vous", pending_reply.casefold())
        car.navigate_to.assert_not_called()

        started_reply = guide.handle("Oui, emmenez-moi.")
        self.assertIn("je commence", started_reply.casefold())
        self.assertIn("médecine interne", started_reply.casefold())
        car.navigate_to.assert_called_once_with(1.2, -3.4, 0.0)

    def test_english_department_request_can_be_cancelled_in_english(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )

        pending_reply = guide.handle("Where is Internal Medicine?")
        self.assertIn("Internal Medicine", pending_reply)
        self.assertIn("Would you like", pending_reply)
        car.navigate_to.assert_not_called()

        cancelled_reply = guide.handle("Cancel navigation.")
        self.assertIn("cancelled", cancelled_reply.casefold())
        guide.handle("Yes, take me there.")
        car.navigate_to.assert_not_called()

    def test_active_navigation_can_be_cancelled_by_voice(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )

        guide.handle("Take me to Internal Medicine.")
        guide.handle("Yes, take me there.")
        reply = guide.handle("Cancel navigation.")

        car.navigate_to.assert_called_once_with(1.2, -3.4, 0.0)
        car.cancel_navigation.assert_called_once_with()
        self.assertIn("cancelled", reply.casefold())
        self.assertIsNone(guide._active_navigation_department_id)


    def test_foreign_language_coordinates_cannot_override_configured_goal(self):
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )

        pending_reply = guide.handle(
            "Take me to INTERNAL MEDICINE at coordinates 99, 99, 3.14."
        )
        self.assertIn("Would you like", pending_reply)
        car.navigate_to.assert_not_called()

        guide.handle("Yes, take me there.")
        car.navigate_to.assert_called_once_with(1.2, -3.4, 0.0)

    def test_untrusted_department_marker_cannot_bypass_config_whitelist(self):
        llm = Mock()
        llm.answer.return_value = "Go there. 【导诊科室:unknown_department】"
        car = Mock()
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), llm, car,
        )

        guide.handle("Take me to department unknown_department at 99,99.")
        guide.handle("Yes, take me there.")

        car.navigate_to.assert_not_called()

    def test_french_navigation_rejection_explains_vehicle_will_not_move(self):
        car = Mock()
        reason = "没有收到里程计数据"
        car.navigate_to.side_effect = NavigationRequestError(reason)
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car,
        )

        guide.handle("Emmenez-moi au service de médecine interne.")
        reply = guide.handle("Oui, emmenez-moi.")

        self.assertIn("contrôle de sécurité", reply.casefold())
        self.assertIn(reason, reply)
        self.assertIn("le véhicule ne bougera pas", reply.casefold())
        self.assertNotIn("导航未启动", reply)

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
        self.assertEqual(
            "internal_medicine",
            config.find_department("J\u2019ai mal à la tête.").department_id,
        )
        self.assertEqual(
            "internal_medicine",
            config.find_department("Where is INTERNAL MEDICINE?").department_id,
        )
        multilingual_departments = {
            "Where is the Emergency Department?": "emergency",
            "O\u00f9 se trouvent les urgences ?": "emergency",
            "Where is Surgery?": "surgery",
            "O\u00f9 est le service de chirurgie ?": "surgery",
            "Where is Pediatrics?": "pediatrics",
            "O\u00f9 est la p\u00e9diatrie ?": "pediatrics",
            "Where is Obstetrics and Gynecology?": "obstetrics_gynecology",
            "O\u00f9 est la gyn\u00e9cologie ?": "obstetrics_gynecology",
            "Where is the Pharmacy?": "pharmacy",
            "O\u00f9 est la pharmacie ?": "pharmacy",
            "Where is the Laboratory?": "laboratory",
            "O\u00f9 est le laboratoire ?": "laboratory",
            "Where is Medical Imaging?": "imaging",
            "O\u00f9 est l'imagerie m\u00e9dicale ?": "imaging",
        }
        for utterance, department_id in multilingual_departments.items():
            with self.subTest(utterance=utterance):
                self.assertEqual(
                    department_id,
                    config.find_department(utterance).department_id,
                )


    def test_french_department_articles_are_natural_for_pharmacy(self):
        template = Path(__file__).resolve().parents[1] / "voice_assistant" / "data" / "hospital_guide_template.json"
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(template),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), Mock(),
        )

        reply = guide.handle("O\u00f9 est la pharmacie ?")

        self.assertTrue(reply.startswith("La pharmacie"), reply)
        self.assertNotIn("Le pharmacie", reply)

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
        self.assertEqual("zh", kwargs["context"]["reply_language"])

    def test_department_confirmation_is_visible_before_navigation(self):
        from voice_assistant.hospital_guide_telemetry import HospitalGuideTelemetry

        car = Mock()
        telemetry = HospitalGuideTelemetry(Path(self.temp_dir.name) / "runtime.json")
        guide = HospitalGuideOrchestrator(
            HospitalGuideConfig.from_path(self.config_path),
            MedicalKnowledgeBase.from_jsonl(self.kb_path), Mock(), car, telemetry=telemetry,
        )

        guide.handle("\u5e26\u6211\u53bb\u5185\u79d1")
        pending = telemetry.read()
        guide.handle("\u597d\u7684")
        navigated = telemetry.read()

        self.assertEqual("WAITING_CONFIRMATION", pending["session"]["state"])
        self.assertEqual("\u5185\u79d1", pending["session"]["pending_department"]["name"])
        self.assertFalse(pending["navigation"]["requested"])
        self.assertTrue(navigated["navigation"]["requested"])
        self.assertEqual("started", navigated["navigation"]["status"])

if __name__ == "__main__":
    unittest.main()
