"""Entry point: `obsidian-postit-kde` / `python -m obsidian_postit_kde`."""

from __future__ import annotations

import argparse
import sys

from . import __version__


def main() -> int:
    parser = argparse.ArgumentParser(prog="obsidian-postit-kde")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--capture-clipboard",
        action="store_true",
        help="Open the capture popup pre-filled from the clipboard, then stay resident.",
    )
    args = parser.parse_args()

    # Import Qt lazily so --version/--help work without a display.
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon

    from .app import PostItApp

    app = QApplication(sys.argv)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print(
            "No system tray available. Ensure a StatusNotifier host is running "
            "(KDE Plasma provides one).",
            file=sys.stderr,
        )
        return 1

    controller = PostItApp(app)
    if args.capture_clipboard:
        controller.new_from_clipboard()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
