"""Headless CLI: write the same notes/diary entries as the GUI, no display needed.

All commands reuse ObsidianVault, so a note captured from the terminal is
byte-for-byte what the tray app would write. Safe to call from scripts, git
hooks, cron or over SSH — it never imports Qt.
"""

from __future__ import annotations

import argparse
import sys

from .config import Config
from .note import Destination, Note, parse_tags
from .vault import ObsidianVault, VaultError


def _read_text(value: str | None) -> str:
    """Return the note text: the given value, or stdin when value is '-' / absent."""
    if value and value != "-":
        return value
    if not sys.stdin.isatty():
        return sys.stdin.read()
    return ""


def _require_vault(cfg: Config) -> ObsidianVault:
    if not cfg.vault_is_valid():
        raise VaultError(
            "No valid Obsidian vault configured. Set it in the app Settings, "
            "or edit ~/.config/obsidian-postit-kde/config.toml (vault_path)."
        )
    return ObsidianVault(cfg)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obsidian-postit-kde",
        description="Quick notes & a daily journal into an Obsidian vault.",
    )
    from . import __version__

    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--capture-clipboard",
        action="store_true",
        help="Launch the GUI and open a capture popup pre-filled from the clipboard.",
    )
    parser.add_argument(
        "--capture-note",
        action="store_true",
        help="Open a new-note popup immediately (for a global hotkey), then exit.",
    )
    parser.add_argument(
        "--capture-diary",
        action="store_true",
        help="Open a diary-entry popup immediately (for a global hotkey), then exit.",
    )

    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="Add a standalone note (a sticky post-it).")
    p_add.add_argument("text", nargs="?", help="Note text. Omit or use '-' to read stdin.")
    p_add.add_argument("-t", "--title", default="", help="Optional note title.")
    p_add.add_argument("--tags", default="", help="Extra tags, space/comma separated.")

    p_diary = sub.add_parser("diary", help="Append a timestamped entry to today's diary.")
    p_diary.add_argument("text", nargs="?", help="Entry text. Omit or use '-' to read stdin.")
    p_diary.add_argument(
        "--url",
        help="Fetch a URL as Markdown into a note and link it from the diary.",
    )
    p_diary.add_argument("--tags", default="", help="Tags for a --url clip (space/comma).")

    p_recent = sub.add_parser("recent", help="List recent notes.")
    p_recent.add_argument("-n", "--limit", type=int, default=10, help="How many (default 10).")

    p_search = sub.add_parser("search", help="Search notes (filename + full text).")
    p_search.add_argument("query", help="Text to search for.")

    sub.add_parser("show-diary", help="Print the diary document to stdout.")

    sub.add_parser(
        "mcp",
        help="Run as an MCP server over stdio (for AI agents). Needs the 'mcp' extra.",
    )

    p_mcpi = sub.add_parser(
        "mcp-install",
        help="Register this MCP server in an AI agent's config.",
    )
    p_mcpi.add_argument("agent", choices=["claude", "opencode", "codex"], help="Which agent.")
    return parser


def run_cli(args: argparse.Namespace) -> int:
    if args.command == "mcp":
        from .mcp_server import run as run_mcp

        return run_mcp()

    if args.command == "mcp-install":
        from .mcp_install import install

        return install(args.agent)

    cfg = Config.load()
    try:
        if args.command == "add":
            vault = _require_vault(cfg)
            text = _read_text(args.text).strip()
            if not text:
                print("Nothing to add (no text / empty stdin).", file=sys.stderr)
                return 2
            note = Note(
                body=text,
                title=args.title.strip(),
                tags=parse_tags(args.tags),
                source="cli",
                destination=Destination.FILE,
            )
            path = vault.save(note)
            print(path)
            return 0

        if args.command == "diary":
            vault = _require_vault(cfg)
            if getattr(args, "url", None):
                note_path, diary_path = vault.clip_url(args.url, tags=args.tags)
                print(note_path)
                print(diary_path)
                return 0
            text = _read_text(args.text).strip()
            if not text:
                print("Nothing to add (no text / empty stdin).", file=sys.stderr)
                return 2
            path = vault.add_diary_smart(text)
            print(path)
            return 0

        if args.command == "recent":
            vault = _require_vault(cfg)
            for hit in vault.recent_notes(limit=args.limit):
                print(f"{hit.title}\t{hit.path}")
            return 0

        if args.command == "search":
            vault = _require_vault(cfg)
            hits = vault.search_notes(args.query)
            for hit in hits:
                line = f"{hit.title}\t{hit.path}"
                if hit.snippet:
                    line += f"\t{hit.snippet}"
                print(line)
            return 0 if hits else 1

        if args.command == "show-diary":
            vault = _require_vault(cfg)
            sys.stdout.write(vault.read_diary())
            return 0
    except VaultError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return 0
