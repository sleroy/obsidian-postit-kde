from datetime import date, datetime, timedelta

from PySide6.QtCore import QUrl

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.ui.diary import DiaryWindow, _entry_html, _first_h1, _replace_section
from obsidian_postit_kde.vault import ObsidianVault


def test_first_h1_skips_frontmatter():
    md = "---\ndevice: x\n---\n\n# my-device — daily note\n\n## 2026-10-31\n- a\n"
    assert _first_h1(md) == "my-device — daily note"


def test_replace_section_replaces_only_target():
    doc = "# T\n\n## 2026-10-31\n- a\n- b\n\n## 2026-11-01\n- c\n"
    out = _replace_section(doc, "## 2026-10-31", "summarized single entry")
    assert "summarized single entry" in out
    assert "- a" not in out and "- b" not in out
    assert "## 2026-11-01" in out and "- c" in out  # other day preserved


def test_replace_section_appends_when_absent():
    doc = "# T\n\n## 2026-10-31\n- a\n"
    out = _replace_section(doc, "## 2099-01-01", "new day entry")
    assert "## 2099-01-01" in out
    assert "new day entry" in out
    assert "- a" in out  # original kept


def test_diary_shows_one_day_and_navigation_uses_day_sections(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    vault = ObsidianVault(Config(vault_path=str(root)))
    yesterday = date.today() - timedelta(days=1)
    vault.save(
        Note(
            body="older entry",
            destination=Destination.DAILY,
            created=datetime.combine(yesterday, datetime.min.time()),
        )
    )
    vault.save(Note(body="today entry", destination=Destination.DAILY))

    window = DiaryWindow(vault)
    assert "today entry" in window.doc.toPlainText()
    assert "older entry" not in window.doc.toPlainText()
    window.prev_btn.click()
    assert "older entry" in window.doc.toPlainText()
    assert "today entry" not in window.doc.toPlainText()
    window.next_btn.click()
    assert "today entry" in window.doc.toPlainText()
    window.close()


def test_clipped_wikilink_opens_postit_and_escapes_title(tmp_path):
    root = tmp_path / "vault"
    root.mkdir()
    vault = ObsidianVault(Config(vault_path=str(root)))
    path = vault.save(Note(body="article", title="A & B", destination=Destination.FILE))
    opened = []
    window = DiaryWindow(vault, on_open_note=opened.append)
    rendered = _entry_html(f"- 16:00 Clipped [[{path.stem}]] — A & B #clip", 15)
    assert f"postit:{path.stem}" in rendered
    assert "A &amp; B" in rendered
    window.doc.anchorClicked.emit(QUrl(f"postit:{path.stem}"))
    assert opened == [path.stem]
    assert vault.find_note_by_stem(opened[0]) == path
    assert vault.find_note_by_stem("../outside") is None
    window.close()
