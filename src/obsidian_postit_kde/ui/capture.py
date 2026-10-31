"""Capture popup: enter a note, pick destination, tag it, optionally AI-assist."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import Config, device_slug
from ..note import Destination, Note, parse_tags
from ..openrouter import OpenRouterClient, OpenRouterError, has_api_key
from . import app_icon
from .theme import make_header


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setObjectName("FieldLabel")
    return lbl


class CaptureDialog(QDialog):
    """Capture window. Returns a Note via `result_note` on accept."""

    def __init__(
        self,
        config: Config,
        initial_body: str = "",
        source: str = "manual",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.source = source
        self.result_note: Note | None = None

        title = "New note from clipboard" if source == "clipboard" else "New note"
        self.setWindowTitle(title)
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(480, 420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(make_header(title, "Capture straight into your Obsidian vault"))

        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card, 1)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(14, 14, 14, 14)
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(14, 14, 14, 14)
        card_lay.setSpacing(8)

        # Destination
        card_lay.addWidget(_field_label("Destination"))
        self.destination = QComboBox()
        self.destination.addItem("Sticky daily note", Destination.DAILY.value)
        self.destination.addItem("New note (file)", Destination.FILE.value)
        idx = self.destination.findData(config.default_destination)
        if idx >= 0:
            self.destination.setCurrentIndex(idx)
        self.destination.currentIndexChanged.connect(self._update_target)
        card_lay.addWidget(self.destination)

        self.target_preview = QLabel()
        self.target_preview.setObjectName("TargetPreview")
        card_lay.addWidget(self.target_preview)

        # Title + Tags on one row
        row = QHBoxLayout()
        row.setSpacing(10)
        title_col = QVBoxLayout()
        title_col.addWidget(_field_label("Title (optional)"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Optional title")
        self.title_edit.textChanged.connect(self._update_target)
        title_col.addWidget(self.title_edit)
        tags_col = QVBoxLayout()
        tags_col.addWidget(_field_label("Tags"))
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("space or comma separated")
        tags_col.addWidget(self.tags_edit)
        row.addLayout(title_col, 1)
        row.addLayout(tags_col, 1)
        card_lay.addLayout(row)

        # Body
        card_lay.addWidget(_field_label("Note"))
        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlainText(initial_body)
        card_lay.addWidget(self.body_edit, 1)

        # AI assist row + hint
        ai_row = QHBoxLayout()
        self.summarize_btn = QPushButton("✦ Summarize")
        self.clean_btn = QPushButton("✦ Clean")
        for btn in (self.summarize_btn, self.clean_btn):
            btn.setObjectName("Assist")
        self.summarize_btn.clicked.connect(self._on_summarize)
        self.clean_btn.clicked.connect(self._on_clean)
        ai_row.addWidget(self.summarize_btn)
        ai_row.addWidget(self.clean_btn)
        ai_row.addStretch(1)
        self.ai_hint = QLabel()
        self.ai_hint.setObjectName("Hint")
        ai_row.addWidget(self.ai_hint)
        card_lay.addLayout(ai_row)

        enabled = has_api_key()
        for btn in (self.summarize_btn, self.clean_btn):
            btn.setEnabled(enabled)
        self.ai_hint.setText("" if enabled else "Add an OpenRouter key in Settings")

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save  (Ctrl+⏎)")
        self.save_btn.setObjectName("Primary")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_accept)
        btn_row.addWidget(cancel)
        btn_row.addWidget(self.save_btn)
        card_lay.addLayout(btn_row)

        # Shortcuts: Ctrl+Enter saves, Esc cancels (Esc is default for QDialog)
        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            shortcut = QShortcut(QKeySequence(seq), self)
            shortcut.activated.connect(self._on_accept)

        self._update_target()
        self.body_edit.setFocus()

    # ---- target preview ---------------------------------------------------

    def _update_target(self) -> None:
        dest = Destination(self.destination.currentData())
        if dest is Destination.DAILY:
            name = self.config.daily_filename.format(device=device_slug())
            path = f"{self.config.daily_folder}/{name}.md"
        else:
            title = self.title_edit.text().strip()
            from ..note import slugify

            stem = "<timestamp>"
            if self.config.add_title_slug and title and slugify(title):
                stem += f"-{slugify(title)}"
            path = f"{self.config.subfolder}/{stem}.md"
        self.target_preview.setText(f"→ {path}")

    # ---- AI actions -------------------------------------------------------

    def _client(self) -> OpenRouterClient:
        return OpenRouterClient(self.config.openrouter_model)

    def _on_summarize(self) -> None:
        self._run_ai(lambda c, t: c.summarize(t))

    def _on_clean(self) -> None:
        self._run_ai(lambda c, t: c.clean(t))

    def _run_ai(self, fn) -> None:
        text = self.body_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Nothing to do", "The note is empty.")
            return
        self.setEnabled(False)
        try:
            result = fn(self._client(), text)
            self.body_edit.setPlainText(result)
        except OpenRouterError as exc:
            QMessageBox.warning(self, "OpenRouter error", str(exc))
        finally:
            self.setEnabled(True)

    # ---- accept -----------------------------------------------------------

    def _on_accept(self) -> None:
        body = self.body_edit.toPlainText().strip()
        if not body:
            QMessageBox.information(self, "Empty note", "Please enter some text.")
            return
        self.result_note = Note(
            body=body,
            title=self.title_edit.text().strip(),
            tags=parse_tags(self.tags_edit.text()),
            source=self.source,
            destination=Destination(self.destination.currentData()),
        )
        self.accept()
