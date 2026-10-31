from datetime import date, datetime

import pytest

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.vault import ObsidianVault, VaultError


@pytest.fixture
def vault(tmp_path):
    vdir = tmp_path / "v"
    vdir.mkdir()
    return ObsidianVault(Config(vault_path=str(vdir)))


# ---- delete ---------------------------------------------------------------


def test_delete_note_removes_file(vault):
    p = vault.save(Note(body="bye", destination=Destination.FILE))
    assert p.exists()
    vault.delete_note(p)
    assert not p.exists()


def test_delete_missing_is_ok(vault, tmp_path):
    vault.delete_note(tmp_path / "v" / "PostIt" / "nope.md")  # no raise


def test_delete_refuses_diary(vault):
    p = vault.save(Note(body="entry", destination=Destination.DAILY))
    with pytest.raises(VaultError):
        vault.delete_note(p)
    assert p.exists()  # diary untouched


# ---- diary ----------------------------------------------------------------


def test_read_diary_creates_header_when_empty(vault):
    text = vault.read_diary()
    assert "daily note" in text
    assert text.startswith("---")


def test_append_diary_entry_adds_bullet(vault):
    vault.append_diary_entry("bought milk #shopping")
    text = vault.read_diary()
    assert "bought milk #shopping" in text
    assert "## " in text  # a date heading exists


def test_append_diary_entry_empty_raises(vault):
    with pytest.raises(VaultError):
        vault.append_diary_entry("   ")


def test_write_diary_free_edit(vault):
    vault.append_diary_entry("original", when=date(2026, 10, 31))
    prev = vault.read_diary()
    edited = prev + "\n- 23:59 added by free edit #late\n"
    vault.write_diary(edited, expected_prev=prev)
    assert "added by free edit #late" in vault.read_diary()


def test_write_diary_guard_rejects_external_change(vault):
    vault.append_diary_entry("original", when=date(2026, 10, 31))
    stale = "stale snapshot that no longer matches disk"
    with pytest.raises(VaultError):
        vault.write_diary("whatever", expected_prev=stale)


def test_append_diary_groups_same_day(vault):
    day = date(2026, 10, 31)
    vault.append_diary_entry("first", when=day)
    vault.append_diary_entry("second", when=day)
    text = vault.read_diary()
    assert text.count(f"## {day.strftime('%Y-%m-%d')}") == 1
    assert "first" in text and "second" in text


# ---- search/recent exclude diary -----------------------------------------


def test_search_excludes_diary(vault):
    vault.append_diary_entry("secret diary word zebra", when=date(2026, 10, 31))
    vault.save(
        Note(
            body="a note with zebra too",
            destination=Destination.FILE,
            created=datetime(2026, 10, 31, 10, 0, 0),
        )
    )
    hits = vault.search_notes("zebra")
    assert len(hits) == 1
    assert not hits[0].path.name.endswith("-daily-note.md")
