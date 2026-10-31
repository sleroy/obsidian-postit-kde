"""Application controller: wires the tray to capture/settings and the vault."""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from .config import Config
from .note import Note
from .ui import app_icon
from .ui.capture import CaptureDialog
from .ui.settings import SettingsDialog
from .ui.tray import Tray
from .vault import ObsidianVault, VaultError


class PostItApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        self.app.setWindowIcon(app_icon())
        self.app.setApplicationName("obsidian-postit-kde")
        self.app.setApplicationDisplayName("Obsidian PostIt")
        self.app.setQuitOnLastWindowClosed(False)

        self.config = Config.load()

        self.tray = Tray(
            on_new_note=self.new_note,
            on_from_clipboard=self.new_from_clipboard,
            on_open_vault=self.open_vault,
            on_settings=self.open_settings,
            on_quit=self.quit,
        )
        self.tray.show()

        if not self.config.vault_is_valid():
            self.tray.showMessage(
                "Obsidian PostIt",
                "No vault configured yet — open Settings to pick your vault.",
                app_icon(),
                5000,
            )

    # ---- flows ------------------------------------------------------------

    def new_note(self, initial_body: str = "", source: str = "manual") -> None:
        if not self._require_vault():
            return
        dlg = CaptureDialog(self.config, initial_body=initial_body, source=source)
        if dlg.exec() and dlg.result_note is not None:
            self._save(dlg.result_note)

    def new_from_clipboard(self) -> None:
        clip = QGuiApplication.clipboard()
        text = clip.text() if clip else ""
        if not text.strip():
            self.tray.showMessage("Obsidian PostIt", "Clipboard is empty.", app_icon(), 3000)
            return
        self.new_note(initial_body=text, source="clipboard")

    def open_vault(self) -> None:
        if not self._require_vault():
            return
        assert self.config.vault is not None
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.vault)))

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.config)
        if dlg.exec():
            self.config = Config.load()  # reload persisted values

    def quit(self) -> None:
        self.tray.hide()
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

    def _save(self, note: Note) -> None:
        try:
            path = ObsidianVault(self.config).save(note)
        except VaultError as exc:
            QMessageBox.critical(None, "Save failed", str(exc))
            return
        self.tray.showMessage("Note saved", str(path.name), app_icon(), 3000)
