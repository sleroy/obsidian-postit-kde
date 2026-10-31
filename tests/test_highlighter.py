from obsidian_postit_kde.ui.highlighter import find_tokens


def test_find_tags():
    t = find_tokens("remember #work and #to-read today")
    assert t["tag"] == ["#work", "#to-read"]


def test_find_links_bold_code():
    t = find_tokens("see [[Project X]] it is **done** run `make`")
    assert t["link"] == ["[[Project X]]"]
    assert t["bold"] == ["**done**"]
    assert t["code"] == ["`make`"]


def test_hash_midword_not_a_tag():
    t = find_tokens("color #fff but not aa#bb")
    assert t["tag"] == ["#fff"]
