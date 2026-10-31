import json

from obsidian_postit_kde import mcp_install


def test_install_claude_writes_json(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rc = mcp_install.install("claude")
    assert rc == 0
    cfg = json.loads((tmp_path / "Claude" / "claude_desktop_config.json").read_text())
    assert cfg["mcpServers"]["obsidian-postit"]["args"] == ["mcp"]


def test_install_opencode_merges_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    p = tmp_path / "opencode" / "opencode.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"theme": "dark", "mcp": {"other": {"command": "x"}}}))
    mcp_install.install("opencode")
    cfg = json.loads(p.read_text())
    assert cfg["theme"] == "dark"  # preserved
    assert "other" in cfg["mcp"]  # preserved
    assert cfg["mcp"]["obsidian-postit"]["args"] == ["mcp"]


def test_install_codex_writes_toml(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    mcp_install.install("codex")
    text = (tmp_path / ".codex" / "config.toml").read_text()
    assert "[mcp_servers.obsidian-postit]" in text
    assert 'args = ["mcp"]' in text


def test_install_codex_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    mcp_install.install("codex")
    mcp_install.install("codex")  # second run must not duplicate the block
    text = (tmp_path / ".codex" / "config.toml").read_text()
    assert text.count("[mcp_servers.obsidian-postit]") == 1


def test_install_unknown_agent(capsys):
    rc = mcp_install.install("notanagent")
    assert rc == 2
