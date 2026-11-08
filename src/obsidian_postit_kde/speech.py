"""Optional microphone capture and local whisper.cpp transcription.

Reuse KiroCrew's verified GGML model cache when present. Missing models are
downloaded into this app's own cache and checked against pinned SHA-256 hashes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from threading import Lock
from typing import Any

from .config import config_dir

MODELS = ("tiny", "base", "small", "large-v3-turbo")
# Human-readable choices for Settings: download size ≈ memory used while loaded.
MODEL_LABELS = {
    "tiny": "Tiny — 75 MB, fastest, least accurate",
    "base": "Base — 142 MB, fast, good for clear speech (recommended)",
    "small": "Small — 466 MB, more accurate, slower",
    "large-v3-turbo": "Large v3 Turbo — 1.6 GB, most accurate, slow to load",
}
LANGUAGES = (
    ("auto", "Detect automatically"),
    ("fr", "French"),
    ("en", "English"),
    ("de", "German"),
    ("es", "Spanish"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("nl", "Dutch"),
    ("pl", "Polish"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
)
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
        raise SpeechError(
            'Speech support is missing. Install with: pip install "obsidian-postit-kde[speech]"'
        ) from exc
    path = _model_path(model_name)
    return Model(
        model=str(path),
        language=language,
        n_threads=max(1, min(8, (os.cpu_count() or 2) // 2)),
        print_progress=False,
        print_realtime=False,
        no_context=True,
        no_timestamps=True,
        suppress_nst=True,
    )


def ensure_model(model_name: str) -> None:
    """Download/verify the model without loading whisper.cpp in this process."""
    with _model_lock:
        _model_path(model_name)
    if importlib.util.find_spec("pywhispercpp") is None:
        raise SpeechError(
            'Speech support is missing. Install with: pip install "obsidian-postit-kde[speech]"'
        )


def _check_language(language: str) -> None:
    if language != "auto" and (len(language) != 2 or not language.isalpha()):
        raise SpeechError("Speech language must be 'auto' or a two-letter language code.")


_NOISE_SEGMENT = re.compile(r"^\s*[\[(][^\])]*[\])]\s*$")  # [BLANK_AUDIO], (music)…


def _join_segments(segments) -> str:
    parts = (segment.text.strip() for segment in segments)
    # Drop [BLANK_AUDIO]-style tags and punctuation-only output ("...") on silence.
    return " ".join(
        p for p in parts if p and not _NOISE_SEGMENT.match(p) and any(c.isalnum() for c in p)
    ).strip()


class SpeechWorker:
    """A long-lived child process that keeps one whisper.cpp model loaded.

    pywhispercpp's native binding can abort the whole interpreter (a GIL fatal
    error seen on Python 3.15 inside the Qt app). Running it in a subprocess
    turns such a crash into a SpeechError instead of killing the tray app, and
    keeping the child alive lets the live preview reuse the loaded model.

    Blocking: construct and call `transcribe` from a worker thread.
    """

    def __init__(self, model_name: str, language: str) -> None:
        _check_language(language)
        _model_path(model_name)  # validate + download before spawning
        self._lock = Lock()
        self._dir = Path(tempfile.mkdtemp(prefix="postit-speech-"))
        self._log = (self._dir / "worker.log").open("w+", encoding="utf-8")
        self._calls = 0
        self._ready = False
        self._proc = subprocess.Popen(  # noqa: S603
            [sys.executable, "-m", "obsidian_postit_kde.speech", "--serve", model_name, language],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._log,
            text=True,
            bufsize=1,
        )

    def _reply(self) -> dict:
        assert self._proc.stdout is not None
        line = self._proc.stdout.readline()
        if not line:
            code = self._proc.wait(timeout=5)
            self._log.seek(0)
            tail = "\n".join(self._log.read().strip().splitlines()[-5:])
            how = f"signal {-code}" if code < 0 else f"exit {code}"
            raise SpeechError(f"Speech engine crashed ({how}).\n\n{tail}")
        payload = json.loads(line)
        if "error" in payload:
            raise SpeechError(payload["error"])
        return payload

    def transcribe(self, audio) -> str:
        """Return the transcript of `audio` (may be empty for silence)."""
        import numpy as np

        with self._lock:
            if not self._ready:
                self._reply()  # waits for the model; raises if loading failed
                self._ready = True
            self._calls += 1
            path = self._dir / f"audio-{self._calls}.npy"
            np.save(path, np.ascontiguousarray(audio, dtype=np.float32))
            try:
                assert self._proc.stdin is not None
                try:
                    self._proc.stdin.write(f"{path}\n")
                    self._proc.stdin.flush()
                except (BrokenPipeError, OSError):
                    pass  # the reply read below reports the crash
                return str(self._reply()["text"])
            finally:
                path.unlink(missing_ok=True)

    def close(self) -> None:
        """Stop the child; safe to call from any thread, even mid-request."""
        with suppress(OSError):
            if self._proc.stdin is not None:
                self._proc.stdin.close()
        try:
            self._proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        self._log.close()
        shutil.rmtree(self._dir, ignore_errors=True)


def _serve(model_name: str, language: str) -> int:
    """Child-process loop: one .npy path per stdin line, one JSON reply per line."""
    import numpy as np

    out = os.fdopen(os.dup(1), "w", buffering=1, encoding="utf-8")
    os.dup2(2, 1)  # whisper.cpp/native chatter must not corrupt the protocol
    try:
        model = _load_model(model_name, language.lower())
    except Exception as exc:
        out.write(json.dumps({"error": str(exc)}) + "\n")
        return 1
    out.write(json.dumps({"ready": True}) + "\n")
    for line in sys.stdin:
        path = line.strip()
        if not path:
            continue
        try:
            payload: dict = {"text": _join_segments(model.transcribe(np.load(path)))}
        except Exception as exc:
            payload = {"error": f"Transcription failed: {exc}"}
        out.write(json.dumps(payload) + "\n")
    return 0


class LiveTranscript:
    """Incremental transcript for a growing recording.

    Audio older than `window_s` seconds is committed in chunks (cut at the
    quietest 0.1 s inside the last few seconds of the window, to avoid
    splitting words); only the uncommitted tail is re-transcribed on each
    update, so a preview costs at most one window of audio. The final text
    reuses the committed chunks, so stopping only transcribes the tail.
    """

    def __init__(
        self,
        transcribe_fn: Callable[[Any], str],
        sample_rate: int = SAMPLE_RATE,
        window_s: float = 25.0,
        search_s: float = 5.0,
        min_tail_s: float = 0.3,
    ) -> None:
        self._fn = transcribe_fn
        self._sr = sample_rate
        self._window = int(window_s * sample_rate)
        self._search = int(search_s * sample_rate)
        self._min_tail = int(min_tail_s * sample_rate)
        self._committed: list[str] = []
        self._start = 0
        self._lock = Lock()

    def _cut(self, audio) -> int:
        import numpy as np

        hi = self._start + self._window
        lo = hi - self._search
        frame = max(1, self._sr // 10)
        region = np.abs(audio[lo:hi])
        n = len(region) // frame
        if n == 0:
            return hi
        energy = region[: n * frame].reshape(n, frame).mean(axis=1)
        return lo + int(np.argmin(energy)) * frame + frame // 2

    def update(self, audio) -> str:
        """Commit full windows, transcribe the tail, return the text so far."""
        with self._lock:
            while len(audio) - self._start > self._window:
                cut = self._cut(audio)
                text = self._fn(audio[self._start : cut])
                if text:
                    self._committed.append(text)
                self._start = cut
            tail = audio[self._start :]
            tail_text = self._fn(tail) if len(tail) >= self._min_tail else ""
            return " ".join(t for t in [*self._committed, tail_text] if t)


class Recorder:
    def __init__(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise SpeechError(
                'Microphone support is missing. Install with: pip install "obsidian-postit-kde[speech]"'
            ) from exc
        self._chunks: list[Any] = []
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

    def snapshot(self):
        """Audio captured so far (the stream keeps running)."""
        import numpy as np

        chunks = list(self._chunks)
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks, axis=0).reshape(-1)

    def discard(self) -> None:
        self._stream.stop()
        self._stream.close()


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--serve":
        raise SystemExit(_serve(sys.argv[2], sys.argv[3]))
    raise SystemExit("usage: python -m obsidian_postit_kde.speech --serve MODEL LANGUAGE")
