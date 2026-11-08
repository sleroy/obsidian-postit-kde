"""Settings dialog, organised in tabs: notes, voice, integrations, system.

Every field sits in a titled section with a short hint under it, and every
fixed choice is a dropdown with a visible chevron (see theme.py), so a choice
never looks like a free-text field.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import autostart, openrouter, todoist
from ..config import Config
from ..note import Destination
from ..speech import LANGUAGES, MODEL_LABELS, MODELS
from . import app_icon
from .theme import make_header

DEFAULT_AI_MODEL = "google/gemini-2.5-flash-lite"
LABEL_WIDTH = 140  # shared label column, so sections line up across a tab


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(True)
    return label


def _with_hint(widget: QWidget, hint: str | None) -> QWidget:
    """Stack a field and its hint so the explanation sits right under it."""
    if not hint:
        return widget
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(3)
    lay.addWidget(widget)
    lay.addWidget(_hint(hint))
    return box


def _section(title: str, description: str = "") -> tuple[QFrame, QFormLayout]:
    """A framed card: a header (title + optional one-line description) above a form."""
    frame = QFrame()
    frame.setObjectName("Section")
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(14, 12, 14, 14)
    outer.setSpacing(10)
    head = QLabel(title)
    head.setObjectName("SectionTitle")
    outer.addWidget(head)
    if description:
        outer.addWidget(_hint(description))
    rule = QFrame()
    rule.setObjectName("SectionRule")
    rule.setFixedHeight(1)
    outer.addWidget(rule)
    form = QFormLayout()
    outer.addLayout(form)
    form.setSpacing(10)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return frame, form


def _align_labels(root: QWidget) -> None:
    """Give every form label the same width so fields line up between sections."""
    for form in root.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            label = item.widget() if item is not None else None
            if label is not None:
                label.setMinimumWidth(LABEL_WIDTH)


def _page(*sections: QWidget) -> QScrollArea:
    body = QWidget()
    lay = QVBoxLayout(body)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(12)
    for section in sections:
        lay.addWidget(section)
    lay.addStretch(1)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setWidget(body)
    return scroll


def _dropdown(items, current) -> QComboBox:
    """A non-editable dropdown of (value, label) pairs; keeps unknown values."""
    combo = QComboBox()
    for value, label in items:
        combo.addItem(label, value)
    index = combo.findData(current)
    if index < 0 and current:
        combo.addItem(str(current), current)  # preserve a hand-edited config value
        index = combo.count() - 1
    combo.setCurrentIndex(max(index, 0))
    return combo


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
        self.resize(660, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(make_header("Settings", "Vault, notes, voice and integrations"))

        card = QFrame()
        card.setObjectName("Card")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(0, 4, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._notes_tab(), "Vault && notes")
        self.tabs.addTab(self._voice_tab(), "Voice notes")
        self.tabs.addTab(self._integrations_tab(), "Integrations")
        self.tabs.addTab(self._system_tab(on_configure_shortcuts), "System")
        card_lay.addWidget(self.tabs, 1)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(14, 8, 14, 12)
        btn_row.addWidget(
            _hint("🔒 API keys are stored in the system keyring, never in the config file."), 1
        )
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.setDefault(True)
        save.clicked.connect(self._on_accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        card_lay.addLayout(btn_row)
        outer.addWidget(card, 1)

        _align_labels(self)
        self._sync_voice_state()

    # ---- tabs --------------------------------------------------------------

    def _notes_tab(self) -> QWidget:
        c = self.config
        vault_group, form = _section("Obsidian vault", "Where your notes are saved.")
        vault_row = QWidget()
        row = QHBoxLayout(vault_row)
        row.setContentsMargins(0, 0, 0, 0)
        self.vault_edit = QLineEdit(c.vault_path)
        self.vault_edit.setPlaceholderText("/home/you/Obsidian")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_vault)
        row.addWidget(self.vault_edit, 1)
        row.addWidget(browse)
        form.addRow("Vault folder", _with_hint(vault_row, "The folder that contains .obsidian/."))
        self.default_dest = _dropdown(
            [
                (Destination.DAILY.value, "Add to today's daily note"),
                (Destination.FILE.value, "Create a new note file"),
            ],
            c.default_destination,
        )
        form.addRow(
            "New post-it goes to",
            _with_hint(self.default_dest, "You can still switch per note in the capture window."),
        )

        notes_group, form = _section("Note files", "Used when a post-it is saved as its own file.")
        self.subfolder_edit = QLineEdit(c.subfolder)
        form.addRow("Folder", _with_hint(self.subfolder_edit, "Relative to the vault."))
        self.filename_edit = QLineEdit(c.filename_template)
        form.addRow(
            "File name",
            _with_hint(self.filename_edit, "Date pattern, e.g. %Y-%m-%d-%H%M%S."),
        )
        self.tags_edit = QLineEdit(" ".join(c.default_tags))
        form.addRow("Default tags", _with_hint(self.tags_edit, "Separated by spaces or commas."))

        daily_group, form = _section("Daily note", "One running note per day and per computer.")
        self.daily_folder_edit = QLineEdit(c.daily_folder)
        form.addRow("Folder", self.daily_folder_edit)
        self.daily_filename_edit = QLineEdit(c.daily_filename)
        form.addRow(
            "File name",
            _with_hint(self.daily_filename_edit, "{device} is replaced with this computer's name."),
        )
        self.diary_font_spin = QSpinBox()
        self.diary_font_spin.setRange(10, 28)
        self.diary_font_spin.setSuffix(" px")
        self.diary_font_spin.setValue(getattr(c, "diary_font_px", 15))
        self.diary_font_spin.setMaximumWidth(120)
        form.addRow("Diary text size", self.diary_font_spin)
        return _page(vault_group, notes_group, daily_group)

    def _voice_tab(self) -> QWidget:
        c = self.config
        enable_group, form = _section(
            "Voice notes", "Dictate a note; the transcript is appended to today's daily note."
        )
        self.speech_check = QCheckBox("Enable “Record a note” in the tray menu")
        self.speech_check.setChecked(c.speech_enabled)
        self.speech_check.toggled.connect(self._sync_voice_state)
        form.addRow(self.speech_check)

        engine_group, form = _section("Speech engine", "Where your recording is turned into text.")
        self.local_radio = QRadioButton("On this computer")
        self.cloud_radio = QRadioButton("OpenRouter (cloud)")
        self._engine_buttons = QButtonGroup(self)
        self._engine_buttons.addButton(self.local_radio)
        self._engine_buttons.addButton(self.cloud_radio)
        (self.cloud_radio if c.speech_engine == "openrouter" else self.local_radio).setChecked(True)
        self.local_radio.toggled.connect(self._sync_voice_state)
        engines = QWidget()
        lay = QVBoxLayout(engines)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.local_radio)
        lay.addWidget(_hint("Private and free. The model is loaded into memory while you record."))
        lay.addSpacing(6)
        lay.addWidget(self.cloud_radio)
        lay.addWidget(
            _hint(
                "Nothing to load and no memory used, for about a cent per hour of audio. "
                "Your recording is sent to OpenRouter."
            )
        )
        form.addRow(engines)

        model_group, form = _section("Model and language")
        self.speech_model = _dropdown([(m, MODEL_LABELS[m]) for m in MODELS], c.speech_model)
        self.speech_model.setToolTip(
            "Downloaded automatically on first use (reuses KiroCrew's model cache when present)."
        )
        form.addRow("Local model", self.speech_model)

        self.speech_cloud_model = _dropdown(openrouter.STT_MODELS, c.speech_cloud_model)
        self._cloud_key_hint = _hint("")
        self._cloud_box = QWidget()
        cloud_lay = QVBoxLayout(self._cloud_box)
        cloud_lay.setContentsMargins(0, 0, 0, 0)
        cloud_lay.setSpacing(3)
        cloud_lay.addWidget(self.speech_cloud_model)
        cloud_lay.addWidget(self._cloud_key_hint)
        form.addRow("Cloud model", self._cloud_box)
        self._voice_form = form

        self.speech_language = _dropdown(LANGUAGES, c.speech_language)
        form.addRow(
            "Language",
            _with_hint(self.speech_language, "Choosing your language is faster and more accurate."),
        )

        extras_group, form = _section("While recording")
        self._voice_sections = (engine_group, model_group, extras_group)
        self.speech_live_check = QCheckBox("Show the transcript live as I speak")
        self.speech_live_check.setChecked(c.speech_live_preview)
        form.addRow(
            _with_hint(
                self.speech_live_check,
                "With OpenRouter this sends the audio a few extra times; still well under a cent.",
            )
        )
        self.speech_clean_check = QCheckBox("Tidy the transcript with AI before saving")
        self.speech_clean_check.setChecked(c.speech_clean_with_openrouter)
        form.addRow(
            _with_hint(
                self.speech_clean_check,
                "Fixes punctuation and typos using the AI model from the Integrations tab.",
            )
        )
        return _page(enable_group, engine_group, model_group, extras_group)

    def _integrations_tab(self) -> QWidget:
        c = self.config
        ai_group, form = _section("OpenRouter", "AI summaries, clean-up and cloud transcription.")
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText(
            "Saved — leave blank to keep it" if openrouter.has_api_key() else "sk-or-…"
        )
        form.addRow(
            "API key",
            _with_hint(
                self.key_edit,
                'Get one at <a style="color:#a78bfa" href="https://openrouter.ai/keys">'
                "openrouter.ai/keys</a>.",
            ),
        )
        self.model_edit = QComboBox()
        self.model_edit.setEditable(True)
        self.model_edit.addItems(openrouter.CHAT_MODELS)
        self.model_edit.setCurrentText(c.openrouter_model)
        form.addRow(
            "AI model",
            _with_hint(
                self.model_edit,
                "Used to summarise and clean notes. Pick one or type any OpenRouter model id.",
            ),
        )

        todo_group, form = _section("Todoist", "Send a note to Todoist as a task.")
        self.todoist_token_edit = QLineEdit()
        self.todoist_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.todoist_token_edit.setPlaceholderText(
            "Saved — leave blank to keep it" if todoist.has_api_token() else "Not set"
        )
        form.addRow(
            "API token",
            _with_hint(
                self.todoist_token_edit,
                "Todoist → Settings → Integrations → Developer → API token.",
            ),
        )
        self.key_edit.textChanged.connect(self._sync_voice_state)
        return _page(ai_group, todo_group)

    def _system_tab(self, on_configure_shortcuts: Callable[[], None] | None) -> QWidget:
        group, form = _section("Desktop", "How the app integrates with KDE Plasma.")
        self.autostart_check = QCheckBox("Start automatically when I log in")
        self.autostart_check.setChecked(autostart.is_enabled())
        form.addRow(self.autostart_check)
        shortcuts_btn = QPushButton("Configure KDE shortcuts…")
        shortcuts_btn.setEnabled(on_configure_shortcuts is not None)
        if on_configure_shortcuts is not None:
            shortcuts_btn.clicked.connect(on_configure_shortcuts)
        form.addRow(
            "Global shortcuts",
            _with_hint(shortcuts_btn, "Opens KDE System Settings for this app's shortcuts."),
        )
        return _page(group)

    # ---- behaviour -----------------------------------------------------------

    def _sync_voice_state(self) -> None:
        enabled = self.speech_check.isChecked()
        for section in self._voice_sections:
            section.setEnabled(enabled)
        local = self.local_radio.isChecked()
        form = self._voice_form
        form.setRowVisible(self.speech_model, local)
        form.setRowVisible(self._cloud_box, not local)
        if openrouter.has_api_key() or self.key_edit.text().strip():
            self._cloud_key_hint.setText("Uses your OpenRouter API key (Integrations tab).")
        else:
            self._cloud_key_hint.setText(
                "⚠ Needs an OpenRouter API key: add it in the Integrations tab."
            )

    def _browse_vault(self) -> None:
        start = self.vault_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Obsidian vault", start)
        if chosen:
            self.vault_edit.setText(chosen)

    def _on_accept(self) -> None:
        vault = self.vault_edit.text().strip()
        if vault and not Path(vault).expanduser().is_dir():
            self.tabs.setCurrentIndex(0)
            QMessageBox.warning(
                self,
                "Invalid vault",
                f"The vault path is not a directory:\n{vault}\n\n"
                "Pick an existing folder, or clear the field.",
            )
            self.vault_edit.setFocus()
            return

        new_key = self.key_edit.text().strip()
        if new_key and not openrouter.is_valid_key_format(new_key):
            self.tabs.setCurrentIndex(2)
            QMessageBox.warning(
                self,
                "Invalid API key",
                "That doesn't look like an OpenRouter key.\n"
                "Keys start with “sk-or-”. Get one at openrouter.ai/keys.",
            )
            self.key_edit.setFocus()
            return

        c = self.config
        c.vault_path = vault
        c.default_destination = self.default_dest.currentData()
        c.subfolder = self.subfolder_edit.text().strip() or "PostIt"
        c.filename_template = self.filename_edit.text().strip() or "%Y-%m-%d-%H%M%S"
        c.daily_folder = self.daily_folder_edit.text().strip() or "Daily"
        c.daily_filename = self.daily_filename_edit.text().strip() or "{device}-daily-note"
        c.default_tags = self.tags_edit.text().replace(",", " ").split()
        c.diary_font_px = self.diary_font_spin.value()
        c.openrouter_model = self.model_edit.currentText().strip() or DEFAULT_AI_MODEL
        c.speech_enabled = self.speech_check.isChecked()
        c.speech_engine = "local" if self.local_radio.isChecked() else "openrouter"
        c.speech_model = self.speech_model.currentData()
        c.speech_cloud_model = self.speech_cloud_model.currentData()
        c.speech_language = self.speech_language.currentData()
        c.speech_live_preview = self.speech_live_check.isChecked()
        c.speech_clean_with_openrouter = self.speech_clean_check.isChecked()

        try:
            c.save()
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
