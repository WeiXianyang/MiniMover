"""云端接收 API 的配置加载。

沿用车端 fire_monitor 的 .env 读取风格：从 cloud_platform/.env 读取，
环境变量优先级更高（os.environ.setdefault，不覆盖已存在的变量）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _int(name: str, default: str) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True)
class CloudConfig:
    db_host: str
    db_port: int
    db_user: str
    db_password: str
    db_name: str
    api_token: str
    api_port: int
    evidence_dir: Path
    evidence_base_url: str
    max_upload_mb: int

    @classmethod
    def from_env(cls, root: Path) -> "CloudConfig":
        root = Path(root).resolve()
        load_dotenv(root / ".env")
        evidence_dir = Path(
            os.environ.get("EVIDENCE_DIR", "/data/fireguard/evidence")
        )
        return cls(
            db_host=os.environ.get("DB_HOST", "127.0.0.1"),
            db_port=_int("DB_PORT", "3306"),
            db_user=os.environ.get("DB_USER", "root"),
            db_password=os.environ.get("DB_PASSWORD", ""),
            db_name=os.environ.get("DB_NAME", "dev_fireguard"),
            api_token=os.environ.get("API_TOKEN", "").strip(),
            api_port=_int("API_PORT", "8000"),
            evidence_dir=evidence_dir,
            evidence_base_url=os.environ.get(
                "EVIDENCE_BASE_URL", "http://8.140.28.233/evidence"
            ).rstrip("/"),
            max_upload_mb=_int("MAX_UPLOAD_MB", "10"),
        )
