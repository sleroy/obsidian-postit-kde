"""MCP server — expose the Obsidian vault to AI agents over the Model Context
Protocol (stdio). Tools write/read the same way the GUI and CLI do, by reusing
ObsidianVault, so an agent's note is byte-for-byte what you'd capture by hand.

Run with:  obsidian-postit-kde mcp
Optional dependency: install with  pip install "obsidian-postit-kde[mcp]"
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .note import Destination, Note, parse_tags
from .openrouter import OpenRouterClient, OpenRouterError, has_api_key
from .vault import ObsidianVault, VaultError


def _vault() -> ObsidianVault:
    cfg = Config.load()
    if not cfg.vault_is_valid():
        raise VaultError(
            "No valid Obsidian vault configured. Set vault_path in "
            "~/.config/obsidian-postit-kde/config.toml or via the app Settings."
        )
    return ObsidianVault(cfg)


def _contained_note_path(path: str, vault: ObsidianVault) -> Path:
    """Resolve a note path while refusing reads outside the configured vault."""
    assert vault.config.vault is not None
    target = Path(path).expanduser().resolve()
    root = vault.config.vault.resolve()
    if not target.is_relative_to(root):
        raise VaultError("Refusing to read a path outside the vault.")
    return target


def build_server():  # returns an MCPServer; typed loosely so mcp stays optional
    try:
        from mcp.server.mcpserver import MCPServer
    except ModuleNotFoundError as exc:  # pragma: no cover - import-guard
        raise SystemExit(
            "The 'mcp' package is required for the MCP server. Install it with:\n"
            "  pipx inject obsidian-postit-kde mcp     # or\n"
            '  pip install "obsidian-postit-kde[mcp]"'
        ) from exc

    server = MCPServer("obsidian-postit-kde")

    # ---- tools: write ----------------------------------------------------

    @server.tool(description="Create a standalone note (a sticky post-it) in the vault.")
    def add_note(text: str, title: str = "", tags: str = "") -> str:
        """Write a note to the PostIt/ folder. Returns the created file path."""
        note = Note(
            body=text.strip(),
            title=title.strip(),
            tags=parse_tags(tags),
            source="mcp",
            destination=Destination.FILE,
        )
        return str(_vault().save(note))

    @server.tool(
        description="Append an entry to today's diary. If the entry is just a URL, "
        "it is automatically fetched and clipped into a linked note."
    )
    def add_diary_entry(text: str) -> str:
        """Append an entry under today's date (auto-clips a bare URL)."""
        return str(_vault().add_diary_smart(text.strip()))

    @server.tool(
        description="Fetch a URL, convert it to Markdown, save it as a note, and "
        "link it from today's diary. Returns the note and diary paths."
    )
    def add_diary_link(url: str, tags: str = "") -> dict:
        note_path, diary_path = _vault().clip_url(url, tags=tags)
        return {"note": str(note_path), "diary": str(diary_path)}

    # ---- tools: read -----------------------------------------------------

    @server.tool(description="Search notes by filename and full text; returns matches.")
    def search_notes(query: str, limit: int = 20) -> list[dict]:
        return [
            {"title": h.title, "path": str(h.path), "snippet": h.snippet}
            for h in _vault().search_notes(query, limit=limit)
        ]

    @server.tool(description="List the most recently modified notes.")
    def recent_notes(limit: int = 10) -> list[dict]:
        return [{"title": h.title, "path": str(h.path)} for h in _vault().recent_notes(limit=limit)]

    @server.tool(description="Read a single note file by its path; returns (title, body).")
    def read_note(path: str) -> dict:
        vault = _vault()
        target = _contained_note_path(path, vault)
        title, body = vault.read_display(target)
        return {"title": title, "body": body}

    @server.tool(description="Read the full diary document (the rolling daily journal).")
    def read_diary() -> str:
        return _vault().read_diary()

    @server.tool(
        description="Summarize today's diary entries into one entry using OpenRouter "
        "(requires an API key); returns the summary without modifying the diary."
    )
    def summarize_day() -> str:
        if not has_api_key():
            raise VaultError("No OpenRouter API key configured.")
        vault = _vault()
        from datetime import date

        from .vault import _extract_section

        raw = vault.read_diary()
        heading = f"## {date.today().strftime(vault.config.daily_heading_date)}"
        section = _extract_section(raw, heading).strip()
        if not section:
            return "No entries for today yet."
        try:
            return OpenRouterClient(vault.config.openrouter_model).summarize(
                "Summarize these diary entries into one concise entry, keeping key "
                "facts and #tags:\n\n" + section
            )
        except OpenRouterError as exc:
            raise VaultError(str(exc)) from exc

    # ---- resources: readable content -------------------------------------

    @server.resource(
        "obsidian-postit://diary",
        name="Diary",
        description="The full rolling daily journal document.",
        mime_type="text/markdown",
    )
    def diary_resource() -> str:
        return _vault().read_diary()

    @server.resource(
        "obsidian-postit://recent",
        name="Recent notes",
        description="A list of recent notes (title and path), newest first.",
        mime_type="text/markdown",
    )
    def recent_resource() -> str:
        hits = _vault().recent_notes(limit=20)
        if not hits:
            return "_No notes yet._"
        return "\n".join(f"- [{h.title}]({h.path})" for h in hits)

    return server


def run() -> int:
    build_server().run(transport="stdio")
    return 0
