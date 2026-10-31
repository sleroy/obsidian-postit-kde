from datetime import datetime

import pytest

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.vault import ObsidianVault, VaultError, _insert_under_heading


@pytest.fixture
def vault(tmp_path):
    vdir = tmp_path / "vault"
    vdir.mkdir()
    return ObsidianVault(Config(vault_path=str(vdir)))


def test_save_invalid_vault_raises(tmp_path):
    v = ObsidianVault(Config(vault_path=str(tmp_path / "missing")))
    with pytest.raises(VaultError):
        v.save(Note(body="x"))


def test_file_note_written(vault):
    note = Note(
        body="Hello",
        title="Buy Milk",
        destination=Destination.FILE,
        created=datetime(2026, 10, 31, 12, 57, 40),
    )
    path = vault.save(note)
    assert path.exists()
    assert path.name == "2026-10-31-125740-buy-milk.md"
    assert "Hello" in path.read_text(encoding="utf-8")


def test_file_note_unique_on_collision(vault):
    ts = datetime(2026, 10, 31, 12, 0, 0)
    # Identical content + timestamp -> same guessed name -> must disambiguate.
    p1 = vault.save(Note(body="same text", destination=Destination.FILE, created=ts))
    p2 = vault.save(Note(body="same text", destination=Destination.FILE, created=ts))
    assert p1 != p2
    assert p2.name.endswith("-2.md")


def test_daily_creates_file_with_header_and_bullet(vault):
    note = Note(body="first", tags=["idea"], created=datetime(2026, 10, 31, 13, 40, 0))
    path = vault.save(note)
    text = path.read_text(encoding="utf-8")
    assert path.name.endswith("-daily-note.md")
    assert "# " in text and "daily note" in text
    assert "## 2026-10-31" in text
    # Diary bullets carry only the user's tags — no default #postit noise.
    assert "- 13:40 first #idea" in text
    assert "#postit" not in text


def test_daily_appends_same_day_under_one_heading(vault):
    vault.save(Note(body="first", created=datetime(2026, 10, 31, 9, 0, 0)))
    path = vault.save(Note(body="second", created=datetime(2026, 10, 31, 10, 0, 0)))
    text = path.read_text(encoding="utf-8")
    assert text.count("## 2026-10-31") == 1
    assert "- 09:00 first" in text
    assert "- 10:00 second" in text
    assert text.index("first") < text.index("second")


def test_daily_new_day_adds_new_heading(vault):
    vault.save(Note(body="day one", created=datetime(2026, 10, 31, 9, 0, 0)))
    path = vault.save(Note(body="day two", created=datetime(2026, 11, 1, 9, 0, 0)))
    text = path.read_text(encoding="utf-8")
    assert "## 2026-10-31" in text
    assert "## 2026-11-01" in text
    assert text.index("2026-10-31") < text.index("2026-11-01")


# ---- pure insert helper --------------------------------------------------


def test_insert_new_heading_when_absent():
    out = _insert_under_heading("# Title\n", "## 2026-10-31", "- a")
    assert out == "# Title\n\n## 2026-10-31\n- a\n"


def test_insert_under_existing_heading():
    content = "# T\n\n## 2026-10-31\n- a\n"
    out = _insert_under_heading(content, "## 2026-10-31", "- b")
    assert out == "# T\n\n## 2026-10-31\n- a\n- b\n"


def test_insert_before_later_section():
    content = "## 2026-10-31\n- a\n\n## 2026-11-01\n- z\n"
    out = _insert_under_heading(content, "## 2026-10-31", "- b")
    lines = out.splitlines()
    assert lines == ["## 2026-10-31", "- a", "- b", "", "## 2026-11-01", "- z"]
