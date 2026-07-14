"""MySQL 访问层（PyMySQL）。

只负责 fire_alarm 表的写入与查询。写入用 INSERT ... ON DUPLICATE KEY
配合 uk_event_type(event_id, alarm_type) 唯一索引做幂等去重。
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Optional

import pymysql
from pymysql.cursors import DictCursor

from .config import CloudConfig


class Database:
    def __init__(self, config: CloudConfig):
        self._config = config

    @contextmanager
    def _connect(self):
        conn = pymysql.connect(
            host=self._config.db_host,
            port=self._config.db_port,
            user=self._config.db_user,
            password=self._config.db_password,
            database=self._config.db_name,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )
        try:
            yield conn
        finally:
            conn.close()

    def ping(self) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True

    def insert_alarm(self, record: dict[str, Any]) -> tuple[int, bool]:
        """写入一条告警，返回 (id, duplicated)。

        命中 uk_event_type 时视为重复：不新增行，返回已存在记录的 id。
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fire_alarm
                        (event_id, alarm_type, occurred_at, reason, confidence,
                         evidence_url, detection_classes, max_confidence,
                         local_detection_gone, car_id, received_at, raw_payload)
                    VALUES
                        (%(event_id)s, %(alarm_type)s, %(occurred_at)s, %(reason)s,
                         %(confidence)s, %(evidence_url)s, %(detection_classes)s,
                         %(max_confidence)s, %(local_detection_gone)s, %(car_id)s,
                         %(received_at)s, %(raw_payload)s)
                    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)
                    """,
                    record,
                )
                # rowcount: 1 = 新插入, 2 = 触发了 ON DUPLICATE KEY UPDATE
                duplicated = cur.rowcount == 2
                row_id = cur.lastrowid
            conn.commit()
        return row_id, duplicated

    def list_alarms(
        self,
        alarm_type: Optional[str],
        car_id: Optional[str],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        page: int,
        size: int,
    ) -> dict[str, Any]:
        where = []
        params: list[Any] = []
        if alarm_type:
            where.append("alarm_type = %s")
            params.append(alarm_type)
        if car_id:
            where.append("car_id = %s")
            params.append(car_id)
        if date_from:
            where.append("occurred_at >= %s")
            params.append(date_from)
        if date_to:
            where.append("occurred_at <= %s")
            params.append(date_to)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        offset = (page - 1) * size
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS total FROM fire_alarm {clause}", params)
                total = cur.fetchone()["total"]
                cur.execute(
                    f"""
                    SELECT id, event_id, alarm_type, occurred_at, reason, confidence,
                           evidence_url, detection_classes, max_confidence,
                           local_detection_gone, car_id, received_at
                    FROM fire_alarm {clause}
                    ORDER BY occurred_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params + [size, offset],
                )
                rows = cur.fetchall()
        return {"total": total, "page": page, "size": size, "items": _serialize_rows(rows)}

    def get_hourly_stats(
        self,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """返回最近 24 小时按小时聚合的告警数量（0-23 点全覆盖）。"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                now = datetime.now().astimezone()
                start = date_from or (now - timedelta(hours=24))
                # MySQL GROUP BY HOUR + 补齐空缺小时
                cur.execute(
                    """
                    SELECT HOUR(occurred_at) AS hour_bucket, COUNT(*) AS cnt
                    FROM fire_alarm
                    WHERE occurred_at >= %s AND occurred_at <= %s
                    GROUP BY HOUR(occurred_at)
                    ORDER BY hour_bucket
                    """,
                    [start, date_to or now],
                )
                db_rows = cur.fetchall()
        # 构建 0-23 完整数组
        lookup = {r["hour_bucket"]: r["cnt"] for r in db_rows}
        result = []
        for h in range(24):
            result.append({"hour": f"{h:02d}:00", "count": lookup.get(h, 0)})
        return result

    def get_vehicle_status(self) -> list[dict[str, Any]]:
        """返回各车辆最近一次告警的 received_at，按 car_id 分组。"""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT car_id, MAX(received_at) AS last_seen
                    FROM fire_alarm
                    GROUP BY car_id
                    ORDER BY last_seen DESC
                    """
                )
                rows = cur.fetchall()
        out = []
        for row in rows:
            ts = row["last_seen"]
            if isinstance(ts, datetime):
                row["last_seen"] = ts.isoformat()
            out.append(row)
        return out

    def get_alarm(self, row_id: int) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_id, alarm_type, occurred_at, reason, confidence,
                           evidence_url, detection_classes, max_confidence,
                           local_detection_gone, car_id, received_at, raw_payload
                    FROM fire_alarm WHERE id = %s
                    """,
                    [row_id],
                )
                row = cur.fetchone()
        if not row:
            return None
        serialized = _serialize_rows([row])[0]
        if isinstance(row.get("raw_payload"), str):
            try:
                serialized["raw_payload"] = json.loads(row["raw_payload"])
            except (ValueError, TypeError):
                serialized["raw_payload"] = row["raw_payload"]
        return serialized


def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        item = dict(row)
        for key in ("occurred_at", "received_at"):
            value = item.get(key)
            if isinstance(value, datetime):
                item[key] = value.isoformat()
        for key in ("confidence", "max_confidence"):
            value = item.get(key)
            if value is not None:
                item[key] = float(value)
        if "local_detection_gone" in item:
            item["local_detection_gone"] = bool(item["local_detection_gone"])
        item.pop("raw_payload", None)
        out.append(item)
    return out
