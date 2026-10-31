"""Qt UI layer (tray, capture popup, settings dialog)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

_ICON = Path(__file__).resolve().parent.parent / "resources" / "icon.svg"


def app_icon() -> QIcon:
    """Load the bundled tray/app icon, with a themed fallback."""
    if _ICON.is_file():
        return QIcon(str(_ICON))
    return QIcon.fromTheme("accessories-text-editor")
