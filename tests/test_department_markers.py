import json
import math

import pytest

from navigation import department_markers


def test_missing_marker_file_returns_an_empty_marker_collection(monkeypatch, tmp_path):
    monkeypatch.setattr(department_markers, 'MARKERS_PATH', tmp_path / 'markers.json')

    assert department_markers.list_markers() == {'version': 1, 'markers': []}


def test_save_marker_persists_only_whitelisted_department(monkeypatch, tmp_path):
    path = tmp_path / 'markers.json'
    monkeypatch.setattr(department_markers, 'MARKERS_PATH', path)

    saved = department_markers.save_marker('internal_medicine', 1.25, -0.5)

    assert saved == {
        'department': 'internal_medicine',
        'label': '内科',
        'color': '#2563eb',
        'x': 1.25,
        'y': -0.5,
    }
    assert department_markers.list_markers() == {'version': 1, 'markers': [saved]}
    assert json.loads(path.read_text(encoding='utf-8'))['markers']['internal_medicine'] == {
        'x': 1.25,
        'y': -0.5,
    }


def test_saving_the_same_department_replaces_its_coordinates(monkeypatch, tmp_path):
    monkeypatch.setattr(department_markers, 'MARKERS_PATH', tmp_path / 'markers.json')

    department_markers.save_marker('surgery', 0.0, 0.0)
    department_markers.save_marker('surgery', -2.0, 3.5)

    assert department_markers.list_markers()['markers'] == [{
        'department': 'surgery', 'label': '外科', 'color': '#f97316',
        'x': -2.0, 'y': 3.5,
    }]


@pytest.mark.parametrize('department,x,y', [
    ('pharmacy', 1.0, 2.0),
    ('internal_medicine', math.inf, 2.0),
    ('surgery', 1.0, math.nan),
])
def test_save_marker_rejects_unknown_or_nonfinite_input(monkeypatch, tmp_path, department, x, y):
    monkeypatch.setattr(department_markers, 'MARKERS_PATH', tmp_path / 'markers.json')

    with pytest.raises(ValueError):
        department_markers.save_marker(department, x, y)


def test_malformed_marker_file_is_reported_without_overwriting(monkeypatch, tmp_path):
    path = tmp_path / 'markers.json'
    path.write_text('{not-json', encoding='utf-8')
    monkeypatch.setattr(department_markers, 'MARKERS_PATH', path)

    with pytest.raises(ValueError, match='科室标注配置格式错误'):
        department_markers.list_markers()
    assert path.read_text(encoding='utf-8') == '{not-json'
