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

## 3. Flatpak (KDE runtime)

`packaging/io.github.sleroy.ObsidianPostitKde.yml` targets `org.kde.Platform`
6.11 with the `io.qt.PySide.BaseApp` 6.11 base (PySide6). It builds
**offline**: the Python dependencies are pinned with hashes in
`packaging/python-deps.yaml`, and the app is built from the checked-out tree.
Unused parts of the PySide base (QtWebEngine, QtPdf, LLVM, developer tools) are
removed with `cleanup-commands`, which keeps the repository around 150 MB.

### Automated publishing (CI)

`.github/workflows/flatpak.yml` does everything on a release tag:

1. builds the Flatpak in the `ghcr.io/flathub-infra/flatpak-github-actions:kde-6.11` container,
2. signs it with the repository key,
3. attaches `obsidian-postit-kde.flatpak` to the GitHub release,
4. publishes the signed OSTree repository, `obsidian-postit-kde.flatpakref` and
   `obsidian-postit-kde.flatpakrepo` to GitHub Pages
   (<https://sleroy.github.io/obsidian-postit-kde/>).

So a release is just `scripts/release.sh --publish` (section 3b). Pull requests
and pushes that touch `packaging/` only build, to catch breakage early. A
manual run (Actions → Flatpak → Run workflow, with *publish*) republishes Pages.

The workflow needs two repository secrets, already set:

| Secret | Content |
|---|---|
| `FLATPAK_GPG_PRIVATE_KEY` | Armored private key of the repository signing key (no passphrase) |
| `FLATPAK_GPG_KEY_ID` | Its fingerprint |

The matching public key is `packaging/flatpak-repo.gpg`; it is embedded in the
`.flatpakref` / `.flatpakrepo` files so clients verify every update. The
`github-pages` environment allows deployments from `main` and from `v*` tags.

To **rotate the key**, generate a new one, update both secrets and
`packaging/flatpak-repo.gpg`, and publish. Existing users must then re-add the
remote (`flatpak remote-modify --gpg-import=… obsidian-postit-kde-origin` or
reinstall from the `.flatpakref`).

### Local build

```bash
flatpak install -y flathub org.kde.Platform//6.11 org.kde.Sdk//6.11 io.qt.PySide.BaseApp//6.11
sudo dnf install flatpak-builder      # Fedora
scripts/flatpak-build.sh --run        # build, install (--user), and launch
```

### Updating dependencies

After changing `dependencies` in `pyproject.toml`, regenerate the pinned list:

```bash
pipx install flatpak-pip-generator
scripts/flatpak-deps.sh
```

### Permissions

- `--filesystem=home`: the vault is a user-chosen folder anywhere under
  `$HOME` (often a synced folder) that the app reads and writes continuously.
- `--talk-name=org.freedesktop.secrets`: API keys in KDE Wallet / Secret Service.
- `--talk-name=org.kde.StatusNotifierWatcher`: the tray icon.
- `--share=network`: OpenRouter and web clipping.

Voice notes are not packaged yet (they need `--socket=pulseaudio`, plus numpy,
sounddevice and pywhispercpp).

### Flathub

Not submitted. Flathub's
[requirements](https://docs.flathub.org/docs/for-app-authors/requirements)
forbid AI-generated or AI-assisted manifests and AI-automated submissions, and
require disclosure of AI-generated application code. A submission would need a
hand-written manifest and a human-driven pull request. The app ID would also
have to become `io.github.sleroy.obsidian-postit-kde`, because Flathub derives
the repository URL from the last ID component.

## 3b. Releasing

```bash
scripts/bump-version.sh 0.3.2 "What changed, in one sentence."
git commit -am "Release 0.3.2" && git push
scripts/release.sh --publish
```

`bump-version.sh` sets the version in `pyproject.toml`, `__init__.py`, the RPM
spec (with a `%changelog` entry) and the AppStream metainfo (with a `<release>`
entry). `release.sh` refuses to run if those disagree, builds and validates the
wheel and sdist, then with `--publish` tags `vX.Y.Z` and creates the GitHub
release (needs the `gh` CLI, authenticated). The tag triggers the Flatpak
workflow (section 3), which adds the Flatpak bundle and updates the repository.

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
