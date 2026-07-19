"""Probe the local TTS HTTP endpoint."""

import json


def main() -> int:
    import requests

    response = requests.post(
        "http://127.0.0.1:5000/api/audio/say",
        json={"text": "bailian test"},
        timeout=30,
    )
    print(f"Status: {response.status_code}")
    print(f"Body: {json.dumps(response.json(), ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
