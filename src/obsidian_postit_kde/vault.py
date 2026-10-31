"""ObsidianVault: writes notes to disk (file-per-note or rolling daily note)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import Config, device_slug
from .note import Destination, Note


class VaultError(Exception):
    """Raised when the vault is misconfigured or a write fails."""


@dataclass
class NoteHit:
    """A note surfaced by browsing or search."""

    path: Path
    title: str
    snippet: str = ""


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

    # ---- read / browse ----------------------------------------------------

    def _note_dirs(self) -> list[Path]:
        """Folders we consider 'notes' for browsing: PostIt/ and Daily/."""
        assert self.config.vault is not None
        dirs = [self.config.postit_dir(), self.config.vault / self.config.daily_folder]
        return [d for d in dirs if d.is_dir()]

    def _all_note_files(self) -> list[Path]:
        files: list[Path] = []
        for d in self._note_dirs():
            files.extend(p for p in d.glob("*.md") if p.is_file())
        return files

    def recent_notes(self, limit: int = 5) -> list[NoteHit]:
        """The most recently modified note files, newest first."""
        if not self.config.vault_is_valid():
            return []
        dated: list[tuple[float, Path]] = []
        for p in self._all_note_files():
            try:
                dated.append((p.stat().st_mtime, p))
            except OSError:
                continue  # file vanished (sync/deletion) between glob and stat
        dated.sort(key=lambda t: t[0], reverse=True)
        return [NoteHit(path=p, title=_display_title(p)) for _, p in dated[:limit]]

    def search_notes(self, query: str, limit: int = 50) -> list[NoteHit]:
        """Case-insensitive match on filename or file contents.

        Returns hits newest-first, each with a short snippet around the first
        content match (or the title when only the filename matched). Frontmatter
        is excluded from both the match and the snippet so YAML keys do not
        pollute results.
        """
        if not self.config.vault_is_valid() or not query.strip():
            return []
        needle = query.strip().lower()
        hits: list[tuple[float, NoteHit]] = []
        for p in self._all_note_files():
            try:
                mtime = p.stat().st_mtime
                raw = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue  # file vanished or unreadable; skip
            body = _strip_frontmatter(raw)
            name_match = needle in p.name.lower()
            content_match = needle in body.lower()
            if not (name_match or content_match):
                continue
            snippet = _snippet(body, needle) if content_match else ""
            hits.append((mtime, NoteHit(path=p, title=_display_title(p), snippet=snippet)))
        hits.sort(key=lambda t: t[0], reverse=True)
        return [h for _, h in hits[:limit]]

    def daily_path(self) -> Path | None:
        """Path to the rolling daily file if the vault is valid, else None."""
        if not self.config.vault_is_valid():
            return None
        return self.config.daily_file()

    def is_daily(self, path: Path) -> bool:
        dp = self.daily_path()
        return dp is not None and path.resolve() == dp.resolve()

    def read_display(self, path: Path, today: date | None = None) -> tuple[str, str]:
        """Return (title, markdown_body) for displaying a note in the app.

        For the rolling daily file, only *today's* dated section is returned so
        the viewer shows today's notes rather than the entire history.
        """
        raw = path.read_text(encoding="utf-8", errors="replace")
        if self.is_daily(path):
            day = today or date.today()
            heading = f"## {day.strftime(self.config.daily_heading_date)}"
            section = _extract_section(raw, heading)
            title = f"Today — {day.isoformat()}"
            return title, (section or "_No notes yet today._")
        return _display_title(path), _strip_frontmatter(raw)

    def load_note(self, path: Path) -> Note:
        """Reconstruct an editable Note from an existing standalone file note.

        Reads the frontmatter title/tags/source when present and the body with
        the frontmatter and a leading duplicate '# title' heading removed.
        """
        raw = path.read_text(encoding="utf-8", errors="replace")
        title, tags, source = _parse_frontmatter(raw)
        body = _strip_frontmatter(raw)
        # Drop a leading '# <title>' line that to_file_markdown re-adds on save.
        lines = body.splitlines()
        if title and lines and lines[0].strip() == f"# {title}":
            lines = lines[1:]
            while lines and lines[0].strip() == "":
                lines.pop(0)
        return Note(
            body="\n".join(lines).strip(),
            title=title,
            tags=tags,
            source=source or "manual",
            destination=Destination.FILE,
        )

    def update_file_note(self, path: Path, note: Note) -> Path:
        """Rewrite an existing standalone file note in place (same filename)."""
        content = note.to_file_markdown(self.config.default_tags)
        _atomic_write(path, content)
        return path

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
        if self.config.add_title_slug:
            slug = note.guess_name()
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

    def _is_date_heading(ln: str) -> bool:
        return ln.strip().startswith("## ")

    try:
        idx = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration:
        # New date section at end of file.
        while lines and lines[-1].strip() == "":
            lines.pop()
        block = ["", heading, *bullet.splitlines()]
        lines.extend(block)
        return "\n".join(lines).strip("\n") + "\n"

    # Find the end of this section (next date heading or EOF), using the same
    # whitespace-tolerant predicate as the match above.
    end = len(lines)
    for i in range(idx + 1, len(lines)):
        if _is_date_heading(lines[i]):
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


def _strip_frontmatter(text: str) -> str:
    """Return the body of a note with a leading YAML --- ... --- block removed."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines()
    # lines[0] is the opening '---'; find the closing one.
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1 :]).lstrip("\n")
    return text  # no closing fence; treat as-is


def _parse_frontmatter(text: str) -> tuple[str, list[str], str]:
    """Extract (title, tags, source) from a leading YAML block. Best-effort,
    tolerant of the double-quoted scalars this app writes."""
    title, source = "", ""
    tags: list[str] = []
    if not text.startswith("---"):
        return title, tags, source
    lines = text.splitlines()
    for ln in lines[1:]:
        s = ln.strip()
        if s == "---":
            break
        if s.startswith("title:"):
            title = _unquote(s[len("title:") :].strip())
        elif s.startswith("source:"):
            source = _unquote(s[len("source:") :].strip())
        elif s.startswith("tags:"):
            inside = s[len("tags:") :].strip().lstrip("[").rstrip("]")
            tags = [_unquote(t.strip()) for t in inside.split(",") if t.strip()]
    return title, tags, source


def _unquote(value: str) -> str:
    """Reverse the double-quoted YAML scalar encoding this app emits."""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        inner = value[1:-1]
        return (
            inner.replace('\\"', '"')
            .replace("\\n", "\n")
            .replace("\\t", "\t")
            .replace("\\r", "\r")
            .replace("\\\\", "\\")
        )
    return value


def _extract_section(text: str, heading: str) -> str:
    """Return the lines under `heading` up to the next '## ' heading (or EOF)."""
    lines = text.splitlines()
    try:
        idx = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration:
        return ""
    end = len(lines)
    for i in range(idx + 1, len(lines)):
        if lines[i].strip().startswith("## "):
            end = i
            break
    body = "\n".join(lines[idx + 1 : end]).strip("\n")
    return body


def _display_title(path: Path) -> str:
    """A human title for a note file: first '# ' heading, else the filename."""
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("# "):
                    return stripped[2:].strip()
    except OSError:
        pass
    return path.stem


def _snippet(text: str, needle: str, width: int = 60) -> str:
    """A one-line snippet of `text` centered on the first match of `needle`."""
    low = text.lower()
    pos = low.find(needle)
    if pos < 0:
        return ""
    start = max(0, pos - width // 2)
    end = min(len(text), pos + len(needle) + width // 2)
    chunk = text[start:end].replace("\n", " ").strip()
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{chunk}{suffix}"
