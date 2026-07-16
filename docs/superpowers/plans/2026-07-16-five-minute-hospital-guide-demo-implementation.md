# 五分钟医院导诊小车演示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (\- [ ]\) syntax for tracking.

**Goal:** 在实体车上完成可重复、可恢复且不伪造到达状态的五分钟演示：自动人脸欢迎 → 语音导诊 → 用户确认 → 内科实走导航 → 真实到达播报与控制台展示。

**Architecture:** 新增只保存会话 ID 与显示名的演示会话状态机，将自动人脸扫描、欢迎播报确认、导诊确认门控和导航结果串成明确状态转换。保留现有导诊编排器与单点导航入口；扩展 Nav2 action 的真实状态追踪，并用 map 位姿与目标距离共同判定到达。

**Tech Stack:** Python 3、Flask、pytest、ROS 2 / Nav2 CLI、车载 ROS 相机快照、PC ASR WebSocket、Jetson TTS/CaptureGate、JSON 配置。

---

## 安全不变量

1. 唯一实走目标是 internal_medicine；其它科室导航继续禁用。
2. 识别结果只决定欢迎显示名或访客模式；不得持久化照片、候选项、置信度、邮箱、手机号、密码或病历。
3. 只有演示会话处于 WAITING_CONFIRMATION，导诊匹配到已启用内科，且用户最终 ASR 文本明确确认时，才能发送导航目标。
4. 已到达必须同时满足 Nav2 action 输出 SUCCEEDED 和 map 位姿距离目标不超过 0.15 m。HTTP 成功、目标已提交、TTS 播完或普通移动接口都不等于到达或停止。
5. 取消功能默认关闭；只有完成清场实车验证后，以显式环境变量开放。普通 move API 永远不能代替 Nav2 取消。
6. 所有失败显示真实失败原因，并维持安全操作员/硬件停止路径；不得伪造状态或隐藏错误。

## 文件结构

| 文件 | 责任 |
| --- | --- |
| voice_assistant/demo_session.py | 最小化、线程安全演示会话状态。 |
| face/recognition.py | 无副作用的图像字节识别服务。 |
| hospital_guide_demo.py | 自动扫描、欢迎领取/确认、演示 Flask API 与导航状态对接。 |
| voice_assistant/hospital_guide.py | 仅传递最小导诊事件。 |
| hospital_guide_bridge.py | 受锁 reset 与导诊事件处理器注册。 |
| voice_assistant/demo_session_client.py | Jetson 一次性欢迎轮询客户端。 |
| voice_assistant/car_client_jetson.py | 仅演示模式下的 TTS、CaptureGate、ASR 接管。 |
| navigation/ros_bridge.py | 唯一活跃 Nav2 goal、最终状态、到达计算、受保护取消。 |
| navigation/routes.py | demo goal 状态和取消 API。 |
| hospital_guide_console.py | 匿名化展示演示阶段和真实导航证据。 |
| docs/runbooks/five-minute-hospital-guide-demo.md | 标定、启动、五分钟脚本、恢复与放行记录。 |

---

### Task 1: 创建演示会话状态机

**Files:**
- Create: voice_assistant/demo_session.py
- Create: tests/test_demo_session.py

- [ ] **Step 1: 先写失败测试。**

~~~python
from voice_assistant.demo_session import DemoPhase, DemoSession


def test_start_replaces_session_and_enters_scanning():
    session = DemoSession()
    first = session.start()
    second = session.start()
    assert first["session_id"] != second["session_id"]
    assert second["phase"] == DemoPhase.SCANNING.value
    assert second["display_name"] is None


def test_welcome_claim_is_once_and_ack_must_match_current_session():
    session = DemoSession()
    started = session.start()
    assert session.set_welcome("王小明") is True
    assert session.claim_welcome() == {
        "session_id": started["session_id"],
        "text": "你好，王小明。请问您需要去哪个科室？",
    }
    assert session.claim_welcome() is None
    assert session.acknowledge_welcome("old") is False
    assert session.acknowledge_welcome(started["session_id"]) is True
    assert session.snapshot()["phase"] == "LISTENING"


def test_only_confirmation_then_navigation_then_arrival_is_valid():
    session = DemoSession()
    started = session.start()
    session.set_welcome(None)
    session.claim_welcome()
    session.acknowledge_welcome(started["session_id"])
    assert session.mark_navigation_started() is False
    assert session.mark_waiting_confirmation("internal_medicine") is True
    assert session.mark_navigation_started() is True
    assert session.mark_arrived() is True
    assert session.snapshot()["phase"] == "ARRIVED"
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_demo_session.py

