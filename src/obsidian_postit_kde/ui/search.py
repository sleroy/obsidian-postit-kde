"""Search dialog: query the vault, open a note, or delete notes in place."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ..vault import NoteHit, ObsidianVault, VaultError
from .theme import make_header


class SearchDialog(QDialog):
    def __init__(
        self,
        vault: ObsidianVault,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vault = vault
        self.chosen_path: Path | None = None
        self.setWindowTitle("Search notes")
        self.resize(520, 460)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(make_header("Search notes", "Open with Enter · delete with Del"))

        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card, 1)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        self.query = QLineEdit()
        self.query.setPlaceholderText("Type to search… (empty shows recent notes)")
        self.query.textChanged.connect(self._run)
        self.query.returnPressed.connect(self._open_selected)
        lay.addWidget(self.query)

        self.count = QLabel("")
        self.count.setObjectName("Hint")
        lay.addWidget(self.count)

        self.results = QListWidget()
        self.results.itemActivated.connect(lambda _it: self._open_selected())
        lay.addWidget(self.results, 1)

        hint = QLabel("↵ open    ·    Del delete    ·    Esc close")
        hint.setObjectName("Hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        lay.addWidget(hint)

        # Del removes the selected note (with confirmation), in place.
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self.results).activated.connect(
            self._delete_selected
        )

        self.query.setFocus()
        self._run("")

    def _run(self, _text: str = "") -> None:
        q = self.query.text().strip()
        self.results.clear()
        hits: list[NoteHit] = self.vault.search_notes(q) if q else self.vault.recent_notes(limit=10)
        for hit in hits:
            label = hit.title
            if hit.snippet:
                label += f"\n    {hit.snippet}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(hit.path))
            self.results.addItem(item)
        if q:
            self.count.setText(f"{len(hits)} result(s)")
        else:
            self.count.setText("Recent notes")
        if self.results.count():
            self.results.setCurrentRow(0)

    def _selected_path(self) -> Path | None:
        item = self.results.currentItem()
        return Path(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def _open_selected(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        self.chosen_path = path
        self.accept()

    def _delete_selected(self) -> None:
        path = self._selected_path()
        if path is None:
            return
        resp = QMessageBox.question(
            self,
            "Delete note?",
            f"Delete “{path.name}” permanently? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        try:
            self.vault.delete_note(path)
        except VaultError as exc:
            QMessageBox.warning(self, "Delete failed", str(exc))
            return
        self._run()  # refresh the list in place; dialog stays open
        self.count.setText(f"Deleted {path.name}")
