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

<img src="docs/images/diary.png" width="520" alt="Diary window — the daily journal"/>

</div>

---

## Why

Obsidian is wonderful — and heavy to open for a single line. Classic sticky-note
apps (KNotes is discontinued, Xpad, Indicator Stickynotes) are light but trap
your notes in their own silos. **Obsidian PostIt** gives you the tray-capture
convenience *and* keeps everything in a real Markdown vault: full Obsidian
search, tags and backlinks, no lock-in, no Obsidian process required.

## Two surfaces: Diary & Notes

|  |  |
|---|---|
| **📔 Diary** — a continuous daily journal, one rolling file per device (`Daily/<device>-daily-note.md`). Open it to read today's entries, scroll back through past days (`PgUp`/`PgDn`), add a timestamped entry, copy a day, edit a day or the whole document, or **summarize a day** with AI into one entry. | **🗒️ Notes** — discrete sticky post-its, one tidy `.md` each in `PostIt/`, filename **guessed from your content**. Create, edit in place, or delete. For things you'll keep, link or expand. |

## Features

### Diary
- 📖 **Read your journal** — the whole rolling document, scrolled to today
- ✍️ **Add entries** — a quick box appends a timestamped bullet under today
- ↕️ **Jump between days** with `PgUp` / `PgDn` or Prev/Next buttons
- 📋 **Copy a day** to the clipboard in one click
- ✎ **Edit today's section** or free-edit the whole document (safe atomic save)
- ✦ **Summarize a day** — AI rewrites all of today's entries into one

### Notes
- 🎯 **Sticky capture** — the window *is* the note: a yellow post-it with an
  optional title and a body. Type, `Ctrl+Enter`, done. Resizable.
- 📋 **Clipboard capture** on demand (Wayland-friendly — user-initiated)
- ✏️ **Edit & delete** — open a note to change it in place, or delete it
- 🔎 **Recent & search** — your last 5 notes and full-text search across the vault

### Everywhere
- 🏷️ **Tags** — Obsidian `#tags` inline, highlighted live, mirrored to frontmatter
- ✨ **Syntax highlighting** (`#tags`, `[[wikilinks]]`, `**bold**`, *italic*,
  `` `code` ``) plus an **Edit ⇄ Preview** toggle
- 🤖 **Optional AI** (OpenRouter), run off the UI thread — key in the system
  keyring (KDE Wallet), **never** in a config file
- 🚀 **Autostart on login**, managed from Settings

## Screenshots

<div align="center">

| 📔 Diary — your daily journal | 🗒️ Note — a sticky post-it |
|:---:|:---:|
| <img src="docs/images/diary.png" width="400"/> | <img src="docs/images/note.png" width="300"/> |

| 🔎 Search your notes | ⚙️ Settings |
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
Obsidian vault. **Left-click** the tray icon to open your **Diary**;
**right-click** for the Diary, a new note, clipboard capture, recent notes,
search, and settings.

## CLI

The same binary works headlessly — no display needed — writing exactly what the
GUI would. Handy for scripts, git hooks, cron, or over SSH:

```bash
obsidian-postit-kde add "Refactor the parser #idea"        # a sticky note
obsidian-postit-kde add "Meeting notes" -t "Standup"       # with a title
obsidian-postit-kde diary "Shipped the CLI #work"          # append to today's diary
echo "piped from anywhere" | obsidian-postit-kde add -     # read stdin
obsidian-postit-kde recent -n 5                            # list recent notes
obsidian-postit-kde search parser                          # full-text search
obsidian-postit-kde show-diary                             # print the diary
```

Running with no subcommand launches the tray GUI as usual.

## Clip a web page into your diary

Fetch a URL, convert it to Markdown, save it as a note, and drop a linked
bullet in today's diary — so you can stash useful things as you find them:

```bash
obsidian-postit-kde diary --url https://example.com/article --tags reading
```

A diary entry that is **just a URL** is auto-clipped the same way (mixed text is left alone). The article is stored in `PostIt/` and the diary gets `Clipped [[note]] — Title`.
Install the optional `[web]` extra for faithful HTML→Markdown (`markdownify`);
without it, a built-in stdlib fallback is used.

## Global hotkey (KDE)

Wayland blocks app-level global shortcuts, so bind one in KDE instead:
**System Settings → Shortcuts → Custom Shortcuts → Edit → New → Global Shortcut
→ Command/URL**, with the command:

```bash
obsidian-postit-kde --capture-note     # or --capture-diary
```

Assign a key (e.g. `Meta+N`). It opens the capture popup instantly and exits
when you're done — no need to click the tray.

## MCP server (for AI agents)

The app can run as an [MCP](https://modelcontextprotocol.io) server over stdio,
exposing your vault to AI agents (Kiro, Claude, opencode, …) — they capture
notes and diary entries the same way the GUI does. Install the extra and run:

```bash
pipx inject obsidian-postit-kde mcp     # or: pip install "obsidian-postit-kde[mcp]"
obsidian-postit-kde mcp                 # speaks MCP over stdio
```

Register it with your agent, e.g.:

```json
{ "mcpServers": { "obsidian-postit": { "command": "obsidian-postit-kde", "args": ["mcp"] } } }
```

…or let the app write that config for you:

```bash
obsidian-postit-kde mcp-install claude      # Claude Desktop
obsidian-postit-kde mcp-install opencode    # opencode
obsidian-postit-kde mcp-install codex       # Codex
```

**Tools:** `add_note`, `add_diary_entry` (auto-clips a bare URL),
`add_diary_link` (clip a URL), `search_notes`, `recent_notes`, `read_note`
(confined to the vault), `read_diary`, `summarize_day`.
**Resources:** `obsidian-postit://diary`, `obsidian-postit://recent`.

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

pytest          # 102 tests, no display needed
ruff check .
mypy src
```

## License

[MIT](LICENSE) © sleroy
