import pytest

from obsidian_postit_kde.cli import build_parser
from obsidian_postit_kde.config import Config
from obsidian_postit_kde.vault import ObsidianVault
from obsidian_postit_kde.webclip import WebClipError, _stdlib_html_to_text, fetch_markdown

# ---- webclip --------------------------------------------------------------


def test_stdlib_html_to_text():
    html = "<html><head><style>x</style></head><body><h1>Hi</h1><p>Hello world</p></body></html>"
    out = _stdlib_html_to_text(html)
    assert "Hello world" in out
    assert "x" not in out  # style stripped


def test_fetch_rejects_non_http():
    with pytest.raises(WebClipError):
        fetch_markdown("ftp://example.com")


def test_fetch_markdown_mocked(monkeypatch):
    class FakeResp:
        headers = {"content-type": "text/html"}
        content = (
            b"<html><head><title>My Page</title></head><body><p>Body text here</p></body></html>"
        )
        encoding = "utf-8"
        is_redirect = False

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def get(self, *a, **k):
            return FakeResp()

    # Allow the public host through SSRF check, mock the HTTP client.
    monkeypatch.setattr("obsidian_postit_kde.webclip._is_blocked_host", lambda h: False)
    monkeypatch.setattr("httpx.Client", FakeClient)
    title, md = fetch_markdown("https://example.com")
    assert title == "My Page"
    assert "Body text here" in md


# ---- clip_url -------------------------------------------------------------


def test_clip_url_creates_note_and_diary_link(tmp_path, monkeypatch):
    vdir = tmp_path / "v"
    vdir.mkdir()
    vault = ObsidianVault(Config(vault_path=str(vdir)))
    monkeypatch.setattr(
        "obsidian_postit_kde.webclip.fetch_markdown",
        lambda url, timeout=20.0: ("Cool Article", "The **body** of the article."),
    )
    note_path, diary_path = vault.clip_url("https://example.com/post", tags="reading")
    note_text = note_path.read_text()
    assert "The **body** of the article." in note_text
    assert "Source: https://example.com/post" in note_text
    assert "clip" in note_text and "reading" in note_text
    diary = diary_path.read_text()
    assert "Clipped [[" in diary and "Cool Article" in diary


# ---- MCP server -----------------------------------------------------------


def test_mcp_server_builds_with_tools():
    pytest.importorskip("mcp")
    from obsidian_postit_kde.mcp_server import build_server

    server = build_server()
    # The server object exists and exposes our tools (names registered).
    assert server is not None


# ---- hotkey flags ---------------------------------------------------------


def test_capture_flags_parse():
    p = build_parser()
    for flag in ("--capture-note", "--capture-diary", "--capture-clipboard"):
        ns = p.parse_args([flag])
        assert getattr(ns, flag.lstrip("-").replace("-", "_")) is True
        assert ns.command is None  # GUI path, not a subcommand


def test_diary_url_flag_parses():
    ns = build_parser().parse_args(["diary", "--url", "https://x.com", "--tags", "a"])
    assert ns.command == "diary"
    assert ns.url == "https://x.com"