Expected: FAIL，缺少 voice_assistant.demo_session。

- [ ] **Step 3: 实现最小状态机。**

~~~python
from enum import Enum
from threading import RLock
from uuid import uuid4


class DemoPhase(str, Enum):
    READY = "READY"
    SCANNING = "SCANNING"
    WELCOME_PENDING = "WELCOME_PENDING"
    LISTENING = "LISTENING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    NAVIGATING = "NAVIGATING"
    ARRIVED = "ARRIVED"
    RECOVERY = "RECOVERY"


class DemoSession:
    def __init__(self):
        self._lock = RLock()
        self._session_id = None
        self._phase = DemoPhase.READY
        self._display_name = None
        self._department_id = None
        self._welcome_claimed = False
        self._recovery_reason = None

    def start(self):
        with self._lock:
            self._session_id = uuid4().hex
            self._phase = DemoPhase.SCANNING
            self._display_name = self._department_id = self._recovery_reason = None
            self._welcome_claimed = False
            return self.snapshot()

    def set_welcome(self, display_name):
        with self._lock:
            if self._phase is not DemoPhase.SCANNING:
                return False
            self._display_name = str(display_name).strip() or None
            self._phase, self._welcome_claimed = DemoPhase.WELCOME_PENDING, False
            return True

    def claim_welcome(self):
        with self._lock:
            if self._phase is not DemoPhase.WELCOME_PENDING or self._welcome_claimed:
                return None
            self._welcome_claimed = True
            return {"session_id": self._session_id, "text": "你好，%s。请问您需要去哪个科室？" % (self._display_name or "访客")}

    def acknowledge_welcome(self, session_id):
        with self._lock:
            if self._phase is not DemoPhase.WELCOME_PENDING or not self._welcome_claimed or session_id != self._session_id:
                return False
            self._phase = DemoPhase.LISTENING
            return True

    def mark_waiting_confirmation(self, department_id):
        with self._lock:
            if self._phase is not DemoPhase.LISTENING:
                return False
            self._department_id, self._phase = str(department_id), DemoPhase.WAITING_CONFIRMATION
            return True

    def mark_navigation_started(self):
        with self._lock:
            if self._phase is not DemoPhase.WAITING_CONFIRMATION:
                return False
            self._phase = DemoPhase.NAVIGATING
            return True

    def mark_arrived(self):
        with self._lock:
            if self._phase is not DemoPhase.NAVIGATING:
                return False
            self._phase = DemoPhase.ARRIVED
            return True

    def recover(self, reason):
        with self._lock:
            self._phase, self._recovery_reason = DemoPhase.RECOVERY, str(reason)
            return self.snapshot()

    def snapshot(self):
        with self._lock:
            return {"session_id": self._session_id, "phase": self._phase.value, "display_name": self._display_name, "department_id": self._department_id, "recovery_reason": self._recovery_reason}
~~~

- [ ] **Step 4: 运行 GREEN 测试。**

Run: python -m pytest -q tests/test_demo_session.py

Expected: PASS。

- [ ] **Step 5: 提交。**

~~~bash
git add voice_assistant/demo_session.py tests/test_demo_session.py
git commit -m "feat: add hospital demo session state"
~~~

### Task 2: 抽取无副作用的人脸识别服务

**Files:**
- Create: face/recognition.py
- Modify: face/routes.py:8-94
- Create: tests/test_face_recognition_service.py

- [ ] **Step 1: 写失败测试，锁定既有 API 返回形状和 404 行为。**

~~~python
from unittest.mock import patch
from face.recognition import identify_from_bytes


def test_identify_from_bytes_keeps_success_shape():
    result = {"ok": True, "user_id": "u1", "score": 93.0, "candidates": []}
    with patch("face.recognition.baidu.identify_person", return_value=result), patch("face.recognition.store.get_user_by_id", return_value={"username": "王小明", "email": "x@example.test"}):
        payload, status = identify_from_bytes(b"jpeg")
    assert status == 200
    assert payload["identity"] == "王小明"
    assert payload["confidence"] == 0.93


def test_unknown_face_remains_404():
    with patch("face.recognition.baidu.identify_person", return_value={"ok": False, "error_code": 222207, "msg": "未识别"}):
        payload, status = identify_from_bytes(b"jpeg")
    assert status == 404
    assert payload == {"ok": False, "msg": "未识别", "error_code": 222207}
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_face_recognition_service.py

Expected: FAIL，缺少 face.recognition。

- [ ] **Step 3: 迁移现有私有实现。**

