"""System tray icon and menu — Diary (journal) vs Notes (post-its)."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import app_icon


class Tray(QSystemTrayIcon):
    def __init__(
        self,
        on_open_diary: Callable[[], None],
        on_record_note: Callable[[], None],
        speech_enabled: Callable[[], bool],
        on_new_note: Callable[[], None],
        on_from_clipboard: Callable[[], None],
        on_open_vault: Callable[[], None],
        on_settings: Callable[[], None],
        on_search: Callable[[], None],
        on_open_path: Callable[[Path], None],
        recent_provider: Callable[[], list[tuple[str, Path]]],
        on_quit: Callable[[], None],
    ) -> None:
        super().__init__(app_icon())
        self.setToolTip("Obsidian PostIt — Diary & Notes")
        self._on_open_diary = on_open_diary
        self._on_record_note = on_record_note
        self._speech_enabled = speech_enabled
        self._on_new_note = on_new_note
        self._on_from_clipboard = on_from_clipboard
        self._on_open_vault = on_open_vault
        self._on_settings = on_settings
        self._on_search = on_search
        self._on_open_path = on_open_path
        self._recent_provider = recent_provider
        self._on_quit = on_quit

        self._menu = QMenu()
        self._menu.aboutToShow.connect(self._rebuild)
        self.setContextMenu(self._menu)
        self._rebuild()

        self.activated.connect(self._on_activated)

    def _rebuild(self) -> None:
        """Rebuild the menu so the recent-notes list is always current."""
        m = self._menu
        m.clear()

        # Diary (journal)
        m.addAction("📔  Open Diary…", self._on_open_diary)
        suffix = "" if self._speech_enabled() else " (enable in Settings)"
        m.addAction(f"🎙️  Record a note…{suffix}", self._on_record_note)
        m.addSeparator()

        # Notes (post-its)
        m.addAction("🗒️  New note…", self._on_new_note)
        m.addAction("📋  New note from clipboard…", self._on_from_clipboard)
        m.addAction("🔎  Search notes…", self._on_search)

        # Recent notes, inline (not a submenu) between dividers.
        recents = self._recent_provider()
        if recents:
            m.addSeparator()
            header = m.addAction("Recent notes")
            header.setEnabled(False)
            for title, path in recents:
                label = title if len(title) <= 48 else title[:47] + "…"
                m.addAction(f"   {label}", partial(self._on_open_path, path))

        m.addSeparator()
        m.addAction("Open vault folder", self._on_open_vault)
        m.addAction("Settings…", self._on_settings)
        m.addSeparator()
        m.addAction("Quit", self._on_quit)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left-click opens the Diary — the most frequent action.
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._on_open_diary()
