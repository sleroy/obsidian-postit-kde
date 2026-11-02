"""Register application shortcuts with KDE through the desktop portal."""

from __future__ import annotations

import os
import threading
import uuid
from collections import deque
from typing import Any

from jeepney import DBus, DBusAddress, HeaderFields, MatchRule, MessageType, new_method_call
from jeepney.io.blocking import DBusConnection, open_dbus_connection
from PySide6.QtCore import QObject, Signal

_PORTAL = "org.freedesktop.portal.Desktop"
_PATH = "/org/freedesktop/portal/desktop"
_INTERFACE = "org.freedesktop.portal.GlobalShortcuts"
_REQUEST = "org.freedesktop.portal.Request"
_SHORTCUTS = (
    ("open_diary", "Open Diary", "CTRL+ALT+d"),
    ("new_note", "Create a post-it", "CTRL+ALT+n"),
    ("from_clipboard", "Create a post-it from clipboard", "CTRL+ALT+SHIFT+n"),
)


def _binding_specs() -> list[tuple[str, dict[str, tuple[str, str]]]]:
    return [
        (
            action,
            {"description": ("s", description), "preferred_trigger": ("s", trigger)},
        )
        for action, description, trigger in _SHORTCUTS
    ]


def _method(conn: DBusConnection, member: str, signature: str = "", body: tuple = ()) -> Any:
    address = DBusAddress(_PATH, bus_name=_PORTAL, interface=_INTERFACE)
    reply = conn.send_and_get_reply(new_method_call(address, member, signature, body), timeout=8)
    if reply.header.message_type == MessageType.error:
        raise RuntimeError(f"Desktop portal {member} failed: {reply.body[0]}")
    return reply.body[0] if reply.body else None


class GlobalShortcuts(QObject):
    activated = Signal(str)
    status = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._stop = threading.Event()
        self._configure = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="postit-shortcuts", daemon=True)
            self._thread.start()

    def configure(self) -> None:
        self._configure.set()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            # A portal method call may still be waiting for its eight-second timeout.
            # Keep the QObject alive until the worker has stopped emitting signals.
            self._thread.join(timeout=9)

    def _next_signal(self, conn: DBusConnection, queue: deque, timeout: float) -> Any | None:
        try:
            return conn.recv_until_filtered(queue, timeout=timeout)
        except TimeoutError:
            return None

    def _request(
        self, conn: DBusConnection, queue: deque, member: str, signature: str, body: tuple
    ) -> dict:
        path = _method(conn, member, signature, body)
        while not self._stop.is_set():
            message = self._next_signal(conn, queue, 0.5)
            if message is None:
                continue
            fields = message.header.fields
            interface = fields.get(HeaderFields.interface)
            if interface == _INTERFACE and fields.get(HeaderFields.member) == "Activated":
                self.activated.emit(message.body[1])
            elif interface == _REQUEST and fields.get(HeaderFields.path) == path:
                code, result = message.body
                if code != 0:
                    raise RuntimeError(f"Desktop portal {member} was not accepted ({code}).")
                return result
        return {}

    def _run(self) -> None:
        try:
            with open_dbus_connection(bus="SESSION") as conn:
                if not os.environ.get("FLATPAK_ID"):
                    registry = DBusAddress(
                        _PATH, bus_name=_PORTAL, interface="org.freedesktop.host.portal.Registry"
                    )
                    reply = conn.send_and_get_reply(
                        new_method_call(
                            registry,
                            "Register",
                            "sa{sv}",
                            ("io.github.sleroy.ObsidianPostitKde", {}),
                        ),
                        timeout=8,
                    )
                    if reply.header.message_type == MessageType.error:
                        raise RuntimeError(
                            f"Desktop portal app registration failed: {reply.body[0]}"
                        )
                for interface in (_REQUEST, _INTERFACE):
                    rule = MatchRule(type="signal", interface=interface)
                    conn.send_and_get_reply(DBus().AddMatch(rule), timeout=8)
                with conn.filter(MatchRule(type="signal"), bufsize=64) as queue:
                    token = "postit_" + uuid.uuid4().hex
                    result = self._request(
                        conn,
                        queue,
                        "CreateSession",
                        "a{sv}",
                        ({"handle_token": ("s", token), "session_handle_token": ("s", token)},),
                    )
                    if self._stop.is_set():
                        return
                    session = result["session_handle"][1]
                    try:
                        result = self._request(
                            conn,
                            queue,
                            "BindShortcuts",
                            "oa(sa{sv})sa{sv}",
                            (
                                session,
                                _binding_specs(),
                                "",
                                {"handle_token": ("s", token + "_bind")},
                            ),
                        )
                    except RuntimeError:
                        result = {}
                    if self._stop.is_set():
                        return
                    shortcuts = result.get("shortcuts", ("a(sa{sv})", []))[1]
                    self.status.emit(
                        f"{len(shortcuts)} KDE shortcuts active"
                        + ("; open Settings to configure" if not shortcuts else "")
                    )
                    while not self._stop.is_set():
                        if self._configure.is_set():
                            self._configure.clear()
                            _method(
                                conn,
                                "ConfigureShortcuts",
                                "osa{sv}",
                                (session, "", {}),
                            )
                            listed = self._request(
                                conn,
                                queue,
                                "ListShortcuts",
                                "oa{sv}",
                                (session, {"handle_token": ("s", "postit_" + uuid.uuid4().hex)}),
                            )
                            active = listed.get("shortcuts", ("a(sa{sv})", []))[1]
                            self.status.emit(f"{len(active)} KDE shortcuts active")
                        message = self._next_signal(conn, queue, 0.25)
                        if message is None:
                            continue
                        fields = message.header.fields
                        if (
                            fields.get(HeaderFields.interface) == _INTERFACE
                            and fields.get(HeaderFields.member) == "Activated"
                            and message.body[0] == session
                        ):
                            self.activated.emit(message.body[1])
                    session_address = DBusAddress(
                        session, bus_name=_PORTAL, interface="org.freedesktop.portal.Session"
                    )
                    conn.send_and_get_reply(new_method_call(session_address, "Close"), timeout=2)
        except Exception as exc:
            if not self._stop.is_set():
                self.status.emit(f"KDE shortcuts unavailable: {exc}")
