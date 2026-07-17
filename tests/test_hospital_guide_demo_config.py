import json
import math
from pathlib import Path


CONFIG_PATH = Path("voice_assistant/data/hospital_guide_template.json")


def test_only_internal_medicine_may_enable_navigation_with_real_coordinates():
    """Keep the template safe until field calibration authorizes the sole demo target."""
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    enabled = []

    for department in data["departments"]:
        navigation = department["navigation"]
        assert isinstance(navigation["enabled"], bool)
        if navigation["enabled"]:
            enabled.append(department)

    assert [department["id"] for department in enabled] == ["internal_medicine"]
    assert enabled[0]["navigation"] == {
        "enabled": True,
        "x": 2.0,
        "y": 0.0,
        "theta": 0.0,
    }
    for department in enabled:
        navigation = department["navigation"]
        coordinates = tuple(navigation[key] for key in ("x", "y", "theta"))
        assert all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value)
            for value in coordinates
        )
        assert coordinates[:2] != (0.0, 0.0)


def test_demo_symptom_phrase_routes_to_internal_medicine_without_llm_guessing():
    from voice_assistant.hospital_guide import HospitalGuideConfig

    config = HospitalGuideConfig.from_path(CONFIG_PATH)
    department = config.find_department("我头疼，应该挂什么科？")
    assert department is not None
    assert department.department_id == "internal_medicine"


def test_internal_medicine_demo_copy_is_valid_chinese():
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    internal = next(
        department for department in data["departments"]
        if department["id"] == "internal_medicine"
    )

    assert internal["floor"] == "一层"
    assert internal["directions"] == "请前往前方内科演示点。"
    assert "?" not in internal["floor"] + internal["directions"]
