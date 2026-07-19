"""Run the final local TTS endpoint smoke probe."""


def main() -> int:
    import requests

    response = requests.post(
        "http://127.0.0.1:5000/api/audio/say",
        json={"text": "\u4f60\u597d\u6211\u662f\u5c0f\u5357\u767e\u70bc\u8bed\u97f3\u6d4b\u8bd5"},
        timeout=30,
    )
    print(f"{response.status_code} {response.json()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
