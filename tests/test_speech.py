import sys
from types import SimpleNamespace

import pytest

from obsidian_postit_kde import speech
from obsidian_postit_kde.config import Config
from obsidian_postit_kde.ui.voice import VoiceNoteDialog


def test_transcribe_uses_local_model_and_selected_language(monkeypatch, tmp_path):
    calls = {}

    class FakeModel:
        def __init__(self, **kwargs):
            calls["model"] = kwargs

        def transcribe(self, audio):
            calls["audio"] = audio
            return [SimpleNamespace(text=" Bonjour"), SimpleNamespace(text=" monde ")]

    monkeypatch.setitem(sys.modules, "pywhispercpp", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "pywhispercpp.model", SimpleNamespace(Model=FakeModel))
    monkeypatch.setattr(speech, "_model_path", lambda model: tmp_path / "ggml-small.bin")
    audio = object()
    assert speech.transcribe(audio, "small", "fr") == "Bonjour monde"
    assert calls["model"]["language"] == "fr"
    assert calls["model"]["model"] == str(tmp_path / "ggml-small.bin")
    assert calls["audio"] is audio


def test_invalid_model_never_loads(monkeypatch):
    with pytest.raises(speech.SpeechError, match="Unsupported"):
        speech.ensure_model("untrusted/model")


def test_voice_result_appends_today_in_daily_file(tmp_path, monkeypatch, _qt_app):
    monkeypatch.setattr(
        "obsidian_postit_kde.ui.voice.QMessageBox.information", lambda *_args: None
    )
    dialog = VoiceNoteDialog(Config(vault_path=str(tmp_path), speech_enabled=True))
    dialog._done(("Spoken entry", None))
    daily_files = list((tmp_path / "Daily").glob("*.md"))
    assert len(daily_files) == 1
    assert "Spoken entry" in daily_files[0].read_text(encoding="utf-8")
