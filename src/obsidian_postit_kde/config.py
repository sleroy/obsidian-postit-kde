"""Configuration: TOML load/save under XDG config dir, plus derived paths."""

from __future__ import annotations

import os
import socket
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .note import Destination, slugify

APP_ID = "obsidian-postit-kde"


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def config_dir() -> Path:
    return xdg_config_home() / APP_ID


def config_path() -> Path:
    return config_dir() / "config.toml"


def device_slug() -> str:
    """Slugified hostname, used in the daily-note filename."""
    return slugify(socket.gethostname()) or "device"


@dataclass
class Config:
    """User configuration. Secrets (API key) are NOT stored here."""

    vault_path: str = ""
    default_destination: str = Destination.DAILY.value
    # regular file-per-note
    subfolder: str = "PostIt"
    filename_template: str = "%Y-%m-%d-%H%M%S"
    add_title_slug: bool = True
    # rolling daily note
    daily_folder: str = "Daily"
    daily_filename: str = "{device}-daily-note"
    daily_heading_date: str = "%Y-%m-%d"
    daily_bullet_time: bool = True
    diary_font_px: int = 15
    # shared
    default_tags: list[str] = field(default_factory=lambda: ["postit"])
    autostart: bool = False
    openrouter_model: str = "google/gemini-2.5-flash-lite"
    speech_enabled: bool = False
    speech_engine: str = "local"  # "local" (whisper.cpp) or "openrouter" (cloud)
    speech_model: str = "base"  # local whisper.cpp model
    speech_cloud_model: str = "openai/whisper-large-v3-turbo"
    speech_language: str = "auto"
    speech_live_preview: bool = True
    speech_clean_with_openrouter: bool = False

    # ---- validation / derived ---------------------------------------------

    @property
    def vault(self) -> Path | None:
        return Path(self.vault_path).expanduser() if self.vault_path else None

    def vault_is_valid(self) -> bool:
        v = self.vault
        return bool(v and v.is_dir())

    def daily_file(self) -> Path:
        assert self.vault is not None
        name = self.daily_filename.format(device=device_slug())
        if not name.endswith(".md"):
            name += ".md"
        return self.vault / self.daily_folder / name

    def postit_dir(self) -> Path:
        assert self.vault is not None
        return self.vault / self.subfolder

    # ---- persistence ------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        path = path or config_path()
        if not path.is_file():
            return cls()
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        known = set(cls().__dict__)
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        text = _to_toml(asdict(self))
        tmp = path.with_suffix(".toml.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)


def _to_toml(data: dict) -> str:
    """Minimal TOML writer (stdlib has a reader only). Flat keys only."""
    lines: list[str] = []
    for key, value in data.items():
        lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def _toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return _toml_string(str(value))


def _toml_string(value: str) -> str:
    """Encode a TOML basic string. Basic strings forbid literal control chars,
    so newlines/tabs/etc. must be escaped or tomllib fails to read them back."""
    out = []
    for ch in value:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif ord(ch) < 0x20:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'
