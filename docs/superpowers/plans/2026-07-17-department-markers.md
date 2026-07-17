# Department Marker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent, display-only `内科` and `外科` markers to the map patrol console without changing or invoking navigation, patrol, velocity, or chassis control behavior.

**Architecture:** Add a small Python persistence module that owns the department whitelist, JSON validation, and atomic writes. Expose that module through two Flask routes and extend the existing single-page patrol console with a marker-selection mode, overlay rendering, and a coordinate sidebar. The marker API is intentionally independent of `ros_bridge`, Nav2, Docker, and the existing route/initial-pose endpoints.

**Tech Stack:** Python 3, Flask blueprint, standard-library JSON/file APIs, existing inline HTML/CSS/JavaScript in `navigation/patrol_page.py`, pytest.

---

## File structure

- Create `navigation/department_markers.py`: owns the fixed department metadata, JSON loading, finite-coordinate validation, and atomic file replacement.
- Modify `navigation/routes.py:1-111`: imports the marker module and adds GET/POST routes before ROS-control routes.
- Modify `navigation/patrol_page.py:16-161`: adds display-only buttons, styles, sidebar, state, persistence calls, and overlay rendering while preserving every existing route/start/patrol branch.
- Create `tests/test_department_markers.py`: tests persistence in a temporary directory, HTTP status codes, marker route isolation, and rendered-page safety contracts.
- Create `navigation/data/department_markers.json` only at runtime: do **not** commit a map coordinate placeholder that could be mistaken for a validated department location.

## Safety invariants

1. Only `internal_medicine` and `surgery` are accepted as marker identifiers.
2. A marker save is filesystem state only; it must not import or call `ros_bridge`, `stack_manager`, Docker, ROS, Nav2, `/navigate`, `/initial_pose`, or `/patrol/*`.
3. A successful save can change only `navigation/data/department_markers.json`; it cannot alter route points, `startPose`, `robotPose`, or patrol state.
4. The browser must not call a vehicle-control API from either marker-specific function.

### Task 1: Add isolated marker persistence with validation

**Files:**
- Create: `navigation/department_markers.py`
- Create: `tests/test_department_markers.py`

- [ ] **Step 1: Write failing persistence tests**

Create `tests/test_department_markers.py` with these initial tests. Patch `MARKERS_PATH` so tests never write to the repository or Jetson runtime directory.

```python
import json
import math
from pathlib import Path

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
```

- [ ] **Step 2: Run the new test file and verify it fails**

Run from `E:\MiniMover\.worktrees\five-minute-hospital-guide-demo-implementation`:

```powershell
python -m pytest tests/test_department_markers.py -q
```

Expected: collection fails because `navigation.department_markers` does not yet exist.

- [ ] **Step 3: Implement the minimum isolated persistence module**

Create `navigation/department_markers.py` with this complete implementation. Keep metadata server-owned so the browser cannot choose labels or colors.

```python
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
    pass


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
```

- [ ] **Step 4: Run the persistence tests and verify they pass**

```powershell
python -m pytest tests/test_department_markers.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit the isolated persistence slice**

```powershell
git add navigation/department_markers.py tests/test_department_markers.py
git commit -m "feat: persist display-only department markers"
```

### Task 2: Add marker-specific HTTP routes

**Files:**
- Modify: `navigation/routes.py:1-38`
- Modify: `tests/test_department_markers.py`

- [ ] **Step 1: Add failing Flask route tests**

Append these tests to `tests/test_department_markers.py`.

```python
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
```

- [ ] **Step 2: Run only the two new route tests and verify failure**

```powershell
python -m pytest tests/test_department_markers.py::test_marker_routes_return_empty_then_persist_a_marker tests/test_department_markers.py::test_marker_route_rejects_invalid_payload_without_writing -q
```

Expected: FAIL with HTTP `404` because the routes are absent.

- [ ] **Step 3: Add routes that delegate only to `department_markers`**

At `navigation/routes.py:7`, change the imports to:

```python
from . import department_markers, map_utils, ros_bridge
```

After `_err` at `navigation/routes.py:21`, add:

```python
@nav_bp.route('/department-markers', methods=['GET'])
def department_marker_list():
    try:
        return _ok(department_markers.list_markers())
    except department_markers.MarkerConfigError as exc:
        return _err(str(exc), 500)


