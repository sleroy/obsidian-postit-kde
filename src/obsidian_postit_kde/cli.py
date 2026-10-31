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

    sub = parser.add_subparsers(dest="command")

    p_add = sub.add_parser("add", help="Add a standalone note (a sticky post-it).")
    p_add.add_argument("text", nargs="?", help="Note text. Omit or use '-' to read stdin.")
    p_add.add_argument("-t", "--title", default="", help="Optional note title.")
    p_add.add_argument("--tags", default="", help="Extra tags, space/comma separated.")

    p_diary = sub.add_parser("diary", help="Append a timestamped entry to today's diary.")
    p_diary.add_argument("text", nargs="?", help="Entry text. Omit or use '-' to read stdin.")

    p_recent = sub.add_parser("recent", help="List recent notes.")
    p_recent.add_argument("-n", "--limit", type=int, default=10, help="How many (default 10).")

    p_search = sub.add_parser("search", help="Search notes (filename + full text).")
    p_search.add_argument("query", help="Text to search for.")

    sub.add_parser("show-diary", help="Print the diary document to stdout.")
    return parser


def run_cli(args: argparse.Namespace) -> int:
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
            text = _read_text(args.text).strip()
            if not text:
                print("Nothing to add (no text / empty stdin).", file=sys.stderr)
                return 2
            path = vault.append_diary_entry(text)
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
