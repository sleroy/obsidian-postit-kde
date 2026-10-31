"""View an existing note inside the app (sticky-note styled, read view)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QTextBrowser,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .theme import POSTIT_STYLESHEET


class ViewDialog(QDialog):
    """Read-only sticky note for an existing file, rendered as Markdown."""

    def __init__(
        self, path: Path, title: str, markdown: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.path = path
        self._drag_offset: QPoint | None = None

        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(POSTIT_STYLESHEET)
        self.resize(360, 320)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 14)

        paper = QFrame()
        paper.setObjectName("Paper")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 120))
        paper.setGraphicsEffect(shadow)
        root.addWidget(paper)

        lay = QVBoxLayout(paper)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        heading = QLabel(title)
        heading.setObjectName("PostitTitle")
        lay.addWidget(heading)

        self.view = QTextBrowser()
        self.view.setObjectName("PostitBody")
        self.view.setOpenExternalLinks(True)
        self.view.setMarkdown(markdown)
        lay.addWidget(self.view, 1)

        footer = QWidget()
        footer.setObjectName("PostitFooter")
        frow = QHBoxLayout(footer)
        frow.setContentsMargins(0, 0, 0, 0)
        name = QLabel(path.name)
        name.setObjectName("Hint")
        frow.addWidget(name)
        frow.addStretch(1)

        open_ext = QToolButton()
        open_ext.setText("Open in editor")
        open_ext.setToolTip("Open the file in your default Markdown app (e.g. Obsidian)")
        open_ext.clicked.connect(self._open_external)
        close = QToolButton()
        close.setObjectName("PostitSave")
        close.setText("Close")
        close.clicked.connect(self.accept)
        frow.addWidget(open_ext)
        frow.addWidget(close)
        lay.addWidget(footer)

    def _open_external(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.path)))
        self.accept()

    # drag to move (frameless)
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