@nav_bp.route('/department-markers', methods=['POST'])
def department_marker_save():
    data = request.json or {}
    try:
        marker = department_markers.save_marker(
            data.get('department'), data.get('x'), data.get('y'))
    except department_markers.MarkerConfigError as exc:
        return _err(str(exc), 500)
    except ValueError as exc:
        return _err(str(exc), 400)
    except OSError as exc:
        return _err('保存科室标注失败: %s' % exc, 500)
    return _ok(marker, '科室标注已保存')
```

Do not call any existing route handler from either function. In particular, do not reuse `initial_pose`, `patrol_set_route`, `navigate`, or `ros_bridge`.

- [ ] **Step 4: Run the marker test suite and the existing navigation route tests**

```powershell
python -m pytest tests/test_department_markers.py tests/test_navigation_pose.py tests/test_demo_navigation.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the HTTP slice**

```powershell
git add navigation/routes.py tests/test_department_markers.py
git commit -m "feat: expose department marker API"
```

### Task 3: Add map click-and-render interaction

**Files:**
- Modify: `navigation/patrol_page.py:21-161`
- Modify: `tests/test_department_markers.py`

- [ ] **Step 1: Add failing rendered-page contracts**

Append the following tests. These tests intentionally inspect only marker-specific contracts; the existing page contains separate authorized patrol controls and must not be treated as a marker-feature violation.

```python
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
```

- [ ] **Step 2: Run the rendered-page contract tests and verify failure**

```powershell
python -m pytest tests/test_department_markers.py::test_patrol_page_exposes_two_display_only_department_marker_modes tests/test_department_markers.py::test_marker_specific_javascript_does_not_reference_vehicle_controls -q
```

Expected: FAIL because the marker modes and functions do not exist.

- [ ] **Step 3: Add minimal UI state, controls, and sidebar**

In the CSS block near `navigation/patrol_page.py:26-29`, add a visible department label style:

```css
.marker.department{width:auto;min-width:18px;height:18px;padding:1px 6px;border-radius:9px;white-space:nowrap;font-size:11px;line-height:14px;font-weight:bold;box-shadow:0 1px 5px rgba(0,0,0,.55)}
```

In the mode toolbar at `navigation/patrol_page.py:58-67`, insert these buttons after `② 设起点`:

```html
<button id="modeInternalMedicine" onclick="setMode('internal_medicine')">标注内科</button>
<button id="modeSurgery" onclick="setMode('surgery')">标注外科</button>
<button id="modeCancelMarker" onclick="setMode('route')">取消标注</button>
```

After the start-pose panel at `navigation/patrol_page.py:79`, insert:

```html
<div class="panel"><h3>科室标注</h3><div id="departmentList">（尚未标注）</div></div>
```

Replace the declaration at `navigation/patrol_page.py:85` with:

```javascript
var points=[],startPose={x:0,y:0,yaw:0},clickMode='route',departmentMarkers=[];
```

Replace `setMode` with this implementation so each mode has a deterministic active button and status text:

```javascript
function setMode(m){
  clickMode=m;
  document.getElementById('modeRoute').classList.toggle('active',m==='route');
  document.getElementById('modeStart').classList.toggle('active',m==='start');
  document.getElementById('modeInternalMedicine').classList.toggle('active',m==='internal_medicine');
  document.getElementById('modeSurgery').classList.toggle('active',m==='surgery');
  if(m==='internal_medicine'){setStatus('请在地图上点击内科位置');}
  if(m==='surgery'){setStatus('请在地图上点击外科位置');}
}
```

- [ ] **Step 4: Add marker load/save and overlay rendering**

Add these functions immediately after `refreshList`. They use the existing `apiPost`, `screenToMap`, `redraw`, and map-coordinate conversion; they do not alter `points` or `startPose`.

