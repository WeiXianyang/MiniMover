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

from flask import Flask

from navigation.routes import nav_bp


def _marker_client(monkeypatch, tmp_path):
    monkeypatch.setattr(department_markers, 'MARKERS_PATH', tmp_path / 'markers.json')
    app = Flask(__name__)
    app.register_blueprint(nav_bp, url_prefix='/api/nav')
    return app.test_client()


def test_marker_routes_return_empty_then_persist_a_marker(monkeypatch, tmp_path):
    client = _marker_client(monkeypatch, tmp_path)

    initial = client.get('/api/nav/department-markers')
    saved = client.post('/api/nav/department-markers', json={
        'department': 'internal_medicine', 'x': 1.5, 'y': -2.0,
    })
    reread = client.get('/api/nav/department-markers')

    assert initial.status_code == 200
    assert initial.get_json()['data']['markers'] == []
    assert saved.status_code == 200
    assert saved.get_json()['data']['label'] == '内科'
    assert reread.get_json()['data']['markers'][0]['x'] == 1.5


def test_marker_route_rejects_invalid_payload_without_writing(monkeypatch, tmp_path):
    client = _marker_client(monkeypatch, tmp_path)

    response = client.post('/api/nav/department-markers', json={
        'department': 'pharmacy', 'x': 1.0, 'y': 2.0,
    })

    assert response.status_code == 400
    assert response.get_json()['code'] == -1
    assert not (tmp_path / 'markers.json').exists()


def test_marker_routes_report_corrupted_storage_as_server_error(monkeypatch, tmp_path):
    path = tmp_path / 'markers.json'
    path.write_text('{not-json', encoding='utf-8')
    client = _marker_client(monkeypatch, tmp_path)

    response = client.get('/api/nav/department-markers')

    assert response.status_code == 500
    assert response.get_json()['code'] == -1
    assert path.read_text(encoding='utf-8') == '{not-json'

from navigation.patrol_page import PATROL_PAGE_HTML


def test_patrol_page_exposes_two_display_only_department_marker_modes():
    assert 'id="modeInternalMedicine"' in PATROL_PAGE_HTML
    assert 'id="modeSurgery"' in PATROL_PAGE_HTML
    assert '标注内科' in PATROL_PAGE_HTML
    assert '标注外科' in PATROL_PAGE_HTML
    assert 'function saveDepartmentMarker' in PATROL_PAGE_HTML
    assert 'function loadDepartmentMarkers' in PATROL_PAGE_HTML
    assert "'/api/nav/department-markers'" in PATROL_PAGE_HTML


def test_marker_specific_javascript_does_not_reference_vehicle_controls():
    start = PATROL_PAGE_HTML.index('function saveDepartmentMarker')
    end = PATROL_PAGE_HTML.index('function recordRobotTrail')
    marker_code = PATROL_PAGE_HTML[start:end]

    for forbidden in ('/navigate', '/initial_pose', '/patrol/', 'ros2', 'cmd_vel'):
        assert forbidden not in marker_code


def test_repository_contains_fixed_competition_department_markers():
    original_path = department_markers.MARKERS_PATH
    try:
        department_markers.MARKERS_PATH = (
            __import__('pathlib').Path(__file__).resolve().parents[1]
            / 'navigation' / 'data' / 'department_markers.json'
        )
        assert department_markers.list_markers()['markers'] == [
            {
                'department': 'internal_medicine',
                'label': department_markers.DEPARTMENTS['internal_medicine']['label'],
                'color': '#2563eb',
                'x': 8.0,
                'y': 3.0,
            },
            {
                'department': 'surgery',
                'label': department_markers.DEPARTMENTS['surgery']['label'],
                'color': '#f97316',
                'x': -1.5,
                'y': 0.0,
            },
        ]
    finally:
        department_markers.MARKERS_PATH = original_path
