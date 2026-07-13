"""Shared video-source aliases for MiniMover visual detectors."""

from __future__ import annotations

CAR_STREAMS = {
    "car_a": "http://192.168.137.23:8080/stream?topic=/camera/color/image_raw",
    "car_b": "http://192.168.137.254:8080/stream?topic=/camera/color/image_raw",
}
PROXY_STREAMS = {
    "proxy:car_a": "http://localhost:8888/proxy/camera/car_A",
    "proxy:car_b": "http://localhost:8888/proxy/camera/car_B",
}


def resolve_source(source: str) -> str:
    """Expand a documented car alias while preserving OpenCV-compatible inputs."""
    value = str(source).strip()
    return {**CAR_STREAMS, **PROXY_STREAMS}.get(value.lower(), value)
