import pytest

from obsidian_postit_kde.config import Config
from obsidian_postit_kde.vault import ObsidianVault, VaultError
from obsidian_postit_kde.webclip import WebClipError, _is_blocked_host, fetch_markdown

# ---- SSRF ----------------------------------------------------------------


def test_blocked_hosts():
    assert _is_blocked_host("localhost") is True
    assert _is_blocked_host("127.0.0.1") is True
    assert _is_blocked_host("169.254.169.254") is True  # cloud metadata
    assert _is_blocked_host("10.0.0.5") is True
    assert _is_blocked_host("192.168.1.1") is True


def test_fetch_refuses_internal_url():
    with pytest.raises(WebClipError):
        fetch_markdown("http://127.0.0.1:8080/secret")
    with pytest.raises(WebClipError):
        fetch_markdown("http://169.254.169.254/latest/meta-data/")


# ---- title injection ------------------------------------------------------


def test_clip_url_sanitizes_title(tmp_path, monkeypatch):
    vdir = tmp_path / "v"
    vdir.mkdir()
    vault = ObsidianVault(Config(vault_path=str(vdir)))
    evil = "]] [[Daily/secret #evil **x**"
    monkeypatch.setattr(
        "obsidian_postit_kde.webclip.fetch_markdown",
        lambda url, timeout=20.0: (evil, "body"),
    )
    _note, diary_path = vault.clip_url("https://example.com")
    diary = diary_path.read_text()
    # No injected second wikilink or stray markdown/tag from the title.
    assert "[[Daily/secret" not in diary
    assert "#evil" not in diary
    assert "**x**" not in diary
    assert "Clipped [[" in diary  # the legitimate link remains


# ---- MCP read_note containment -------------------------------------------


def test_mcp_read_note_blocks_traversal(tmp_path, monkeypatch):
    pytest.importorskip("mcp")
    from obsidian_postit_kde import mcp_server

    vdir = tmp_path / "v"
    vdir.mkdir()
    cfg = Config(vault_path=str(vdir))
    monkeypatch.setattr(mcp_server, "_vault", lambda: ObsidianVault(cfg))
    # Rebuild to capture the tool closures bound to our patched _vault.
    server = mcp_server.build_server()
    # Find the read_note handler via the server's tool registry.
    import asyncio

    with pytest.raises((VaultError, Exception)):
        asyncio.run(server.call_tool("read_note", {"path": "/etc/passwd"}))
