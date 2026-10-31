"""Note model and Markdown/frontmatter serialization helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Destination(StrEnum):
    """Where a captured note is written."""

    DAILY = "daily"
    FILE = "file"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 48) -> str:
    """Lowercase, hyphenate, strip to a filesystem-safe slug."""
    slug = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return slug[:max_len].strip("-")


def normalize_tag(tag: str) -> str:
    """Normalize a single tag: strip leading #, spaces -> hyphen, lowercase."""
    tag = tag.strip().lstrip("#").strip()
    return _SLUG_RE.sub("-", tag.lower()).strip("-")


def parse_tags(raw: str) -> list[str]:
    """Parse a free-form tag field (comma/space/# separated) into clean tags."""
    parts = re.split(r"[,\s]+", raw.strip()) if raw else []
    out: list[str] = []
    for part in parts:
        norm = normalize_tag(part)
        if norm and norm not in out:
            out.append(norm)
    return out


def _yaml_tag_list(tags: list[str]) -> str:
    return "[" + ", ".join(tags) + "]"


@dataclass
class Note:
    """A single captured note, destination-agnostic."""

    body: str
    title: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = "manual"  # "manual" | "clipboard"
    destination: Destination = Destination.DAILY
    created: datetime = field(default_factory=datetime.now)

    def merged_tags(self, default_tags: list[str]) -> list[str]:
        """Default tags first, then note tags, de-duplicated preserving order."""
        out: list[str] = []
        for tag in [*default_tags, *self.tags]:
            if tag and tag not in out:
                out.append(tag)
        return out

    def to_file_markdown(self, default_tags: list[str]) -> str:
        """Full standalone Markdown document with YAML frontmatter."""
        tags = self.merged_tags(default_tags)
        lines = ["---", f"created: {self.created.isoformat(timespec='seconds')}"]
        if tags:
            lines.append(f"tags: {_yaml_tag_list(tags)}")
        lines.append(f"source: {self.source}")
        if self.title:
            lines.append(f"title: {self.title}")
        lines.append("---")
        lines.append("")
        if self.title:
            lines.append(f"# {self.title}")
            lines.append("")
        lines.append(self.body.rstrip())
        lines.append("")
        return "\n".join(lines)

    def to_daily_bullet(self, default_tags: list[str], with_time: bool = True) -> str:
        """One-line (or multi-line) bullet for the rolling daily note.

        Tags are inline in daily mode. Multi-line bodies are rendered as a
        lead bullet plus indented continuation lines.
        """
        tags = self.merged_tags(default_tags)
        inline_tags = " ".join(f"#{t}" for t in tags)
        time_prefix = f"{self.created:%H:%M} " if with_time else ""

        body_lines = self.body.strip().splitlines()
        head = body_lines[0] if body_lines else ""
        rest = body_lines[1:]

        first = f"- {time_prefix}"
        if self.title:
            first += f"**{self.title}** — "
        first += head
        if inline_tags:
            first += f" {inline_tags}"

        out = [first]
        out.extend(f"  {line}" for line in rest)
        return "\n".join(out)
