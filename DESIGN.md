# obsidian-postit-kde — Design & Plan

A lightweight KDE tray application to capture quick notes and clipboard
contents straight into an Obsidian vault — without launching Obsidian.

- **Platform:** Fedora 45, KDE Plasma 6.7, Qt 6.11 (Wayland), Python 3.13+
- **Stack:** Python + PySide6 (Qt6), standard library for file I/O
- **License:** MIT (open source)
- **Repo:** `sleroy/obsidian-postit-kde`

---

## 1. Problem & goal

Obsidian is heavy to launch for a one-line thought or a clipboard snippet.
This app lives in the system tray and writes well-formed Markdown notes
(with YAML frontmatter and tags) directly into the vault folder, so the notes
are indexed by Obsidian the next time it opens. No Obsidian process required.

## 2. Competitive comparison

| Feature | KNotes | Xpad | Indicator Stickynotes | **obsidian-postit-kde** |
|---|---|---|---|---|
| Tray / indicator control | ✓ | ✓ | ✓ | ✓ |
| Status | **discontinued** | X11-focused | Ubuntu-focused | active, KDE/Wayland |
| Storage | own DB | `~/.config/xpad` | own format | **Obsidian Markdown vault** |
| Tags | limited | ✗ | categories/colors | **Obsidian #tags + frontmatter** |
| Clipboard capture | ✗ | ✗ | ✗ | **✓ (on demand)** |
| Searchable later | in-app | in-app | in-app | **full Obsidian graph/search** |
| AI assist | ✗ | ✗ | ✗ | **OpenRouter summarize/clean** |

Gap we fill: KNotes is discontinued; none store into Obsidian. We give the
tray-capture convenience of a sticky-note app with the durability and
searchability of a real Markdown vault.

## 3. Features

### v1 (MVP)
- System tray icon (`QSystemTrayIcon`, StatusNotifier under Plasma 6)
  - Left-click → capture popup
  - Right-click → menu: New note, New from clipboard, Open vault, Settings, Quit
- Capture popup: title (optional), body text, tags field, destination
  toggle (**Sticky daily** / **New note**), Save / Cancel
- Clipboard capture **on demand** (read clipboard when action triggered)
- Two destinations behind one `vault.save()` interface:
  - **Sticky daily note** — appends a timestamped bullet to a single
    per-device rolling file (`<device>-daily-note.md`), grouped under
    `## YYYY-MM-DD` date headings
  - **Regular note** — one small standalone `.md` file per note
- Settings dialog with persisted config
- Autostart on login (`.desktop` in `~/.config/autostart`, toggle in settings)
- OpenRouter integration: **Summarize** and **Clean** buttons in the popup

### Later (v2+)
- KDE global shortcut (D-Bus CLI entrypoint) for instant clipboard capture
- Recent-notes list / quick re-open
- Template editor
- Attachments (screenshots) into vault `attachments/`

## 4. Note format

Two destinations, chosen per capture via the popup toggle.

### 4a. Regular note (one file per note)

- Default filename = timestamp. Template: `%Y-%m-%d-%H%M%S` → `2026-10-31-125740.md`
- Collision-safe; if a title is given, optional slug suffix:
  `2026-10-31-130412-buy-milk.md`
- Target subfolder inside vault: configurable, default `PostIt/`
- Frontmatter:

```markdown
---
created: 2026-10-31T12:54:31+01:00
tags: [postit, clipboard]
source: clipboard        # or "manual"
title: Optional title
---

Note body text here.
```

### 4b. Sticky daily note (single rolling per-device file)

- **One file per device**, never dated in the filename:
  `Daily/<device>-daily-note.md` where `<device>` is the slugified hostname
  (`socket.gethostname()`), e.g. `sleroy-thinkpad-daily-note.md`.
- Rationale: in a vault synced across machines, a per-device file avoids
  append conflicts; a single rolling file (your choice **b**) keeps one
  perpetual log per machine.
- Captures append as timestamped bullets grouped under `## YYYY-MM-DD`:

```markdown
---
device: sleroy-thinkpad
tags: [daily]
---
# sleroy-thinkpad — daily note

## 2026-10-31
- 12:59 Clipboard snippet #clipboard
- 13:40 Another quick thought #idea

## 2026-11-01
- 09:12 New day, new bullet #idea
```

