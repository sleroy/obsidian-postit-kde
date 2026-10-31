from obsidian_postit_kde.ui.diary import _first_h1, _replace_section


def test_first_h1_skips_frontmatter():
    md = "---\ndevice: x\n---\n\n# my-device — daily note\n\n## 2026-10-31\n- a\n"
    assert _first_h1(md) == "my-device — daily note"


def test_replace_section_replaces_only_target():
    doc = "# T\n\n## 2026-10-31\n- a\n- b\n\n## 2026-11-01\n- c\n"
    out = _replace_section(doc, "## 2026-10-31", "summarized single entry")
    assert "summarized single entry" in out
    assert "- a" not in out and "- b" not in out
    assert "## 2026-11-01" in out and "- c" in out  # other day preserved


def test_replace_section_appends_when_absent():
    doc = "# T\n\n## 2026-10-31\n- a\n"
    out = _replace_section(doc, "## 2099-01-01", "new day entry")
    assert "## 2099-01-01" in out
    assert "new day entry" in out
    assert "- a" in out  # original kept
