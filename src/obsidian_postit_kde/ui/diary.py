"""Diary window — read and append to the rolling daily journal.

A continuous document (one per device): shows the whole diary, scrolled to
today, with an input box to append a timestamped entry. Page Up / Page Down
jump between ``## date`` sections. Non-modal so the tray stays responsive.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..vault import ObsidianVault, VaultError
from . import app_icon
from .theme import STYLESHEET, make_header


class DiaryWindow(QWidget):
    """Top-level window (not a modal dialog) for the daily journal."""

    def __init__(self, vault: ObsidianVault, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self.setWindowTitle("Diary")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(STYLESHEET)
        self.resize(560, 640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(make_header("Diary", "Your daily journal — newest at the bottom"))

        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card, 1)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        self.doc = QTextBrowser()
        self.doc.setOpenExternalLinks(True)
        lay.addWidget(self.doc, 1)

        # Jump controls + hint
        nav = QHBoxLayout()
        self.prev_btn = QPushButton("↑ Prev day")
        self.next_btn = QPushButton("↓ Next day")
        self.prev_btn.clicked.connect(lambda: self._jump_section(-1))
        self.next_btn.clicked.connect(lambda: self._jump_section(+1))
        hint = QLabel("PgUp / PgDn jump between days")
        hint.setObjectName("Hint")
        nav.addWidget(self.prev_btn)
        nav.addWidget(self.next_btn)
        nav.addStretch(1)
        nav.addWidget(hint)
        lay.addLayout(nav)

        # Append-entry box
        entry_row = QHBoxLayout()
        self.entry = QPlainTextEdit()
        self.entry.setObjectName("PostitBody")
        self.entry.setPlaceholderText("New diary entry…  Ctrl+Enter to add  ·  use #tags inline")
        self.entry.setFixedHeight(70)
        add = QPushButton("Add entry")
        add.setObjectName("Primary")
        add.clicked.connect(self._add_entry)
        entry_row.addWidget(self.entry, 1)
        entry_row.addWidget(add, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(entry_row)

        # Shortcuts
        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(seq), self).activated.connect(self._add_entry)
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self).activated.connect(
            lambda: self._jump_section(-1)
        )
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self).activated.connect(
            lambda: self._jump_section(+1)
        )

        self._reload(scroll_to_end=True)
        self.entry.setFocus()

    # ---- data -------------------------------------------------------------

    def _reload(self, scroll_to_end: bool = False) -> None:
        try:
            markdown = self.vault.read_diary()
        except VaultError as exc:
            self.doc.setPlainText(str(exc))
            return
        self.doc.setMarkdown(markdown)
        if scroll_to_end:
            self.doc.moveCursor(QTextCursor.MoveOperation.End)
            sb = self.doc.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _add_entry(self) -> None:
        text = self.entry.toPlainText().strip()
        if not text:
            return
        try:
            self.vault.append_diary_entry(text)
        except VaultError:
            return
        self.entry.clear()
        self._reload(scroll_to_end=True)
        self.entry.setFocus()

    # ---- navigation -------------------------------------------------------

    def _heading_blocks(self) -> list[int]:
        """Block numbers of the rendered heading lines (## date -> H2)."""
        blocks: list[int] = []
        doc = self.doc.document()
        for i in range(doc.blockCount()):
            block = doc.findBlockByNumber(i)
            # Rendered Markdown headings carry a larger font / heading level.
            fmt = block.blockFormat()
            if fmt.headingLevel() in (1, 2):
                blocks.append(i)
        return blocks

    def _jump_section(self, direction: int) -> None:
        blocks = self._heading_blocks()
        if not blocks:
            return
        doc = self.doc.document()
        cur_block = self.doc.textCursor().blockNumber()
        target = None
        if direction < 0:
            for b in reversed(blocks):
                if b < cur_block:
                    target = b
                    break
            target = target if target is not None else blocks[0]
        else:
            for b in blocks:
                if b > cur_block:
                    target = b
                    break
            target = target if target is not None else blocks[-1]
        cursor = QTextCursor(doc.findBlockByNumber(target))
        self.doc.setTextCursor(cursor)
        self.doc.ensureCursorVisible()
