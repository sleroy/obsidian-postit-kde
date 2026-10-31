from obsidian_postit_kde.note import Destination, Note


def test_guess_name_prefers_title():
    n = Note(body="some body text", title="Buy Milk")
    assert n.guess_name() == "buy-milk"


def test_guess_name_from_first_body_line():
    n = Note(body="Call the dentist tomorrow morning about the appointment")
    assert n.guess_name() == "call-the-dentist-tomorrow-morning-about-the"


def test_guess_name_strips_tags_and_markdown():
    n = Note(body="#idea **Refactor** the parser")
    assert n.guess_name() == "refactor-the-parser"


def test_guess_name_skips_blank_lines():
    n = Note(body="\n\n   \nReal content here")
    assert n.guess_name() == "real-content-here"


def test_guess_name_empty_when_nothing_usable():
    n = Note(body="###", destination=Destination.FILE)
    assert n.guess_name() == ""
