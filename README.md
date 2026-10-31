# obsidian-postit-kde

A lightweight **KDE system-tray app** to capture quick notes and clipboard
contents straight into an **Obsidian vault** — without launching Obsidian.

Built with Python + PySide6 (Qt6) for KDE Plasma 6 on Wayland. MIT licensed.

## Why

Obsidian is heavy to open for a one-line thought. This app lives in the tray
and writes well-formed Markdown (YAML frontmatter + tags) directly into your
vault folder, so notes are indexed next time Obsidian opens. No Obsidian
process required.

Compared to classic sticky-note apps (KNotes — discontinued, Xpad,
Indicator Stickynotes): same tray-capture convenience, but notes land in a real
Markdown vault with full Obsidian search, tags and backlinks.

## Two capture modes

- **Sticky daily note** — appends a timestamped bullet to a single rolling
  per-device file `Daily/<device>-daily-note.md`, grouped under `## YYYY-MM-DD`
  date headings. Great for a fast running log.
- **Regular note** — one small standalone `.md` file per note in `PostIt/`.
  Great for notes you'll keep, link or expand.

## Features

- Tray icon: left-click to capture, right-click menu (new note, from clipboard,
  open vault, settings, quit)
- On-demand clipboard capture (Wayland-friendly — user-initiated)
- Tags (Obsidian `#tags` + frontmatter), default tags from settings
- Settings dialog: vault picker, folders, templates, defaults
- Autostart on login (managed XDG `.desktop` entry)
- Optional **OpenRouter** integration: **Summarize** and **Clean** buttons.
  The API key is stored in the system keyring (KDE Wallet), never in config.

## Install

Requires Python 3.13+ and PySide6 (on Fedora KDE: `sudo dnf install python3-pyside6`).

```bash
pipx install .
# or for development:
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
obsidian-postit-kde
# or
python -m obsidian_postit_kde
```

On first run, open **Settings** and select your Obsidian vault folder.

## Configuration

Config lives at `~/.config/obsidian-postit-kde/config.toml` (human-editable).
The OpenRouter API key is **not** stored there — it goes in the system keyring,
or the `OPENROUTER_API_KEY` environment variable as a fallback.

See [DESIGN.md](DESIGN.md) for the full design, note format spec and roadmap.

## Development

```bash
. .venv/bin/activate
pytest            # core modules, no display needed
ruff check .
mypy src
```

## License

MIT — see [LICENSE](LICENSE).
