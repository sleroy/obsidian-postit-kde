"""Register the MCP server in AI-agent configs (Claude, opencode, Codex).

Each agent stores MCP servers in a different file/format; this writes the
right entry so `obsidian-postit-kde mcp` is available without hand-editing.
Idempotent: re-running updates the existing entry.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

_SERVER_KEY = "obsidian-postit"


def _config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _command() -> str:
    return shutil.which("obsidian-postit-kde") or "obsidian-postit-kde"


def _json_merge(path: Path, section: str) -> str:
    """Merge our server into a JSON config under `section`. Returns a status line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path} is not valid JSON ({exc}); not touching it.") from exc
    servers = data.setdefault(section, {})
    servers[_SERVER_KEY] = {"command": _command(), "args": ["mcp"]}
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return f"registered '{_SERVER_KEY}' in {path} ({section})"


def _toml_merge_codex(path: Path) -> str:
    """Register our server in Codex's TOML, reading with tomllib to avoid
    corrupting or duplicating tables, then re-emitting the config."""
    import tomllib

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    try:
        data = tomllib.loads(existing) if existing.strip() else {}
    except tomllib.TOMLDecodeError as exc:
        raise SystemExit(f"{path} is not valid TOML ({exc}); not touching it.") from exc

    servers = data.setdefault("mcp_servers", {})
    if not isinstance(servers, dict):
        raise SystemExit(f"{path}: 'mcp_servers' is not a table; refusing to edit.")
    servers[_SERVER_KEY] = {"command": _command(), "args": ["mcp"]}

    text = _emit_toml(data)
    tmp = path.with_suffix(".toml.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return f"registered '{_SERVER_KEY}' in {path} ([mcp_servers.{_SERVER_KEY}])"


def _toml_scalar(v: object) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_scalar(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _emit_toml(data: dict) -> str:
    """Emit a dict as TOML: top-level scalars, then [table] and [a.b] tables."""
    lines: list[str] = []
    scalars = {k: v for k, v in data.items() if not isinstance(v, dict)}
    tables = {k: v for k, v in data.items() if isinstance(v, dict)}
    for k, v in scalars.items():
        lines.append(f"{k} = {_toml_scalar(v)}")
    if scalars:
        lines.append("")
    for name, table in tables.items():
        sub_scalars = {k: v for k, v in table.items() if not isinstance(v, dict)}
        sub_tables = {k: v for k, v in table.items() if isinstance(v, dict)}
        if sub_scalars or not sub_tables:
            lines.append(f"[{name}]")
            for k, v in sub_scalars.items():
                lines.append(f"{k} = {_toml_scalar(v)}")
            lines.append("")
        for sub_name, sub in sub_tables.items():
            lines.append(f"[{name}.{sub_name}]")
            for k, v in sub.items():
                lines.append(f"{k} = {_toml_scalar(v)}")
            lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def install(agent: str) -> int:
    agent = agent.lower()
    try:
        if agent == "claude":
            print(
                _json_merge(_config_home() / "Claude" / "claude_desktop_config.json", "mcpServers")
            )
        elif agent == "opencode":
            print(_json_merge(_config_home() / "opencode" / "opencode.json", "mcp"))
        elif agent == "codex":
            print(_toml_merge_codex(Path.home() / ".codex" / "config.toml"))
        else:
            print(f"Unknown agent '{agent}'. Choose: claude, opencode, codex.")
            return 2
    except OSError as exc:
        print(f"error: {exc}")
        return 1
    print("Restart the agent to pick up the new MCP server.")
    return 0
