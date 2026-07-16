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

    assert [department["id"] for department in enabled] in ([], ["internal_medicine"])
    for department in enabled:
        navigation = department["navigation"]
        coordinates = tuple(navigation[key] for key in ("x", "y", "theta"))
        assert all(
            isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value)
            for value in coordinates
        )
        assert coordinates[:2] != (0.0, 0.0)
