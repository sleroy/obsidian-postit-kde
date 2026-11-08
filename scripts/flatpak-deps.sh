#!/usr/bin/env bash
# Regenerate packaging/python-deps.yaml: the Python dependencies of the
# Flatpak, pinned with sha256 for an offline build.
#
# Run after changing `dependencies` in pyproject.toml.
# Requires: pipx install flatpak-pip-generator  (command: flatpak_pip_generator)
#           flatpak install flathub org.kde.Sdk//6.11
set -euo pipefail
cd "$(dirname "$0")/.."

# PySide6 comes from io.qt.PySide.BaseApp; every other runtime dependency is
# listed here, plus hatchling to install the app itself without network.
PACKAGES=(keyring httpx trafilatura markdownify jeepney hatchling)
# Use prebuilt wheels for C/Rust extensions (no Rust toolchain in the SDK).
WHEELS=lxml,cryptography,cffi,regex

GEN=$(command -v flatpak_pip_generator || command -v flatpak-pip-generator) || {
  echo "flatpak-pip-generator not found: pipx install flatpak-pip-generator" >&2
  exit 1
}

"$GEN" --runtime=org.kde.Sdk//6.11 --yaml --prefer-wheels "$WHEELS" \
  -o packaging/python-deps "${PACKAGES[@]}" || true  # its CLI shim may error on exit
test -s packaging/python-deps.yaml || { echo "generation failed" >&2; exit 1; }
if grep -q '\.tar\.gz' packaging/python-deps.yaml; then
  echo "warning: some dependencies are sdists and will be compiled:" >&2
  grep -o '[^/]*\.tar\.gz' packaging/python-deps.yaml >&2
fi
echo "Updated packaging/python-deps.yaml"
