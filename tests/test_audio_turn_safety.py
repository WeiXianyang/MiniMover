from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from voice_assistant.audio_turn_safety import CaptureGate, normalized_rms, wav_duration_ms


class AudioTurnSafetyTests(unittest.TestCase):
    def test_capture_is_muted_during_playback_and_post_playback_tail(self):
        now = [100.0]
        gate = CaptureGate(post_playback_ms=600, clock=lambda: now[0])

        gate.begin_playback()
        self.assertTrue(gate.is_muted())

        gate.finish_playback(1000)
        now[0] += 1.59
        self.assertTrue(gate.is_muted())
        now[0] += 0.02
        self.assertFalse(gate.is_muted())

    def test_overlapping_playbacks_keep_capture_muted_until_last_playback_ends(self):
        now = [0.0]
        gate = CaptureGate(post_playback_ms=100, clock=lambda: now[0])

        gate.begin_playback()
        gate.begin_playback()
        gate.finish_playback(0)
        now[0] = 10.0
        self.assertTrue(gate.is_muted())

        gate.finish_playback(500)
        now[0] = 10.59
        self.assertTrue(gate.is_muted())
        now[0] = 10.61
        self.assertFalse(gate.is_muted())


    def test_new_playback_invalidates_a_pending_release(self):
        now = [0.0]
        gate = CaptureGate(post_playback_ms=100, clock=lambda: now[0])

        gate.begin_playback()
        release = gate.finish_playback(0)
        self.assertIsNotNone(release)
        _, generation = release

        gate.begin_playback()
        self.assertFalse(gate.can_release_capture(generation))

    def test_normalized_rms_uses_pcm_scale(self):
        self.assertAlmostEqual(normalized_rms([32767, -32768]), 1.0, delta=0.001)
        self.assertEqual(normalized_rms([]), 0.0)

    def test_wav_duration_clamps_streaming_placeholder_to_received_pcm(self):
        # DashScope may set the RIFF data chunk length to 0xFFFFFFFF for a
        # streaming response even though the returned bytes are complete.
        wav = (
            b"RIFF" + (36 + 32000).to_bytes(4, "little") + b"WAVEfmt "
            + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (0xFFFFFFFF).to_bytes(4, "little")
            + b"\x00" * 32000
        )
        self.assertEqual(wav_duration_ms(wav), 1000)
    def test_wav_duration_reads_pcm_metadata(self):
        wav = (
            b"RIFF" + (36 + 32000).to_bytes(4, "little") + b"WAVEfmt "
            + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (32000).to_bytes(4, "little")
            + b"\x00" * 32000
        )
        self.assertEqual(wav_duration_ms(wav), 1000)


    def test_hospital_guide_demo_has_no_legacy_wake_or_motion_path(self):
        client = Path("voice_assistant/car_client_jetson.py").read_text(encoding="utf-8")
        launcher = Path("scripts/start_hospital_guide_demo.sh").read_text(encoding="utf-8")
        asr = Path("voice_assistant/pc_asr_server.py").read_text(encoding="utf-8")

        self.assertIn('"type": "guide_mode"', client)
        self.assertIn('"final_text"', asr)
        for legacy_token in (
            "MINIMOVER_WAKE_WORD",
            "MINIMOVER_WAKE_GREETING",
            "_execute_command",
            "/api/move",
            "wake_detected",
            "chat_reply",
            "command_exit",
        ):
            self.assertNotIn(legacy_token, client)
        for legacy_token in (
            "pypinyin",
            "_COMMAND_PATTERNS",
            "_parse_command",
            "_is_exit",
            "wake_word",
            "wake_detected",
            "command_exit",
            '"command"',
        ):
            self.assertNotIn(legacy_token, asr)
        self.assertNotIn("MINIMOVER_HOSPITAL_GUIDE_MODE", launcher)
        self.assertNotIn("MINIMOVER_HOSPITAL_GUIDE_NO_WAKE", launcher)
        for legacy_path in (
            "voice_assistant/car_client.py",
            "voice_assistant/car_ws_client.py",
            "voice_assistant/command_parser.py",
            "voice_assistant/launcher.py",
            "voice_assistant/llm_client.py",
            "voice_assistant/voice_service.py",
            "voice_assistant/wake_word.py",
        ):
            self.assertFalse(Path(legacy_path).exists(), legacy_path)

    @patch("voice_assistant.car_client_jetson.time.sleep")
    @patch("requests.post")
    def test_tts_turn_sends_capture_gate_before_and_after_playback(self, post, sleep):
        from voice_assistant.car_client_jetson import _speak

        response = Mock()
        response.json.return_value = {"code": 0, "data": {"playback_duration_ms": 750}}
        post.return_value = response
        controls = []
        gate = CaptureGate(post_playback_ms=650)

        _speak("test response", capture_gate=gate, send_control=controls.append)

        self.assertEqual(controls, [
            {"type": "capture_gate", "active": True},
            {"type": "capture_gate", "active": False},
        ])
        sleep.assert_called_once_with(1.4)


    def test_dedicated_demo_starts_silently(self):
        source = Path("voice_assistant/car_client_jetson.py").read_text(encoding="utf-8")
        startup = source[source.index('print("Mic open, listening...", flush=True)'):source.index('            while ws.connected:')]
        self.assertNotIn("_speak(", startup)
        self.assertNotIn("/api/audio/say", startup)

    @patch("audio.icar_audio._dashscope_tts", side_effect=RuntimeError("provider unavailable"))
    def test_tts_does_not_silently_fall_back_when_dashscope_fails(self, dashscope_tts):
        from audio.icar_audio import say

        with patch.dict("os.environ", {"MINIMOVER_TTS_ALLOW_ESPEAK_FALLBACK": "0"}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "DashScope TTS failed"):
                say("??")
        dashscope_tts.assert_called_once_with("??")


    @patch("dashscope.audio.tts_v2.SpeechSynthesizer")
    def test_dashscope_tts_uses_wav_and_explicit_workspace(self, synthesizer):
        import dashscope
        from audio import icar_audio
        from dashscope.audio.tts_v2.speech_synthesizer import AudioFormat

        wav = (
            b"RIFF" + (36 + 3200).to_bytes(4, "little") + b"WAVEfmt "
            + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (3200).to_bytes(4, "little")
            + b"\x00" * 3200
        )
        synthesizer.return_value.call.return_value = wav
        with patch.dict("os.environ", {
            "MINIMOVER_DASHSCOPE_API_KEY": "test-key",
            "MINIMOVER_DASHSCOPE_WORKSPACE_ID": "ws-test",
            "MINIMOVER_COSYVOICE_MODEL": "cosyvoice-v3-flash",
            "MINIMOVER_COSYVOICE_VOICE": "longanhuan",
        }, clear=False), patch.object(icar_audio, "_load_tts_env"):
            self.assertEqual(icar_audio._dashscope_tts("test"), wav)

        self.assertEqual(dashscope.api_key, "test-key")
        synthesizer.assert_called_once_with(
            model="cosyvoice-v3-flash",
            voice="longanhuan",
            format=AudioFormat.WAV_16000HZ_MONO_16BIT,
            workspace="ws-test",
        )

    @patch("dashscope.audio.tts_v2.SpeechSynthesizer")
    def test_dashscope_tts_retries_one_empty_audio_response(self, synthesizer):
        from audio import icar_audio

        wav = (
            b"RIFF" + (36 + 3200).to_bytes(4, "little") + b"WAVEfmt "
            + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (3200).to_bytes(4, "little")
            + b"\x00" * 3200
        )
        first = Mock()
        first.call.return_value = b""
        second = Mock()
        second.call.return_value = wav
        synthesizer.side_effect = [first, second]
        with patch.dict("os.environ", {
            "MINIMOVER_DASHSCOPE_API_KEY": "test-key",
        }, clear=False), patch.object(icar_audio, "_load_tts_env"):
            self.assertEqual(icar_audio._dashscope_tts("test"), wav)

        self.assertEqual(synthesizer.call_count, 2)
        first.call.assert_called_once_with(text="test")
        second.call.assert_called_once_with(text="test")


    def test_tts_cache_annotations_are_compatible_with_jetson_python_38(self):
        source = Path("audio/icar_audio.py").read_text(encoding="utf-8")

        self.assertNotIn("bytes | None", source)
        self.assertIn("Optional[bytes]", source)

    @patch("audio.icar_audio._dashscope_tts")
    def test_successful_tts_is_persisted_and_reused_without_provider(self, dashscope_tts):
        from audio import icar_audio

        wav = (
            b"RIFF" + (36 + 3200).to_bytes(4, "little") + b"WAVEfmt "
            + (16).to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
            + (32000).to_bytes(4, "little") + (2).to_bytes(2, "little")
            + (16).to_bytes(2, "little") + b"data" + (3200).to_bytes(4, "little")
            + b"\x00" * 3200
        )
        dashscope_tts.return_value = wav
        with tempfile.TemporaryDirectory() as cache_dir, patch.dict(
            "os.environ",
            {"MINIMOVER_TTS_CACHE_DIR": cache_dir},
            clear=False,
        ), patch.object(icar_audio._player, "stop"):
            self.assertEqual(icar_audio.say("cached demo phrase"), wav)
            dashscope_tts.reset_mock(side_effect=True, return_value=True)
            dashscope_tts.side_effect = RuntimeError("provider unavailable")

            self.assertEqual(icar_audio.say("cached demo phrase"), wav)

        dashscope_tts.assert_not_called()


if __name__ == "__main__":
    unittest.main()
