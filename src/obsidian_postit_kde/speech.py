"""Optional microphone capture and local whisper.cpp transcription.

Reuse KiroCrew's verified GGML model cache when present. Missing models are
downloaded into this app's own cache and checked against pinned SHA-256 hashes.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock

from .config import config_dir

MODELS = ("tiny", "base", "small", "large-v3-turbo")
SAMPLE_RATE = 16000
MAX_SECONDS = 600
_BASE_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
_MODEL_HASHES = {
    "tiny": "be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21",
    "base": "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe",
    "small": "1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b",
    "large-v3-turbo": "1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69",
}
_model_lock = Lock()


class SpeechError(Exception):
    pass


def _verified(path: Path, expected: str) -> bool:
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest() == expected


def _model_path(model_name: str) -> Path:
    if model_name not in MODELS:
        raise SpeechError(f"Unsupported speech model: {model_name}")
    filename = f"ggml-{model_name}.bin"
    shared_home = Path(os.environ.get("KIROCREW_HOME", Path.home() / ".kiro" / "crew"))
    shared = shared_home / "models" / "whisper" / filename
    own = config_dir() / "models" / "whisper" / filename
    expected = _MODEL_HASHES[model_name]
    if _verified(shared, expected):
        return shared
    if _verified(own, expected):
        return own

    own.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=own.parent, suffix=".part", delete=False) as fh:
            staged = Path(fh.name)
            digest = hashlib.sha256()
            with urllib.request.urlopen(f"{_BASE_URL}/{filename}", timeout=60) as response:
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    fh.write(chunk)
                    digest.update(chunk)
        if digest.hexdigest() != expected:
            raise SpeechError(f"Downloaded model failed verification: {model_name}")
        os.replace(staged, own)
        return own
    except (OSError, urllib.error.URLError) as exc:
        raise SpeechError(f"Could not download speech model {model_name}: {exc}") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def _load_model(model_name: str, language: str):
    try:
        from pywhispercpp.model import Model
    except ImportError as exc:
        raise SpeechError('Speech support is missing. Install with: pip install "obsidian-postit-kde[speech]"') from exc
    path = _model_path(model_name)
    return Model(
        model=str(path), language=language, n_threads=max(1, min(8, (os.cpu_count() or 2) // 2)),
        print_progress=False, print_realtime=False, no_context=True,
        no_timestamps=True, suppress_nst=True,
    )


def ensure_model(model_name: str) -> None:
    with _model_lock:
        _load_model(model_name, "auto")


def transcribe(audio, model_name: str, language: str) -> str:
    if language != "auto" and (len(language) != 2 or not language.isalpha()):
        raise SpeechError("Speech language must be 'auto' or a two-letter language code.")
    with _model_lock:
        model = _load_model(model_name, language.lower())
        segments = model.transcribe(audio)
        result = " ".join(segment.text.strip() for segment in segments).strip()
    if not result:
        raise SpeechError("No speech was detected. Nothing was added to the daily note.")
    return result


class Recorder:
    def __init__(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise SpeechError('Microphone support is missing. Install with: pip install "obsidian-postit-kde[speech]"') from exc
        self._chunks = []
        self._frames = 0
        self._overflow = False

        def callback(indata, frames, _time, status) -> None:
            if status:
                self._overflow = True
            if self._frames + frames <= SAMPLE_RATE * MAX_SECONDS:
                self._chunks.append(indata.copy())
                self._frames += frames

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=callback
            )
            self._stream.start()
        except Exception as exc:
            raise SpeechError(f"Could not start microphone: {exc}") from exc

    def stop(self):
        self._stream.stop()
        self._stream.close()
        if self._overflow:
            raise SpeechError("Audio input overflowed. Please record again.")
        if not self._chunks:
            raise SpeechError("No audio was recorded.")
        import numpy as np

        return np.concatenate(self._chunks, axis=0).reshape(-1)

    def discard(self) -> None:
        self._stream.stop()
        self._stream.close()
