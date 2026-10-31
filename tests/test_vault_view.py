from datetime import date, datetime

import pytest

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.vault import ObsidianVault, _extract_section


@pytest.fixture
def vault(tmp_path):
    vdir = tmp_path / "vault"
    vdir.mkdir()
    return ObsidianVault(Config(vault_path=str(vdir)))


def test_is_daily_identifies_rolling_file(vault):
    p = vault.save(
        Note(body="hi", destination=Destination.DAILY, created=datetime(2026, 10, 31, 9, 0, 0))
    )
    assert vault.is_daily(p) is True


def test_read_display_file_note_strips_frontmatter(vault):
    p = vault.save(Note(body="plain body here", title="Title", destination=Destination.FILE))
    title, md = vault.read_display(p)
    assert title == "Title"
    assert "plain body here" in md
    assert "source:" not in md  # frontmatter removed


def test_read_display_daily_returns_todays_section(vault):
    day = date(2026, 10, 31)
    vault.save(
        Note(
            body="morning note",
            destination=Destination.DAILY,
            created=datetime(2026, 10, 31, 9, 0, 0),
        )
    )
    vault.save(
        Note(
            body="old note", destination=Destination.DAILY, created=datetime(2026, 10, 30, 9, 0, 0)
        )
    )
    p = vault.daily_path()
    title, md = vault.read_display(p, today=day)
    assert "2026-10-31" in title
    assert "morning note" in md
    assert "old note" not in md  # only today's section


def test_read_display_daily_empty_today(vault):
    vault.save(
        Note(
            body="yesterday", destination=Destination.DAILY, created=datetime(2026, 10, 30, 9, 0, 0)
        )
    )
    p = vault.daily_path()
    title, md = vault.read_display(p, today=date(2026, 10, 31))
    assert "No notes yet today" in md


def test_extract_section():
    text = "# T\n\n## 2026-10-31\n- a\n- b\n\n## 2026-11-01\n- c\n"
    assert _extract_section(text, "## 2026-10-31") == "- a\n- b"
    assert _extract_section(text, "## 2026-11-01") == "- c"
    assert _extract_section(text, "## 2099-01-01") == ""