将 face/routes.py 的 _build_success 与 _identify_from_bytes 原样迁移至 face/recognition.py，重命名公开函数为 identify_from_bytes。该文件导入 baidu、store 与 resolve_display_name；返回值继续是二元组 payload、status。

将路由改为：

~~~python
from .recognition import identify_from_bytes

payload, status = identify_from_bytes(_read_image_file(image))
~~~

仅浏览器 route 在 status 为 200 且 ok 时保留 threading.Thread target=play_say 的现有行为。自动扫描器只能调用新服务，绝不能调用 TTS。

- [ ] **Step 4: 运行 GREEN 与兼容回归。**

Run: python -m pytest -q tests/test_face_recognition_service.py tests/test_hospital_guide.py

Expected: PASS。

- [ ] **Step 5: 提交。**

~~~bash
git add face/recognition.py face/routes.py tests/test_face_recognition_service.py
git commit -m "refactor: extract face recognition service"
~~~

### Task 3: 为导诊编排器添加最小、受锁保护的演示事件

**Files:**
- Modify: voice_assistant/hospital_guide.py
- Modify: hospital_guide_bridge.py
- Modify: tests/test_hospital_guide_bridge.py

- [ ] **Step 1: 写失败测试。**

~~~python
def test_guide_event_requires_confirmation_before_navigation(self):
    events = []
    with TemporaryDirectory() as directory:
        client, _ = self._create_client(directory, enabled=True, on_guide_event=events.append)
        client.post("/api/hospital-guide/turn", json={"text": "我要去内科"})
        client.post("/api/hospital-guide/turn", json={"text": "好的，带我去"})
    assert events == [
        {"type": "department_matched", "department_id": "internal_medicine"},
        {"type": "navigation_started", "department_id": "internal_medicine"},
    ]


def test_bridge_reset_discards_pending_department(self):
    with TemporaryDirectory() as directory:
        client, _ = self._create_client(directory, enabled=True)
        client.post("/api/hospital-guide/turn", json={"text": "我要去内科"})
        self.bridge.reset()
        assert "导航" not in client.post("/api/hospital-guide/turn", json={"text": "好的，带我去"}).get_json()["data"]["reply"]
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_hospital_guide_bridge.py -k "guide_event or bridge_reset"

Expected: FAIL，未知 on_guide_event 或缺少 reset。

- [ ] **Step 3: 实现事件接口。**

在 HospitalGuideOrchestrator 构造函数尾部添加 on_guide_event=None，存为 self._on_guide_event。添加如下方法：

~~~python
def _emit_guide_event(self, event_type, department=None):
    if self._on_guide_event is not None:
        self._on_guide_event({"type": event_type, "department_id": department.department_id if department else None})
~~~

在匹配 department 后、设置 pending id 后调用 department_matched；在 _start_pending_navigation 中，且仅在 self._car_client.navigate_to 成功返回后调用 navigation_started。回调不得接收 ASR 原文、人脸结果、置信度、邮箱、电话、密码、图片或 LLM evidence。

HospitalGuideBridge 添加：

~~~python
def reset(self):
    with self._lock:
        self.orchestrator.reset()

def set_guide_event_handler(self, handler):
    with self._lock:
        self.orchestrator._on_guide_event = handler
~~~

register_hospital_guide_bridge 增加关键字参数 on_guide_event=None，并传给 orchestrator。

- [ ] **Step 4: 运行 GREEN 回归。**

Run: python -m pytest -q tests/test_hospital_guide.py tests/test_hospital_guide_bridge.py tests/test_hospital_guide_client.py

Expected: PASS。

- [ ] **Step 5: 提交。**

~~~bash
git add voice_assistant/hospital_guide.py hospital_guide_bridge.py tests/test_hospital_guide_bridge.py
git commit -m "feat: publish hospital guide demo events"
~~~

### Task 4: 创建自动扫描和演示 Flask 控制器

**Files:**
- Create: hospital_guide_demo.py
- Modify: api_server.py:34-56
- Create: tests/test_hospital_guide_demo.py

- [ ] **Step 1: 写失败测试。**

~~~python
from flask import Flask
from hospital_guide_demo import HospitalGuideDemoController, register_hospital_guide_demo


def test_camera_failure_falls_back_to_guest_after_timeout():
    bridge = type("Bridge", (), {"reset": lambda self: None})()
    controller = HospitalGuideDemoController(bridge=bridge, snapshot_fetcher=lambda: (_ for _ in ()).throw(RuntimeError("camera")), recognizer=lambda _: ({}, 503), scan_timeout_s=0.0)
    controller.start()
    controller.scan_once()
    assert controller.claim_welcome()["text"] == "你好，访客。请问您需要去哪个科室？"


