from __future__ import annotations

from datetime import date

import httpx
import pytest
from PySide6.QtCore import QThreadPool

from obsidian_postit_kde import todoist
from obsidian_postit_kde.config import Config
from obsidian_postit_kde.ui.diary import DiaryWindow
from obsidian_postit_kde.ui.settings import SettingsDialog
from obsidian_postit_kde.vault import ObsidianVault


def test_diary_task_parser():
    assert todoist.parse_diary_task("todo: Buy milk tomorrow #Shopping @groceries p1") == (
        "Buy milk tomorrow #Shopping @groceries p1"
    )
    assert todoist.parse_diary_task("  TODO:  Review PR\n tomorrow  ") == "Review PR tomorrow"
    assert todoist.parse_diary_task("A regular diary entry") is None
    with pytest.raises(todoist.TodoistError):
        todoist.parse_diary_task("todo:   ")


def test_token_uses_same_keyring_service_as_openrouter(monkeypatch):
    calls = []
    monkeypatch.delenv("TODOIST_API_TOKEN", raising=False)
    monkeypatch.setattr("keyring.set_password", lambda *args: calls.append(args))
    monkeypatch.setattr("keyring.get_password", lambda *args: "stored-token")
    todoist.set_api_token("secret")
    assert calls == [("obsidian-postit-kde", "todoist_api_token", "secret")]
    assert todoist.get_api_token() == "stored-token"
    monkeypatch.setenv("TODOIST_API_TOKEN", "env-token")
    assert todoist.get_api_token() == "env-token"


def test_quick_add_http_contract(monkeypatch):
    monkeypatch.setenv("TODOIST_API_TOKEN", "test-token")
    seen = []

    def post(url, **kwargs):
        seen.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request("POST", url), json={})

    monkeypatch.setattr(todoist.httpx, "post", post)
    todoist.quick_add("Buy milk tomorrow #Shopping @groceries p1")
    assert seen[0][0] == "https://api.todoist.com/api/v1/tasks/quick"
    assert seen[0][1]["json"] == {"text": "Buy milk tomorrow #Shopping @groceries p1"}
    assert seen[0][1]["headers"] == {"Authorization": "Bearer test-token"}


def test_quick_add_failure_does_not_leak_token(monkeypatch):
    monkeypatch.setenv("TODOIST_API_TOKEN", "private-token")

    def post(url, **_kwargs):
        return httpx.Response(401, request=httpx.Request("POST", url), text="private-token")

    monkeypatch.setattr(todoist.httpx, "post", post)
    with pytest.raises(todoist.TodoistError, match="HTTP 401") as exc:
        todoist.quick_add("Task")
    assert "private-token" not in str(exc.value)


def test_diary_task_is_saved_and_sent_without_blocking_ui(tmp_path, monkeypatch, _qt_app):
    root = tmp_path / "vault"
    root.mkdir()
    vault = ObsidianVault(Config(vault_path=str(root)))
    monkeypatch.setattr("obsidian_postit_kde.ui.diary.has_api_token", lambda: True)
    sent = []
    monkeypatch.setattr("obsidian_postit_kde.ui.diary.quick_add", sent.append)
    window = DiaryWindow(vault)
    window.entry.setPlainText("todo: Buy milk tomorrow #Shopping")
    window._add_entry()
    assert "todo: Buy milk tomorrow #Shopping" in vault.read_diary()
    assert window._clip_task is not None
    assert QThreadPool.globalInstance().waitForDone(5000)
    _qt_app.processEvents()
    assert sent == ["Buy milk tomorrow #Shopping"]
    assert window._clip_task is None
    assert "Todoist ✓" in window.hint.text()
    assert date.today().strftime(vault.config.daily_heading_date) in vault.read_diary()
    window.close()


def test_diary_keeps_task_when_todoist_token_missing(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    vault = ObsidianVault(Config(vault_path=str(root)))
    monkeypatch.setattr("obsidian_postit_kde.ui.diary.has_api_token", lambda: False)
    window = DiaryWindow(vault)
    window.entry.setPlainText("todo: Call Alex tomorrow")
    window._add_entry()
    assert "todo: Call Alex tomorrow" in vault.read_diary()
    assert "add a Todoist token" in window.hint.text()
    assert window._clip_task is None
    window.close()


def test_settings_saves_todoist_token_to_keyring(tmp_path, monkeypatch):
    root = tmp_path / "vault"
    root.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr("obsidian_postit_kde.ui.settings.autostart.set_enabled", lambda *_: None)
    monkeypatch.setattr("obsidian_postit_kde.ui.settings.todoist.has_api_token", lambda: False)
    saved = []
    monkeypatch.setattr("obsidian_postit_kde.ui.settings.todoist.set_api_token", saved.append)
    settings = SettingsDialog(Config(vault_path=str(root)))
    settings.todoist_token_edit.setText("personal-token")
    settings._on_accept()
    assert saved == ["personal-token"]
    assert "personal-token" not in (tmp_path / "config/obsidian-postit-kde/config.toml").read_text()
