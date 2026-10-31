"""Entry point: GUI by default, or a headless CLI subcommand.

obsidian-postit-kde                  # launch the tray GUI
obsidian-postit-kde add "idea #x"    # write a note (no display needed)
obsidian-postit-kde diary "log line" # append to today's diary
echo "piped" | obsidian-postit-kde add -
"""

from __future__ import annotations

import sys

from .cli import build_parser, run_cli


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # A subcommand means headless CLI — never import Qt (works over SSH/scripts).
    if args.command:
        return run_cli(args)

    # No subcommand: launch the GUI. Import Qt lazily so CLI/--version/--help
    # work without a display.
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
    if args.capture_note:
        from .note import Destination

        controller.capture_once(Destination.FILE)
    elif args.capture_diary:
        from .note import Destination

        controller.capture_once(Destination.DAILY)
    elif args.capture_clipboard:
        controller.new_from_clipboard()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
