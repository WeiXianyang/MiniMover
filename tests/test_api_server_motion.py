import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Blueprint


class _FakeSensor:
    def get_data(self):
        return {}


class _FakeBot:
    instances = 0
    receive_thread_calls = 0

    def __init__(self, *args, **kwargs):
        type(self).instances += 1
        self.motion_calls = []

    def create_receive_threading(self):
        type(self).receive_thread_calls += 1

    def set_car_motion(self, vx, vy, vz):
        self.motion_calls.append((vx, vy, vz))


def _load_api_server(env=None):
    sensor_package = types.ModuleType('sensors')
    sensor_package.__path__ = []
    sensor_driver = types.ModuleType('sensors.icar_sensor_driver')
    sensor_driver.iCarSensorDriver = _FakeSensor

    rosmaster = types.ModuleType('Rosmaster_Lib')
    rosmaster.Rosmaster = _FakeBot

    audio_package = types.ModuleType('audio')
    audio_package.__path__ = []
    audio_driver = types.ModuleType('audio.icar_audio')
    for name in ('record_start', 'record_status', 'record_stop', 'record_get',
                 'play_wav', 'stop_playback', 'say', 'get_devices'):
        setattr(audio_driver, name, lambda *args, **kwargs: {} if name == 'get_devices' else b'')

    navigation = types.ModuleType('navigation')
    navigation.nav_bp = Blueprint('nav', __name__)
    navigation.register_legacy_routes = lambda app: None
    navigation.register_patrol_page = lambda app: None

    face = types.ModuleType('face')
    face.register_face_routes = lambda app: None

    hospital_guide_console = types.ModuleType('hospital_guide_console')
    hospital_guide_console.register_hospital_guide_console = lambda *args, **kwargs: None

    hospital_guide_bridge = types.ModuleType('hospital_guide_bridge')

    class _FakeGuideBridge:
        def set_guide_event_handler(self, handler):
            self.handler = handler

    hospital_guide_bridge.register_hospital_guide_bridge = lambda *args, **kwargs: _FakeGuideBridge()

    hospital_guide_demo = types.ModuleType('hospital_guide_demo')

    class _FakeDemoController:
        def __init__(self, bridge):
            self.bridge = bridge

        def on_guide_event(self, event):
            return None

    hospital_guide_demo.HospitalGuideDemoController = _FakeDemoController
    hospital_guide_demo.register_hospital_guide_demo = lambda *args, **kwargs: None

    modules = {
        'sensors': sensor_package,
        'sensors.icar_sensor_driver': sensor_driver,
        'Rosmaster_Lib': rosmaster,
        'audio': audio_package,
        'audio.icar_audio': audio_driver,
        'navigation': navigation,
        'face': face,
        'hospital_guide_console': hospital_guide_console,
        'hospital_guide_bridge': hospital_guide_bridge,
        'hospital_guide_demo': hospital_guide_demo,
    }
    spec = importlib.util.spec_from_file_location('api_server_under_test', Path(__file__).parents[1] / 'api_server.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules), patch.dict(os.environ, env or {}, clear=False):
        spec.loader.exec_module(module)
    return module


class ApiServerMovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_server = _load_api_server()

    def setUp(self):
        self.api_server.bot = _FakeBot()
        self.api_server._stop_deadline = 0.0

    def test_http_move_clamps_speed_and_sets_watchdog_deadline(self):
        response = self.api_server.app.test_client().post(
            '/api/move', json={'cmd': 'left', 'speed': '150', 'duration': '0.5'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['msg'], 'left @ 100%')
        self.assertEqual(self.api_server.bot.motion_calls, [(0.0, 0.0, 3.0)])
        self.assertGreater(self.api_server._stop_deadline, self.api_server.time.monotonic())

    def test_invalid_http_move_is_rejected_without_touching_the_chassis(self):
        response = self.api_server.app.test_client().post(
            '/api/move', json={'cmd': 'teleport', 'speed': 50, 'duration': 0.5}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.api_server.bot.motion_calls, [])

    def test_stop_clears_the_watchdog_deadline(self):
        self.api_server._stop_deadline = self.api_server.time.monotonic() + 60

        response = self.api_server.app.test_client().post('/api/move', json={'cmd': 'stop'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.api_server.bot.motion_calls, [(0.0, 0.0, 0.0)])
        self.assertEqual(self.api_server._stop_deadline, 0.0)

    def test_watchdog_stops_only_after_an_expired_deadline(self):
        self.api_server._stop_deadline = self.api_server.time.monotonic() - 0.1

        self.assertTrue(self.api_server._stop_if_deadline_elapsed())
        self.assertEqual(self.api_server.bot.motion_calls, [(0.0, 0.0, 0.0)])
        self.assertEqual(self.api_server._stop_deadline, 0.0)
        self.assertFalse(self.api_server._stop_if_deadline_elapsed())


class ApiServerNavOwnedChassisTests(unittest.TestCase):
    def setUp(self):
        _FakeBot.instances = 0
        _FakeBot.receive_thread_calls = 0
        self.api_server = _load_api_server({"MINIMOVER_NAV_OWNS_CHASSIS": "1"})

    def test_nav_owned_mode_does_not_open_rosmaster_serial(self):
        self.assertIsNone(self.api_server.bot)
        self.assertEqual(_FakeBot.instances, 0)
        self.assertEqual(_FakeBot.receive_thread_calls, 0)

    def test_nav_owned_mode_keeps_status_available_without_chassis(self):
        self.api_server.get_ip = lambda: '127.0.0.1'
        response = self.api_server.app.test_client().get('/api/status')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data']['battery'], 12.0)

    def test_nav_owned_mode_rejects_legacy_motion_commands(self):
        response = self.api_server.app.test_client().post(
            '/api/move', json={'cmd': 'forward', 'speed': 50, 'duration': 0.5}
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()['code'], -1)
        self.assertIn('Nav2', response.get_json()['msg'])

    def test_nav_owned_mode_watchdog_never_touches_missing_chassis(self):
        self.api_server._stop_deadline = self.api_server.time.monotonic() - 0.1

        self.assertFalse(self.api_server._stop_if_deadline_elapsed())
        self.assertEqual(self.api_server._stop_deadline, 0.0)


if __name__ == '__main__':
    unittest.main()