def test_navigation_event_outside_confirmation_is_rejected():
    controller = HospitalGuideDemoController(bridge=type("Bridge", (), {"reset": lambda self: None})())
    controller.start()
    assert controller.on_guide_event({"type": "navigation_started", "department_id": "internal_medicine"}) is False


def test_claim_absent_welcome_is_204_and_bad_ack_is_409():
    app = Flask(__name__)
    controller = HospitalGuideDemoController(bridge=type("Bridge", (), {"reset": lambda self: None})())
    register_hospital_guide_demo(app, controller)
    client = app.test_client()
    assert client.post("/api/hospital-guide/demo/claim-welcome").status_code == 204
    started = client.post("/api/hospital-guide/demo/start").get_json()["data"]
    assert client.post("/api/hospital-guide/demo/ack-welcome", json={"session_id": started["session_id"]}).status_code == 409
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_hospital_guide_demo.py

Expected: FAIL，缺少 hospital_guide_demo。

- [ ] **Step 3: 实现控制器及 API。**

HospitalGuideDemoController 使用 DemoSession。snapshot_fetcher 默认通过 urllib.request.urlopen 读取固定 URL http://127.0.0.1:8080/snapshot?topic=/camera/color/image_raw，timeout=3，并拒绝小于 500 bytes 的响应；recognizer 默认使用 face.recognition.identify_from_bytes。

实现以下最小方法：

~~~python
def start(self):
    self._bridge.reset()
    started = self._session.start()
    self._start_scanner(started["session_id"])
    return started

def scan_once(self):
    if self._session.snapshot()["phase"] != "SCANNING":
        return False
    try:
        payload, status = self._recognizer(self._snapshot_fetcher())
    except Exception:
        payload, status = {}, 503
    name = payload.get("identity") if status == 200 and payload.get("ok") and float(payload.get("confidence", 0)) >= self._confidence_threshold else None
    return self._session.set_welcome(name)

def on_guide_event(self, event):
    if event.get("department_id") != "internal_medicine":
        return False
    if event.get("type") == "department_matched":
        return self._session.mark_waiting_confirmation("internal_medicine")
    if event.get("type") == "navigation_started":
        return self._session.mark_navigation_started()
    return False
~~~

_start_scanner 必须在 lock 下保证同时只存在一个 daemon；每 0.5 秒 scan_once；session ID 被替换或 phase 改变即退出；达到 scan_timeout_s 后只调用一次 set_welcome(None)。

注册接口：

~~~text
POST /api/hospital-guide/demo/start          -> 200 code 0 与 session
POST /api/hospital-guide/demo/reset          -> 等同 start，生成新 session ID
GET  /api/hospital-guide/demo/status         -> 200 code 0 与公共状态
POST /api/hospital-guide/demo/claim-welcome  -> 204 或 200 code 0 与 session_id/text
POST /api/hospital-guide/demo/ack-welcome    -> 匹配且领取过返回 200，否则 409
~~~

在 api_server.py 保存 bridge 变量，创建 controller，调用 bridge.set_guide_event_handler(controller.on_guide_event)，然后 register_hospital_guide_demo(app, controller)。保留现有 face route 与导航注册顺序。

- [ ] **Step 4: 运行 GREEN。**

Run: python -m pytest -q tests/test_demo_session.py tests/test_hospital_guide_demo.py tests/test_hospital_guide_bridge.py

Expected: PASS。

- [ ] **Step 5: 提交。**

~~~bash
git add hospital_guide_demo.py api_server.py tests/test_hospital_guide_demo.py hospital_guide_bridge.py
git commit -m "feat: add automatic hospital demo controller"
~~~

### Task 5: Jetson 一次性欢迎播报和 ASR 接管

**Files:**
- Create: voice_assistant/demo_session_client.py
- Modify: voice_assistant/car_client_jetson.py
- Create: tests/test_demo_session_client.py
- Modify: scripts/start_hospital_guide_demo.sh
- Modify: tests/test_hospital_guide_demo_launcher.py

**Dirty-worktree constraint:** 后两个文件当前已有用户修改。实现者必须先检查 git diff，只以最小补丁合并本任务的环境开关和断言，不得覆盖、暂存或提交其它用户变更。

- [ ] **Step 1: 写失败测试。**

~~~python
from voice_assistant.demo_session_client import DemoWelcomePoller


