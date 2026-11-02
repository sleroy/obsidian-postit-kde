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
install -Dm644 packaging/io.github.sleroy.ObsidianPostitKde.desktop \
  ~/.local/share/applications/io.github.sleroy.ObsidianPostitKde.desktop
install -Dm644 src/obsidian_postit_kde/resources/icon.svg \
  ~/.local/share/icons/hicolor/scalable/apps/obsidian-postit-kde.svg
update-desktop-database ~/.local/share/applications 2>/dev/null || true
```

Autostart is managed from within the app (Settings → Autostart), which writes
`~/.config/autostart/obsidian-postit-kde.desktop`.

## 3. Flatpak (KDE runtime) — experimental

> **Status:** the manifest builds and installs, but the packaged app does not
> launch due to an **upstream version skew**: `io.qt.PySide.BaseApp//6.11`
> ships PySide6 **6.11.2**, while `org.kde.Platform//6.11` is already Qt
> **6.11.3**. PySide's generated bindings are patch-version sensitive, so
> `PySide6.QtCore` fails to load (`libshiboken: could not import module
> 'PySide6.QtGui'`) even though every shared library resolves. This will clear
> once the BaseApp catches up to 6.11.3 (or by pinning both to the same patch
> commit). Until then, **use the pipx install (section 2)** — it works today.

`packaging/io.github.sleroy.ObsidianPostitKde.yml` targets the `org.kde.Platform`
6.11 runtime with the `io.qt.PySide.BaseApp` 6.11 base. The helper script:

```bash
# one-time: the KDE runtime + SDK (the script will also try this for you)
flatpak install -y flathub org.kde.Platform//6.11 org.kde.Sdk//6.11
sudo dnf install flatpak-builder      # Fedora

scripts/flatpak-build.sh --run        # build, install (--user), and launch
```

Under the hood it runs `flatpak-builder --user --install` against
`packaging/io.github.sleroy.ObsidianPostitKde.yml`. PySide6 is already part of
the `org.kde.Platform` runtime, so the manifest only installs `keyring`,
`httpx` and their pure-Python deps, then installs the `.desktop`, icon and
AppStream metainfo under the app-id.

For a **Flathub submission** the build must be offline: pin those Python
dependencies as generated module sources with
[`flatpak-pip-generator`](https://github.com/flatpak/flatpak-builder-tools)
(replace the `--share=network` pip step), and keep
`packaging/io.github.sleroy.ObsidianPostitKde.metainfo.xml` (already validates
with `appstreamcli validate`). Then open a PR against
`flathub/flathub` with the manifest.

The manifest grants `--talk-name=org.freedesktop.secrets` so the OpenRouter key
can live in KDE Wallet, and `--filesystem=home` for vault access (narrow this to
your actual vault path if you prefer).

## 3b. Release artifacts (GitHub)

`scripts/release.sh` builds the wheel+sdist and validates them; with
`--publish` it tags `vX.Y.Z` and creates a GitHub release with the artifacts
attached (needs the `gh` CLI, authenticated):

```bash
scripts/release.sh            # build + validate into dist/
scripts/release.sh --publish  # also tag and publish a GitHub release
```

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
