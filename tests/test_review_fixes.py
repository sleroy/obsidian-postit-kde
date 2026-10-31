"""Regression tests for findings from the independent review."""

import tomllib
from datetime import datetime

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.vault import _strip_frontmatter


def test_title_with_colon_and_quote_is_quoted_yaml():
    note = Note(body="x", title='Draft: "ideas" & stuff', destination=Destination.FILE)
    md = note.to_file_markdown(default_tags=[])
    # The frontmatter block must stay valid: parse just the YAML part.
    fm = md.split("---")[1]
    import re

    line = next(ln for ln in fm.splitlines() if ln.startswith("title:"))
    assert line == 'title: "Draft: \\"ideas\\" & stuff"'
    assert re.search(r"injected", md) is None


def test_title_with_newline_cannot_inject_frontmatter():
    note = Note(body="body", title="safe\ninjected: true", destination=Destination.FILE)
    md = note.to_file_markdown(default_tags=[])
    # Exactly one closing fence region; 'injected:' must not be its own fm key.
    fm = md.split("---")[1]
    assert "\ninjected: true" not in fm


def test_tag_with_special_char_is_quoted():
    note = Note(body="x", tags=["a]b", "c,d"], destination=Destination.FILE)
    md = note.to_file_markdown(default_tags=[])
    assert 'tags: ["a]b", "c,d"]' in md


def test_toml_roundtrip_with_newline_and_tab(tmp_path):
    path = tmp_path / "c.toml"
    cfg = Config(vault_path="/x", filename_template="a\tb", daily_heading_date="line1\nline2")
    cfg.save(path)
    # Must be readable back by tomllib (would raise if control chars unescaped).
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    assert data["filename_template"] == "a\tb"
    assert data["daily_heading_date"] == "line1\nline2"
    loaded = Config.load(path)
    assert loaded.filename_template == "a\tb"


def test_strip_frontmatter():
    doc = "---\ntitle: X\ntags: [a]\n---\n\nreal body #tag\n"
    assert _strip_frontmatter(doc) == "real body #tag"


def test_strip_frontmatter_none():
    assert _strip_frontmatter("no fm here") == "no fm here"


def test_search_ignores_frontmatter_keys(tmp_path):
    from obsidian_postit_kde.vault import ObsidianVault

    vdir = tmp_path / "v"
    vdir.mkdir()
    v = ObsidianVault(Config(vault_path=str(vdir)))
    v.save(
        Note(
            body="just groceries",
            title="Shopping",
            tags=["source"],
            destination=Destination.FILE,
            created=datetime(2026, 10, 31, 12, 0, 0),
        )
    )
    # "source" appears in frontmatter (source: manual, tags) but not the body.
    hits = v.search_notes("source")
    # Only a filename/body match should count — body has no "source".
    assert all("source" not in h.snippet.lower() or h.snippet == "" for h in hits)
