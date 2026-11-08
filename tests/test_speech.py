import sys
from types import SimpleNamespace

import pytest

from obsidian_postit_kde import speech
from obsidian_postit_kde.config import Config
from obsidian_postit_kde.ui.voice import VoiceNoteDialog


def test_invalid_model_never_loads(monkeypatch):
    with pytest.raises(speech.SpeechError, match="Unsupported"):
        speech.ensure_model("untrusted/model")


def test_voice_result_appends_today_in_daily_file(tmp_path, monkeypatch, _qt_app):
    monkeypatch.setattr("obsidian_postit_kde.ui.voice.QMessageBox.information", lambda *_args: None)
    dialog = VoiceNoteDialog(Config(vault_path=str(tmp_path), speech_enabled=True))
    dialog._done(("Spoken entry", None))
    daily_files = list((tmp_path / "Daily").glob("*.md"))
    assert len(daily_files) == 1
    assert "Spoken entry" in daily_files[0].read_text(encoding="utf-8")


def test_live_transcript_commits_windows_and_reuses_them():
    np = pytest.importorskip("numpy")
    calls = []

    def fake(audio):
        calls.append(len(audio))
        return f"w{len(calls)}"

    live = speech.LiveTranscript(fake, sample_rate=10, window_s=3, search_s=1)
    assert live.update(np.ones(20, dtype=np.float32)) == "w1"  # tail only
    # 45 samples > 30-sample window: one chunk committed, then the tail.
    assert live.update(np.ones(45, dtype=np.float32)) == "w2 w3"
    committed = calls[1]
    assert 20 <= committed <= 30
    # Committed text is reused: only the new tail is transcribed again.
    assert live.update(np.ones(50, dtype=np.float32)) == "w2 w4"
    assert calls[3] == 50 - committed


def test_live_transcript_cuts_at_the_quietest_point():
    np = pytest.importorskip("numpy")
    audio = np.ones(100, dtype=np.float32)
    audio[42:46] = 0.0  # a pause inside the search region [30, 50)
    seen = []
    live = speech.LiveTranscript(
        lambda a: seen.append(len(a)) or "", sample_rate=20, window_s=2.5, search_s=1
    )
    live.update(audio)
    assert seen[0] in range(42, 47)


def test_noise_segments_are_dropped():
    segs = [
        SimpleNamespace(text=" [BLANK_AUDIO]"),
        SimpleNamespace(text=" Bonjour "),
        SimpleNamespace(text="(music)"),
        SimpleNamespace(text=" ..."),
    ]
    assert speech._join_segments(segs) == "Bonjour"


def test_worker_reports_child_crash(monkeypatch, tmp_path):
    np = pytest.importorskip("numpy")
    monkeypatch.setattr(speech, "_model_path", lambda model: tmp_path / "ggml-base.bin")
    real_popen = speech.subprocess.Popen

    def crashing_popen(_cmd, **kwargs):
        script = "import os, sys; sys.stderr.write('Fatal Python error: take_gil'); sys.stderr.flush(); os.kill(os.getpid(), 9)"
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(speech.subprocess, "Popen", crashing_popen)
    worker = speech.SpeechWorker("base", "fr")
    try:
        with pytest.raises(speech.SpeechError, match="signal 9") as info:
            worker.transcribe(np.zeros(160, dtype=np.float32))
        assert "take_gil" in str(info.value)
    finally:
        worker.close()


def test_worker_round_trip_with_fake_engine(monkeypatch, tmp_path):
    np = pytest.importorskip("numpy")
    monkeypatch.setattr(speech, "_model_path", lambda model: tmp_path / "ggml-base.bin")
    real_popen = speech.subprocess.Popen
    script = (
        "import json, sys, numpy as np\n"
        "print(json.dumps({'ready': True}), flush=True)\n"
        "for line in sys.stdin:\n"
        "    n = len(np.load(line.strip()))\n"
        "    print(json.dumps({'text': f'{n} samples'}), flush=True)\n"
    )

    def fake_popen(_cmd, **kwargs):
        return real_popen([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(speech.subprocess, "Popen", fake_popen)
    worker = speech.SpeechWorker("base", "fr")
    try:
        assert worker.transcribe(np.zeros(160, dtype=np.float32)) == "160 samples"
        assert worker.transcribe(np.zeros(80, dtype=np.float32)) == "80 samples"
    finally:
        worker.close()
