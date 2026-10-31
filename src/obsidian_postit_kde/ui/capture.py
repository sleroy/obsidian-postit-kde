"""Capture popup styled as a single yellow sticky note.

Design goal: writing a note is one step. The window *is* the note — a yellow
paper card with an optional title line and a body. Destination, inline tags
and AI actions live in a slim footer so they never get in the way of typing.
Tags are written inline as Obsidian #tags in the body.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QKeySequence, QMouseEvent, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QSizeGrip,
    QStackedWidget,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..config import Config, device_slug
from ..note import Destination, Note, parse_tags, slugify
from ..openrouter import OpenRouterClient, OpenRouterError, has_api_key
from .highlighter import MarkdownHighlighter, find_tokens
from .theme import POSTIT_STYLESHEET


class PinLabel(QLabel):
    """A little red push-pin drawn at the top of the note."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(18)
        self.setText(
            '<span style="font-size:18px; color:#dc2626;">\u25cf</span>'
            '<span style="font-size:11px; color:#991b1b;"> \u2502</span>'
        )
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter)


class CaptureDialog(QDialog):
    """Sticky-note capture window. Returns a Note via `result_note` on accept."""

    def __init__(
        self,
        config: Config,
        initial_body: str = "",
        initial_title: str = "",
        source: str = "manual",
        destination: Destination | None = None,
        edit_path: object = None,
        allow_delete: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.source = source
        self.result_note: Note | None = None
        self.edit_path = edit_path  # when set, caller rewrites this file
        self.allow_delete = allow_delete
        self.delete_requested = False
        self._drag_offset: QPoint | None = None
        self._dest = destination or Destination(config.default_destination)

        self.setWindowTitle("Edit note" if edit_path else "New note")
        # Frameless, translucent so the rounded paper + shadow show through.
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(POSTIT_STYLESHEET)
        # Post-it ratio: square. Resizable (grip added in the footer below).
        self.setMinimumSize(260, 260)
        self.resize(360, 360)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 14)  # room for the shadow

        paper = QFrame()
        paper.setObjectName("Paper")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 120))
        paper.setGraphicsEffect(shadow)
        root.addWidget(paper)

        lay = QVBoxLayout(paper)
        lay.setContentsMargins(14, 6, 14, 10)
        lay.setSpacing(6)

        lay.addWidget(PinLabel())

        self.title_edit = QLineEdit()
        self.title_edit.setObjectName("PostitTitle")
        self.title_edit.setPlaceholderText("Title (optional)")
        self.title_edit.setText(initial_title)
        self.title_edit.textChanged.connect(self._update_dest_label)
        lay.addWidget(self.title_edit)

        # Editor + preview share a stack; the footer toggles between them.
        self.stack = QStackedWidget()
        self.body_edit = QPlainTextEdit()
        self.body_edit.setObjectName("PostitBody")
        self.body_edit.setPlaceholderText("Write your note…  use #tags inline")
        self.body_edit.setPlainText(initial_body)
        self._highlighter = MarkdownHighlighter(self.body_edit.document())

        self.preview = QTextBrowser()
        self.preview.setObjectName("PostitBody")
        self.preview.setOpenExternalLinks(True)

        self.stack.addWidget(self.body_edit)  # index 0 = edit
        self.stack.addWidget(self.preview)  # index 1 = preview
        lay.addWidget(self.stack, 1)

        lay.addLayout(self._build_footer())

        # Shortcuts
        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(seq), self).activated.connect(self._on_accept)

        self._update_dest_label()
        self.body_edit.setFocus()

    # ---- footer -----------------------------------------------------------

    def _build_footer(self) -> QHBoxLayout:
        footer = QHBoxLayout()
        footer_host = QWidget()
        footer_host.setObjectName("PostitFooter")
        # Build buttons parented to a host so object-name styling applies.
        self.dest_btn = QToolButton(footer_host)
        self.dest_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.dest_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        dest_menu = QMenu(self.dest_btn)
        self._act_daily = dest_menu.addAction("Sticky daily note")
        self._act_file = dest_menu.addAction("New note (file)")
        self._act_daily.setCheckable(True)
        self._act_file.setCheckable(True)
        self._act_daily.triggered.connect(lambda: self._set_dest(Destination.DAILY))
        self._act_file.triggered.connect(lambda: self._set_dest(Destination.FILE))
        self.dest_btn.setMenu(dest_menu)

        self.preview_btn = QToolButton(footer_host)
        self.preview_btn.setText("\U0001f441 Preview")
        self.preview_btn.setCheckable(True)
        self.preview_btn.setToolTip("Toggle Markdown preview")
        self.preview_btn.toggled.connect(self._toggle_preview)

        self.ai_btn = QToolButton(footer_host)
        self.ai_btn.setText("\u2726 AI")
        self.ai_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        ai_menu = QMenu(self.ai_btn)
        ai_menu.addAction("Summarize", self._on_summarize)
        ai_menu.addAction("Clean", self._on_clean)
        self.ai_btn.setMenu(ai_menu)
        if not has_api_key():
            self.ai_btn.setEnabled(False)
            self.ai_btn.setToolTip("Add an OpenRouter key in Settings to enable.")

        self.save_btn = QToolButton(footer_host)
        self.save_btn.setObjectName("PostitSave")
        self.save_btn.setText("Save")
        self.save_btn.setToolTip("Save (Ctrl+Enter)")
        self.save_btn.clicked.connect(self._on_accept)

        close_btn = QToolButton(footer_host)
        close_btn.setText("\u2715")
        close_btn.setToolTip("Cancel (Esc)")
        close_btn.clicked.connect(self.reject)

        footer.addWidget(self.dest_btn)
        footer.addStretch(1)
        if self.allow_delete:
            del_btn = QToolButton(footer_host)
            del_btn.setText("🗑")
            del_btn.setToolTip("Delete this note")
            del_btn.clicked.connect(self._on_delete)
            footer.addWidget(del_btn)
        footer.addWidget(self.preview_btn)
        footer.addWidget(self.ai_btn)
        footer.addWidget(close_btn)
        footer.addWidget(self.save_btn)

        grip = QSizeGrip(footer_host)
        grip.setToolTip("Drag to resize")
        footer.addWidget(grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        # Parent the host widget's object name onto the layout via a wrapper.
        self._footer_host = footer_host
        wrapper = QHBoxLayout()
        footer_host.setLayout(footer)
        wrapper.addWidget(footer_host)
        wrapper.setContentsMargins(0, 0, 0, 0)
        return wrapper

    def _set_dest(self, dest: Destination) -> None:
        self._dest = dest
        self._update_dest_label()

    def _toggle_preview(self, on: bool) -> None:
        if on:
            body = self.body_edit.toPlainText()
            title = self.title_edit.text().strip()
            md = f"# {title}\n\n{body}" if title else body
            self.preview.setMarkdown(md)
            self.stack.setCurrentIndex(1)
            self.preview_btn.setText("\u270e Edit")
        else:
            self.stack.setCurrentIndex(0)
            self.preview_btn.setText("\U0001f441 Preview")
            self.body_edit.setFocus()

    def _update_dest_label(self) -> None:
        if self._dest is Destination.DAILY:
            name = self.config.daily_filename.format(device=device_slug())
            self.dest_btn.setText(f"\u25be  {self.config.daily_folder}/{name}.md")
        else:
            title = self.title_edit.text().strip()
            stem = "…"
            if self.config.add_title_slug and title and slugify(title):
                stem = slugify(title)
            self.dest_btn.setText(f"\u25be  {self.config.subfolder}/{stem}.md")
        self._act_daily.setChecked(self._dest is Destination.DAILY)
        self._act_file.setChecked(self._dest is Destination.FILE)

    # ---- drag to move (frameless) ----------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ---- AI ---------------------------------------------------------------

    def _client(self) -> OpenRouterClient:
        return OpenRouterClient(self.config.openrouter_model)

    def _on_summarize(self) -> None:
        self._run_ai(lambda c, t: c.summarize(t))

    def _on_clean(self) -> None:
        self._run_ai(lambda c, t: c.clean(t))

    def _run_ai(self, fn) -> None:
        from PySide6.QtWidgets import QMessageBox

        text = self.body_edit.toPlainText().strip()
        if not text:
            return
        self.setEnabled(False)
        try:
            self.body_edit.setPlainText(fn(self._client(), text))
        except OpenRouterError as exc:
            QMessageBox.warning(self, "OpenRouter error", str(exc))
        finally:
            self.setEnabled(True)

    # ---- delete -----------------------------------------------------------

    def _on_delete(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        resp = QMessageBox.question(
            self,
            "Delete note?",
            "Delete this note permanently? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.delete_requested = True
            self.reject()  # caller checks delete_requested

    # ---- accept -----------------------------------------------------------

    def _on_accept(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        body = self.body_edit.toPlainText().strip()
        if not body:
            QMessageBox.information(self, "Empty note", "Please write something first.")
            return
        # Tags are inline #tags in the body; extract with the same regex the
        # highlighter uses so extraction matches what the user sees.
        inline = find_tokens(body)["tag"]
        self.result_note = Note(
            body=body,
            title=self.title_edit.text().strip(),
            tags=parse_tags(" ".join(inline)),
            source=self.source,
            destination=self._dest,
        )
        self.accept()
