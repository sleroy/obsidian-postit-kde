"""Settings dialog: vault, folders, defaults, autostart, OpenRouter key."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import autostart, openrouter
from ..config import Config
from ..note import Destination
from . import app_icon


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setWindowIcon(app_icon())
        self.resize(520, 420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Vault picker
        vault_row = QHBoxLayout()
        self.vault_edit = QLineEdit(config.vault_path)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_vault)
        vault_row.addWidget(self.vault_edit, 1)
        vault_row.addWidget(browse)
        form.addRow("Obsidian vault", vault_row)

        self.default_dest = QComboBox()
        self.default_dest.addItem("Sticky daily note", Destination.DAILY.value)
        self.default_dest.addItem("New note (file)", Destination.FILE.value)
        i = self.default_dest.findData(config.default_destination)
        if i >= 0:
            self.default_dest.setCurrentIndex(i)
        form.addRow("Default destination", self.default_dest)

        self.subfolder_edit = QLineEdit(config.subfolder)
        form.addRow("Note folder", self.subfolder_edit)

        self.filename_edit = QLineEdit(config.filename_template)
        form.addRow("Filename template", self.filename_edit)

        self.daily_folder_edit = QLineEdit(config.daily_folder)
        form.addRow("Daily folder", self.daily_folder_edit)

        self.daily_filename_edit = QLineEdit(config.daily_filename)
        self.daily_filename_edit.setToolTip("{device} is replaced with the hostname.")
        form.addRow("Daily filename", self.daily_filename_edit)

        self.tags_edit = QLineEdit(" ".join(config.default_tags))
        form.addRow("Default tags", self.tags_edit)

        self.model_edit = QLineEdit(config.openrouter_model)
        form.addRow("OpenRouter model", self.model_edit)

        # API key (kept in keyring; shown masked, blank = unchanged)
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            "set — leave blank to keep" if openrouter.has_api_key() else "not set"
        )
        form.addRow("OpenRouter API key", self.key_edit)

        self.autostart_check = QCheckBox("Start automatically on login")
        self.autostart_check.setChecked(autostart.is_enabled())
        form.addRow("Autostart", self.autostart_check)

        layout.addLayout(form)
        layout.addWidget(
            QLabel("The API key is stored in the system keyring, not in the config file.")
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_vault(self) -> None:
        start = self.vault_edit.text() or str(__import__("pathlib").Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Obsidian vault", start)
        if chosen:
            self.vault_edit.setText(chosen)

    def _on_accept(self) -> None:
        self.config.vault_path = self.vault_edit.text().strip()
        self.config.default_destination = self.default_dest.currentData()
        self.config.subfolder = self.subfolder_edit.text().strip() or "PostIt"
        self.config.filename_template = self.filename_edit.text().strip() or "%Y-%m-%d-%H%M%S"
        self.config.daily_folder = self.daily_folder_edit.text().strip() or "Daily"
        self.config.daily_filename = (
            self.daily_filename_edit.text().strip() or "{device}-daily-note"
        )
        self.config.default_tags = self.tags_edit.text().replace(",", " ").split()
        self.config.openrouter_model = self.model_edit.text().strip() or "openai/gpt-4o-mini"

        try:
            self.config.save()
            autostart.set_enabled(self.autostart_check.isChecked())
            new_key = self.key_edit.text().strip()
            if new_key:
                openrouter.set_api_key(new_key)
        except Exception as exc:  # pragma: no cover - UI error path
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.accept()