**Append algorithm (must be robust):**
1. If the file is missing, create it with frontmatter + `# <device> — daily note`.
2. Locate today's `## YYYY-MM-DD` heading.
   - Found → insert the bullet after the last line of that date's section.
   - Not found → append a new `## YYYY-MM-DD` block at end of file, then the bullet.
3. Write to a temp file and `os.replace()` (atomic; never corrupts the log).

Tags in daily mode are **inline** in the bullet (frontmatter tags would apply
to the whole file). In regular-note mode, tags go in frontmatter. Entered tags
are normalized (spaces→`-`) and merged with `default_tags`.

## 5. Configuration

Stored via a TOML file at `~/.config/obsidian-postit-kde/config.toml`
(human-editable), not QSettings, so it's portable and inspectable.

| Key | Default | Meaning |
|---|---|---|
| `vault_path` | *(unset)* | Absolute path to the Obsidian vault |
| `default_destination` | `daily` | Preselected toggle: `daily` or `file` |
| `subfolder` | `PostIt` | Folder for regular (file-per-note) notes |
| `filename_template` | `%Y-%m-%d-%H%M%S` | strftime pattern for regular notes |
| `add_title_slug` | `true` | Append slug of title to regular-note filename |
| `daily_folder` | `Daily` | Folder holding the rolling daily note |
| `daily_filename` | `{device}-daily-note` | Rolling file name; `{device}` = hostname slug |
| `daily_heading_date` | `%Y-%m-%d` | strftime pattern for the `##` date heading |
| `daily_bullet_time` | `true` | Prefix each bullet with `HH:MM` |
| `default_tags` | `["postit"]` | Tags added to every note |
| `autostart` | `false` | Managed `.desktop` autostart entry |
| `openrouter_model` | `openai/gpt-4o-mini` | Model for AI actions |

Secrets: the OpenRouter API key is **not** stored in the TOML. It is kept in
the KDE wallet / libsecret via `keyring` (fallback: `OPENROUTER_API_KEY` env
var). Never logged, never echoed.

## 6. Architecture

```
src/obsidian_postit_kde/
├── __init__.py
├── __main__.py        # entrypoint: python -m obsidian_postit_kde
├── app.py             # QApplication + tray wiring
├── config.py          # load/save TOML config, paths (XDG)
├── note.py            # Note model + frontmatter serialization
├── vault.py           # ObsidianVault: write note, validate vault
├── openrouter.py      # OpenRouterClient: summarize() / clean()
├── autostart.py       # install/remove ~/.config/autostart entry
├── ui/
│   ├── tray.py        # QSystemTrayIcon + menu
│   ├── capture.py     # capture popup dialog
│   └── settings.py    # settings dialog
└── resources/
    └── icon.svg
```

Core (config, note, vault, openrouter, autostart) is **UI-free and unit
testable**. Qt is confined to `app.py` and `ui/`.

## 7. Wayland notes

- Clipboard read is user-initiated (tray/menu action), so Wayland's
  restrictions don't block us. We use Qt's `QClipboard`; `wl-paste` is a
  fallback if needed.
- App-level global hotkeys are blocked on Wayland by design → deferred to v2
  via a KDE custom shortcut invoking a CLI flag (`--capture-clipboard`).

## 8. Packaging & CI/CD

- `pyproject.toml` (PEP 621), build backend `hatchling`.
- Console entrypoint `obsidian-postit-kde` + GUI `.desktop` file.
- Install paths: `pipx install .` for users; venv for dev.
- Packaging docs for **Flatpak** (preferred for KDE distribution) and a
  **Fedora RPM** `.spec` sketch.
- **GitHub Actions**:
  - `lint`: ruff + mypy
  - `test`: pytest on core modules (headless; no Qt display needed)
  - `build`: `python -m build` sdist+wheel, upload artifact
- Pre-commit config (ruff format/lint).

## 9. Milestones

- **M1 — Core**: config, note, vault, tests. Writes a valid note from a script.
- **M2 — Tray UI**: tray icon, capture popup, manual + clipboard save.
- **M3 — Settings + autostart**: settings dialog, vault picker, autostart toggle.
- **M4 — OpenRouter**: summarize/clean buttons, keyring for the key.
- **M5 — Packaging/CI**: pyproject, .desktop, icon, GitHub Actions, README.

## 10. Open risks

- Tray icon visibility depends on a running StatusNotifier host (Plasma 6 has
  it; documented for other DEs).
- OpenRouter is optional; the app must be fully functional with no key set.
