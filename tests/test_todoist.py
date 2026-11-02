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


def test_task_fields_support_due_priority_project_labels_and_description():
    parsed = todoist.parse_task_fields(
        "Review PR next Monday at 10am #Work @review p2 // Check login flow"
    )
    assert parsed.content == "Review PR"
    assert parsed.due_string == "next Monday at 10am"
    assert parsed.project == "Work"
    assert parsed.labels == ("review",)
    assert parsed.priority == 2
    assert parsed.description == "Check login flow"


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


def test_create_task_http_contract_and_link(monkeypatch):
    monkeypatch.setenv("TODOIST_API_TOKEN", "test-token")
    seen = []

    def post(url, **kwargs):
        seen.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request("POST", url), json={"id": "Task123"})

    def get(url, **kwargs):
        seen.append((url, kwargs))
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={"results": [{"id": "Project123", "name": "Shopping"}]},
        )

    monkeypatch.setattr(todoist.httpx, "post", post)
    monkeypatch.setattr(todoist.httpx, "get", get)
    url = todoist.create_task("Buy milk tomorrow #Shopping @groceries p1")
    assert seen[0][0] == "https://api.todoist.com/api/v1/projects"
    assert seen[1][0] == "https://api.todoist.com/api/v1/tasks"
    assert seen[1][1]["json"] == {
        "content": "Buy milk",
        "due_string": "tomorrow",
        "priority": 1,
        "labels": ["groceries"],
        "project_id": "Project123",
    }
    assert seen[1][1]["headers"] == {"Authorization": "Bearer test-token"}
    assert url == "https://app.todoist.com/app/task/Task123"


def test_create_task_failure_does_not_leak_token(monkeypatch):
    monkeypatch.setenv("TODOIST_API_TOKEN", "private-token")

    def post(url, **_kwargs):
        return httpx.Response(401, request=httpx.Request("POST", url), text="private-token")

    monkeypatch.setattr(todoist.httpx, "post", post)
    with pytest.raises(todoist.TodoistError, match="HTTP 401") as exc:
        todoist.create_task("Task")
    assert "private-token" not in str(exc.value)


def test_diary_task_is_saved_and_sent_without_blocking_ui(tmp_path, monkeypatch, _qt_app):
    root = tmp_path / "vault"
    root.mkdir()
    vault = ObsidianVault(Config(vault_path=str(root)))
    monkeypatch.setattr("obsidian_postit_kde.ui.diary.has_api_token", lambda: True)
    sent = []

    def create(task):
        sent.append(task)
        return "https://app.todoist.com/app/task/Task123"

    monkeypatch.setattr("obsidian_postit_kde.ui.diary.create_task", create)
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
    assert "[Open in Todoist](https://app.todoist.com/app/task/Task123)" in vault.read_diary()
    assert "Open in Todoist" in window.doc.toPlainText()
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