def test_each_session_is_acknowledged_and_returned_once():
    claims = iter([{"session_id": "s1", "text": "你好"}, {"session_id": "s1", "text": "重复"}, None])
    calls = []
    poller = DemoWelcomePoller(claim=lambda: next(claims), ack=lambda ident: calls.append(ident) or True)
    assert poller.poll_once() == {"session_id": "s1", "text": "你好"}
    assert poller.poll_once() is None
    assert calls == ["s1"]
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_demo_session_client.py

Expected: FAIL，缺少 demo_session_client。

- [ ] **Step 3: 实现轮询器与车端接入。**

~~~python
import json
from urllib import request

class DemoWelcomePoller:
    def __init__(self, base_url="http://127.0.0.1:5000", timeout=2.0, claim=None, ack=None):
        self.base_url, self.timeout, self._seen = base_url.rstrip("/"), float(timeout), set()
        self._claim, self._ack = claim or self._http_claim, ack or self._http_ack
    def poll_once(self):
        payload = self._claim()
        if not payload or payload.get("session_id") in self._seen:
            return None
        if not self._ack(payload["session_id"]):
            return None
        self._seen.add(payload["session_id"])
        return {"session_id": payload["session_id"], "text": str(payload["text"])}
~~~

_http_claim POST 到 /api/hospital-guide/demo/claim-welcome，204 返回 None；_http_ack JSON POST session_id 到 ack-welcome，只有 200 返回 True，任何网络错误返回 False。

在 car_client_jetson.py 增加：

~~~python
HOSPITAL_GUIDE_DEMO_MODE = os.environ.get("MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE") == "1"
~~~

仅当 HOSPITAL_GUIDE_MODE 与 HOSPITAL_GUIDE_DEMO_MODE 都为真时，在 _connect_and_stream 中启动 0.5 秒 daemon poll loop。每条领取到的欢迎语严格按此顺序执行：

~~~python
_guide_mark_asleep()
_speak(payload["text"], capture_gate=capture_gate, send_control=_send_control)
_guide_mark_awake()
~~~

CaptureGate 不可移除。普通导诊 final_text 在欢迎 ack 前保持忽略；非演示模式的行为完全不变。启动脚本传入 MINIMOVER_HOSPITAL_GUIDE_DEMO_MODE=1，并在复用进程时同时验证 guide 与 demo 两个环境变量。

- [ ] **Step 4: 运行 GREEN 与启动器回归。**

Run: python -m pytest -q tests/test_demo_session_client.py tests/test_audio_turn_safety.py tests/test_hospital_guide_demo_launcher.py

Expected: PASS。

- [ ] **Step 5: 提交。**

~~~bash
git add voice_assistant/demo_session_client.py voice_assistant/car_client_jetson.py tests/test_demo_session_client.py
# 仅在确认 diff 只含本任务增量后再 add：
git add scripts/start_hospital_guide_demo.sh tests/test_hospital_guide_demo_launcher.py
git commit -m "feat: speak hospital demo welcome automatically"
~~~

### Task 6: Nav2 goal 追踪、到达双条件和默认关闭的取消

**Files:**
- Modify: navigation/ros_bridge.py:415-427
- Modify: navigation/routes.py:212-216
- Create: tests/test_demo_navigation.py

- [ ] **Step 1: 写失败测试。**

~~~python
from unittest.mock import patch
from navigation import ros_bridge


def test_arrival_requires_succeeded_and_map_tolerance():
    ros_bridge._demo_goal = {"x": 1.0, "y": 2.0, "theta": 0.0, "status": "SUCCEEDED", "message": "Goal finished with status: SUCCEEDED"}
    with patch.object(ros_bridge, "get_robot_pose", return_value={"valid": True, "frame_id": "map", "x": 1.10, "y": 2.0, "yaw": 0.0}):
        status = ros_bridge.demo_goal_status(tolerance=0.15)
    assert status["arrived"] is True
    assert status["distance_m"] == 0.1


def test_active_goal_never_claims_arrived():
    ros_bridge._demo_goal = {"x": 1.0, "y": 2.0, "theta": 0.0, "status": "ACTIVE", "message": "Goal accepted"}
    assert ros_bridge.demo_goal_status()["arrived"] is False


def test_cancel_disabled_without_verified_environment(monkeypatch):
    monkeypatch.delenv("MINIMOVER_DEMO_CANCEL_ENABLED", raising=False)
    assert ros_bridge.cancel_demo_goal()["success"] is False
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_demo_navigation.py

Expected: FAIL，缺少 demo_goal_status。

