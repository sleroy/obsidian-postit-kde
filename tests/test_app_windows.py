from __future__ import annotations

from PySide6.QtCore import QUrl

from obsidian_postit_kde.app import PostItApp
from obsidian_postit_kde.config import Config
from obsidian_postit_kde.note import Destination, Note
from obsidian_postit_kde.vault import ObsidianVault


def test_diary_and_multiple_note_windows_stay_independent(tmp_path, monkeypatch, _qt_app):
    root = tmp_path / "vault"
    root.mkdir()
    config = Config(vault_path=str(root))
    monkeypatch.setattr("obsidian_postit_kde.app.Config.load", lambda: config)
    controller = PostItApp(_qt_app)
    controller.open_diary()
    controller.new_note()
    controller.new_note()

    assert controller._diary is not None and controller._diary.isVisible()
    assert len(controller._notes) == 2
    assert all(note.isVisible() and not note.isModal() for note in controller._notes)

    path = ObsidianVault(config).save(Note(body="existing", destination=Destination.FILE))
    controller.open_path(path)
    assert len(controller._notes) == 3
    controller._diary.doc.anchorClicked.emit(QUrl(f"postit:{path.stem}"))
    assert len(controller._notes) == 4
    controller.open_search()
    assert len(controller._searches) == 1
    assert next(iter(controller._searches)).isVisible()
    assert controller._diary.isVisible()

    for note in tuple(controller._notes):
        note.reject()
    for search in tuple(controller._searches):
        search.reject()
    assert not controller._notes
    assert not controller._searches
    controller.quit()
    assert controller._diary is None


def test_closing_diary_releases_it_before_next_open(tmp_path, monkeypatch, _qt_app):
    root = tmp_path / "vault"
    root.mkdir()
    config = Config(vault_path=str(root))
    monkeypatch.setattr("obsidian_postit_kde.app.Config.load", lambda: config)
    controller = PostItApp(_qt_app)
    controller.open_diary()
    first = controller._diary
    first.close()
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert controller._diary is None
    controller.open_diary()
    assert controller._diary is not first
    controller.quit()
