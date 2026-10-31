import pytest

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.vault import ObsidianVault
from obsidian_postit_kde.webclip import detect_bare_url


def test_detect_bare_url_plain():
    assert detect_bare_url("https://example.com/a") == ("https://example.com/a", "")


def test_detect_bare_url_with_tags():
    assert detect_bare_url("https://example.com #read #later") == (
        "https://example.com",
        "read later",
    )


def test_detect_mixed_text_is_none():
    assert detect_bare_url("interesting url https://example.com") is None


def test_detect_multiple_urls_is_none():
    assert detect_bare_url("https://a.com https://b.com") is None


def test_detect_no_url_is_none():
    assert detect_bare_url("just a plain thought #idea") is None


@pytest.fixture
def vault(tmp_path):
    vdir = tmp_path / "v"
    vdir.mkdir()
    return ObsidianVault(Config(vault_path=str(vdir)))


def test_smart_plain_text_appends_verbatim(vault):
    vault.add_diary_smart("interesting url https://example.com")
    diary = vault.read_diary()
    assert "interesting url https://example.com" in diary
    assert "Clipped [[" not in diary


def test_smart_bare_url_autoclips(vault, monkeypatch):
    monkeypatch.setattr(
        "obsidian_postit_kde.webclip.fetch_markdown",
        lambda url, timeout=20.0: ("Example Title", "Article **body**."),
    )
    vault.add_diary_smart("https://example.com/post #reading")
    diary = vault.read_diary()
    assert "Clipped [[" in diary and "Example Title" in diary
    notes = list(vault.config.postit_dir().glob("*.md"))
    assert any("Article **body**." in p.read_text() for p in notes)


def test_smart_fallback_on_fetch_failure(vault, monkeypatch):
    from obsidian_postit_kde.webclip import WebClipError

    def boom(url, timeout=20.0):
        raise WebClipError("offline")

    monkeypatch.setattr("obsidian_postit_kde.webclip.fetch_markdown", boom)
    vault.add_diary_smart("https://example.com/down")
    diary = vault.read_diary()
    assert "https://example.com/down" in diary
    assert "Clipped [[" not in diary