- [ ] **Step 3: 实现真实 action 状态与到达计算。**

在 ros_bridge.py 定义 _demo_goal_lock=threading.RLock() 与 _demo_goal=None。将 navigate_to 保持现有请求体与成功响应，但 subprocess.Popen 改为 stdout=PIPE、stderr=STDOUT、text=True，并在后台 reader 读取 ros2 action send_goal 的 --feedback 输出。只允许一个 PENDING 或 ACTIVE goal；另一个请求应返回 success False。

状态机只可由实际输出变化：包含 Goal accepted 为 ACTIVE；包含 Goal finished with status: SUCCEEDED 为 SUCCEEDED；包含 CANCELED 或 Goal canceled 为 CANCELLED；进程退出但没有 SUCCEEDED 为 FAILED。不得由 HTTP accepted 置为 SUCCEEDED。

~~~python
def demo_goal_status(tolerance=0.15):
    with _demo_goal_lock:
        goal = dict(_demo_goal) if _demo_goal else None
    if not goal:
        return {"active": False, "arrived": False, "status": "IDLE", "message": "no demo navigation goal"}
    pose = get_robot_pose(force=True)
    distance = None
    arrived = False
    if goal["status"] == "SUCCEEDED" and pose.get("valid") and pose.get("frame_id") == "map":
        distance = math.hypot(float(pose["x"]) - goal["x"], float(pose["y"]) - goal["y"])
        arrived = distance <= float(tolerance)
    return {"active": goal["status"] in {"PENDING", "ACTIVE"}, "arrived": arrived, "status": goal["status"], "message": goal["message"], "target": {"x": goal["x"], "y": goal["y"], "theta": goal["theta"]}, "pose": pose, "distance_m": distance, "tolerance_m": float(tolerance)}

def cancel_demo_goal():
    if os.environ.get("MINIMOVER_DEMO_CANCEL_ENABLED") != "1":
        return {"success": False, "message": "demo cancel is disabled until verified on the real vehicle"}
    # 仅运行 runbook 中已实车验证的 Nav2 cancel 命令；不能调用 /api/move。
~~~

在实际验证取消命令前，保持 MINIMOVER_DEMO_CANCEL_ENABLED 未设置。只有 ROS 命令真实确认取消后才能更新 goal 为 CANCELLED。

在 navigation/routes.py 新增：

~~~python
@nav_bp.route("/demo/goal-status", methods=["GET"])
def demo_goal_status_api():
    return _ok(ros_bridge.demo_goal_status())

@nav_bp.route("/demo/cancel", methods=["POST"])
def demo_cancel_api():
    result = ros_bridge.cancel_demo_goal()
    return _ok(result, result["message"]) if result.get("success") else _err(result["message"], 409)
~~~

- [ ] **Step 4: 运行 GREEN 与位姿回归。**

Run: python -m pytest -q tests/test_demo_navigation.py tests/test_navigation_pose.py

Expected: PASS。

- [ ] **Step 5: 提交。**

~~~bash
git add navigation/ros_bridge.py navigation/routes.py tests/test_demo_navigation.py
git commit -m "feat: track hospital demo navigation status"
~~~

### Task 7: 控制台只展示匿名化演示状态与真实证据

**Files:**
- Modify: hospital_guide_demo.py
- Modify: hospital_guide_console.py
- Modify: tests/test_hospital_guide_demo.py
- Modify: tests/test_hospital_guide_console.py

- [ ] **Step 1: 写失败测试。**

~~~python
def test_arrival_transition_uses_real_navigation_evidence_only():
    bridge = type("Bridge", (), {"reset": lambda self: None})()
    controller = HospitalGuideDemoController(bridge=bridge, navigation_status=lambda: {"arrived": False})
    controller.start()
    controller._session.set_welcome(None)
    claim = controller.claim_welcome()
    controller.acknowledge_welcome(claim["session_id"])
    controller.on_guide_event({"type": "department_matched", "department_id": "internal_medicine"})
    controller.on_guide_event({"type": "navigation_started", "department_id": "internal_medicine"})
    assert controller.refresh_navigation() is False
    controller._navigation_status = lambda: {"arrived": True}
    assert controller.refresh_navigation() is True
    assert controller.status()["phase"] == "ARRIVED"


