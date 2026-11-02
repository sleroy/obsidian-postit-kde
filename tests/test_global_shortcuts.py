from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from jeepney import HeaderFields

from obsidian_postit_kde.ui import global_shortcuts


def test_portal_bindings_have_stable_ids_and_xdg_triggers():
    specs = global_shortcuts._binding_specs()
    assert [item[0] for item in specs] == ["open_diary", "new_note", "from_clipboard"]
    assert specs[0][1]["preferred_trigger"] == ("s", "CTRL+ALT+d")
    assert specs[1][1]["preferred_trigger"] == ("s", "CTRL+ALT+n")
    assert specs[2][1]["preferred_trigger"] == ("s", "CTRL+ALT+SHIFT+n")


def test_portal_request_handles_activation_and_response(monkeypatch):
    shortcuts = global_shortcuts.GlobalShortcuts()
    activated = []
    shortcuts.activated.connect(activated.append)
    request_path = "/org/freedesktop/portal/desktop/request/test"
    monkeypatch.setattr(global_shortcuts, "_method", lambda *_args: request_path)
    messages = deque(
        [
            SimpleNamespace(
                header=SimpleNamespace(
                    fields={
                        HeaderFields.interface: global_shortcuts._INTERFACE,
                        HeaderFields.member: "Activated",
                    }
                ),
                body=["session", "new_note", 0, {}],
            ),
            SimpleNamespace(
                header=SimpleNamespace(
                    fields={
                        HeaderFields.interface: global_shortcuts._REQUEST,
                        HeaderFields.path: request_path,
                    }
                ),
                body=[0, {"session_handle": ("s", "/session/test")}],
            ),
        ]
    )
    monkeypatch.setattr(shortcuts, "_next_signal", lambda *_args: messages.popleft())
    result = shortcuts._request(None, deque(), "CreateSession", "a{sv}", ({},))
    assert result["session_handle"][1] == "/session/test"
    assert activated == ["new_note"]
