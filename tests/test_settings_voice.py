import base64
import io
import wave

import pytest

from obsidian_postit_kde import openrouter
from obsidian_postit_kde.config import Config
from obsidian_postit_kde.ui.settings import SettingsDialog


@pytest.fixture
def settings_env(tmp_path, monkeypatch, _qt_app):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr("obsidian_postit_kde.ui.settings.autostart.set_enabled", lambda *_: None)
    monkeypatch.setattr("obsidian_postit_kde.ui.settings.autostart.is_enabled", lambda: False)
    monkeypatch.setattr("obsidian_postit_kde.ui.settings.todoist.has_api_token", lambda: False)
    monkeypatch.setattr("obsidian_postit_kde.ui.settings.openrouter.has_api_key", lambda: True)
    vault = tmp_path / "vault"
    vault.mkdir()
    return vault


def test_settings_saves_cloud_speech_choice(settings_env):
    cfg = Config(vault_path=str(settings_env))
    dlg = SettingsDialog(cfg)
    dlg.speech_check.setChecked(True)
    dlg.cloud_radio.setChecked(True)
    dlg.speech_cloud_model.setCurrentIndex(
        dlg.speech_cloud_model.findData("openai/whisper-large-v3")
    )
    dlg.speech_language.setCurrentIndex(dlg.speech_language.findData("fr"))
    dlg.speech_live_check.setChecked(False)
    dlg._on_accept()
    loaded = Config.load()
    assert loaded.speech_enabled is True
    assert loaded.speech_engine == "openrouter"
    assert loaded.speech_cloud_model == "openai/whisper-large-v3"
    assert loaded.speech_language == "fr"
    assert loaded.speech_live_preview is False


def test_settings_shows_only_the_selected_engine_model(settings_env):
    dlg = SettingsDialog(Config(vault_path=str(settings_env), speech_enabled=True))
    form = dlg._voice_form
    assert form.isRowVisible(dlg.speech_model)
    assert not form.isRowVisible(dlg._cloud_box)
    dlg.cloud_radio.setChecked(True)
    assert not form.isRowVisible(dlg.speech_model)
    assert form.isRowVisible(dlg._cloud_box)


def test_settings_keeps_unknown_config_values(settings_env):
    cfg = Config(
        vault_path=str(settings_env), speech_cloud_model="vendor/new-stt", speech_language="sv"
    )
    dlg = SettingsDialog(cfg)
    assert dlg.speech_cloud_model.currentData() == "vendor/new-stt"
    assert dlg.speech_language.currentData() == "sv"
    dlg._on_accept()
    assert (Config.load().speech_cloud_model, Config.load().speech_language) == (
        "vendor/new-stt",
        "sv",
    )


def test_openrouter_transcribe_sends_wav_and_language(monkeypatch):
    np = pytest.importorskip("numpy")
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": " Bonjour le monde "}

    def fake_post(url, json, headers, timeout):
        sent.update(url=url, json=json, headers=headers)
        return Resp()

    monkeypatch.setattr(openrouter, "get_api_key", lambda: "sk-or-test-key-1234567890")
    monkeypatch.setattr(openrouter.httpx, "post", fake_post)
    audio = np.zeros(16000, dtype=np.float32)
    text = openrouter.transcribe(audio, 16000, "openai/whisper-large-v3-turbo", "fr")
    assert text == "Bonjour le monde"
    assert sent["url"].endswith("/audio/transcriptions")
    assert sent["json"]["language"] == "fr"
    assert sent["json"]["input_audio"]["format"] == "wav"
    with wave.open(io.BytesIO(base64.b64decode(sent["json"]["input_audio"]["data"]))) as wav:
        assert (wav.getnchannels(), wav.getframerate(), wav.getnframes()) == (1, 16000, 16000)


def test_openrouter_transcribe_auto_language_is_omitted(monkeypatch):
    np = pytest.importorskip("numpy")
    sent = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": "hi"}

    monkeypatch.setattr(openrouter, "get_api_key", lambda: "sk-or-test-key-1234567890")
    monkeypatch.setattr(
        openrouter.httpx, "post", lambda url, json, headers, timeout: sent.update(json) or Resp()
    )
    openrouter.transcribe(np.zeros(800, dtype=np.float32), 16000, "m", "auto")
    assert "language" not in sent


def test_openrouter_transcribe_needs_key(monkeypatch):
    np = pytest.importorskip("numpy")
    monkeypatch.setattr(openrouter, "get_api_key", lambda: None)
    with pytest.raises(openrouter.OpenRouterError, match="API key"):
        openrouter.transcribe(np.zeros(10, dtype=np.float32), 16000, "m", "fr")