def test_console_has_demo_fields_but_no_face_sensitive_fields():
    from hospital_guide_console import HOSPITAL_GUIDE_CONSOLE_HTML
    assert "demo-phase-value" in HOSPITAL_GUIDE_CONSOLE_HTML
    assert "demo-identity-value" in HOSPITAL_GUIDE_CONSOLE_HTML
    assert "confidence" not in HOSPITAL_GUIDE_CONSOLE_HTML
    assert "candidates" not in HOSPITAL_GUIDE_CONSOLE_HTML
    assert "face_image" not in HOSPITAL_GUIDE_CONSOLE_HTML
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_hospital_guide_demo.py tests/test_hospital_guide_console.py

Expected: FAIL。

- [ ] **Step 3: 实现状态合成和只读 UI。**

~~~python
def refresh_navigation(self):
    result = self._navigation_status()
    if result.get("arrived"):
        return self._session.mark_arrived()
    if result.get("status") in {"FAILED", "CANCELLED"}:
        self._session.recover(result.get("message", "navigation stopped"))
    return False

def public_status(self):
    self.refresh_navigation()
    return {"session": self._session.snapshot(), "navigation": self._navigation_status()}
~~~

status API 返回 public_status。hospital_guide_console.py 每秒请求 demo/status，并只渲染 phase、display_name 或访客模式、action 状态、目标、map pose、distance_m、tolerance_m、recovery_reason。只有 navigation.arrived 为 true 显示已到达；PENDING、ACTIVE、FAILED、CANCELLED 原样显示。不得增加停止、移动或取消按钮。

- [ ] **Step 4: 运行 GREEN。**

Run: python -m pytest -q tests/test_hospital_guide_demo.py tests/test_hospital_guide_console.py tests/test_hospital_guide_telemetry.py

Expected: PASS。

- [ ] **Step 5: 提交。**

~~~bash
git add hospital_guide_demo.py hospital_guide_console.py tests/test_hospital_guide_demo.py tests/test_hospital_guide_console.py
git commit -m "feat: display hospital demo navigation evidence"
~~~

### Task 8: 内科点位标定、配置守卫和演示 Runbook

**Files:**
- Modify: voice_assistant/data/hospital_guide_template.json
- Create: docs/runbooks/five-minute-hospital-guide-demo.md
- Create: tests/test_hospital_guide_demo_config.py

- [ ] **Step 1: 写失败配置测试。**

~~~python
import json
from pathlib import Path

def test_only_internal_medicine_has_a_real_enabled_target():
    data = json.loads(Path("voice_assistant/data/hospital_guide_template.json").read_text(encoding="utf-8"))
    enabled = [item for item in data["departments"] if item["navigation"]["enabled"]]
    assert [item["id"] for item in enabled] == ["internal_medicine"]
    target = enabled[0]["navigation"]
    assert all(isinstance(target[key], (int, float)) for key in ("x", "y", "theta"))
    assert (target["x"], target["y"]) != (0.0, 0.0)
~~~

- [ ] **Step 2: 运行 RED 测试。**

Run: python -m pytest -q tests/test_hospital_guide_demo_config.py

Expected: FAIL，因为目前没有已启用实车内科点位。

- [ ] **Step 3: 清场实车采集、双人复核并写入真实点位。**

~~~bash
# 启动实际使用的 Nav2 地图环境，确认这两个服务可用：
ros2 action list | grep navigate_to_pose
ros2 service list | grep patrol/get_robot_pose
curl -fsS http://127.0.0.1:5000/api/nav/pose
~~~

在固定起点设置初始位姿，手动把车移到安全的内科候诊区终点，从 pose API 记录有限十进制 x、y、yaw，并由第二名操作员复核。仅将 internal_medicine 的 navigation 修改为 enabled true 和这三个实测数字；任何其它科室继续 false。不能提交零点、尖括号占位符或推测坐标。

随后从同一固定起点连续实走三次。每次记录 action 最终状态、pose valid/frame_id、终点距离、0.15 m 结果及人工确认停车结果。任意失败立即将内科重新禁用，修复后从第一次重新计数。

- [ ] **Step 4: 编写 runbook。**

Runbook 必须逐字包含以下要点：

