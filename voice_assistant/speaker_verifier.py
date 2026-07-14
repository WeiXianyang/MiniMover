"""CAM++ speaker enrollment and verification for motion-command gating."""

import json
import os
from pathlib import Path

THRESHOLD = 0.38
SAMPLE_RATE = 16000
DEFAULT_MODEL = "damo/speech_campplus_sv_zh-cn_16k-common"


def cosine_similarity(left, right):
    import numpy as np
    left = np.asarray(left, dtype=np.float32).ravel()
    right = np.asarray(right, dtype=np.float32).ravel()
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denominator <= 1e-8:
        return 0.0
    return float(np.dot(left, right) / denominator)


class SpeakerVerifier:
    def __init__(self, profile_path, threshold=THRESHOLD):
        self.profile_path = Path(profile_path)
        self.threshold = float(threshold)
        self._model = None

    @property
    def enrolled(self):
        return self.profile_path.is_file()

    def _load_model(self):
        if self._model is None:
            try:
                from funasr import AutoModel
            except ImportError as exc:
                raise RuntimeError("speaker verification requires FunASR and CAM++ dependencies") from exc
            self._model = AutoModel(
                model=os.getenv("MINIMOVER_SPEAKER_MODEL", DEFAULT_MODEL),
                disable_update=True,
                disable_pbar=True,
            )
        return self._model

    def _embedding(self, samples):
        import numpy as np
        audio = np.asarray(samples, dtype=np.int16).ravel().astype(np.float32) / 32768.0
        if len(audio) < int(SAMPLE_RATE * 0.8):
            raise ValueError("speaker verification audio is too short")
        result = self._load_model().generate(input=audio)
        if not result or not isinstance(result[0], dict) or "spk_embedding" not in result[0]:
            raise RuntimeError("CAM++ did not return a speaker embedding")
        return np.asarray(result[0]["spk_embedding"], dtype=np.float32).ravel()

    def enroll(self, samples):
        import numpy as np
        embedding = self._embedding(samples)
        self.profile_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(self.profile_path, embedding)
        return {"enrolled": True, "path": str(self.profile_path), "dim": int(len(embedding))}

    def verify(self, samples):
        import numpy as np
        if not self.enrolled:
            return {"verified": False, "reason": "not-enrolled", "similarity": 0.0}
        profile = np.load(self.profile_path).astype(np.float32).ravel()
        similarity = cosine_similarity(self._embedding(samples), profile)
        return {
            "verified": similarity >= self.threshold,
            "similarity": round(similarity, 4),
            "threshold": self.threshold,
        }


def record_audio(seconds, device=None):
    import numpy as np
    import sounddevice as sd
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16", device=device)
    sd.wait()
    return np.asarray(audio).reshape(-1)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enroll or verify a MiniMover speaker profile")
    parser.add_argument("profile")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--seconds", type=float, default=None)
    args = parser.parse_args()
    verifier = SpeakerVerifier(args.profile)
    seconds = args.seconds if args.seconds is not None else (5.0 if args.verify else 15.0)
    try:
        samples = record_audio(seconds)
        result = verifier.verify(samples) if args.verify else verifier.enroll(samples)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result.get("verified", True) else 2
    except Exception as exc:
        print(json.dumps({"verified": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


