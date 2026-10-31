"""Lightweight syntax highlighter for the sticky-note body editor.

Highlights the handful of Markdown/Obsidian tokens that matter for quick
notes: #tags, [[wikilinks]], **bold**, *italic* and `inline code`. Tuned for
dark ink on yellow paper.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import (
    QColor,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)


def _fmt(
    color: str, *, bold: bool = False, italic: bool = False, mono: bool = False
) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(700)
    if italic:
        f.setFontItalic(True)
    if mono:
        f.setFontFamilies(["monospace"])
    return f


class MarkdownHighlighter(QSyntaxHighlighter):
    """Applies inline formatting to #tags, [[links]], **bold**, *italic*, `code`."""

    # (pattern, format) — order matters; code last so it can sit visually apart.
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(r"(?<!\w)#[\w/-]+"), _fmt("#b45309", bold=True)),  # #tag amber
            (QRegularExpression(r"\[\[[^\]]+\]\]"), _fmt("#1d4ed8", bold=True)),  # [[link]] blue
            (QRegularExpression(r"\*\*[^*]+\*\*"), _fmt("#3f3a1e", bold=True)),  # **bold**
            (QRegularExpression(r"(?<!\*)\*(?!\*)[^*\n]+\*(?!\*)"), _fmt("#3f3a1e", italic=True)),
            (QRegularExpression(r"`[^`\n]+`"), _fmt("#9d174d", mono=True)),  # `code` pink
        ]

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt override)
        for pattern, fmt in self._rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


# Pure helper (unit-testable without Qt rendering): which tokens a line holds.
_TOKEN_RE = {
    "tag": re.compile(r"(?<!\w)#[\w/-]+"),
    "link": re.compile(r"\[\[[^\]]+\]\]"),
    "bold": re.compile(r"\*\*[^*]+\*\*"),
    "code": re.compile(r"`[^`\n]+`"),
}


def find_tokens(text: str) -> dict[str, list[str]]:
    """Return the matched tokens per kind. Used by tests and by tag extraction."""
    return {kind: rx.findall(text) for kind, rx in _TOKEN_RE.items()}
