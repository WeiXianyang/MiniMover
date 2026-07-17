from unittest.mock import patch

from face.recognition import identify_from_bytes


def test_identify_from_bytes_keeps_success_shape():
    result = {"ok": True, "user_id": "u1", "score": 93.0, "candidates": []}
    local_user = {"username": "王小明", "email": "x@example.test"}

    with patch("face.recognition.baidu.identify_person", return_value=result), patch(
        "face.recognition.store.get_user_by_id", return_value=local_user
    ):
        payload, status = identify_from_bytes(b"jpeg")

    assert status == 200
    assert payload["ok"] is True
    assert payload["identity"] == "王小明"
    assert payload["confidence"] == 0.93
    assert payload["user"]["source"] == "local_db"


def test_unknown_face_remains_404():
    with patch(
        "face.recognition.baidu.identify_person",
        return_value={"ok": False, "error_code": 222207, "msg": "未识别"},
    ):
        payload, status = identify_from_bytes(b"jpeg")

    assert status == 404
    assert payload == {"ok": False, "msg": "未识别", "error_code": 222207}

def test_registration_and_login_routes_keep_baidu_client_available():
    from face import routes

    assert callable(routes.baidu.add_face)
    assert callable(routes.baidu.match_face)
