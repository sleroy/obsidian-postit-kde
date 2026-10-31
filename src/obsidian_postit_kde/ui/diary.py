"""Diary window — read, append to, and edit the rolling daily journal.

A continuous document (one per device). Shows the whole diary scrolled to
today, with an input box to append a timestamped entry, per-day copy, and two
edit modes: edit today's section, or free-edit the whole document. Page Up /
Page Down jump between ``## date`` sections. Esc closes. Non-modal.
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..openrouter import OpenRouterClient, has_api_key
from ..vault import ObsidianVault, VaultError, _extract_section, _strip_frontmatter
from . import app_icon
from .ai_worker import AiTask, BgTask
from .theme import STYLESHEET, make_header


class DiaryWindow(QWidget):
    """Top-level window (not a modal dialog) for the daily journal."""

    def __init__(self, vault: ObsidianVault, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vault = vault
        self._editing = False
        self._edit_scope = "doc"  # "doc" (whole file) or "today" (section)
        self._loaded_raw = ""
        self._ai_task: AiTask | None = None
        self._clip_task: BgTask | None = None
        self._font_px = getattr(vault.config, "diary_font_px", 15)
        self.setWindowTitle("Diary")
        self.setWindowIcon(app_icon())
        self.setStyleSheet(STYLESHEET)
        self.resize(600, 680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # Header text is set from the diary's own H1 in _reload().
        self.header = make_header("Diary", "")
        outer.addWidget(self.header)
        self._header_title = self.header.findChild(QLabel, "HeaderTitle")
        self._header_sub = self.header.findChild(QLabel, "HeaderSubtitle")

        card = QFrame()
        card.setObjectName("Card")
        outer.addWidget(card, 1)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        self.doc = QTextBrowser()
        self.doc.setObjectName("PaperDoc")
        self.doc.setOpenExternalLinks(True)
        lay.addWidget(self.doc, 1)

        self.editor = QPlainTextEdit()
        self.editor.setObjectName("PaperEdit")
        self.editor.setStyleSheet(f"font-size: {self._font_px}px;")
        self.editor.hide()
        lay.addWidget(self.editor, 1)

        # Toolbar
        bar = QHBoxLayout()
        self.prev_btn = QPushButton("↑ Prev day")
        self.next_btn = QPushButton("↓ Next day")
        self.prev_btn.clicked.connect(lambda: self._jump_section(-1))
        self.next_btn.clicked.connect(lambda: self._jump_section(+1))
        self.copy_today_btn = QPushButton("📋 Copy today")
        self.copy_today_btn.setToolTip("Copy today's entries to the clipboard")
        self.copy_today_btn.clicked.connect(self._copy_today)
        self.edit_today_btn = QPushButton("✎ Edit today")
        self.edit_today_btn.setCheckable(True)
        self.edit_today_btn.setToolTip("Edit the whole of today's section")
        self.edit_today_btn.clicked.connect(lambda: self._toggle_edit("today"))
        self.edit_doc_btn = QPushButton("✎ Edit all")
        self.edit_doc_btn.setCheckable(True)
        self.edit_doc_btn.setToolTip("Free-edit the entire diary document")
        self.edit_doc_btn.clicked.connect(lambda: self._toggle_edit("doc"))
        self.summarize_btn = QPushButton("✦ Summarize day")
        self.summarize_btn.setToolTip(
            "Rewrite all of today's entries into one consolidated entry (OpenRouter)"
        )
        self.summarize_btn.clicked.connect(self._summarize_day)
        if not has_api_key():
            self.summarize_btn.setEnabled(False)
            self.summarize_btn.setToolTip("Add an OpenRouter key in Settings to enable.")
        for b in (
            self.prev_btn,
            self.next_btn,
            self.copy_today_btn,
            self.edit_today_btn,
            self.edit_doc_btn,
            self.summarize_btn,
        ):
            bar.addWidget(b)
        bar.addStretch(1)
        self.hint = QLabel("PgUp/PgDn: days · Esc: close")
        self.hint.setObjectName("Hint")
        bar.addWidget(self.hint)
        lay.addLayout(bar)

        # Append-entry box
        entry_row = QHBoxLayout()
        self.entry = QPlainTextEdit()
        self.entry.setObjectName("PaperEdit")
        self.entry.setStyleSheet(f"font-size: {self._font_px}px;")
        self.entry.setPlaceholderText("New entry…  Ctrl+Enter to add  ·  #tags inline")
        self.entry.setFixedHeight(76)
        add = QPushButton("Add entry")
        add.setObjectName("Primary")
        add.clicked.connect(self._add_entry)
        entry_row.addWidget(self.entry, 1)
        entry_row.addWidget(add, 0, Qt.AlignmentFlag.AlignBottom)
        self.entry_container = QWidget()
        self.entry_container.setLayout(entry_row)
        lay.addWidget(self.entry_container)

        # Save/cancel bar for edit modes
        self.save_bar = QWidget()
        sbrow = QHBoxLayout(self.save_bar)
        sbrow.setContentsMargins(0, 0, 0, 0)
        self.edit_label = QLabel("")
        self.edit_label.setObjectName("Hint")
        sbrow.addWidget(self.edit_label)
        sbrow.addStretch(1)
        cancel = QPushButton("← Back to view")
        cancel.setToolTip("Discard changes and return to reading")
        cancel.clicked.connect(self._exit_edit)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._save_edit)
        sbrow.addWidget(cancel)
        sbrow.addWidget(self.save_btn)
        self.save_bar.hide()
        lay.addWidget(self.save_bar)

        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self._add_entry)
        QShortcut(QKeySequence("Ctrl+Enter"), self).activated.connect(self._add_entry)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(self._on_escape)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(self.close)
        QShortcut(QKeySequence(Qt.Key.Key_PageUp), self).activated.connect(
            lambda: self._jump_section(-1)
        )
        QShortcut(QKeySequence(Qt.Key.Key_PageDown), self).activated.connect(
            lambda: self._jump_section(+1)
        )

        self._reload(scroll_to_end=True)
        self.entry.setFocus()

    # ---- data -------------------------------------------------------------

    def _today_heading(self) -> str:
        return f"## {date.today().strftime(self.vault.config.daily_heading_date)}"

    def _reload(self, scroll_to_end: bool = False) -> None:
        try:
            markdown = self.vault.read_diary()
        except VaultError as exc:
            self.doc.setPlainText(str(exc))
            return
        self._loaded_raw = markdown
        self.doc.setHtml(
            _render_diary_html(markdown, self._font_px, self.vault.config.daily_heading_date)
        )
        # Friendly header: the day, not the hostname.
        today = date.today()
        if self._header_title is not None:
            self._header_title.setText(today.strftime("📔  %A, %d %B"))
        if self._header_sub is not None:
            dev = _first_h1(markdown).replace(" — daily note", "")
            self._header_sub.setText(f"Journal · {dev}")
        self.setWindowTitle(today.strftime("Diary — %A %d %B"))
        if scroll_to_end:
            self.doc.moveCursor(QTextCursor.MoveOperation.End)
            sb = self.doc.verticalScrollBar()
            sb.setValue(sb.maximum())

    def _copy_today(self) -> None:
        section = _extract_section(self._loaded_raw, self._today_heading())
        clip = QGuiApplication.clipboard()
        if clip is not None:
            clip.setText(section or "")
        self.hint.setText("Copied today ✓")

    # ---- AI: summarize the whole day into one entry -----------------------

    def _summarize_day(self) -> None:
        section = _extract_section(self._loaded_raw, self._today_heading()).strip()
        if not section:
            QMessageBox.information(self, "Nothing to summarize", "No entries for today yet.")
            return
        resp = QMessageBox.question(
            self,
            "Summarize today?",
            "Rewrite all of today's entries into one consolidated entry?\n"
            "This replaces today's section (you can undo via Edit all).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp != QMessageBox.StandardButton.Yes:
            return
        self.summarize_btn.setEnabled(False)
        self.summarize_btn.setText("⏳ Summarizing…")

        def run(client: OpenRouterClient, text: str) -> str:
            prompt = (
                "These are my diary entries for one day, each a timestamped bullet. "
                "Rewrite them into a single concise diary entry (a short paragraph "
                "or a few bullets), preserving key facts and any #tags. "
                "Return only the rewritten entry:\n\n" + text
            )
            return client.summarize(prompt)

        self._ai_task = AiTask(
            run,
            OpenRouterClient(self.vault.config.openrouter_model),
            section,
            on_done=self._summary_done,
            on_failed=self._summary_failed,
        )
        self._ai_task.start()

    def _summary_done(self, summary: str) -> None:
        # Replace today's section with a single summarized entry.
        bullet = summary.strip()
        merged = _replace_section(self._loaded_raw, self._today_heading(), bullet)
        try:
            self.vault.write_diary(merged, expected_prev=self._loaded_raw)
        except VaultError as exc:
            QMessageBox.warning(self, "Could not save summary", str(exc))
        self._summary_reset()
        self._reload(scroll_to_end=True)

    def _summary_failed(self, message: str) -> None:
        QMessageBox.warning(self, "OpenRouter error", message)
        self._summary_reset()

    def _summary_reset(self) -> None:
        self.summarize_btn.setEnabled(has_api_key())
        self.summarize_btn.setText("✦ Summarize day")
        self._ai_task = None

    # ---- edit modes -------------------------------------------------------

    def _on_escape(self) -> None:
        """Esc exits edit mode if editing, otherwise closes the window."""
        if self._editing:
            self._exit_edit()
        else:
            self.close()

    def _toggle_edit(self, scope: str) -> None:
        """Enter edit for `scope`, or return to view if already editing it."""
        if self._editing and self._edit_scope == scope:
            self._exit_edit()
            return
        self._enter_edit(scope)

    def _enter_edit(self, scope: str) -> None:
        self._editing = True
        self._edit_scope = scope
        if scope == "today":
            self.editor.setPlainText(_extract_section(self._loaded_raw, self._today_heading()))
            self.edit_label.setText("Editing today's section — click “Edit today” again to cancel")
        else:
            self.editor.setPlainText(self._loaded_raw)
            self.edit_label.setText("Editing the whole diary — click “Edit all” again to cancel")
        # Reflect state on the toggles; only the active one stays checked.
        self.edit_today_btn.setChecked(scope == "today")
        self.edit_doc_btn.setChecked(scope == "doc")
        # Disable actions that don't make sense mid-edit.
        for b in (self.prev_btn, self.next_btn, self.copy_today_btn, self.summarize_btn):
            b.setEnabled(False)
        self.doc.hide()
        self.editor.show()
        self.entry_container.hide()
        self.save_bar.show()
        self.editor.setFocus()

    def _exit_edit(self) -> None:
        self._editing = False
        self.edit_today_btn.setChecked(False)
        self.edit_doc_btn.setChecked(False)
        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.copy_today_btn.setEnabled(True)
        self.summarize_btn.setEnabled(has_api_key())
        self.editor.hide()
        self.doc.show()
        self.entry_container.show()
        self.save_bar.hide()
        self._reload()

    def _save_edit(self) -> None:
        new_text = self.editor.toPlainText()
        try:
            if self._edit_scope == "today":
                merged = _replace_section(self._loaded_raw, self._today_heading(), new_text)
                self.vault.write_diary(merged, expected_prev=self._loaded_raw)
            else:
                self.vault.write_diary(new_text, expected_prev=self._loaded_raw)
        except VaultError as exc:
            QMessageBox.warning(self, "Could not save diary", str(exc))
            return
        self._exit_edit()
        self._reload(scroll_to_end=True)

    # ---- append -----------------------------------------------------------

    def _add_entry(self) -> None:
        if self._editing:
            return
        if self._clip_task is not None:
            return  # a clip is already in flight — ignore re-triggers
        text = self.entry.toPlainText().strip()
        if not text:
            return

        from ..webclip import detect_bare_url

        if detect_bare_url(text) is not None:
            # Bare URL: clip off the UI thread so the window never freezes.
            self.hint.setText("Clipping…")
            self.entry.setEnabled(False)
            vault = self.vault

            def work() -> object:
                return vault.add_diary_smart(text)

            self._clip_task = BgTask(work, on_done=self._clip_done, on_failed=self._clip_failed)
            self._clip_task.start()
            return

        # Plain entry: cheap, do it inline.
        try:
            self.vault.append_diary_entry(text)
        except VaultError:
            return
        self.entry.clear()
        self._reload(scroll_to_end=True)
        self.entry.setFocus()

    def _clip_done(self, _path: object) -> None:
        self._clip_task = None
        self.entry.setEnabled(True)
        self.entry.clear()
        self.hint.setText("Clipped ✓")
        self._reload(scroll_to_end=True)
        self.entry.setFocus()

    def _clip_failed(self, _msg: object) -> None:
        # Safe fallback already stored the text in add_diary_smart; recover UI
        # and clear the box so the user doesn't re-add the same URL.
        self._clip_task = None
        self.entry.setEnabled(True)
        self.entry.clear()
        self.hint.setText("Saved (clip failed)")
        self._reload(scroll_to_end=True)
        self.entry.setFocus()

    # ---- navigation -------------------------------------------------------

    def _jump_section(self, direction: int) -> None:
        import re

        doc = self.doc.document()
        # Day dividers are uppercase date labels (e.g. "TODAY · …", a weekday,
        # or a raw date). Match blocks that look like a day label.
        day_re = re.compile(
            r"^(today|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
            r"|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|\d{4}-\d{2})",
            re.IGNORECASE,
        )
        blocks = [
            i
            for i in range(doc.blockCount())
            if day_re.match(doc.findBlockByNumber(i).text().strip())
        ]
        if not blocks:
            return
        cur = self.doc.textCursor().blockNumber()
        if direction < 0:
            target = next((b for b in reversed(blocks) if b < cur), blocks[0])
        else:
            target = next((b for b in blocks if b > cur), blocks[-1])
        self.doc.setTextCursor(QTextCursor(doc.findBlockByNumber(target)))
        self.doc.ensureCursorVisible()


# ---- helpers --------------------------------------------------------------


def _first_h1(markdown: str) -> str:
    for line in _strip_frontmatter(markdown).splitlines():
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return ""


def _replace_section(doc: str, heading: str, new_body: str) -> str:
    """Replace the body under `heading` with `new_body`, preserving the rest.

    If the heading is absent, appends the heading + body at the end.
    """
    lines = doc.splitlines()
    try:
        idx = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration:
        tail = doc.rstrip("\n")
        return f"{tail}\n\n{heading}\n{new_body.strip()}\n"
    end = len(lines)
    for i in range(idx + 1, len(lines)):
        if lines[i].strip().startswith("## "):
            end = i
            break
    rebuilt = lines[: idx + 1] + new_body.strip("\n").splitlines() + [""] + lines[end:]
    return "\n".join(rebuilt).rstrip("\n") + "\n"


def _parse_days(markdown: str) -> list[tuple[str, list[str]]]:
    """Parse the diary body into [(date_heading_text, [entry_lines])], newest last."""
    body = _strip_frontmatter(markdown)
    days: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for line in body.splitlines():
        s = line.rstrip()
        if s.startswith("## "):
            current = (s[3:].strip(), [])
            days.append(current)
        elif current is not None and s.strip():
            current[1].append(s)
    return days


def _entry_html(line: str, font_px: int) -> str:
    """Render one diary bullet as a row: quiet inline time + text + tag chips."""
    import html
    import re

    text = line.lstrip().lstrip("-").strip()
    time = ""
    m = re.match(r"^(\d{1,2}:\d{2})\s+(.*)$", text)
    if m:
        time, text = m.group(1), m.group(2)
    tags = re.findall(r"(?<!\w)#([\w/-]+)", text)
    text_wo = re.sub(r"(?<!\w)#[\w/-]+", "", text).strip()
    body = html.escape(text_wo) or "&nbsp;"
    body = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", body)
    body = re.sub(r"`(.+?)`", r"<code>\1</code>", body)
    chips = "".join(
        f'&nbsp;<span style="background:#ede9fe;color:#6d28d9;border-radius:8px;'
        f'padding:1px 7px;font-size:{font_px - 3}px;">#{html.escape(t)}</span>'
        for t in tags
    )
    time_html = (
        f'<span style="color:#9a97a8;font-size:{font_px - 3}px;">{time}&nbsp;&nbsp;</span>'
        if time
        else ""
    )
    return (
        f'<p style="margin:0 0 7px 0;font-size:{font_px}px;color:#2b2b33;line-height:1.45;">'
        f"{time_html}{body}{chips}</p>"
    )


def _friendly_date(heading: str, date_fmt: str) -> str:
    """Turn a '2026-10-31' heading into 'Saturday, 31 October' when parseable."""
    from datetime import datetime

    try:
        d = datetime.strptime(heading, date_fmt).date()
    except ValueError:
        return heading
    today = date.today()
    if d == today:
        return "Today · " + d.strftime("%A %d %B")
    return d.strftime("%A, %d %B %Y")


def _render_diary_html(markdown: str, font_px: int = 15, date_fmt: str = "%Y-%m-%d") -> str:
    days = _parse_days(markdown)
    sections = []
    for i, (heading, entries) in enumerate(days):
        rows = (
            "".join(_entry_html(e, font_px) for e in entries)
            if entries
            else (
                f'<p style="color:#b9b5c6;font-style:italic;font-size:{font_px - 1}px;margin:0;">'
                "Nothing yet — write your first entry below.</p>"
            )
        )
        # Quiet date divider: a thin top rule + small muted uppercase label,
        # not a big heading. First day has no top margin/rule.
        rule = "" if i == 0 else "border-top:1px solid #ece9f6;padding-top:12px;"
        top = "0" if i == 0 else "16px"
        label = _friendly_date(heading, date_fmt)
        sections.append(
            f'<p style="margin:{top} 0 7px 0;{rule}font-size:{font_px - 4}px;'
            f'color:#9a97a8;letter-spacing:1px;text-transform:uppercase;">{label}</p>{rows}'
        )
    if not days:
        sections.append(
            '<p style="color:#b9b5c6;font-style:italic;">Your journal is empty. '
            "Write your first entry below.</p>"
        )
    return '<div style="font-family:sans-serif;">' + "".join(sections) + "</div>"
