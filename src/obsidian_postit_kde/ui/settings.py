"""Settings dialog: vault, folders, defaults, autostart, OpenRouter key."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import autostart, openrouter
from ..config import Config
from ..note import Destination
from . import app_icon
from .theme import make_header


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setWindowIcon(app_icon())
        self.resize(540, 480)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(make_header("Settings", "Vault, note format, autostart and AI"))

        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card, 1)
        form = QFormLayout(card)
        form.setContentsMargins(16, 16, 16, 12)
        form.setSpacing(9)

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

        self.diary_font_spin = QSpinBox()
        self.diary_font_spin.setRange(10, 28)
        self.diary_font_spin.setSuffix(" px")
        self.diary_font_spin.setValue(getattr(config, "diary_font_px", 15))
        form.addRow("Diary font size", self.diary_font_spin)

        self.tags_edit = QLineEdit(" ".join(config.default_tags))
        form.addRow("Default tags", self.tags_edit)

        self.model_edit = QLineEdit(config.openrouter_model)
        form.addRow("OpenRouter model", self.model_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            "set — leave blank to keep" if openrouter.has_api_key() else "not set"
        )
        form.addRow("OpenRouter API key", self.key_edit)

        self.autostart_check = QCheckBox("Start automatically on login")
        self.autostart_check.setChecked(autostart.is_enabled())
        form.addRow("Autostart", self.autostart_check)

        hint = QLabel("🔒 The API key is stored in the system keyring, not in the config file.")
        hint.setObjectName("Hint")
        form.addRow("", hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.setDefault(True)
        save.clicked.connect(self._on_accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        form.addRow("", self._row_widget(btn_row))

    @staticmethod
    def _row_widget(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _browse_vault(self) -> None:
        start = self.vault_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Obsidian vault", start)
        if chosen:
            self.vault_edit.setText(chosen)

    def _on_accept(self) -> None:
        vault = self.vault_edit.text().strip()
        if vault and not Path(vault).expanduser().is_dir():
            QMessageBox.warning(
                self,
                "Invalid vault",
                f"The vault path is not a directory:\n{vault}\n\n"
                "Pick an existing folder, or clear the field.",
            )
            self.vault_edit.setFocus()
            return

        self.config.vault_path = vault
        self.config.default_destination = self.default_dest.currentData()
        self.config.subfolder = self.subfolder_edit.text().strip() or "PostIt"
        self.config.filename_template = self.filename_edit.text().strip() or "%Y-%m-%d-%H%M%S"
        self.config.daily_folder = self.daily_folder_edit.text().strip() or "Daily"
        self.config.daily_filename = (
            self.daily_filename_edit.text().strip() or "{device}-daily-note"
        )
        self.config.default_tags = self.tags_edit.text().replace(",", " ").split()
        self.config.diary_font_px = self.diary_font_spin.value()
        self.config.openrouter_model = (
            self.model_edit.text().strip() or "google/gemini-2.5-flash-lite"
        )

        new_key = self.key_edit.text().strip()
        if new_key and not openrouter.is_valid_key_format(new_key):
            QMessageBox.warning(
                self,
                "Invalid API key",
                "That doesn't look like an OpenRouter key.\n"
                "Keys start with “sk-or-”. Get one at openrouter.ai/keys.",
            )
            self.key_edit.setFocus()
            return

        try:
            self.config.save()
            autostart.set_enabled(self.autostart_check.isChecked())
            if new_key:
                openrouter.set_api_key(new_key)
        except Exception as exc:  # pragma: no cover - UI error path
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.accept()
