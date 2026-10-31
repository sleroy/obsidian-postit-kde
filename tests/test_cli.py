import io

import pytest

from obsidian_postit_kde.cli import build_parser, run_cli
from obsidian_postit_kde.config import Config


@pytest.fixture
def vault_cfg(tmp_path, monkeypatch):
    vdir = tmp_path / "vault"
    vdir.mkdir()
    cfg = Config(vault_path=str(vdir))
    # Make cli's Config.load() return our temp config regardless of XDG.
    monkeypatch.setattr("obsidian_postit_kde.cli.Config.load", staticmethod(lambda: cfg))
    return vdir


def _run(argv):
    return run_cli(build_parser().parse_args(argv))


def test_add_note(vault_cfg, capsys):
    rc = _run(["add", "buy milk #errand", "-t", "Groceries"])
    out = capsys.readouterr().out.strip()
    assert rc == 0
    assert out.endswith(".md")
    assert "buy milk #errand" in (vault_cfg / "PostIt").glob("*.md").__next__().read_text()


def test_add_with_tags(vault_cfg, capsys):
    _run(["add", "a thought", "--tags", "idea, work"])
    text = next((vault_cfg / "PostIt").glob("*.md")).read_text()
    assert "idea" in text and "work" in text


def test_diary_entry(vault_cfg, capsys):
    rc = _run(["diary", "went for a run #health"])
    assert rc == 0
    daily = next((vault_cfg / "Daily").glob("*-daily-note.md")).read_text()
    assert "went for a run #health" in daily
    assert "## " in daily


def test_add_from_stdin(vault_cfg, capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("piped note #x"))
    rc = _run(["add", "-"])
    assert rc == 0
    assert "piped note #x" in next((vault_cfg / "PostIt").glob("*.md")).read_text()


def test_recent_and_search(vault_cfg, capsys):
    _run(["add", "alpha note about kiwi", "-t", "Alpha"])
    _run(["add", "beta note", "-t", "Beta"])
    capsys.readouterr()  # clear
    _run(["recent", "-n", "5"])
    recent_out = capsys.readouterr().out
    assert "Alpha" in recent_out and "Beta" in recent_out
    rc = _run(["search", "kiwi"])
    search_out = capsys.readouterr().out
    assert rc == 0
    assert "Alpha" in search_out


def test_no_vault_errors(monkeypatch, capsys):
    monkeypatch.setattr("obsidian_postit_kde.cli.Config.load", staticmethod(Config))
    rc = _run(["add", "x"])
    assert rc == 1
    assert "vault" in capsys.readouterr().err.lower()
