#!/usr/bin/env bash
# Set the version everywhere it lives, and record the release notes.
#
# Usage: scripts/bump-version.sh X.Y.Z "One-sentence release notes."
#
# Updates pyproject.toml, src/obsidian_postit_kde/__init__.py, the RPM spec
# (Version + %changelog) and the AppStream metainfo (<release> entry, shown by
# software centers and required for the Flatpak). Then run:
#   git commit -am "Release X.Y.Z" && git push && scripts/release.sh --publish
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${1:?usage: scripts/bump-version.sh X.Y.Z "release notes"}
NOTES=${2:?usage: scripts/bump-version.sh X.Y.Z "release notes"}
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "version must be X.Y.Z" >&2; exit 1; }

python3 - "$VERSION" "$NOTES" <<'PY'
import datetime
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

version, notes = sys.argv[1], sys.argv[2]
today = datetime.date.today()


def sub(path: str, pattern: str, repl: str) -> None:
    p = Path(path)
    text, n = re.subn(pattern, repl, p.read_text(encoding="utf-8"), count=1, flags=re.M)
    if n != 1:
        sys.exit(f"{path}: pattern not found: {pattern}")
    p.write_text(text, encoding="utf-8")


sub("pyproject.toml", r'^version = "[^"]+"', f'version = "{version}"')
sub("src/obsidian_postit_kde/__init__.py", r'^__version__ = "[^"]+"', f'__version__ = "{version}"')

spec = "packaging/obsidian-postit-kde.spec"
sub(spec, r"^Version:(\s+)\S+", rf"Version:\g<1>{version}")
if f"- {version}-1\n" not in Path(spec).read_text(encoding="utf-8"):
    stamp = today.strftime("%a %b %d %Y")
    sub(spec, r"^%changelog\n", f"%changelog\n* {stamp} sleroy - {version}-1\n- {notes}\n\n")

meta = Path("packaging/io.github.sleroy.ObsidianPostitKde.metainfo.xml")
xml = meta.read_text(encoding="utf-8")
if f'<release version="{version}"' not in xml:
    entry = (
        f'    <release version="{version}" date="{today.isoformat()}">\n'
        f"      <description>\n        <p>{escape(notes)}</p>\n      </description>\n"
        f"    </release>\n"
    )
    xml = xml.replace("  <releases>\n", "  <releases>\n" + entry, 1)
    meta.write_text(xml, encoding="utf-8")
print(f"Version set to {version}")
PY

if command -v appstreamcli >/dev/null; then
  appstreamcli validate --no-net packaging/io.github.sleroy.ObsidianPostitKde.metainfo.xml
fi
git --no-pager diff --stat
