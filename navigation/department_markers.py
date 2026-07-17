"""Persistent display-only department markers; contains no ROS or vehicle controls."""

import json
import math
import os
import tempfile
from pathlib import Path


MARKERS_PATH = Path(__file__).with_name('data') / 'department_markers.json'
DEPARTMENTS = {
    'internal_medicine': {'label': '内科', 'color': '#2563eb'},
    'surgery': {'label': '外科', 'color': '#f97316'},
}


class MarkerConfigError(ValueError):
    """The persisted marker document is unreadable or structurally invalid."""


def _as_coordinate(value, field_name):
    try:
        coordinate = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('%s 必须是数字' % field_name) from exc
    if not math.isfinite(coordinate):
        raise ValueError('%s 必须是有限数字' % field_name)
    return coordinate


def _read_stored_markers():
    if not MARKERS_PATH.exists():
        return {}
    try:
        raw = json.loads(MARKERS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarkerConfigError('科室标注配置格式错误') from exc
    markers = raw.get('markers') if isinstance(raw, dict) else None
    if not isinstance(markers, dict):
        raise MarkerConfigError('科室标注配置格式错误')
    return markers


def _public_marker(department, stored):
    metadata = DEPARTMENTS[department]
    return {
        'department': department,
        'label': metadata['label'],
        'color': metadata['color'],
        'x': _as_coordinate(stored.get('x'), 'x'),
        'y': _as_coordinate(stored.get('y'), 'y'),
    }


def list_markers():
    stored_markers = _read_stored_markers()
    markers = []
    for department in DEPARTMENTS:
        stored = stored_markers.get(department)
        if stored is None:
            continue
        if not isinstance(stored, dict):
            raise MarkerConfigError('科室标注配置格式错误')
        markers.append(_public_marker(department, stored))
    return {'version': 1, 'markers': markers}


def _write_markers(markers):
    MARKERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix='.department_markers.', suffix='.json', dir=str(MARKERS_PATH.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'version': 1, 'markers': markers}, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, MARKERS_PATH)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def save_marker(department, x, y):
    if department not in DEPARTMENTS:
        raise ValueError('仅支持标注内科或外科')
    marker = {
        'x': _as_coordinate(x, 'x'),
        'y': _as_coordinate(y, 'y'),
    }
    stored_markers = _read_stored_markers()
    stored_markers[department] = marker
    _write_markers(stored_markers)
    return _public_marker(department, marker)
