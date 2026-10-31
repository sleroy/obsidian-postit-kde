"""System tray icon and menu."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import app_icon


class Tray(QSystemTrayIcon):
    def __init__(
        self,
        on_new_note: Callable[[], None],
        on_from_clipboard: Callable[[], None],
        on_open_vault: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        super().__init__(app_icon())
        self.setToolTip("Obsidian PostIt")
        self._on_new_note = on_new_note

        menu = QMenu()
        menu.addAction("New note…", on_new_note)
        menu.addAction("New from clipboard…", on_from_clipboard)
        menu.addSeparator()
        menu.addAction("Open vault", on_open_vault)
        menu.addAction("Settings…", on_settings)
        menu.addSeparator()
        menu.addAction("Quit", on_quit)
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left-click (Trigger) opens a new note; right-click shows the menu.
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_new_note()