~~~markdown
# 五分钟医院导诊小车演示 Runbook
## 演示前检查
- 清场、指定安全操作员和硬件停止路径。
- 检查 /api/nav/stack/status 与 /api/nav/pose；valid 必须为 true，frame_id 必须为 map。
- 预注册演示者；不导出照片、候选项或置信度。
## 启动
- 在 PC 上运行 hostname -I 获取 ASR 主机 IPv4；将实际 IPv4 作为第一个参数运行 bash scripts/start_hospital_guide_demo.sh 192.168.1.10 8765。
- 打开 /hospital-guide、/nav/patrol、/api/hospital-guide/demo/status。
## 五分钟脚本
1. 00:00–00:30 POST /api/hospital-guide/demo/start，等待个人或访客欢迎。
2. 00:30–01:30 说“我要去内科”。
3. 01:30–02:00 说“好的，带我去”。
4. 02:00–04:30 安全操作员随车，ACTIVE 不得称为到达。
5. 04:30–05:00 仅 status.arrived=true 时播报到达；否则报告真实原因并安全结束。
## 恢复
- 相机或人脸失败：访客导诊；不阻塞。
- ASR/TTS 失败：结束本轮，重新 start；不手工伪造 ack。
- Nav2 或定位失败：报告失败，安全停止，重新标定。
- 取消仅在 MINIMOVER_DEMO_CANCEL_ENABLED=1 且实车验证后使用；move API 不可替代。
## 放行
- 内科坐标、两名复核人、三次试跑、软件 commit、操作员和日期。
~~~

- [ ] **Step 5: 运行 GREEN 与全量 Python 回归。**

Run: python -m pytest -q tests/test_hospital_guide.py tests/test_hospital_guide_bridge.py tests/test_hospital_guide_client.py tests/test_hospital_guide_console.py tests/test_hospital_guide_telemetry.py tests/test_hospital_guide_demo_launcher.py tests/test_demo_session.py tests/test_face_recognition_service.py tests/test_hospital_guide_demo.py tests/test_demo_session_client.py tests/test_demo_navigation.py tests/test_hospital_guide_demo_config.py tests/test_navigation_pose.py

Expected: PASS。

- [ ] **Step 6: 提交。**

~~~bash
git add voice_assistant/data/hospital_guide_template.json docs/runbooks/five-minute-hospital-guide-demo.md tests/test_hospital_guide_demo_config.py
git commit -m "docs: add hospital demo calibration runbook"
~~~

### Task 9: 集成、实车安全验证和发布审查

**Files:**
- Modify only if a verification command reveals a specific defect in a file named above.
- Never commit generated build/install/log folders, credentials, face images, ASR logs, .reasonix data or pre-existing unrelated user changes.

- [ ] **Step 1: 跑自动化、差异与范围检查。**

~~~bash
python -m pytest -q tests/test_hospital_guide.py tests/test_hospital_guide_bridge.py tests/test_hospital_guide_client.py tests/test_hospital_guide_console.py tests/test_hospital_guide_telemetry.py tests/test_hospital_guide_demo_launcher.py tests/test_demo_session.py tests/test_face_recognition_service.py tests/test_hospital_guide_demo.py tests/test_demo_session_client.py tests/test_demo_navigation.py tests/test_hospital_guide_demo_config.py tests/test_navigation_pose.py
git diff --check
git status --short
~~~

Expected: 全部 PASS；diff check 无输出；提交范围仅含本计划文件。

- [ ] **Step 2: 清场实车验证全部门控。**

~~~bash
curl -fsS -X POST http://127.0.0.1:5000/api/hospital-guide/demo/start
curl -fsS http://127.0.0.1:5000/api/hospital-guide/demo/status
curl -fsS http://127.0.0.1:5000/api/nav/demo/goal-status
~~~

验证成功识别、访客降级、未确认不导航、确认后 ACTIVE、SUCCEEDED 但距离超容差时仍不 arrived、双条件满足后才 arrived。取消验证若未成功，保持环境变量未设置并从演示 UI 移除该能力。

- [ ] **Step 3: 代码审查和最小修复提交。**

审查每个公开 API 的状态码、敏感字段、导航门控与到达门控。任何修复必须先补失败测试，再运行针对性 GREEN 和 Step 1 全量回归。

~~~bash
git add -- navigation/ros_bridge.py tests/test_demo_navigation.py
git commit -m "fix: harden hospital demo integration"
~~~

---

## 计划自检

- **设计覆盖：** Task 1 覆盖会话和欢迎去重；Task 2 覆盖无副作用人脸识别；Task 3–5 覆盖导诊事件、自动扫描与 Jetson TTS/ASR；Task 6–7 覆盖 Nav2 真状态、到达判定、控制台；Task 8–9 覆盖真实点位、三次试跑、runbook 和安全放行。
- **无占位实现：** 代码任务给出函数、状态、接口、测试与命令；现场坐标明确要求来自实车双人复核，未测得前不可启用。
- **类型一致：** session phase、on_guide_event、navigation status、public_status 与 HTTP 路由名称在所有任务中一致。
- **范围安全：** 计划承认并保护当前 dirty worktree；任何时候都不将用户已有改动混入当前功能提交。
