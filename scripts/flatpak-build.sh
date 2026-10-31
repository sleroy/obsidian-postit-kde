#!/usr/bin/env bash
# Build and install the Flatpak locally for testing.
#
# Usage: scripts/flatpak-build.sh [--run]
#   builds + installs into the --user installation; --run launches it after.
#
# Requires: flatpak, flatpak-builder, and the KDE 6.7 runtime/SDK:
#   flatpak install -y flathub org.kde.Platform//6.11 org.kde.Sdk//6.11
set -euo pipefail
cd "$(dirname "$0")/.."

MANIFEST="packaging/io.github.sleroy.ObsidianPostitKde.yml"
APP_ID="io.github.sleroy.ObsidianPostitKde"

command -v flatpak-builder >/dev/null || {
  echo "flatpak-builder not found. Install it:" >&2
  echo "  sudo dnf install flatpak-builder   # Fedora" >&2
  exit 1
}

echo "==> Ensuring KDE 6.7 runtime + SDK are present"
flatpak install -y --noninteractive flathub org.kde.Platform//6.11 org.kde.Sdk//6.11 io.qt.PySide.BaseApp//6.11 2>/dev/null || true

echo "==> Building + installing (--user)"
flatpak-builder --user --install --force-clean \
  --state-dir=.flatpak-builder build-flatpak "$MANIFEST"

echo "==> Installed $APP_ID"
if [[ "${1:-}" == "--run" ]]; then
  echo "==> Launching"
  flatpak run "$APP_ID"
else
  echo "Run it with:  flatpak run $APP_ID"
fi
