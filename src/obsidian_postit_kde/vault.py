"""ObsidianVault: writes notes to disk (file-per-note or rolling daily note)."""

from __future__ import annotations

import os
from pathlib import Path

from .config import Config, device_slug
from .note import Destination, Note, slugify


class VaultError(Exception):
    """Raised when the vault is misconfigured or a write fails."""


class ObsidianVault:
    def __init__(self, config: Config) -> None:
        self.config = config

    # ---- public API -------------------------------------------------------

    def save(self, note: Note) -> Path:
        """Dispatch to the correct writer and return the written file path."""
        if not self.config.vault_is_valid():
            raise VaultError(f"Vault path is not a valid directory: {self.config.vault_path!r}")
        if note.destination is Destination.FILE:
            return self._write_file_note(note)
        return self._append_daily_note(note)

    # ---- regular file-per-note -------------------------------------------

    def _write_file_note(self, note: Note) -> Path:
        folder = self.config.postit_dir()
        folder.mkdir(parents=True, exist_ok=True)
        path = self._unique_path(folder, note)
        content = note.to_file_markdown(self.config.default_tags)
        _atomic_write(path, content)
        return path

    def _unique_path(self, folder: Path, note: Note) -> Path:
        stem = note.created.strftime(self.config.filename_template)
        if self.config.add_title_slug and note.title:
            slug = slugify(note.title)
            if slug:
                stem = f"{stem}-{slug}"
        path = folder / f"{stem}.md"
        counter = 2
        while path.exists():
            path = folder / f"{stem}-{counter}.md"
            counter += 1
        return path

    # ---- rolling daily note ----------------------------------------------

    def _append_daily_note(self, note: Note) -> Path:
        path = self.config.daily_file()
        path.parent.mkdir(parents=True, exist_ok=True)

        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if not existing.strip():
            existing = self._daily_header()

        heading = f"## {note.created.strftime(self.config.daily_heading_date)}"
        bullet = note.to_daily_bullet(
            self.config.default_tags, with_time=self.config.daily_bullet_time
        )
        updated = _insert_under_heading(existing, heading, bullet)
        _atomic_write(path, updated)
        return path

    def _daily_header(self) -> str:
        dev = device_slug()
        return f"---\ndevice: {dev}\ntags: [daily]\n---\n\n# {dev} — daily note\n"


# ---- module-level text helpers (pure, unit-tested) -----------------------


def _insert_under_heading(content: str, heading: str, bullet: str) -> str:
    """Insert `bullet` at the end of the section started by `heading`.

    If `heading` is absent, append a new section at the end of the document.
    The document body always ends with a single trailing newline.
    """
    lines = content.splitlines()

    try:
        idx = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration:
        # New date section at end of file.
        while lines and lines[-1].strip() == "":
            lines.pop()
        block = ["", heading, *bullet.splitlines()]
        lines.extend(block)
        return "\n".join(lines).lstrip("\n") + "\n"

    # Find the end of this section (next "## " heading or EOF).
    end = len(lines)
    for i in range(idx + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break

    # Trim trailing blank lines inside the section, then append the bullet.
    insert_at = end
    while insert_at - 1 > idx and lines[insert_at - 1].strip() == "":
        insert_at -= 1
    new_lines = lines[:insert_at] + bullet.splitlines() + lines[insert_at:]
    return "\n".join(new_lines).rstrip("\n") + "\n"


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