```javascript
function refreshDepartmentList(){
  var el=document.getElementById('departmentList');
  el.innerHTML=departmentMarkers.length?departmentMarkers.map(function(marker){
    return marker.label+': ('+marker.x.toFixed(3)+', '+marker.y.toFixed(3)+')';
  }).join('<br>'):'（尚未标注）';
}
function loadDepartmentMarkers(){
  return fetch(API+'/api/nav/department-markers').then(function(r){return r.json();}).then(function(j){
    if(j.code!==0){throw new Error(j.msg||'读取科室标注失败');}
    departmentMarkers=(j.data&&Array.isArray(j.data.markers))?j.data.markers:[];
    refreshDepartmentList();redraw();
  }).catch(function(){setStatus('读取科室标注失败',false);});
}
function saveDepartmentMarker(department, point){
  setStatus('正在保存科室标注…');
  return apiPost('/api/nav/department-markers',{department:department,x:point.x,y:point.y}).then(function(j){
    if(j.code!==0){setStatus(j.msg||'保存科室标注失败',false);return;}
    departmentMarkers=departmentMarkers.filter(function(marker){return marker.department!==j.data.department;});
    departmentMarkers.push(j.data);
    refreshDepartmentList();redraw();
    setStatus(j.msg||'科室标注已保存',true);
    setMode('route');
  });
}
```

Inside `redraw`, after the existing route-point `points.forEach` block and before the robot-pose `if`, add:

```javascript
  departmentMarkers.forEach(function(marker){
    var px4=(marker.x-mapInfo.origin[0])/mapInfo.resolution;
    var py4=mapH-(marker.y-mapInfo.origin[1])/mapInfo.resolution;
    var department=document.createElement('div');department.className='marker department';
    department.style.left=(px4/mapW*100)+'%';department.style.top=(py4/mapH*100)+'%';
    department.style.background=marker.color;department.textContent=marker.label;
    w.appendChild(department);
  });
```

At the beginning of the map click handler, immediately after `var m=screenToMap(...)`, add this short-circuit:

```javascript
  if(clickMode==='internal_medicine'||clickMode==='surgery'){
    saveDepartmentMarker(clickMode,m);
    return;
  }
```

Finally, at page initialization before `refreshList();`, call:

```javascript
loadDepartmentMarkers();
```

- [ ] **Step 5: Run the focused UI contracts and all marker tests**

```powershell
python -m pytest tests/test_department_markers.py -q
```

Expected: all marker persistence, route, and rendered-page tests pass.

- [ ] **Step 6: Commit the UI slice**

```powershell
git add navigation/patrol_page.py tests/test_department_markers.py
git commit -m "feat: add map department marker controls"
```

### Task 4: Verify the integrated feature without driving the vehicle

**Files:**
- Modify: none unless a test exposes a defect.
- Test: `tests/test_department_markers.py`, `tests/test_navigation_pose.py`, `tests/test_demo_navigation.py`

- [ ] **Step 1: Run the full relevant test selection**

```powershell
python -m pytest tests/test_department_markers.py tests/test_navigation_pose.py tests/test_demo_navigation.py -q
```

Expected: all tests pass with no collection errors.

- [ ] **Step 2: Perform static control-boundary verification**

```powershell
Select-String -Path navigation\department_markers.py -Pattern 'ros_bridge|stack_manager|docker|ros2|navigate|cmd_vel|patrol' -CaseSensitive
```

Expected: no matches. If any match appears, remove the coupling before continuing.

- [ ] **Step 3: Inspect the staged and committed scope**

```powershell
git status --short
git log --oneline -3
git show --stat --oneline HEAD
```

Expected: clean worktree and commits only for the department-marker feature plus its tests.

- [ ] **Step 4: Manually validate in a browser against a development server only**

1. Open `/nav/patrol` in a non-production development instance.
2. Click `标注内科`, click a map location, and verify the label and sidebar coordinates appear.
3. Click `标注外科`, click a different map location, and verify both labels appear in different colors.
4. Refresh the browser and verify both remain.
5. Verify no route points were added and no start pose changed.
6. Do not click `应用起点`, `上传路线`, `开始巡逻`, `停止巡逻`, or any navigation action during this validation.

- [ ] **Step 5: Commit only a defect fix if validation required one**

If and only if Steps 1-4 required a code correction:

```powershell
git add navigation/department_markers.py navigation/routes.py navigation/patrol_page.py tests/test_department_markers.py
git commit -m "fix: preserve display-only department markers"
```

If no correction was required, create no additional commit.
