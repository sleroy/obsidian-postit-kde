<div align="center">

<img src="src/obsidian_postit_kde/resources/icon.svg" width="96" alt="Obsidian PostIt icon"/>

# Obsidian PostIt

### Quick sticky notes from your KDE tray, straight into your Obsidian vault.

No waiting for Obsidian to launch — jot a thought or stash the clipboard, and it
lands as clean Markdown your vault indexes the next time you open it.

<br/>

[![CI](https://github.com/sleroy/obsidian-postit-kde/actions/workflows/ci.yml/badge.svg)](https://github.com/sleroy/obsidian-postit-kde/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)](https://www.python.org/)
[![Qt 6 · PySide6](https://img.shields.io/badge/Qt6-PySide6-41cd52.svg)](https://doc.qt.io/qtforpython/)
[![KDE Plasma 6](https://img.shields.io/badge/KDE-Plasma%206-1d99f3.svg)](https://kde.org/plasma-desktop/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

<br/>

<img src="docs/images/capture.png" width="420" alt="Capture window — a yellow sticky note"/>

</div>

---

## Why

Obsidian is wonderful — and heavy to open for a single line. Classic sticky-note
apps (KNotes is discontinued, Xpad, Indicator Stickynotes) are light but trap
your notes in their own silos. **Obsidian PostIt** gives you the tray-capture
convenience *and* keeps everything in a real Markdown vault: full Obsidian
search, tags and backlinks, no lock-in, no Obsidian process required.

## Two ways to capture

|  |  |
|---|---|
| **🗒️ Quick note** → appends a timestamped bullet to a single rolling per-device daily file (`Daily/<device>-daily-note.md`), grouped under `## YYYY-MM-DD`. Perfect for a fast running log. | **📄 New note** → one tidy standalone `.md` in `PostIt/`, with the filename **guessed from your content**. For notes you'll keep, link or expand. |

## Features

- 🎯 **One-surface capture** — the window *is* the note: a yellow sticky with an
  optional title and a body. Type, `Ctrl+Enter`, done.
- 📋 **Clipboard capture** on demand (Wayland-friendly — user-initiated).
- 🏷️ **Tags** — write Obsidian `#tags` inline; they're highlighted live and
  mirrored into YAML frontmatter.
- ✨ **Live syntax highlighting** for `#tags`, `[[wikilinks]]`, `**bold**`,
  *italic* and `` `code` ``, plus an **Edit ⇄ Preview** toggle.
- 🔎 **Browse & search** from the tray — your **last 5 notes** and a full-text
  **search** across the vault.
- 🤖 **Optional AI** (OpenRouter) — **Summarize** and **Clean** buttons. Your API
  key lives in the system keyring (KDE Wallet), **never** in a config file.
- 🚀 **Autostart on login**, managed from Settings.

## Screenshots

<div align="center">

| Capture (edit) | Markdown preview |
|:---:|:---:|
| <img src="docs/images/capture.png" width="380"/> | <img src="docs/images/preview.png" width="380"/> |

| Search your vault | Settings |
|:---:|:---:|
| <img src="docs/images/search.png" width="380"/> | <img src="docs/images/settings.png" width="380"/> |

</div>

## Install

Requires Python 3.13+ and PySide6. On Fedora KDE:

```bash
sudo dnf install python3-pyside6
pipx install .
```

Then add the menu launcher and icon:

```bash
install -Dm644 packaging/obsidian-postit-kde.desktop \
  ~/.local/share/applications/obsidian-postit-kde.desktop
install -Dm644 src/obsidian_postit_kde/resources/icon.svg \
  ~/.local/share/icons/hicolor/scalable/apps/obsidian-postit-kde.svg
```

See [PACKAGING.md](PACKAGING.md) for Flatpak and Fedora RPM instructions.

## Run

```bash
obsidian-postit-kde
```

On first launch, open **Settings** (right-click the tray icon) and pick your
Obsidian vault. **Left-click** the tray icon for a quick note; **right-click**
for new note, clipboard, recent notes, search, and settings.

## Configuration

Config lives at `~/.config/obsidian-postit-kde/config.toml` (human-editable).
The OpenRouter API key is stored in the system keyring, or read from the
`OPENROUTER_API_KEY` environment variable as a fallback.

| Key | Default | Meaning |
|---|---|---|
| `vault_path` | *(unset)* | Absolute path to your Obsidian vault |
| `default_destination` | `daily` | Preselected capture target (`daily` or `file`) |
| `subfolder` | `PostIt` | Folder for standalone notes |
| `daily_filename` | `{device}-daily-note` | Rolling daily file; `{device}` = hostname |
| `default_tags` | `["postit"]` | Tags added to every note |
| `openrouter_model` | `google/gemini-2.5-flash-lite` | Model for AI actions |
| `autostart` | `false` | Managed login autostart entry |

Full note-format spec and roadmap: [DESIGN.md](DESIGN.md).

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

pytest          # 50 tests, no display needed
ruff check .
mypy src
```

## License

[MIT](LICENSE) © sleroy
