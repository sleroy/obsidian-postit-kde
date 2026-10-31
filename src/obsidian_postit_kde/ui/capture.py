"""Capture popup: enter a note, pick destination, tag it, optionally AI-assist."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..note import Destination, Note, parse_tags
from ..openrouter import OpenRouterClient, OpenRouterError, has_api_key
from . import app_icon


class CaptureDialog(QDialog):
    """Modal-ish capture window. Returns a Note via `result_note` on accept."""

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

        self.setWindowTitle("New note")
        self.setWindowIcon(app_icon())
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.resize(460, 340)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.destination = QComboBox()
        self.destination.addItem("Sticky daily note", Destination.DAILY.value)
        self.destination.addItem("New note (file)", Destination.FILE.value)
        idx = self.destination.findData(config.default_destination)
        if idx >= 0:
            self.destination.setCurrentIndex(idx)
        form.addRow("Destination", self.destination)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Optional title")
        form.addRow("Title", self.title_edit)

        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("tags separated by spaces or commas")
        form.addRow("Tags", self.tags_edit)
        layout.addLayout(form)

        layout.addWidget(QLabel("Note"))
        self.body_edit = QPlainTextEdit()
        self.body_edit.setPlainText(initial_body)
        layout.addWidget(self.body_edit, 1)

        # OpenRouter assist row
        ai_row = QHBoxLayout()
        self.summarize_btn = QPushButton("Summarize")
        self.clean_btn = QPushButton("Clean")
        self.summarize_btn.clicked.connect(self._on_summarize)
        self.clean_btn.clicked.connect(self._on_clean)
        enabled = has_api_key()
        for btn in (self.summarize_btn, self.clean_btn):
            btn.setEnabled(enabled)
            if not enabled:
                btn.setToolTip("Set an OpenRouter API key in Settings to enable.")
        ai_row.addWidget(self.summarize_btn)
        ai_row.addWidget(self.clean_btn)
        ai_row.addStretch(1)
        layout.addLayout(ai_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.body_edit.setFocus()

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
