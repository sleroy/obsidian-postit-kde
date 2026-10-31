"""Manage the XDG autostart .desktop entry for login startup."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .config import APP_ID, xdg_config_home

_DESKTOP_NAME = f"{APP_ID}.desktop"


def autostart_dir() -> Path:
    return xdg_config_home() / "autostart"


def autostart_path() -> Path:
    return autostart_dir() / _DESKTOP_NAME


def _exec_command() -> str:
    """Prefer the installed console script; fall back to `python -m`."""
    exe = shutil.which(APP_ID)
    if exe:
        return exe
    return "python -m obsidian_postit_kde"


def desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Obsidian PostIt (KDE)\n"
        "Comment=Quick notes and clipboard into an Obsidian vault\n"
        f"Exec={_exec_command()}\n"
        f"Icon={APP_ID}\n"
        "Terminal=false\n"
        "Categories=Utility;Qt;KDE;\n"
        "X-GNOME-Autostart-enabled=true\n"
    )


def is_enabled() -> bool:
    return autostart_path().is_file()


def enable() -> Path:
    path = autostart_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".desktop.tmp")
    tmp.write_text(desktop_entry(), encoding="utf-8")
    os.replace(tmp, path)
    return path


def disable() -> None:
    path = autostart_path()
    if path.is_file():
        path.unlink()


def set_enabled(enabled: bool) -> None:
    if enabled:
        enable()
    else:
        disable()
