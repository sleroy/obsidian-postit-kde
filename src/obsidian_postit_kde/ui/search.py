"""Search dialog: query the vault and open a matching note."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..vault import NoteHit, ObsidianVault
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
        self.resize(520, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(make_header("Search notes", "Filename and full-text across your vault"))

        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card, 1)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        self.query = QLineEdit()
        self.query.setPlaceholderText("Type to search…")
        self.query.textChanged.connect(self._run)
        self.query.returnPressed.connect(self._open_selected)
        lay.addWidget(self.query)

        self.count = QLabel("")
        self.count.setObjectName("Hint")
        lay.addWidget(self.count)

        self.results = QListWidget()
        self.results.itemActivated.connect(lambda _it: self._open_selected())
        lay.addWidget(self.results, 1)

        # Keyboard: Down from the query box moves into the list.
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

    def _open_selected(self) -> None:
        item = self.results.currentItem()
        if item is None:
            return
        self.chosen_path = Path(item.data(Qt.ItemDataRole.UserRole))
        self.accept()
