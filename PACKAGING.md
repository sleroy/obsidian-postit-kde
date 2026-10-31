# Packaging & distribution

## 1. Development (editable)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
obsidian-postit-kde
```

## 2. pipx (recommended for a single user)

```bash
pipx install .
# installs the `obsidian-postit-kde` console script into ~/.local/bin
```

Then install the launcher + icon for the KDE application menu:

```bash
install -Dm644 packaging/obsidian-postit-kde.desktop \
  ~/.local/share/applications/obsidian-postit-kde.desktop
install -Dm644 src/obsidian_postit_kde/resources/icon.svg \
  ~/.local/share/icons/hicolor/scalable/apps/obsidian-postit-kde.svg
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

Autostart is managed from within the app (Settings → Autostart), which writes
`~/.config/autostart/obsidian-postit-kde.desktop`.

## 3. Flatpak (KDE runtime)

`packaging/io.github.sleroy.ObsidianPostitKde.yml` targets the `org.kde.Platform`
6.7 runtime. For a local build:

```bash
flatpak install flathub org.kde.Platform//6.7 org.kde.Sdk//6.7
flatpak-builder --user --install --force-clean build-dir \
  packaging/io.github.sleroy.ObsidianPostitKde.yml
```

For a Flathub-quality build, pin the Python dependencies (PySide6, keyring,
httpx) as offline pip module sources generated with
[`flatpak-pip-generator`](https://github.com/flatpak/flatpak-builder-tools).

The manifest grants `--talk-name=org.freedesktop.secrets` so the OpenRouter key
can live in KDE Wallet, and `--filesystem=home` for vault access (narrow this to
your actual vault path if you prefer).

## 4. Fedora RPM

`packaging/obsidian-postit-kde.spec` is a `pyproject`-macro spec. Build with:

```bash
sudo dnf install python3-devel python3-hatchling rpm-build
rpmbuild -ba packaging/obsidian-postit-kde.spec
```

Runtime deps map to Fedora packages: `python3-pyside6`, `python3-keyring`,
`python3-httpx`.

## 5. Wheel / sdist

```bash
python -m build
# dist/obsidian_postit_kde-0.1.0-py3-none-any.whl
# dist/obsidian_postit_kde-0.1.0.tar.gz
```
