"""FireGuard 云端接收 API (Flask + PyMySQL)。

职责:
  1. POST /api/v1/evidence     接收证据图片, 落到 Nginx 静态目录, 返回 URL。
  2. POST /api/v1/fire-alarms   幂等写入烟火告警到 MySQL。
  3. GET  /api/v1/fire-alarms   分页查询 (供前端)。
  4. GET  /api/v1/fire-alarms/<id>  单条详情。
  5. GET  /healthz              健康检查 (含 DB ping)。

鉴权: 除 /healthz 外, 写接口要求请求头 Authorization: Bearer <API_TOKEN>。
查询接口默认也校验 token, 便于后续前端统一带 token。
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, request

from .config import CloudConfig
from .db import Database

MODULE_ROOT = Path(__file__).resolve().parent
CONFIG = CloudConfig.from_env(MODULE_ROOT)
DB = Database(CONFIG)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = CONFIG.max_upload_mb * 1024 * 1024

_ALARM_TYPES = {"confirmed_fire", "suspected_smoke", "ai_unavailable"}
_EVENT_ID_RE = re.compile(r"^fire_[0-9]{8}_[0-9]{6}_[0-9]{6}_[0-9]{3}$")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def _unauthorized():
    return jsonify({"code": 401, "msg": "unauthorized"}), 401


def _require_token() -> bool:
    if not CONFIG.api_token:
        # 未配置 token 时放行, 仅用于本地开发; 生产必须配置。
        return True
    header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not header.startswith(prefix):
        return False
    return header[len(prefix):].strip() == CONFIG.api_token


def _bad_request(msg: str):
    return jsonify({"code": 400, "msg": msg}), 400


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid datetime: {value}") from exc


@app.get("/healthz")
def healthz():
    try:
        DB.ping()
        return jsonify({"code": 0, "msg": "ok", "db": "up"})
    except Exception as exc:  # noqa: BLE001 - 健康检查需报告任意故障
        return jsonify({"code": 500, "msg": "db down", "error": str(exc)[:200]}), 500


@app.post("/api/v1/evidence")
def upload_evidence():
    if not _require_token():
        return _unauthorized()
    if "file" not in request.files:
        return _bad_request("missing file field")
    file = request.files["file"]
    if not file.filename:
        return _bad_request("empty filename")
    # 以 event_id 命名 (若提供), 否则用随机名; 统一清洗防路径穿越。
    event_id = request.form.get("event_id", "").strip()
    suffix = Path(file.filename).suffix.lower() or ".jpg"
    if suffix not in (".jpg", ".jpeg", ".png"):
        return _bad_request("unsupported image type")
    stem = event_id if _EVENT_ID_RE.match(event_id) else uuid.uuid4().hex
    safe = _SAFE_NAME_RE.sub("_", stem)
    name = f"{safe}_{uuid.uuid4().hex[:8]}{suffix}"
    CONFIG.evidence_dir.mkdir(parents=True, exist_ok=True)
    dest = CONFIG.evidence_dir / name
    file.save(str(dest))
    url = f"{CONFIG.evidence_base_url}/{name}"
    return jsonify({"code": 0, "msg": "ok", "url": url})


@app.post("/api/v1/fire-alarms")
def create_alarm():
    if not _require_token():
        return _unauthorized()
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _bad_request("invalid JSON body")

    event_id = str(body.get("event_id", "")).strip()
    alarm_type = str(body.get("alarm_type", "")).strip()
    if not event_id:
        return _bad_request("event_id is required")
    if alarm_type not in _ALARM_TYPES:
        return _bad_request(f"alarm_type must be one of {sorted(_ALARM_TYPES)}")

    try:
        occurred_at = _parse_dt(body.get("occurred_at"))
    except ValueError as exc:
        return _bad_request(str(exc))
    if occurred_at is None:
        return _bad_request("occurred_at is required")

    classes = body.get("detection_classes")
    if isinstance(classes, (list, tuple)):
        classes = ",".join(str(c) for c in classes)
    elif classes is not None:
        classes = str(classes)

    confidence = body.get("confidence")
    max_confidence = body.get("max_confidence")
    car_id = str(body.get("car_id", "")).strip() or "unknown"

    record = {
        "event_id": event_id,
        "alarm_type": alarm_type,
        "occurred_at": occurred_at,
        "reason": (str(body["reason"])[:300] if body.get("reason") is not None else None),
        "confidence": float(confidence) if confidence is not None else None,
        "evidence_url": (str(body["evidence_url"]) if body.get("evidence_url") else None),
        "detection_classes": (classes[:64] if classes else None),
        "max_confidence": float(max_confidence) if max_confidence is not None else None,
        "local_detection_gone": 1 if body.get("local_detection_gone") else 0,
        "car_id": car_id[:32],
        "received_at": datetime.now().astimezone(),
        "raw_payload": json.dumps(body, ensure_ascii=False),
    }
    try:
        row_id, duplicated = DB.insert_alarm(record)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"code": 500, "msg": "db error", "error": str(exc)[:200]}), 500
    return jsonify({"code": 0, "msg": "ok", "id": row_id, "duplicated": duplicated})


@app.get("/api/v1/fire-alarms")
def list_alarms():
    if not _require_token():
        return _unauthorized()
    alarm_type = request.args.get("type") or None
    if alarm_type and alarm_type not in _ALARM_TYPES:
        return _bad_request(f"type must be one of {sorted(_ALARM_TYPES)}")
    car_id = request.args.get("car_id") or None
    try:
        date_from = _parse_dt(request.args.get("from"))
        date_to = _parse_dt(request.args.get("to"))
    except ValueError as exc:
        return _bad_request(str(exc))
    try:
        page = max(1, int(request.args.get("page", "1")))
        size = min(200, max(1, int(request.args.get("size", "20"))))
    except ValueError:
        return _bad_request("page/size must be integers")
    result = DB.list_alarms(alarm_type, car_id, date_from, date_to, page, size)
    return jsonify({"code": 0, "msg": "ok", "data": result})


@app.get("/api/v1/fire-alarms/<int:row_id>")
def get_alarm(row_id: int):
    if not _require_token():
        return _unauthorized()
    row = DB.get_alarm(row_id)
    if row is None:
        return jsonify({"code": 404, "msg": "not found"}), 404
    return jsonify({"code": 0, "msg": "ok", "data": row})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=CONFIG.api_port)
