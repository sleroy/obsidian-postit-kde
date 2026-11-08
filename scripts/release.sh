#!/usr/bin/env bash
# Build release artifacts and (optionally) publish a GitHub release.
#
# Usage:
#   scripts/release.sh            # build sdist+wheel into dist/, validate
#   scripts/release.sh --publish  # also: tag vX.Y.Z and create a GitHub release
#
# Requires: python -m build, twine; --publish also needs the `gh` CLI (authed).
set -euo pipefail
cd "$(dirname "$0")/.."

PUBLISH=0
[[ "${1:-}" == "--publish" ]] && PUBLISH=1

VERSION=$(grep -E '^version *= *"' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
TAG="v${VERSION}"
echo "==> obsidian-postit-kde ${VERSION}"

echo "==> Check the version is consistent (use scripts/bump-version.sh to set it)"
fail=0
grep -q "^__version__ = \"${VERSION}\"" src/obsidian_postit_kde/__init__.py || { echo "  __init__.py differs" >&2; fail=1; }
grep -qE "^Version:\s+${VERSION}$" packaging/obsidian-postit-kde.spec || { echo "  RPM spec differs" >&2; fail=1; }
grep -q "<release version=\"${VERSION}\"" packaging/io.github.sleroy.ObsidianPostitKde.metainfo.xml \
  || { echo "  metainfo has no <release> for ${VERSION}" >&2; fail=1; }
[[ "$fail" -eq 0 ]] || { echo "Version mismatch — run: scripts/bump-version.sh ${VERSION} \"notes\"" >&2; exit 1; }

echo "==> Clean"
rm -rf dist build ./*.egg-info src/*.egg-info

echo "==> Build sdist + wheel"
python -m build

echo "==> Validate metadata"
python -m pip install --quiet --upgrade twine >/dev/null
twine check dist/*

echo "==> Artifacts:"
ls -1 dist/

if [[ "$PUBLISH" -eq 0 ]]; then
  echo "Done (build only). Re-run with --publish to tag and release."
  exit 0
fi

command -v gh >/dev/null || { echo "gh CLI not found; cannot publish." >&2; exit 1; }

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Tag $TAG already exists — aborting to avoid clobbering a release." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is dirty — commit or stash before publishing." >&2
  exit 1
fi

echo "==> Tag $TAG"
git tag -a "$TAG" -m "obsidian-postit-kde $VERSION"
git push origin "$TAG"

echo "==> GitHub release"
gh release create "$TAG" dist/* \
  --title "obsidian-postit-kde $VERSION" \
  --notes "Automated release $VERSION. See CHANGELOG / commits for details."

echo "Published $TAG with artifacts."
echo "CI now builds the Flatpak, attaches it to the release and updates the repository:"
echo "  gh run watch -R sleroy/obsidian-postit-kde \$(gh run list -R sleroy/obsidian-postit-kde -w Flatpak -L1 --json databaseId -q '.[0].databaseId')"
