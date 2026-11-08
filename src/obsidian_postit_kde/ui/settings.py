"""Settings dialog: vault, defaults, autostart, and integration tokens."""

from __future__ import annotations

from collections.abc import Callable
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
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import autostart, openrouter, todoist
from ..config import Config
from ..note import Destination
from ..speech import MODELS
from . import app_icon
from .theme import make_header


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        parent: QWidget | None = None,
        on_configure_shortcuts: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Settings")
        self.setWindowIcon(app_icon())
        self.resize(580, 600)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(make_header("Settings", "Vault, note format and integrations"))

        card = QFrame()
        card.setObjectName("Card")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(card)
        outer.addWidget(scroll, 1)
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

        self.speech_check = QCheckBox("Enable local speech-to-text")
        self.speech_check.setChecked(config.speech_enabled)
        form.addRow("Voice notes", self.speech_check)

        self.speech_model = QComboBox()
        for model in MODELS:
            self.speech_model.addItem(model)
        self.speech_model.setCurrentText(config.speech_model)
        self.speech_model.setToolTip("Uses KiroCrew's cached model when available; otherwise downloads it automatically.")
        form.addRow("Speech model", self.speech_model)

        self.speech_language = QComboBox()
        self.speech_language.setEditable(True)
        for code, label in (("auto", "Auto-detect"), ("en", "English"), ("fr", "French"), ("de", "German"), ("it", "Italian"), ("es", "Spanish")):
            self.speech_language.addItem(label, code)
        index = self.speech_language.findData(config.speech_language)
        if index >= 0:
            self.speech_language.setCurrentIndex(index)
        else:
            self.speech_language.setEditText(config.speech_language)
        self.speech_language.setToolTip("Choose a language or type its two-letter code.")
        form.addRow("Speech language", self.speech_language)

        self.speech_clean_check = QCheckBox("Clean transcript with OpenRouter before saving")
        self.speech_clean_check.setChecked(config.speech_clean_with_openrouter)
        form.addRow("Voice cleanup", self.speech_clean_check)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            "set — leave blank to keep" if openrouter.has_api_key() else "not set"
        )
        form.addRow("OpenRouter API key", self.key_edit)

        self.todoist_token_edit = QLineEdit()
        self.todoist_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.todoist_token_edit.setPlaceholderText(
            "set — leave blank to keep" if todoist.has_api_token() else "not set"
        )
        form.addRow("Todoist API token", self.todoist_token_edit)

        shortcuts_btn = QPushButton("Configure KDE shortcuts…")
        shortcuts_btn.setEnabled(on_configure_shortcuts is not None)
        if on_configure_shortcuts is not None:
            shortcuts_btn.clicked.connect(on_configure_shortcuts)
        form.addRow("Global shortcuts", shortcuts_btn)

        self.autostart_check = QCheckBox("Start automatically on login")
        self.autostart_check.setChecked(autostart.is_enabled())
        form.addRow("Autostart", self.autostart_check)

        hint = QLabel("🔒 API tokens are stored in the system keyring, not in the config file.")
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
        language = self.speech_language.currentText().strip().lower()
        labels = {"auto-detect": "auto", "english": "en", "french": "fr", "german": "de", "italian": "it", "spanish": "es"}
        language = labels.get(language, language)
        if language != "auto" and (len(language) != 2 or not language.isalpha()):
            QMessageBox.warning(self, "Invalid language", "Enter 'auto' or a two-letter language code.")
            return
        self.config.speech_enabled = self.speech_check.isChecked()
        self.config.speech_model = self.speech_model.currentText()
        self.config.speech_language = language
        self.config.speech_clean_with_openrouter = self.speech_clean_check.isChecked()

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
            todoist_token = self.todoist_token_edit.text().strip()
            if todoist_token:
                todoist.set_api_token(todoist_token)
        except Exception as exc:  # pragma: no cover - UI error path
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self.accept()
