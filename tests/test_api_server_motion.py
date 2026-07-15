import importlib.util
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
    def __init__(self, *args, **kwargs):
        self.motion_calls = []

    def create_receive_threading(self):
        pass

    def set_car_motion(self, vx, vy, vz):
        self.motion_calls.append((vx, vy, vz))


def _load_api_server():
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

    modules = {
        'sensors': sensor_package,
        'sensors.icar_sensor_driver': sensor_driver,
        'Rosmaster_Lib': rosmaster,
        'audio': audio_package,
        'audio.icar_audio': audio_driver,
        'navigation': navigation,
        'face': face,
    }
    spec = importlib.util.spec_from_file_location('api_server_under_test', Path(__file__).parents[1] / 'api_server.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
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


if __name__ == '__main__':
    unittest.main()
