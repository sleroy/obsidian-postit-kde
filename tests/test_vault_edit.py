from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.vault import ObsidianVault, _parse_frontmatter, _unquote


def _vault(tmp_path):
    vdir = tmp_path / "v"
    vdir.mkdir()
    return ObsidianVault(Config(vault_path=str(vdir)))


def test_unquote_roundtrip():
    assert _unquote('"a \\"b\\" c"') == 'a "b" c'
    assert _unquote('"line1\\nline2"') == "line1\nline2"
    assert _unquote("bare") == "bare"


def test_parse_frontmatter():
    raw = (
        '---\ncreated: x\ntags: ["a", "b"]\nsource: "clipboard"\ntitle: "Hi: there"\n---\n\nbody\n'
    )
    title, tags, source = _parse_frontmatter(raw)
    assert title == "Hi: there"
    assert tags == ["a", "b"]
    assert source == "clipboard"


def test_load_note_roundtrip(tmp_path):
    v = _vault(tmp_path)
    p = v.save(Note(body="original body #idea", title="My Note", destination=Destination.FILE))
    loaded = v.load_note(p)
    assert loaded.title == "My Note"
    assert "original body #idea" in loaded.body
    # The '# My Note' heading must not leak into the editable body.
    assert not loaded.body.lstrip().startswith("# My Note")


def test_update_file_note_rewrites_same_path(tmp_path):
    v = _vault(tmp_path)
    p = v.save(Note(body="v1", title="Doc", destination=Destination.FILE))
    edited = v.load_note(p)
    edited.body = "v2 updated #done"
    saved = v.update_file_note(p, edited)
    assert saved == p  # same file
    text = p.read_text()
    assert "v2 updated #done" in text
    assert "v1" not in text
