from datetime import datetime

from obsidian_postit_kde.note import (
    Destination,
    Note,
    normalize_tag,
    parse_tags,
    slugify,
)


def test_slugify():
    assert slugify("Buy Milk!") == "buy-milk"
    assert slugify("  Hello,  World  ") == "hello-world"
    assert slugify("###") == ""
    assert slugify("a" * 100, max_len=10) == "a" * 10


def test_normalize_tag():
    assert normalize_tag("#Work") == "work"
    assert normalize_tag(" To Read ") == "to-read"


def test_parse_tags_dedup_and_split():
    assert parse_tags("work, #idea idea  reading") == ["work", "idea", "reading"]
    assert parse_tags("") == []


def test_merged_tags_order_and_dedup():
    note = Note(body="x", tags=["idea", "postit"])
    assert note.merged_tags(["postit"]) == ["postit", "idea"]


def test_file_markdown_frontmatter():
    note = Note(
        body="Hello body",
        title="My Title",
        tags=["idea"],
        source="clipboard",
        destination=Destination.FILE,
        created=datetime(2026, 10, 31, 12, 54, 31),
    )
    md = note.to_file_markdown(default_tags=["postit"])
    assert "---" in md
    assert "created: 2026-10-31T12:54:31" in md
    assert 'tags: ["postit", "idea"]' in md
    assert 'source: "clipboard"' in md
    assert 'title: "My Title"' in md
    assert "# My Title" in md
    assert md.rstrip().endswith("Hello body")


def test_daily_bullet_single_line_with_time_and_tags():
    note = Note(
        body="Quick thought",
        tags=["idea"],
        created=datetime(2026, 10, 31, 13, 40, 0),
    )
    bullet = note.to_daily_bullet(default_tags=["postit"], with_time=True)
    assert bullet == "- 13:40 Quick thought #postit #idea"


def test_daily_bullet_multiline_indents_continuation():
    note = Note(body="line one\nline two", created=datetime(2026, 10, 31, 9, 0, 0))
    bullet = note.to_daily_bullet(default_tags=[], with_time=True)
    assert bullet.splitlines()[0] == "- 09:00 line one"
    assert bullet.splitlines()[1] == "  line two"


def test_daily_bullet_no_time():
    note = Note(body="x", created=datetime(2026, 10, 31, 9, 0, 0))
    bullet = note.to_daily_bullet(default_tags=[], with_time=False)
    assert bullet == "- x"


def test_daily_bullet_does_not_duplicate_inline_tags():
    # #idea is already in the body and also a note tag + would be merged;
    # it must appear exactly once.
    note = Note(body="a thought #idea", tags=["idea"],
                created=datetime(2026, 10, 31, 9, 0, 0))
    bullet = note.to_daily_bullet(default_tags=["postit"], with_time=False)
    assert bullet.count("#idea") == 1
    assert "#postit" in bullet  # postit not inline, so it IS appended
    assert bullet == "- a thought #idea #postit"
