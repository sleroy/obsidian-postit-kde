"""Application controller: wires the tray to the Diary, Notes and the vault."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import Config
from .note import Destination, Note
from .openrouter import has_api_key
from .speech import ensure_model
from .ui import app_icon
from .ui.ai_worker import BgTask
from .ui.capture import CaptureDialog
from .ui.diary import DiaryWindow
from .ui.global_shortcuts import GlobalShortcuts
from .ui.search import SearchDialog
from .ui.settings import SettingsDialog
from .ui.theme import STYLESHEET
from .ui.tray import Tray
from .ui.voice import VoiceNoteDialog
from .vault import ObsidianVault, VaultError


class PostItApp(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.app.setWindowIcon(app_icon())
        self.app.setApplicationName("obsidian-postit-kde")
        self.app.setApplicationDisplayName("Obsidian PostIt")
        self.app.setDesktopFileName(
            os.environ.get("FLATPAK_ID", "io.github.sleroy.ObsidianPostitKde")
        )
        self.app.setQuitOnLastWindowClosed(False)
        self.app.setStyleSheet(STYLESHEET)

        self.config = Config.load()
        self._diary: DiaryWindow | None = None  # keep a ref (non-modal window)
        self._notes: set[CaptureDialog] = set()
        self._searches: set[SearchDialog] = set()
        self._voice: VoiceNoteDialog | None = None
        self._model_task: BgTask | None = None
        self._deployed_model: str | None = None

        self.tray = Tray(
            on_open_diary=self.open_diary,
            on_record_note=self.record_note,
            speech_enabled=lambda: self.config.speech_enabled,
            on_new_note=self.new_note,
            on_from_clipboard=self.new_from_clipboard,
            on_open_vault=self.open_vault,
            on_settings=self.open_settings,
            on_search=self.open_search,
            on_open_path=self.open_path,
            recent_provider=self._recent,
            on_quit=self.quit,
        )
        self.tray.show()
        self._deploy_speech_model()
        self._shortcuts: GlobalShortcuts | None = None
        if self.app.platformName() != "offscreen":
            self._shortcuts = GlobalShortcuts()
            self._shortcuts.activated.connect(
                self._activate_shortcut, Qt.ConnectionType.QueuedConnection
            )
            self._shortcuts.status.connect(
                self._on_shortcuts_status, Qt.ConnectionType.QueuedConnection
            )
            self._shortcuts.start()

        if not self.config.vault_is_valid():
            self.tray.showMessage(
                "Obsidian PostIt",
                "No vault configured yet — open Settings to pick your vault.",
                app_icon(),
                5000,
            )

    # ---- Diary ------------------------------------------------------------

    def open_diary(self) -> None:
        if not self._require_vault():
            return
        # Reuse a single diary window; raise it if already open.
        if self._diary is None:
            self._diary = DiaryWindow(
                ObsidianVault(self.config), on_open_note=self._open_diary_note
            )
            self._diary.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self._diary.destroyed.connect(self._on_diary_closed)
        self._diary.show()
        self._diary.raise_()
        self._diary.activateWindow()

    def _on_diary_closed(self, *_args: object) -> None:
        self._diary = None

    def record_note(self) -> None:
        if not self.config.speech_enabled:
            self.open_settings()
            return
        if not self._require_vault():
            return
        if self.config.speech_engine == "openrouter" and not has_api_key():
            QMessageBox.information(
                None,
                "OpenRouter key needed",
                "Voice notes are set to use OpenRouter, but no API key is configured.\n"
                "Add one in Settings → Integrations, or switch to “On this computer”.",
            )
            self.open_settings()
            return
        if self._voice is None:
            self._voice = VoiceNoteDialog(self.config)
            self._voice.finished.connect(lambda _result: self._voice_closed())
        self._voice.show()
        self._voice.raise_()
        self._voice.activateWindow()

    def _voice_closed(self) -> None:
        if self._voice is not None:
            self._voice.deleteLater()
            self._voice = None
        if self._diary is not None and not self._diary._editing:
            self._diary._reload()

    def _deploy_speech_model(self) -> None:
        if (
            not self.config.speech_enabled
            or self.config.speech_engine != "local"
            or self._model_task is not None
        ):
            return
        model = self.config.speech_model
        if model == self._deployed_model:
            return
        self.tray.showMessage("Speech model", f"Preparing {model} locally…", app_icon(), 3000)

        def done(_result: object) -> None:
            self._model_task = None
            self._deployed_model = model
            self.tray.showMessage("Speech model ready", model, app_icon(), 3000)
            if self.config.speech_model != model:
                self._deploy_speech_model()

        def failed(error: str) -> None:
            self._model_task = None
            self.tray.showMessage("Speech model unavailable", error, app_icon(), 6000)

        self._model_task = BgTask(lambda: ensure_model(model), done, failed)
        self._model_task.start()

    # ---- Notes: create ----------------------------------------------------

    def new_note(self) -> None:
        """Create a standalone note (sticky); filename guessed from content."""
        if not self._require_vault():
            return
        self._show_note(CaptureDialog(self.config, destination=Destination.FILE))

    def capture_once(self, destination: Destination) -> None:
        """One-shot capture for a global hotkey: open the popup, save, then quit.

        Does not keep a resident tray — suitable for a KDE custom shortcut.
        """
        if not self._require_vault():
            self.app.quit()
            return
        dlg = CaptureDialog(self.config, destination=destination)
        if dlg.exec() and dlg.result_note is not None:
            self._save_new(dlg.result_note)
        self.app.quit()

    def new_from_clipboard(self) -> None:
        if not self._require_vault():
            return
        clip = QGuiApplication.clipboard()
        text = clip.text() if clip else ""
        if not text.strip():
            self.tray.showMessage("Obsidian PostIt", "Clipboard is empty.", app_icon(), 3000)
            return
        dlg = CaptureDialog(
            self.config, initial_body=text, source="clipboard", destination=Destination.FILE
        )
        if dlg.exec() and dlg.result_note is not None:
            self._save_new(dlg.result_note)

    # ---- Notes: browse / edit / delete ------------------------------------

    def _recent(self) -> list[tuple[str, Path]]:
        if not self.config.vault_is_valid():
            return []
        return [(h.title, h.path) for h in ObsidianVault(self.config).recent_notes(limit=5)]

    def open_search(self) -> None:
        if not self._require_vault():
            return
        dlg = SearchDialog(ObsidianVault(self.config))
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._searches.add(dlg)

        def finished(result: int) -> None:
            self._searches.discard(dlg)
            if result and dlg.chosen_path is not None:
                self.open_path(dlg.chosen_path)

        dlg.finished.connect(finished)
        dlg.show()

    def open_path(self, path: Path) -> None:
        """Open the right surface for a path: Diary -> DiaryWindow, else editor."""
        vault = ObsidianVault(self.config)
        if vault.is_daily(path):
            self.open_diary()
            return
        try:
            note = vault.load_note(path)
        except OSError as exc:
            QMessageBox.warning(None, "Cannot open note", f"{path.name}\n\n{exc}")
            return
        dlg = CaptureDialog(
            self.config,
            initial_body=note.body,
            initial_title=note.title,
            source=note.source,
            destination=Destination.FILE,
            edit_path=path,
            allow_delete=True,
        )
        self._show_note(dlg, path)

    def _open_diary_note(self, stem: str) -> None:
        path = ObsidianVault(self.config).find_note_by_stem(stem)
        if path is None:
            QMessageBox.warning(
                self._diary, "Note not found", f"Cannot find [[{stem}]] in the vault."
            )
            return
        self.open_path(path)

    def _show_note(self, dlg: CaptureDialog, path: Path | None = None) -> None:
        dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._notes.add(dlg)

        def finished(result: int) -> None:
            self._notes.discard(dlg)
            if path is not None and dlg.delete_requested:
                self._delete(path)
            elif result and dlg.result_note is not None:
                if path is None:
                    self._save_new(dlg.result_note)
                else:
                    self._update(path, dlg.result_note)

        dlg.finished.connect(finished)
        dlg.show()

    # ---- misc -------------------------------------------------------------

    def open_vault(self) -> None:
        if not self._require_vault():
            return
        assert self.config.vault is not None
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.vault)))

    def open_settings(self) -> None:
        dlg = SettingsDialog(
            self.config,
            on_configure_shortcuts=(self._shortcuts.configure if self._shortcuts else None),
        )
        if dlg.exec():
            self.config = Config.load()
            self._deploy_speech_model()

    @Slot(str)
    def _activate_shortcut(self, action: str) -> None:
        if action == "open_diary":
            self.open_diary()
        elif action == "new_note":
            self.new_note()
        elif action == "from_clipboard":
            self.new_from_clipboard()

    @Slot(str)
    def _on_shortcuts_status(self, message: str) -> None:
        print(message, file=sys.stderr)
        if message.startswith("KDE shortcuts unavailable"):
            self.tray.showMessage("Global shortcuts", message, app_icon(), 5000)

    def quit(self) -> None:
        if self._shortcuts is not None:
            self._shortcuts.stop()
        for dlg in tuple(self._notes | self._searches):
            dlg.close()
        if self._diary is not None:
            self._diary.close()
        if self._voice is not None:
            self._voice.close()
        self.tray.hide()
        self.tray.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.quit()

    # ---- helpers ----------------------------------------------------------

    def _require_vault(self) -> bool:
        if self.config.vault_is_valid():
            return True
        QMessageBox.information(
            None,
            "No vault configured",
            "Please select your Obsidian vault folder in Settings first.",
        )
        self.open_settings()
        return self.config.vault_is_valid()

    def _save_new(self, note: Note) -> None:
        try:
            path = ObsidianVault(self.config).save(note)
        except VaultError as exc:
            QMessageBox.critical(None, "Save failed", str(exc))
            return
        self.tray.showMessage("Note saved", path.name, app_icon(), 3000)

    def _update(self, path: Path, note: Note) -> None:
        try:
            ObsidianVault(self.config).update_file_note(path, note)
        except OSError as exc:
            QMessageBox.critical(None, "Save failed", str(exc))
            return
        self.tray.showMessage("Note updated", path.name, app_icon(), 3000)

    def _delete(self, path: Path) -> None:
        try:
            ObsidianVault(self.config).delete_note(path)
        except VaultError as exc:
            QMessageBox.critical(None, "Delete failed", str(exc))
            return
        self.tray.showMessage("Note deleted", path.name, app_icon(), 3000)
