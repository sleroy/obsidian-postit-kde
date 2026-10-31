import os
import time
from datetime import datetime

import pytest

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.vault import ObsidianVault


@pytest.fixture
def vault(tmp_path):
    vdir = tmp_path / "vault"
    vdir.mkdir()
    return ObsidianVault(Config(vault_path=str(vdir)))


def _set_mtime(path, seconds_ago):
    t = time.time() - seconds_ago
    os.utime(path, (t, t))


def test_recent_empty_when_no_vault(tmp_path):
    v = ObsidianVault(Config(vault_path=str(tmp_path / "missing")))
    assert v.recent_notes() == []


def test_recent_returns_newest_first_limited(vault):
    for i in range(7):
        p = vault.save(
            Note(
                body=f"note {i}",
                destination=Destination.FILE,
                created=datetime(2026, 10, 31, 12, i, 0),
            )
        )
        _set_mtime(p, seconds_ago=(7 - i))  # i=6 is newest
    hits = vault.recent_notes(limit=5)
    assert len(hits) == 5
    assert "note 6" in hits[0].path.read_text(encoding="utf-8")


def test_recent_excludes_diary_file(vault):
    vault.save(
        Note(
            body="daily thing",
            destination=Destination.DAILY,
            created=datetime(2026, 10, 31, 9, 0, 0),
        )
    )
    vault.save(
        Note(
            body="a real note",
            destination=Destination.FILE,
            created=datetime(2026, 10, 31, 9, 5, 0),
        )
    )
    hits = vault.recent_notes()
    assert not any(h.path.name.endswith("-daily-note.md") for h in hits)
    assert any("a real note" in h.path.read_text(encoding="utf-8") for h in hits)


def test_display_title_prefers_heading(vault):
    vault.save(Note(body="x", title="My Heading", destination=Destination.FILE))
    hit = vault.recent_notes()[0]
    assert hit.title == "My Heading"


def test_search_matches_content_with_snippet(vault):
    vault.save(Note(body="the quick brown fox jumps", destination=Destination.FILE))
    vault.save(Note(body="totally unrelated", destination=Destination.FILE))
    hits = vault.search_notes("brown fox")
    assert len(hits) == 1
    assert "brown fox" in hits[0].snippet.lower()


def test_search_matches_filename(vault):
    vault.save(Note(body="body", title="Groceries", destination=Destination.FILE))
    hits = vault.search_notes("groceries")
    assert len(hits) == 1


def test_search_empty_query_returns_nothing(vault):
    vault.save(Note(body="anything", destination=Destination.FILE))
    assert vault.search_notes("   ") == []
